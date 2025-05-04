import os
import logging
from logging import FileHandler, StreamHandler, Formatter


def configure_logger(
    logger_name: str,
    log_file_name: str,
    console_level=logging.INFO,
    file_level=logging.DEBUG,
) -> logging.Logger:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
    os.makedirs(log_dir, exist_ok=True)

    file_path = os.path.join(log_dir, log_file_name)

    fh = FileHandler(file_path, mode="a", encoding="utf-8")
    fh.setLevel(file_level)

    ch = StreamHandler()
    ch.setLevel(console_level)

    formatter = Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger
