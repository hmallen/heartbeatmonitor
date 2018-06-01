import logging
import os
import time

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

test_file = 'test_modification_file.py'


if __name__ == '__main__':
    """
    stat_info = os.stat(test_file)

    print(stat_info, type(stat_info))

    print(stat_info.st_mtime, type(stat_info.st_mtime))
    """

    try:
        modified_time = os.stat(test_file).st_mtime

        while (True):
            current_modified_time = os.stat(test_file).st_mtime

            if current_modified_time != modified_time:
                print('File modified.')

                modified_time = current_modified_time


            time.sleep(1)

    except Exception as e:
        logger.exception('Exception while monitoring for file changes.')
        logger.exception(e)
