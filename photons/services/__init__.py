"""
Custom :class:`~msl.network.service.Service`\\s.
"""
import os
import importlib

from msl.io import search

from .. import (
    logger,
    Register,
)

services = []
""":class:`list` of :class:`~msl.network.service.Service`: The :class:`~msl.network.service.Service`\\s 
that have been registered."""


def service():
    """Use as a decorator to register a :class:`~msl.network.service.Service` class."""
    def cls(obj):
        services.append(obj)
        logger.debug('added {} to the service registry'.format(obj))
        return obj
    return cls


# import all submodules to register all service classes
for filename in search(os.path.dirname(__file__), pattern=Register.PATTERN, levels=0):
    importlib.import_module(__name__ + '.' + os.path.basename(filename)[:-3])
