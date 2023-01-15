"""
Console script entry points.
"""
import argparse
import re
import sys
from collections import namedtuple

from .app import App
from .equipment import *
from .io import PhotonWriter
from .log import logger
from .samples import Samples
from . import plugins
from . import services

__author__ = 'Joseph Borbely'
__copyright__ = f'\xa9 2022 - 2023 {__author__}'
__version__ = '0.1.0.dev0'

_v = re.search(r'(\d+)\.(\d+)\.(\d+)[.-]?(.*)', __version__).groups()

version_info = namedtuple('version_info', 'major minor micro releaselevel')(int(_v[0]), int(_v[1]), int(_v[2]), _v[3])
""":obj:`~collections.namedtuple`: Contains the version information as a (major, minor, micro, releaselevel) tuple."""


def _maybe_press_enter(no_user: bool) -> None:
    if no_user:
        return
    input('Press <Enter> to exit... ')


def _print_traceback(no_user: bool, *, msg: str = '') -> int:
    import traceback
    tb = ''.join(traceback.format_exception(*sys.exc_info()))
    print(f'\n{tb}{msg}')
    _maybe_press_enter(no_user)
    return 1


def cli_parser(*args: str) -> argparse.Namespace:
    """Parse the command line arguments."""
    if not args:
        args = sys.argv[1:]

    p = argparse.ArgumentParser(
        description='Light Standards Single Photons.',
        formatter_class=argparse.RawTextHelpFormatter
    )
    p.add_argument(
        'config',
        nargs='?',
        help='the path to a configuration file (default is ~/photons.xml)'
    )
    p.add_argument(
        '--alias',
        help='the alias of an EquipmentRecord to start a generic equipment Service'
    )
    p.add_argument(
        '--name',
        help='the name of a registered Service to start'
    )
    p.add_argument(
        '--kwargs',
        help='keyword arguments that are passed to Service.start(), e.g.,\n'
             '--kwargs "{\\"host\\":\\"localhost\\", \\"port\\":1876}"'
    )
    p.add_argument(
        '--no-user',
        action='store_true',
        default=False,
        help='if there was an error then do not wait for the user to acknowledge\n'
             'the error by pressing <Enter>'
    )
    p.add_argument(
        '-j', '--jupyter',
        action='store_true',
        default=False,
        help='start a JupyterLab web server'
    )
    return p.parse_args(args)


def main(*args: str) -> None:
    """Main console script entry point.

    Run ``photons --help`` for more details.

    Args:
        args: Command-line arguments.

    Examples:

        * | Start the main application using the default configuration path
          | ``photons``

        * | Start the main application using the specified configuration file
          | ``photons my_config.xml``

        * | Start an equipment Service (using the default configuration path)
          | ``photons --alias shutter``

        * | Start an equipment Service using the specified configuration file
          | ``photons my_config.xml --alias shutter``

        * | Start a registered Service and specify kwargs
          | ``photons --name MyService --kwargs "{\\"host\\":\\"localhost\\", \\"port\\":1876}"``

        * | Start a JupyterLab web server
          | ``photons --jupyter``

    """
    args = cli_parser(*args)
    if args.jupyter:
        sys.exit(start_jupyter(args.config, args.no_user))
    if not (args.alias or args.name):
        sys.exit(start_app(args.config, args.no_user))
    sys.exit(start_service(**args.__dict__))


def start_app(config: str | None, no_user: bool) -> int:
    """Start the main application instance.

    Args:
        config: The path to a configuration file.
        no_user: Whether to call *input('Press <Enter> to exit... ')* if there was an error.

    Returns:
        The exit code (0 for success, 1 for error).
    """
    try:
        a = App(config)
    except OSError:
        return _print_traceback(no_user)

    a.run()
    a.disconnect_equipment()
    a.unlink()
    a.disconnect_managers()
    return 0


def start_service(
        alias: str | None,
        config: str | None,
        name: str | None,
        kwargs: str | None,
        no_user: bool) -> int:
    """Start a Service.

    Args:
        alias: The alias of an EquipmentRecord to start a generic equipment Service.
        config: The path to a configuration file. Not required if `name` is specified.
        name: The name of a registered Service to start.
        kwargs: The keyword arguments from the command line.
        no_user: Whether to call *input('Press <Enter> to exit... ')* if there was an error.

    Returns:
        The exit code (0 for success, 1 for error).
    """
    if alias and name:
        print(f'\nYou cannot specify both the alias ({alias!r}) and the '
              f'name ({name!r}) to start a Service.')
        _maybe_press_enter(no_user)
        return 1

    try:
        from msl.network.ssh import parse_console_script_kwargs
        kwargs = parse_console_script_kwargs()
    except:  # noqa: Too broad exception clause (PEP8: E722)
        return _print_traceback(no_user, msg=f'\nReceived the following kwargs: {kwargs}')

    if alias:
        try:
            a = App(config)
            a.start_equipment_service(alias, **kwargs)
            return 0
        except:  # noqa: Too broad exception clause (PEP8: E722)
            return _print_traceback(no_user)

    try:
        App.start_service(name, **kwargs)
        return 0
    except:  # noqa: Too broad exception clause (PEP8: E722)
        return _print_traceback(no_user)


def start_jupyter(config: str | None, no_user: bool) -> int:
    """Start a Jupyter web server.

    Args:
        config: The path to a configuration file.
        no_user: Whether to call *input('Press <Enter> to exit... ')* if there was an error.

    Returns:
        The exit code (0 for success, 1 for error).
    """
    import os

    try:
        a = App(config)
    except OSError:
        return _print_traceback(no_user)

    command = 'jupyter lab'
    data_root = a.config.value('data_root')
    if data_root:
        command += f' --notebook-dir={data_root}'
    else:
        a.logger.info('create a <data_root> element in the configuration '
                      'file to change the root notebook directory')

    try:
        os.system(command)
    except KeyboardInterrupt:
        return 0
