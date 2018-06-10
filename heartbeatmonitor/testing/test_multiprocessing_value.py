import logging
from multiprocessing import Process, Value
import os
import sys
import time

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Monitor:
    def __init__(self):
        self.monitor_active = False


    def start(self, monitor_state, kill_monitor):
        Monitor.monitor(self, monitor_state, kill_monitor)


    def stop(self):
        pass


    def monitor(self, monitor_state, kill_monitor):#, monitor_active):
        self.monitor_active = True

        loop_start = time.time()

        while (True):
            try:
                if monitor_state.value == 0:
                    monitor_state.value = 1

                elif monitor_state.value == 1:
                    monitor_state.value = 0

                if kill_monitor == 1 or (time.time() - loop_start) > 60:
                    break

                time.sleep(5)

            except Exception as e:
                logger.exception(e)

            except KeyboardInterrupt:
                logger.info('Exit signal received.')

                break

            finally:
                self.monitor_active = False


if __name__ == '__main__':
    try:
        monitor_state = Value('b', 0)

        kill_monitor = Value('b', 0)

        monitor = Monitor()

        arguments = tuple()

        keyword_arguments = {'monitor_state': monitor_state, 'kill_monitor': kill_monitor}

        monitor_proc = Process(target=monitor.start, args=arguments, kwargs=keyword_arguments)

        logger.info('Starting process.')

        monitor_proc.start()

        loop_start = time.time()

        while (True):
            logger.info('monitor_state.value: ' + str(monitor_state.value))

            time.sleep(5)

        #logger.info('Joining process.')

        #monitor_proc.join()

    except Exception as e:
        logger.exception('Unhandled exception in heartbeatmonitor.monitor.')
        logger.exception(e)

    except KeyboardInterrupt:
        logger.info('Exit signal received.')

    finally:
        monitor_proc.terminate()

        monitor_proc.join()

        logger.info('Done.')
