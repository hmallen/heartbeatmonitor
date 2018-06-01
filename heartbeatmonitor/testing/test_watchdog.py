import logging
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class JSONUpdateHandler(FileSystemEventHandler):
    def on_modified(self, event):
        print('Modified!')


if __name__ == '__main__':
    event_handler = JSONUpdateHandler()

    observer = Observer()

    test_file = './test_modification_file.py'

    observer.schedule(event_handler, path=test_file, recursive=False)

    observer.start()

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        observer.stop()
        observer.join()

    finally:
        logger.info('Exiting.')
