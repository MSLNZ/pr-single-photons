"""Logging configuration."""
import logging
import os


def env_level(key: str = 'PHOTONS_LOG_LEVEL') -> int:
    """Read the logging level from an environment variable."""
    value = os.getenv(key)
    if value is None:
        return logging.DEBUG

    value = logging.getLevelName(value.upper())  # can return a str or an int
    if isinstance(value, int):
        return value

    name = value.removeprefix('Level ')
    try:
        return int(name)
    except ValueError:
        raise ValueError(f'Invalid log level {name!r}') from None


def set_block(*names: str) -> None:
    """Block all messages from the specified loggers."""
    for name in names:
        set_level(name, logging.CRITICAL+1)


def set_debug(*names: str) -> None:
    """Show DEBUG (and above) messages from the specified loggers."""
    for name in names:
        set_level(name, logging.DEBUG)


def set_errors(*names: str) -> None:
    """Show ERROR (and above) messages from the specified loggers."""
    for name in names:
        set_level(name, logging.ERROR)


def set_info(*names: str) -> None:
    """Show INFO (and above) messages from the specified loggers."""
    for name in names:
        set_level(name, logging.INFO)


def set_level(name: str, level: int | str) -> None:
    """Set the logging level for a particular logger."""
    logging.getLogger(name).setLevel(level)


def set_warnings(*names: str) -> None:
    """Show WARNING (and above) messages from the specified loggers."""
    for name in names:
        set_level(name, logging.WARNING)


logger = logging.getLogger(__package__)
logger.setLevel(env_level())

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d [%(levelname)-5s] %(name)s - %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S',
)

set_errors('asyncio', 'urllib3', 'matplotlib')
set_block('pyvisa', 'pyvisa-py')
set_warnings('msl', 'google', 'googleapiclient')
