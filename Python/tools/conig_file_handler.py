"""
Copyright 2024 Lorenzo Grandi

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

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
