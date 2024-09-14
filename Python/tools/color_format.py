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