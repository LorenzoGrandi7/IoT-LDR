import logging

from .color_format import ColorFormatter
from .config_file_handler import ConfigFileHandler

__all__ = ['ConfigFileHandler', 'ColorFormatter']

console_handler = logging.StreamHandler()

formatter = ColorFormatter("%(asctime)s - %(name)s : %(message)s", datefmt="%H:%M:%S")
console_handler.setFormatter(formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(console_handler)