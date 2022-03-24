"""
Console script entry points.
"""
import re
import sys
from collections import namedtuple
from argparse import (
    ArgumentParser,
    RawTextHelpFormatter,
)

from msl.network.ssh import parse_console_script_kwargs
from msl.network.service import filter_service_start_kwargs

from .log import logger
from .utils import Register
from .app import App

__author__ = 'Joseph Borbely'
__copyright__ = '\xa9 2022 ' + __author__
__version__ = '0.1.0.dev0'

_v = re.search(r'(\d+)\.(\d+)\.(\d+)[.-]?(.*)', __version__).groups()

version_info = namedtuple('version_info', 'major minor micro releaselevel')(int(_v[0]), int(_v[1]), int(_v[2]), _v[3])
""":obj:`~collections.namedtuple`: Contains the version information as a (major, minor, micro, releaselevel) tuple."""


def cli_parser(*args):
    """Parse the command line arguments."""
    if not args:
        args = sys.argv[1:]

    p = ArgumentParser(
        description='Light Standards Single Photons.',
        formatter_class=RawTextHelpFormatter
    )
    p.add_argument(
        'config',
        nargs='?',
        default=r'D:\config.xml',
        help='the path to a configuration file'
    )
    p.add_argument(
        '--alias',
        help='the alias of an EquipmentRecord'
    )
    p.add_argument(
        '--name',
        help='the name of the Service to start'
    )
    p.add_argument(
        '--kwargs',
        help='keyword arguments that are used to start a Service, e.g.,\n'
             '--kwargs {"host":"localhost","port":1875}'
    )
    return p.parse_args(args)


def create_app_and_gui(*args):
    """Console script to create the :class:`~photons.app.App` and
    show the :class:`~photons.gui.MainWindow`.

    Usage
    -----
    create-app config.xml
    """
    args = cli_parser(*args)
    a = App(args.config)
    a.gui()
    a.disconnect_equipment()
    a.unlink()
    a.disconnect_clients()


def start_service(*args):
    """Console script to start a :class:`~msl.network.service.Service`.

    You must either specify the alias of an EquipmentRecord to run as a Service
    or the name of a Service to start but not both.

    Usage
    -----
    photons-start-service config.xml --alias superk --kwargs {"host":"localhost","port":1875}
    photons-start-service config.xml --name MyService --kwargs {"host":"localhost","port":1875}
    """
    press_enter_msg = '\nPress <Enter> to exit...'
    args = cli_parser(*args)

    def print_exception():
        import traceback
        input('\n' + ''.join(traceback.format_exception(*sys.exc_info())) + press_enter_msg)

    if not args.alias and not args.name:
        input('\nYou must specify the alias or the name of a Service to start.\n' + press_enter_msg)
    elif args.alias and args.name:
        input('\nYou cannot specify both the alias and the name of a Service to start.\n' + press_enter_msg)
    else:
        kwargs = filter_service_start_kwargs(**parse_console_script_kwargs())
        if args.alias:
            try:
                a = App(args.config)
                a.start_equipment_service(args.alias, **kwargs)
            except:
                print_exception()
        else:
            try:
                App.start_service(args.name, **kwargs)
            except:
                print_exception()
