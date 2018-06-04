import datetime
import dateutil.parser
import json
import logging
from multiprocessing import Process, Manager
import multiprocessing
import os
import time

#logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

#config_path = '../../config/config.ini'


class HeartbeatMonitor:
    def __init__(self, module, monitor, timeout, flatline_timeout,
                 use_json_storage=True, json_directory='json/heartbeatmonitor/',
                 config_path=None, flatline_alerts_only=False, test_channel=False):
        self.module_name = module

        self.heartbeat_monitor = monitor

        self.heartbeat_timeout = datetime.timedelta(minutes=timeout)

        self.heartbeat_delta = datetime.timedelta(seconds=0)

        self.heartbeat_last = datetime.datetime.now()

        self.flatline_timeout = datetime.timedelta(minutes=flatline_timeout)

        self.flatline_delta = datetime.timedelta(minutes=flatline_timeout)

        self.flatline_last = datetime.datetime.now() - self.flatline_delta

        #self.monitor_states['heartbeat_last'] = datetime.datetime.now()

        #self.monitor_states['flatline_last'] = datetime.datetime.now() - self.flatline_delta

        self.flatline_alerts_only = flatline_alerts_only

        self.use_json_storage = use_json_storage

        if self.use_json_storage == True:
            self.json_save_file = json_directory + 'heartbeats_' + module + '.json'

            if not os.path.exists(json_directory):
                #os.mkdir(json_directory)
                os.makedirs(json_directory, exist_ok=True)

            self.json_save_data = {'module': module,
                                   'heartbeat_timeout': self.heartbeat_timeout,
                                   'heartbeat_last': self.heartbeat_last,
                                   'heartbeat_delta': self.heartbeat_delta,
                                   'flatline_timeout': self.flatline_timeout,
                                   'flatline_last': self.flatline_last,
                                   'flatline_delta': self.flatline_delta}

            create_new_file = False

            if not os.path.exists(self.json_save_file):
                create_new_file = True

            else:
                try:
                    #with open(self.json_save_file, 'r', encoding='utf-8') as file:
                        #json_data_old = json.load(file)

                    json_data = HeartbeatMonitor.read_write_json(self)
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
                #with open(self.json_save_file, 'w', encoding='utf-8') as file:
                    #json.dump(self.json_save_data, file, indent=4, sort_keys=True, ensure_ascii=False)

                json_data = HeartbeatMonitor.read_write_json(self, self.json_save_data)
                logger.debug('json_data[\'status\']: ' + str(json_data['status']))

            self.kill_monitor = False

            self.monitor_isrunning = False

            self.monitor_heartbeat = Process(target=HeartbeatMonitor.monitor, args=(self,))

        else:
            self.multiprocessing_manager = Manager()

            #self.multiprocessing_manager = DataManager.ShareManager()

            #self.multiprocessing_manager.start(signal.signal, (signal.SIGINT, signal.SIG_IGN))

            self.monitor_states = self.multiprocessing_manager.dict({'heartbeat_last': datetime.datetime.now(),
                                                                     'flatline_last': datetime.datetime.now() - self.flatline_delta,
                                                                     'kill' : False,
                                                                     'isrunning': False})

            self.monitor_heartbeat = Process(target=HeartbeatMonitor.monitor, args=(self,))

        if self.heartbeat_monitor == 'slack':
            if config_path == None:
                logger.error('Slack alerts enabled. Must provide path to config file with Slack API credentials. Exiting.')

                sys.exit(1)

            import configparser
            from slackclient import SlackClient

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

        elif self.heartbeat_monitor == 'testing':
            logger.info('Using testing heartbeat monitor. Outputting to console.')


    def read_write_json(self, json_data=None):
        # Convert to and from types encodable by json module
        def convert_datetime(dt):
            dt_modified = -1

            try:
                if isinstance(dt, datetime.datetime):
                    logger.debug('[convert_datetime] datetime.datetime')

                    dt_modified = dt.isoformat()

                elif isinstance(dt, str):
                    logger.debug('[convert_datetime] str')

                    dt_modified = dateutil.parser.parse(dt)

                elif isinstance(dt, datetime.timedelta):
                    logger.debug('[convert_datetime] datetime.timedelta')

                    dt_modified = dt.total_seconds()

                elif isinstance(dt, float):
                    logger.debug('[convert_datetime] float')

                    dt_modified = datetime.timedelta(seconds=dt)

                else:
                    logger.error('Incorrect type passed to convert_datetime().')

            except Exception as e:
                logger.exception('Exception while converting date/time.')
                logger.exception(e)

            finally:
                return dt_modified

        """
        {'module': module,
         'heartbeat_timeout': self.heartbeat_timeout,
         'heartbeat_last': self.heartbeat_last,
         'heartbeat_delta': self.heartbeat_delta,
         'flatline_timeout': self.flatline_timeout,
         'flatline_last': self.flatline_last,
         'flatline_delta': self.flatline_delta}
        """

        json_converted_return = {'data': None, 'status': None}

        conversion_list = ['heartbeat_last', 'heartbeat_timeout', 'heartbeat_delta',
                           'flatline_last', 'flatline_timeout', 'flatline_delta']

        json_data_converted = {}

        try:
            #if operation == 'read':
            if json_data == None:
                with open(self.json_save_file, 'r', encoding='utf-8') as file:
                    json_data_raw = json.loads(file.read())

                for data in json_data_raw:
                    if data in conversion_list:
                        if data == 'heartbeat_last' or data == 'flatline_last':
                            json_data_converted[data] = dateutil.parser.parse(json_data_raw[data])

                        elif data == 'heartbeat_timeout' or data == 'heartbeat_delta' or data == 'flatline_timeout' or data == 'flatline_delta':
                            json_data_converted[data] = datetime.timedelta(seconds=json_data_raw[data])

                        else:
                            logger.error('Unknown json data key.')

                    else:
                        json_data_converted[data] = json_data_raw[data]

                json_converted_return['data'] = json_data_converted

                json_converted_return['status'] = True

            #elif operation == 'write':
            else:
                for data in json_data:
                    if data in conversion_list:
                        json_data_converted[data] = convert_datetime(json_data[data])

                    else:
                        json_data_converted[data] = json_data[data]

                with open(self.json_save_file, 'w', encoding='utf-8') as file:
                    json.dump(json_data_converted, file, indent=4, sort_keys=True, ensure_ascii=False)

                json_converted_return['status'] = True

            #else:
                #logger.error('Invalid operation type passed to HeartbeatMonitor.read_write_json().')

        except Exception as e:
            logger.exception('Exception in HeartbeatMonitor.read_write_json()')
            logger.exception(e)

            json_converted_return['status'] = False

        finally:
            return json_converted_return


    def start_monitor(self):
        logger.debug('Starting heartbeat monitor.')

        self.monitor_heartbeat.start()

        time.sleep(5)   # Need more elegant solution to determine when monitor is fully started

        #if self.use_json_storage == True:
            #HeartbeatMonitor.monitor(self)
            #self.monitor_heartbeat.start()

        #else:
            #self.monitor_heartbeat.start()

        alert_message = 'Heartbeat monitor *_ACTIVATED_* at ' + str(datetime.datetime.now()) + '.'

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

        logger.debug('Heartbeat monitor active.')


    def stop_monitor(self):
        logger.debug('Stopping heartbeat monitor.')

        if self.use_json_storage == True:
            self.kill_monitor = True
            logger.debug('self.kill_monitor: ' + str(self.kill_monitor))

            while self.monitor_isrunning == True:
                time.sleep(0.1)

            self.monitor_heartbeat.terminate()

            self.monitor_heartbeat.join()

        else:
            #self.kill_monitor = True
            #logger.debug('[stop_monitor] self.kill_monitor: ' + str(self.kill_monitor))

            self.monitor_states['kill'] = True
            logger.debug('[stop_monitor] self.monitor_states[\'kill\']: ' + str(self.monitor_states['kill']))

            #while self.monitor_isrunning == True:
            while self.monitor_states['isrunning'] == True:
                time.sleep(0.1)

            logger.info('Gathering active child processes.')

            active_processes = multiprocessing.active_children()

            logger.info('Terminating all child processes.')

            for proc in active_processes:
                logger.debug('Child Process: ' + str(proc))

                logger.info('Terminating heartbeat monitor process.')

                proc.terminate()

                logger.info('Joining terminated process to ensure clean exit.')

                proc.join()

            #self.monitor_heartbeat.join()

        alert_message = 'Heartbeat monitor *_DEACTIVATED_* at ' + str(datetime.datetime.now()) + '.'

        alert_submessage = None

        if self.heartbeat_monitor == 'slack':
            alert_result = HeartbeatMonitor.send_slack_alert(self, channel_id=self.slack_alert_channel_id_heartbeat,
                                                             message=alert_message, submessage=alert_submessage, status_message=True)

            logger.debug('alert_result: ' + str(alert_result))

        elif self.heartbeat_monitor == 'testing':
            logger.info('Alert Message:    ' + alert_message)
            logger.info('Alert Submessage: ' + str(alert_submessage))

        logger.info('Heartbeat monitor stopped successfully.')


    def heartbeat(self, message=None):
        if self.use_json_storage == True:
            self.heartbeat_delta = datetime.datetime.now() - self.heartbeat_last
            logger.debug('self.heartbeat_delta: ' + str(self.heartbeat_delta))

            self.heartbeat_last = datetime.datetime.now()
            logger.debug('self.heartbeat_last: ' + str(self.heartbeat_last))

            self.json_save_data['heartbeat_delta'] = self.heartbeat_delta

            self.json_save_data['heartbeat_last'] = self.heartbeat_last

            logger.debug('Dumping heartbeat data to json file.')

            #with open(self.json_save_file, 'w', encoding='utf-8') as file:
                #json.dump(self.json_save_data, file, indent=4, sort_keys=True, ensure_ascii=False)

            json_status = HeartbeatMonitor.read_write_json(self, self.json_save_data)
            logger.debug('json_status[\'status\']: ' + str(json_status['status']))

            if self.flatline_alerts_only == False:
                alert_message = str(self.heartbeat_last)

                if message != None:
                    alert_message += ' - (' + message + ')'

                logger.debug('alert_message: ' + alert_message)

                heartbeat_last_delta = "{:.2f}".format(float(self.heartbeat_delta.total_seconds()) / 60)

                alert_submessage = '*Last heartbeat:* ' + heartbeat_last_delta + ' minutes ago.'

                logger.debug('alert_submessage: ' + alert_submessage)

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

        else:
            #self.heartbeat_delta = (datetime.datetime.now() - self.monitor_states['heartbeat_last']).total_seconds()
            self.heartbeat_delta = datetime.datetime.now() - self.monitor_states['heartbeat_last']
            logger.debug('self.heartbeat_delta: ' + str(self.heartbeat_delta))

            self.monitor_states['heartbeat_last'] = datetime.datetime.now()
            logger.debug('self.monitor_states[\'heartbeat_last\']: ' + str(self.monitor_states['heartbeat_last']))

            if self.flatline_alerts_only == False:
                heartbeat_last_delta = "{:.2f}".format(float((datetime.datetime.now() - self.monitor_states['heartbeat_last']).total_seconds()) / 60)

                alert_message = str(self.monitor_states['heartbeat_last'])

                if message != None:
                    alert_message += ' - (' + message + ')'

                logger.debug('alert_message: ' + alert_message)

                alert_submessage = '*Last heartbeat:* ' + heartbeat_last_delta + ' minutes ago.'

                logger.debug('alert_submessage: ' + alert_submessage)

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
        if self.use_json_storage == True:
            try:
                json_modified_time = os.stat(self.json_save_file).st_mtime

                self.monitor_isrunning = True

                while (True):
                    json_current_modified_time = os.stat(self.json_save_file).st_mtime

                    if json_current_modified_time != json_modified_time:
                        logger.debug('JSON heartbeat save file updated.')

                        #with open(self.json_save_file, 'r', encoding='utf-8') as file:
                            #self.json_save_data = json.load(file)

                        json_data = HeartbeatMonitor.read_write_json(self)
                        logger.debug('json_data[\'status\']: ' + str(json_data['status']))

                        self.json_save_data = json_data['data']

                        self.heartbeat_last = self.json_save_data['heartbeat_last']
                        self.flatline_last = self.json_save_data['flatline_last']

                        json_modified_time = json_current_modified_time

                    if (datetime.datetime.now() - self.heartbeat_last) > self.heartbeat_timeout:
                        if (datetime.datetime.now() - self.flatline_last) > self.flatline_timeout:
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

                            self.json_save_data['flatline_last'] = self.flatline_last

                            logger.debug('Saving flatline alert time to json file.')

                            #with open(self.json_save_file, 'w', encoding='utf-8') as file:
                                #json.dump(self.json_save_data, file, indent=4, sort_keys=True, ensure_ascii=False)

                            json_data = HeartbeatMonitor.read_write_json(self, self.json_save_data)
                            logger.debug('json_data[\'status\']: ' + str(json_data['status']))

                    if self.kill_monitor == True:   # This doesn't get executed?
                        logger.debug('Killing monitor loop.')

                        break

                    time.sleep(1)

                logger.debug('Exited monitor loop.')

            except multiprocessing.ProcessError as e:
                logger.exception('multiprocessing.ProcessError raised in heartbeat monitor.')
                logger.exception(e)

                #raise

            except Exception as e:
                logger.exception('Exception raised in heartbeat monitor.')
                logger.exception(e)

                #raise

            except KeyboardInterrupt:
                logger.debug('KeyboardInterrupt in heartbeat monitor.')

                #raise

            finally:
                self.monitor_isrunning = False
                logger.debug('self.monitor_isrunning: ' + str(self.monitor_isrunning))

                """
                alert_message = 'Heartbeat monitor *_DEACTIVATED_* at ' + str(datetime.datetime.now()) + '.'

                if self.heartbeat_monitor == 'slack':
                    alert_result = HeartbeatMonitor.send_slack_alert(self, channel_id=self.slack_alert_channel_id_heartbeat,
                                                                     message=alert_message, submessage=alert_submessage, status_message=True)
                    logger.debug('alert_result: ' + str(alert_result))

                elif self.heartbeat_monitor == 'testing':
                    logger.info('Alert Message:    ' + alert_message)
                    logger.info('Alert Submessage: ' + alert_submessage)
                """

        else:
            self.monitor_states['kill'] = False
            logger.debug('[stop_monitor] self.monitor_states[\'kill\']: ' + str(self.monitor_states['kill']))

            self.monitor_states['isrunning'] = True
            logger.debug('self.monitor_states[\'isrunning\']: ' + str(self.monitor_states['isrunning']))

            try:
                self.monitor_states['heartbeat_last'] = datetime.datetime.now()
                logger.debug('self.monitor_states[\'heartbeat_last\']: ' + str(self.monitor_states['heartbeat_last']))

                alert_message = 'Heartbeat monitor *_ACTIVATED_* at ' + str(self.monitor_states['heartbeat_last']) + '.'

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
                    if (datetime.datetime.now() - self.monitor_states['heartbeat_last']) > self.heartbeat_timeout and (datetime.datetime.now() - self.monitor_states['flatline_last']) > self.flatline_timeout:
                        # ALERT REQUIRED (HEARTBEAT TIME RESET BY CALLING HeartbeatMonitor.heartbeat())

                        logger.warning('Flatline event detected for ' + self.module_name + '!')

                        heartbeat_last_delta = "{:.2f}".format(float((datetime.datetime.now() - self.monitor_states['heartbeat_last']).total_seconds()) / 60)

                        alert_message = '*Last heartbeat:* ' + heartbeat_last_delta + ' minutes ago.'

                        if self.heartbeat_monitor == 'slack':
                            alert_result = HeartbeatMonitor.send_slack_alert(self, channel_id=self.slack_alert_channel_id_heartbeat, message=alert_message, flatline=True)
                            logger.debug('alert_result: ' + str(alert_result))

                        elif self.heartbeat_monitor == 'testing':
                            logger.info('Alert Message:    ' + alert_message)
                            #logger.info('Alert Submessage: ' + alert_submessage)

                        self.monitor_states['flatline_last'] = datetime.datetime.now()
                        logger.debug('self.monitor_states[\'flatline_last\']: ' + str(self.monitor_states['flatline_last']))

                    #if self.kill_monitor == True:
                    if self.monitor_states['kill'] == True:
                        #logger.debug('self.kill_monitor: ' + str(self.kill_monitor))
                        logger.debug('self.monitor_states[\'kill\']: ' + str(self.monitor_states['kill']))

                        logger.debug('Breaking from monitor loop.')

                        break

                    time.sleep(0.1)

                self.monitor_states['heartbeat_last'] = datetime.datetime.now()
                logger.debug('self.monitor_states[\'heartbeat_last\']: ' + str(self.monitor_states['heartbeat_last']))

            except multiprocessing.ProcessError as e:
                logger.exception('multiprocessing.ProcessError raised in heartbeat monitor.')
                logger.exception(e)

                #raise

            except Exception as e:
                logger.exception('Exception raised in heartbeat monitor.')
                logger.exception(e)

                #raise

            except KeyboardInterrupt:
                logger.debug('KeyboardInterrupt in heartbeat monitor.')

                #raise

            """
            finally:
                #self.monitor_isrunning = False
                #logger.debug('self.monitor_isrunning: ' + str(self.monitor_isrunning))

                self.monitor_states['isrunning'] = False
                logger.debug('self.monitor_states[\'isrunning\']: ' + str(self.monitor_states['isrunning']))

                self.monitor_states['heartbeat_last'] = datetime.datetime.now()
                logger.debug('self.monitor_states[\'heartbeat_last\']: ' + str(self.monitor_states['heartbeat_last']))

                alert_message = 'Heartbeat monitor *_DEACTIVATED_* at ' + str(self.monitor_states['heartbeat_last']) + '.'

                if self.heartbeat_monitor == 'slack':
                    alert_result = HeartbeatMonitor.send_slack_alert(self, channel_id=self.slack_alert_channel_id_heartbeat,
                                                                     message=alert_message, submessage=alert_submessage, status_message=True)
                    logger.debug('alert_result: ' + str(alert_result))

                elif self.heartbeat_monitor == 'testing':
                    logger.info('Alert Message:    ' + alert_message)
                    logger.info('Alert Submessage: ' + alert_submessage)
            """


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
                username=self.slack_bot_user,
                icon_url=self.slack_bot_icon,
                attachments=attachments
            )

        except Exception as e:
            logger.exception('Exception in heartbeat function.')
            logger.exception(e)

            alert_result = False

        finally:
            return alert_result


if __name__ == '__main__':
    test_config_path = '../../TeslaBot/config/config.ini'

    test_timeout = 0.25

    test_flatline_timeout = 1

    hb = HeartbeatMonitor(module='Testing', monitor='slack', config_path=test_config_path,
                          timeout=test_timeout, flatline_timeout=test_flatline_timeout,
                          flatline_alerts_only=False, test_channel=True)

    try:
        hb.start_monitor()

        """
        while (True):
            #logger.debug('hb.monitor_states[\'isrunning\']: ' + str(hb.monitor_states['isrunning']))

            logger.debug('hb.monitor_isrunning: ' + str(hb.monitor_isrunning))

            #if hb.monitor_states['isrunning'] == True:
            if hb.monitor_isrunning == True:
                break

            time.sleep(1)
        """

        logger.info('Heartbeat monitor ready.')

        for x in range(0, 2):
            heartbeat_message = 'Heartbeat #' + str(x + 1)

            logger.debug('heartbeat_message: ' + heartbeat_message)

            hb.heartbeat(message=heartbeat_message)

            if x < 2:
                time.sleep(5)

        logger.debug('Sleeping for >' + str(test_timeout) + ' min to trigger heartbeat flatline alert.')

        test_delay = (test_timeout * 60) + 1

        time.sleep(test_delay)

        hb.stop_monitor()

        logger.debug('Done.')

    #except multiprocessing.ProcessError as e:
        #logger.exception('multiprocessing.ProcessError raised in main.')
        #logger.exception(e)

    except Exception as e:
        logger.exception('Exception raised.')
        logger.exception(e)

    except KeyboardInterrupt:
        logger.info('Exit signal received.')

        hb.stop_monitor()
