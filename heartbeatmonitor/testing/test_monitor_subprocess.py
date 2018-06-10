import logging
import os
import subprocess
import sys

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


if __name__ == '__main__':
    active_file = '../json/ACTIVE'

    try:
        if not os.path.exists(active_file):
            logger.info('Monitor not currently active. Starting monitor.')

            os.chdir('../')

            monitor = subprocess.Popen('python monitor.py -c ../../TeslaBot/config/config.ini -d ../json/heartbeat')

            logger.debug('monitor: ' + str(monitor))

        else:
            logger.info('Monitor already active.')

    except Exception as e:
        logger.exception(e)

    finally:
        logger.info('Done.')
