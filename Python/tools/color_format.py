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

from colorama import Fore, Style, init
import logging

init(autoreset=True)

class ColorFormatter(logging.Formatter):
    def format(self, record):
        log_colors = {
            logging.DEBUG: Fore.CYAN,
            logging.INFO: Fore.GREEN,
            logging.WARNING: Fore.YELLOW,
            logging.ERROR: Fore.RED,
            logging.CRITICAL: Fore.MAGENTA,
        }

        level_color = log_colors.get(record.levelno, Fore.WHITE)
        record.msg = f"{level_color}{record.msg}{Style.RESET_ALL}"

        return super().format(record)