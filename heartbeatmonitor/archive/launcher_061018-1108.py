import logging
import os
import sys

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Launcher:
    def __init__(self):
        pass

    def launch_monitor(self):
        pass


if __name__ == '__main__':
    try:
        pass

    except Exception as e:
        logger.exception('Exception raised in heartbeatmonitor launcher.')
        logger.exception(e)

    except KeyboardInterrupt:
        logger.info('Exit signal received.')
