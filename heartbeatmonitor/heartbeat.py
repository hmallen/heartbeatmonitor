import datetime
import json
import logging
import os
import subprocess
import sys
import time

from json_datetime_converter import JSONDatetimeConverter
from monitor import Monitor

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Heartbeat:
    def __init__(self, module, monitor, heartbeat_timeout, alert_reset_interval,
                 config_path, json_directory,
                 flatline_alerts_only=False, test_channel=False):
        self.config_path = config_path

        self.json_directory = json_directory

        self.module_name = module

        self.heartbeat_monitor = monitor

        self.heartbeat_timeout = datetime.timedelta(minutes=heartbeat_timeout)

        self.heartbeat_last = datetime.datetime.now()

        self.alert_reset_interval = datetime.timedelta(minutes=alert_reset_interval)

        self.flatline_last = datetime.datetime.now() - self.alert_reset_interval

        self.flatline_alerts_only = flatline_alerts_only

        # Necessary for monitor startup at bottom of __init__
        if self.json_directory[-1] != '/':
            self.json_directory += '/'

        if not os.path.exists(self.json_directory):
            #os.mkdir(self.json_directory)
            os.makedirs(self.json_directory, exist_ok=True)

        conversion_list = ['heartbeat_last', 'heartbeat_timeout', 'flatline_last', 'alert_reset_interval']

        self.json_converter = JSONDatetimeConverter(conversion_list=conversion_list)

        self.json_save_file = self.json_directory + 'heartbeat_' + module + '.json'

        self.json_save_data = {'module': module,
                               'heartbeat_timeout': self.heartbeat_timeout,
                               'heartbeat_last': self.heartbeat_last,
                               'alert_reset_interval': self.alert_reset_interval,
                               'flatline_last': self.flatline_last}

        create_new_file = False

        if not os.path.exists(self.json_save_file):
            create_new_file = True

        else:
            try:
                json_data = self.json_converter.read_json(json_file=self.json_save_file)
                logger.debug('json_data[\'status\']: ' + str(json_data['status']))

                json_data_old = json_data['data']

                if (datetime.datetime.now() - json_data_old['heartbeat_last']) > self.heartbeat_timeout:
                    create_new_file = True

                else:
                    self.json_save_data = json_data_old

            except Exception as e:
                logger.exception('Exception while loading data from json file. Removing and creating new file.')
                logger.exception(e)

                create_new_file = True

        if create_new_file == True:
            json_data = self.json_converter.write_json(json_data=self.json_save_data, json_file=self.json_save_file)
            logger.debug('json_data[\'status\']: ' + str(json_data['status']))

        if self.heartbeat_monitor == 'slack':
            import configparser
            from slackclient import SlackClient

            config = configparser.ConfigParser()
            config.read(self.config_path)

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

        elif self.heartbeat_monitor == 'testing':
            logger.info('Using testing heartbeat monitor. Outputting to console.')

        ##########################################
        #### START MONITOR HERE IF NOT ACTIVE ####
        ##########################################

        self.active_file = self.json_directory + 'ACTIVE'

        if not os.path.exists(self.active_file):
            logger.info('Monitor not currently active. Starting monitor.')

            Heartbeat.start_monitor(self)


    def start_monitor(self):
        try:
            #popen_string = 'python monitor.py -c ' + self.config_path + ' -d ' + self.json_directory

            monitor_log = self.module_name.lower() + '_monitor.log'

            popen_args = ['python', 'monitor.py', '-c', self.config_path, '-d', self.json_directory]#, '>', monitor_log]

            stdout_file = open('monitor.out', 'w', encoding='utf-8')

            #subprocess.Popen(popen_string)
            subprocess.Popen(popen_args, stdout=stdout_file, stderr=subprocess.STDOUT)

            # SHOULD USE COMMUNICATE OR SOMETHING INSTEAD OF DELAY
            time.sleep(5)

            logger.info('Monitor startup initiated.')

        except Exception as e:
            logger.exception('Exception while starting monitor with Popen(). Exiting.')
            logger.exception(e)

            sys.exit(1)


    def heartbeat(self, message=None):
        heartbeat_delta = datetime.datetime.now() - self.heartbeat_last
        logger.debug('heartbeat_delta: ' + str(heartbeat_delta))

        self.heartbeat_last = datetime.datetime.now()
        logger.debug('self.heartbeat_last: ' + str(self.heartbeat_last))

        self.json_save_data['heartbeat_last'] = self.heartbeat_last

        logger.debug('Dumping heartbeat data to json file.')

        json_status = self.json_converter.write_json(json_data=self.json_save_data, json_file=self.json_save_file)
        logger.debug('json_status[\'status\']: ' + str(json_status['status']))

        if self.flatline_alerts_only == False:
            alert_message = str(self.heartbeat_last)

            if message != None:
                alert_message += ' - (' + message + ')'

            logger.debug('alert_message: ' + alert_message)

            alert_submessage = '*Last heartbeat:* ' + "{:.2f}".format(float(heartbeat_delta.total_seconds()) / 60) + ' minutes ago.'

            logger.debug('alert_submessage: ' + alert_submessage)

            if self.heartbeat_monitor == 'slack':
                alert_result = Heartbeat.send_slack_alert(self,
                                                          channel_id=self.slack_alert_channel_id_heartbeat,
                                                          message=alert_message,
                                                          submessage=alert_submessage)

                logger.debug('alert_result[\'Exception\']: ' + str(alert_result['Exception']))

                logger.debug('alert_result[\'result\']: ' + str(alert_result['result']))

                if alert_result['Exception'] == True:
                    logger.exception('Exception status returned from attempt to send Slack message.')

            elif self.heartbeat_monitor == 'testing':
                logger.info('Alert Message:    ' + alert_message)
                logger.info('Alert Submessage: ' + alert_submessage)

        else:
            logger.debug('Skipping Slack alert for regular heartbeat trigger.')


    def send_slack_alert(self, channel_id, message, submessage=None, status_message=False):
        alert_return = {'Exception': False, 'result': {}}

        try:
            if status_message == True:
                heartbeat_message = '*Heartbeat monitor status changed.*'
                fallback_message = 'Heartbeat monitor status changed.'
                heartbeat_color = '#FFFF00'     # Yellow

            else:
                heartbeat_message = '*Heartbeat detected.*'
                fallback_message = 'Heartbeat detected.'
                heartbeat_color = '#36A64F'     # Green

            attachment_array =  [{"fallback": fallback_message,
                                  "color": heartbeat_color,   # Green = #36A64F, Blue = #3AA3E3, Yellow = #FFFF00, Orange = #FFA500, Red = #FF0000
                                  "title": "Module: " + self.module_name,
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

            alert_return['Exception'] = True

        finally:
            return alert_return


if __name__ == '__main__':
    test_config_path = '../../TeslaBot/config/config.ini'

    test_json_directory = 'json/heartbeat/'

    test_heartbeat_timeout = 1

    test_alert_reset_interval = 1

    hb = Heartbeat(module='Testing', monitor='slack', config_path=test_config_path, json_directory=test_json_directory,
                   heartbeat_timeout=test_heartbeat_timeout, alert_reset_interval=test_alert_reset_interval,
                   flatline_alerts_only=False, test_channel=True)

    try:
        for x in range(0, 2):
            heartbeat_message = 'Heartbeat #' + str(x + 1)

            logger.debug('heartbeat_message: ' + heartbeat_message)

            hb.heartbeat(message=heartbeat_message)

            if x < 2:
                time.sleep(5)

        logger.debug('Sleeping for >' + str(test_heartbeat_timeout) + ' min to trigger heartbeat flatline alert.')

        test_delay = (test_heartbeat_timeout * 60) + 1

        time.sleep(test_delay)

        logger.debug('Removing heartbeat file to trigger monitor shutdown.')

        if os.path.exists(hb.json_save_file):
            os.remove(hb.json_save_file)

        else:
            logger.warning('JSON save file missing. An error may have occurred.')

        logger.debug('Done.')

    #except multiprocessing.ProcessError as e:
        #logger.exception('multiprocessing.ProcessError raised in main.')
        #logger.exception(e)

    except Exception as e:
        logger.exception('Exception raised.')
        logger.exception(e)

    except KeyboardInterrupt:
        logger.info('Exit signal received.')
