import datetime
import json
import logging
from multiprocessing import Manager, Process
import multiprocessing
import time

#from slackclient import SlackClient

#logging.basicConfig()
logger = logging.getLogger(__name__)
#logger.setLevel(logging.DEBUG)

#config_path = '../../config/config.ini'


class HeartbeatMonitor:
    def __init__(self, module, monitor, timeout, flatline_timeout, config_path=None, flatline_alerts_only=False, test_channel=False):
        self.module_name = module

        self.heartbeat_monitor = monitor

        self.timeout_delta = datetime.timedelta(minutes=timeout)

        self.heartbeat_last = datetime.datetime.now()

        self.flatline_delta = datetime.timedelta(minutes=flatline_timeout)

        self.flatline_last = datetime.datetime.now() - self.flatline_delta

        self.flatline_alerts_only = flatline_alerts_only

        self.heartbeat_delta = datetime.timedelta(seconds=0)

        self.multiprocessing_manager = Manager()

        self.monitor_states = self.multiprocessing_manager.dict({'kill' : False, 'isrunning': False})

        self.monitor_heartbeat = Process(target=HeartbeatMonitor.monitor, args=(self,))

        #self.kill_monitor = False

        #self.monitor_isrunning = False

        if self.heartbeat_monitor == 'slack':
            if config_path == None:
                logger.error('Slack alerts enabled. Must provide path to config file with Slack API credentials. Exiting.')

                sys.exit(1)
            
            import configparser
            from slackclient import SlackClient

            config = configparser.ConfigParser()
            config.read(config_path)

            slack_token = config['slack']['slack_token_test']

            slack_alert_channel_heartbeat = config['settings']['slack_alert_channel_heartbeat']
            logger.debug('slack_alert_channel_heartbeat: ' + slack_alert_channel_heartbeat)

            slack_alert_channel_testing = config['settings']['slack_alert_channel_testing']
            logger.debug('slack_alert_channel_testing: ' + slack_alert_channel_testing)

            # Slack connection
            self.slack_client = SlackClient(slack_token)

            channel_list = self.slack_client.api_call('channels.list')
            group_list = self.slack_client.api_call('groups.list')

            if test_channel == False:
                slack_channel_targets = {'heartbeat': slack_alert_channel_heartbeat}

            else:
                slack_channel_targets = {'heartbeat': slack_alert_channel_testing}

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

            logger.debug('Slack channel for heartbeat alerts: #' + slack_alert_channel_heartbeat +
                        ' (' + self.slack_alert_channel_id_heartbeat + ')')

            self.slack_alert_user = config['settings']['slack_alert_user']
            logger.debug('self.slack_alert_user: ' + self.slack_alert_user)

            self.slack_user_icon = config['settings']['slack_user_icon']
            logger.debug('self.slack_user_icon: ' + self.slack_user_icon)

        elif self.heartbeat_monitor == 'testing':
            logger.info('Using testing heartbeat monitor. Outputting to console.')


    def start_monitor(self):
        #logger.info('Starting heartbeat monitor.')

        self.monitor_heartbeat.start()


    def stop_monitor(self):
        logger.info('Stopping heartbeat monitor.')

        #self.kill_monitor = True
        #logger.debug('[stop_monitor] self.kill_monitor: ' + str(self.kill_monitor))

        self.monitor_states['kill'] = True
        logger.debug('[stop_monitor] self.monitor_states[\'kill\']: ' + str(self.monitor_states['kill']))

        #while self.monitor_isrunning == True:
        while self.monitor_states['isrunning'] == True:
            time.sleep(0.1)

        #self.monitor_heartbeat.terminate()

        active_processes = self.monitor_heartbeat.active_children()

        for proc in active_processes:
            logger.debug('Child Process: ' + str(proc))

            logger.info('Terminating heartbeat monitor process.')

            proc.terminate()

            logger.info('Joining terminated process to ensure clean exit.')

            proc.join()

        #self.monitor_heartbeat.join()

        logger.info('Heartbeat monitor stopped successfully.')


    def heartbeat(self):
        self.heartbeat_delta = (datetime.datetime.now() - self.heartbeat_last).total_seconds()
        logger.debug('self.heartbeat_delta: ' + str(self.heartbeat_delta))

        self.heartbeat_last = datetime.datetime.now()
        logger.debug('self.heartbeat_last: ' + str(self.heartbeat_last))

        if self.flatline_alerts_only == False:
            heartbeat_last_delta = "{:.2f}".format(float((datetime.datetime.now() - self.heartbeat_last).total_seconds()) / 60)

            alert_submessage = '*Last heartbeat:* ' + heartbeat_last_delta + ' minutes ago.'

            alert_message = str(self.heartbeat_last)

            logger.info(alert_message)

            if self.heartbeat_monitor == 'slack':
                alert_result = HeartbeatMonitor.send_slack_alert(self,
                                                                 channel_id=self.slack_alert_channel_id_heartbeat,
                                                                 message=alert_message,
                                                                 submessage=alert_submessage,
                                                                 flatline=False)
                logger.debug('alert_result: ' + str(alert_result))

            elif self.heartbeat_monitor == 'testing':
                logger.info('Alert Message:    ' + alert_message)
                logger.info('Alert Submessage: ' + alert_submessage)

        else:
            logger.debug('Skipping Slack alert for regular heartbeat trigger.')


    def monitor(self):
        #self.kill_monitor = False
        #logger.debug('self.kill_monitor: ' + str(self.kill_monitor))

        self.monitor_states['kill'] = False
        logger.debug('[stop_monitor] self.monitor_states[\'kill\']: ' + str(self.monitor_states['kill']))

        #self.monitor_isrunning = True
        #logger.debug('self.monitor_isrunning: ' + str(self.monitor_isrunning))

        self.monitor_states['isrunning'] = True
        logger.debug('self.monitor_states[\'isrunning\']: ' + str(self.monitor_states['isrunning']))

        try:
            self.heartbeat_last = datetime.datetime.now()
            logger.debug('self.heartbeat_last: ' + str(self.heartbeat_last))

            alert_message = 'Heartbeat monitor *_ACTIVATED_* at ' + str(self.heartbeat_last) + '.'

            if self.flatline_alerts_only == True:
                alert_submessage = 'Regular heartbeat alerts disabled. Only sending alerts on flatline detection.'

            else:
                alert_submessage = None

            if self.heartbeat_monitor == 'slack':
                alert_result = HeartbeatMonitor.send_slack_alert(self, channel_id=self.slack_alert_channel_id_heartbeat,
                                                                 message=alert_message, submessage=alert_submessage, status_message=True)
                logger.debug('alert_result: ' + str(alert_result))

            elif self.heartbeat_monitor == 'testing':
                logger.info('Alert Message:    ' + alert_message)
                logger.info('Alert Submessage: ' + str(alert_submessage))

            while (True):
                if (datetime.datetime.now() - self.heartbeat_last) > self.timeout_delta and (datetime.datetime.now() - self.flatline_last) > self.flatline_delta:
                    # ALERT REQUIRED (HEARTBEAT TIME RESET BY CALLING )

                    heartbeat_last_delta = "{:.2f}".format(float((datetime.datetime.now() - self.heartbeat_last).total_seconds()) / 60)

                    alert_message = '*Last heartbeat:* ' + heartbeat_last_delta + ' minutes ago.'

                    if self.heartbeat_monitor == 'slack':
                        alert_result = HeartbeatMonitor.send_slack_alert(self, channel_id=self.slack_alert_channel_id_heartbeat, message=alert_message, flatline=True)
                        logger.debug('alert_result: ' + str(alert_result))

                    elif self.heartbeat_monitor == 'testing':
                        logger.info('Alert Message:    ' + alert_message)
                        #logger.info('Alert Submessage: ' + alert_submessage)

                    self.flatline_last = datetime.datetime.now()
                    logger.debug('self.flatline_last: ' + str(self.flatline_last))

                #if self.kill_monitor == True:
                if self.monitor_states['kill'] == True:
                    #logger.debug('self.kill_monitor: ' + str(self.kill_monitor))
                    logger.debug('self.monitor_states[\'kill\']: ' + str(self.monitor_states['kill']))

                    logger.debug('Breaking from monitor loop.')

                    break

                time.sleep(0.1)

            self.heartbeat_last = datetime.datetime.now()
            logger.debug('self.heartbeat_last: ' + str(self.heartbeat_last))

            """
            alert_message = 'Heartbeat monitor *_DEACTIVATED_* at ' + str(self.heartbeat_last) + '.'

            if self.heartbeat_monitor == 'slack':
                alert_result = HeartbeatMonitor.send_slack_alert(self, channel_id=self.slack_alert_channel_id_heartbeat,
                                                                 message=alert_message, submessage=alert_submessage, status_message=True)
                logger.debug('alert_result: ' + str(alert_result))

            elif self.heartbeat_monitor == 'testing':
                logger.info('Alert Message:    ' + alert_message)
                logger.info('Alert Submessage: ' + alert_submessage)
            """

            #self.kill_monitor = False

        except multiprocessing.ProcessError as e:
            logger.exception('multiprocessing.ProcessError raised in monitor().')
            logger.exception(e)

            #raise

        except Exception as e:
            logger.exception('Exception raised in heartbeat main loop.')
            logger.exception(e)

            #raise

        except KeyboardInterrupt:
            logger.debug('KeyboardInterrupt in heartbeat main loop.')

            #raise

        finally:
            #self.monitor_isrunning = False
            #logger.debug('self.monitor_isrunning: ' + str(self.monitor_isrunning))

            self.monitor_states['isrunning'] = False
            logger.debug('self.monitor_states[\'isrunning\']: ' + str(self.monitor_states['isrunning']))

            self.heartbeat_last = datetime.datetime.now()
            logger.debug('self.heartbeat_last: ' + str(self.heartbeat_last))

            alert_message = 'Heartbeat monitor *_DEACTIVATED_* at ' + str(self.heartbeat_last) + '.'

            if self.heartbeat_monitor == 'slack':
                alert_result = HeartbeatMonitor.send_slack_alert(self, channel_id=self.slack_alert_channel_id_heartbeat,
                                                                 message=alert_message, submessage=alert_submessage, status_message=True)
                logger.debug('alert_result: ' + str(alert_result))

            elif self.heartbeat_monitor == 'testing':
                logger.info('Alert Message:    ' + alert_message)
                logger.info('Alert Submessage: ' + alert_submessage)


    def send_slack_alert(self, channel_id, message, submessage=None, flatline=False, status_message=False):
        alert_result = True

        try:
            if status_message == True:
                heartbeat_message = '*Heartbeat monitor status changed.*'

                fallback_message = 'Heartbeat monitor status changed.'

                heartbeat_color = '#FFFF00'

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
                                  "title": "Module: " + self.module_name,
                                  "pretext": message}]

            if submessage != None:
                attachment_array[0]['text'] = submessage

            attachments = json.dumps(attachment_array)

            self.slack_client.api_call(
                'chat.postMessage',
                channel=channel_id,
                text=heartbeat_message,
                username=self.slack_alert_user,
                #icon_emoji=slack_alert_user_icon,
                icon_url=self.slack_user_icon,
                attachments=attachments
            )

        except Exception as e:
            logger.exception('Exception in heartbeat function.')
            logger.exception(e)

            alert_result = False

        finally:
            return alert_result


if __name__ == '__main__':
    test_timeout = 1

    test_flatline_timeout = 5

    config_path = '../../TeslaBot/config/config.ini'

    hb = HeartbeatMonitor(module='Testing', monitor='slack', config_path=config_path,
                          timeout=test_timeout, flatline_timeout=test_flatline_timeout,
                          test_channel=True)

    try:
        hb.start_monitor()

        while (True):
            logger.debug('hb.monitor_states[\'isrunning\']: ' + str(hb.monitor_states['isrunning']))

            if hb.monitor_states['isrunning'] == True:
                break

            time.sleep(1)

        logger.info('Heartbeat monitor ready.')

        for x in range(0, 2):
            logger.debug('Heartbeat #' + str(x + 1))

            hb.heartbeat()

            if x < 2:
                time.sleep(5)

        logger.debug('Sleeping for >' + str(test_timeout) + ' minute to trigger heartbeat flatline alert.')

        test_delay = (test_timeout * 60) + 1

        time.sleep(test_delay)

        hb.stop_monitor()

        logger.debug('Done.')

    except multiprocessing.ProcessError as e:
        logger.exception('multiprocessing.ProcessError raised in main.')
        logger.exception(e)

    except Exception as e:
        logger.exception('Exception raised.')
        logger.exception(e)

    except KeyboardInterrupt:
        logger.info('Exit signal received.')

        hb.stop_monitor()
