import configparser
import json
import logging
from multiprocessing import Process, Array
import os
import sys
import time

from slackclient import SlackClient

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Monitor:
    def __init__(self, json_directory='json/heartbeat/'):
        self.json_directory = json_directory

        if not os.path.exists(self.json_directory):
            os.makedirs(self.json_directory, exist_ok=True)


    def start(self, monitor_state):
        logger.info('Start monitor triggered.')

        Monitor.monitor(self, monitor_state)


    def stop(self, monitor_state):
        monitor_state[1] = 1

        while monitor_state[0] == 1:
            time.sleep(1)


    def monitor(self, monitor_state):
        monitor_state[0] = 1

        loop_start = time.time()

        while (True):
            try:
                # Load heartbeats from directory
                heartbeat_files = os.listdir(self.json_directory)

                for file in heartbeat_files:
                    """
                    {
                        "flatline_delta": 60.0,
                        "flatline_last": "2018-06-01T01:54:42.781292",
                        "flatline_timeout": 60.0,
                        "heartbeat_delta": 5.152881,
                        "heartbeat_last": "2018-06-01T01:55:53.824336",
                        "heartbeat_timeout": 15.0,
                        "module": "Testing"
                    }
                    """

                    heartbeat_data = {}

                    with open(file, 'r', encoding='utf-8') as file:
                        heartbeat_data = json.load(file)

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

        monitor_state[0] = 0


if __name__ == '__main__':
    try:
        monitor_state = Array('b', [0, 0])

        monitor = Monitor()
        monitor_proc = Process(target=monitor.start, args=(monitor_state,))

        logger.debug('Starting monitor process.')

        monitor_proc.start()

        logger.info('Waiting for monitor to become active.')

        while monitor_state[0] == 0:
            time.sleep(1)

        logger.info('Monitor ready.')

        loop_start = time.time()

        while (True):
            try:
                time.sleep(5)

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
        logger.info('Terminating process.')

        monitor_proc.terminate()

        logger.info('Joining terminated process.')

        monitor_proc.join()

        logger.info('Done.')
