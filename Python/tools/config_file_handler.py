import logging 
import asyncio
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger("ConfigFileHandler")
logger.setLevel(logging.DEBUG)

class ConfigFileHandler(FileSystemEventHandler):
    def __init__(self, loop, on_modified_callback):
        self.loop = loop
        self.on_modified_callback = on_modified_callback

    def on_modified(self, event):
        if event.src_path.endswith('config.json'):
            logger.info("New JSON configurations detected.")
            asyncio.run_coroutine_threadsafe(self.on_modified_callback(), self.loop)
