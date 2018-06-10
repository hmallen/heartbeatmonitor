import argparse
import configparser
import datetime
import json
import logging
from multiprocessing import Process, Array
import os
import sys
import time

import shutil

from json_datetime_converter import JSONDatetimeConverter
from slackclient import SlackClient

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Monitor:
    def __init__(self, config_path, json_directory, test_channel=False):
        if json_directory[-1] != '/':
            json_directory += '/'

        self.json_directory = json_directory

        self.active_file = self.json_directory + 'ACTIVE'

        if not os.path.exists(self.json_directory):
            os.makedirs(self.json_directory, exist_ok=True)

        conversion_list = ['heartbeat_last', 'heartbeat_timeout', 'heartbeat_delta',
                           'flatline_last', 'flatline_timeout', 'flatline_delta']

        self.json_converter = JSONDatetimeConverter(conversion_list=conversion_list)

        config = configparser.ConfigParser()
        config.read(config_path)

        slack_token = config['slack']['slack_token']

        slack_channel_heartbeat = config['settings']['slack_channel_heartbeat']
        logger.debug('slack_channel_heartbeat: ' + slack_channel_heartbeat)

        slack_channel_testing = config['settings']['slack_channel_testing']
        logger.debug('slack_channel_testing: ' + slack_channel_testing)

        self.slack_bot_user = config['settings']['slack_bot_user']
        logger.debug('self.slack_bot_user: ' + self.slack_bot_user)

        self.slack_bot_icon = config['settings']['slack_bot_icon']
        logger.debug('self.slack_bot_icon: ' + self.slack_bot_icon)

        # Slack connection
        self.slack_client = SlackClient(slack_token)

        channel_list = self.slack_client.api_call('channels.list')
        group_list = self.slack_client.api_call('groups.list')

        if test_channel == False:
            slack_channel_targets = {'heartbeat': slack_channel_heartbeat}

        else:
            slack_channel_targets = {'heartbeat': slack_channel_testing}

        for target in slack_channel_targets:
            try:
                logger.debug('channel_list.get(\'ok\'): ' + str(channel_list.get('ok')))
                if channel_list.get('ok'):
                    for chan in channel_list['channels']:
                        logger.debug('chan[\'name\']: ' + chan['name'])
                        if chan['name'] == slack_channel_targets[target]:
                            if target == 'heartbeat':
                                self.slack_alert_channel_id_heartbeat = chan['id']

                            break
                    else:
                        logger.error('No valid Slack channel found for alert in channel list.')

                        sys.exit(1)

                else:
                    logger.error('Channel list API call failed.')

                    sys.exit(1)

            except:
                logger.debug('group_list.get(\'ok\'): ' + str(group_list.get('ok')))
                if group_list.get('ok'):
                    for group in group_list['groups']:
                        logger.debug('group[\'name\']: ' + group['name'])
                        if group['name'] == slack_channel_targets[target]:
                            if target == 'heartbeat':
                                self.slack_alert_channel_id_heartbeat = group['id']

                            break
                    else:
                        logger.error('No valid Slack channel found for alert in group list.')

                        sys.exit(1)

                else:
                    logger.error('Group list API call failed.')

                    sys.exit(1)

        logger.debug('Slack channel for heartbeat alerts: #' + slack_channel_targets['heartbeat'] +
                    ' (' + self.slack_alert_channel_id_heartbeat + ')')


    def start(self, monitor_state):
        logger.info('Start monitor triggered.')

        Monitor.monitor(self, monitor_state)


    def stop(self, monitor_state):
        monitor_state[1] = 1

        while monitor_state[0] == 1:
            time.sleep(1)


    def monitor(self, monitor_state):
        with open(self.active_file, 'w', encoding='utf-8') as file:
            file.write('ACTIVE')

        if not os.path.exists(self.active_file):
            logger.error('Monitor active file creation failed. Exiting.')

            sys.exit(1)

        monitor_state[0] = 1

        loop_start = time.time()

        while (True):
            try:
                # Load heartbeats from directory
                heartbeat_files = os.listdir(self.json_directory)

                for file in heartbeat_files:
                    if file != 'ACTIVE':
                        """
                        {
                            "flatline_last": "2018-06-01T01:54:42.781292",
                            "alert_reset_interval": 60.0,
                            "heartbeat_last": "2018-06-01T01:55:53.824336",
                            "heartbeat_timeout": 15.0,
                            "module": "Testing"
                        }
                        """

                        heartbeat_data = {}

                        file_path = self.json_directory + file

                        json_read_converted = self.json_converter.read_json(json_file=file_path)

                        json_data = {}

                        if json_read_converted['status'] == True:
                            json_data = json_read_converted['data']

                        else:
                            logger.error('Error while converting json data during read.')

                        dt_current = datetime.datetime.now()

                        if (dt_current - json_data['heartbeat_last']) > json_data['heartbeat_timeout']:
                            if (dt_current - json_data['flatline_last']).total_seconds() > json_data['alert_reset_interval']:
                                heartbeat_last_delta = "{:.2f}".format(float((datetime.datetime.now() - json_data['heartbeat_last']).total_seconds()) / 60)

                                alert_message = '*Last heartbeat:* ' + heartbeat_last_delta + ' minutes ago.'

                                alert_result = Monitor.send_slack_alert(self, channel_id=self.slack_alert_channel_id_heartbeat,
                                                                        module_name=json_data['module'], message=alert_message, flatline=True)

                                logger.debug('alert_result[\'Exception\']: ' + str(alert_result['Exception']))

                                logger.debug('alert_result[\'result\']: ' + str(alert_result['result']))

                                json_data['flatline_last'] = datetime.datetime.now()

                                json_write_converted = self.json_converter.write_json(json_data=json_data, json_file=file_path)

                                if json_write_converted['status'] == False:
                                    logger.error('Error occurred while converting json data during write.')

                            else:
                                logger.debug('Heartbeat timeout passed, but alert reset interval not reached. Skipping slack alert.')

                        else:
                            pass

                if monitor_state[1] == 1:
                    logger.info('Kill monitor signalled.')

                    break

                time.sleep(5)

            except Exception as e:
                logger.exception(e)

            except KeyboardInterrupt:
                logger.info('Exit signal received. Breaking.')

                break

            finally:
                pass

        if os.path.exists(self.active_file):
            logger.debug('Removing monitor active file.')

            os.remove(self.active_file)

        else:
            logger.error('Monitor active file not present at shutdown. An error has likely occurred.')

        monitor_state[0] = 0
        logger.debug('monitor_state[0]: ' + str(monitor_state[0]))


    def send_slack_alert(self, channel_id, message, module_name, submessage=None, flatline=False, status_message=False):
        #alert_result = True
        alert_return = {'Exception': False, 'result': {}}

        try:
            if status_message == True:
                heartbeat_message = '*Heartbeat monitor status changed.*'
                fallback_message = 'Heartbeat monitor status changed.'
                heartbeat_color = '#FFFF00'     # Yellow

            elif flatline == False:
                heartbeat_message = '*Heartbeat detected.*'
                fallback_message = 'Heartbeat detected.'
                heartbeat_color = '#36A64F'     # Green

            else:
                heartbeat_message = '*WARNING: No heartbeat detected!*'
                fallback_message = 'WARNING: No heartbeat detected!'
                heartbeat_color = '#FF0000'     # Red

            attachment_array =  [{"fallback": fallback_message,
                                  "color": heartbeat_color,   # Green = #36A64F, Blue = #3AA3E3, Yellow = #FFFF00, Orange = #FFA500, Red = #FF0000
                                  "title": "Module: " + module_name,
                                  "pretext": message}]

            if submessage != None:
                attachment_array[0]['text'] = submessage

            attachments = json.dumps(attachment_array)

            alert_return['result'] = self.slack_client.api_call(
                'chat.postMessage',
                channel=channel_id,
                text=heartbeat_message,
                username=self.slack_bot_user,
                icon_url=self.slack_bot_icon,
                attachments=attachments
            )

        except Exception as e:
            logger.exception('Exception in heartbeat function.')
            logger.exception(e)

            #alert_result = False
            alert_return['Exception'] = True

        finally:
            #return alert_result
            return alert_return


if __name__ == '__main__':
    startup_complete = False

    try:
        parser = argparse.ArgumentParser()
        parser.add_argument('-c', '--config', type=str, default='', help='Path to config file with Slack API credentials.')
        parser.add_argument('-d', '--directory', type=str, default='', help='Directory for json file storage.')
        args = parser.parse_args()

        config_path = args.config
        json_directory = args.directory

        if config_path == '':
            logger.error('No config path provided. Exiting.')

            sys.exit(1)

        if json_directory == '':
            logger.error('No json directory provided. Exiting.')

            sys.exit(1)

        monitor_state = Array('b', [0, 0])

        monitor = Monitor(config_path=config_path, json_directory=json_directory, test_channel=True)

        monitor_proc = Process(target=monitor.start, args=(monitor_state,))

        logger.debug('Starting monitor process.')

        monitor_proc.start()

        logger.info('Waiting for monitor to become active.')

        while monitor_state[0] == 0:
            time.sleep(1)

        startup_complete = True

        logger.info('Monitor ready.')

        directory_empty = False

        timeout_start = None

        shutdown_start = None

        while monitor_state[0] == 1:
            try:
                json_dir_contents = os.listdir(json_directory)

                if monitor_state[1] == 0:
                    if 'ACTIVE' not in json_dir_contents:
                        logger.error('Monitor active file no longer present. Exiting.')

                        sys.exit(1)

                    elif timeout_start != None and len(json_dir_contents) > 1:
                        logger.info('New heartbeat file added during shutdown timeout sequence. Resetting timer.')

                        timeout_start = None

                    elif len(json_dir_contents) == 1:
                        if timeout_start == None:
                            logger.info('No heartbeat files found in directory. Starting 30 second shutdown timer.')

                            timeout_start = time.time()

                        else:
                            if monitor_state[1] == 0 and (time.time() - timeout_start) > 30:
                                logger.info('Signalling monitor to shutdown.')

                                #monitor_state[1] = 1

                                monitor.stop(monitor_state)

                                shutdown_start = time.time()

                    else:
                        logger.debug('Monitor active at ' + datetime.datetime.now().strftime('%H:%M:%S, %m-%d-%y') + '.')

                elif monitor_state[1] == 1 and shutdown_start != None and (time.time() - shutdown_start) > 30:
                    logger.warning('30 seconds have elapsed without monitor shutdown. Forcing exit.')

                    break

                elif shutdown_start == None:
                    logger.error('No shutdown start time recorded. An error has occurred. Forcing exit.')

                    break

                #time.sleep(30)
                sleep_start = time.time()
                while (time.time() - sleep_start) < 30:
                    if monitor_state[0] == 0:
                        break

                    time.sleep(1)

            except Exception as e:
                logger.exception('Exception in inner loop.')
                logger.exception(e)

            except KeyboardInterrupt:
                logger.info('Exit signal received. Triggering monitor shutdown.')

                monitor_state[1] = 1

        logger.debug('Monitor stopped successfully.')

    except Exception as e:
        logger.exception('Unhandled exception in heartbeatmonitor.monitor.')
        logger.exception(e)

    except KeyboardInterrupt:
        logger.info('Exit signal received.')

    finally:
        if os.path.exists('monitor.out'):
            if not os.path.exists('logs/'):
                os.mkdir('logs/')

            archive_file = 'logs/monitor_' + datetime.datetime.now().strftime('%m%d%Y-%H%M%S') + '.out'

            shutil.move('monitor.out', archive_file)

    """
    finally:
        if startup_complete == True:
            logger.info('Terminating process.')

            monitor_proc.terminate()

            logger.info('Joining terminated process.')

            monitor_proc.join()

            logger.info('Removing active monitor file.')

            if os.path.exists(monitor.active_file):
                logger.warning('Monitor active file present at exit but should have been deleted by monitor. An error has likely occurred.')

                os.remove(monitor.active_file)


        logger.info('Done.')
    """
