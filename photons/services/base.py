"""
Base class for :class:`~msl.network.service.Service`\\s.
"""
from dataclasses import dataclass
from typing import TypeVar

from msl.network import Service

from ..log import logger

DecoratedService = TypeVar('DecoratedService', bound=Service)


def service(*, name: str = None, description: str = None):
    """A decorator to register a :class:`~msl.network.service.Service`.

    Args:
        name: The name of the registered Service. If not specified then uses
            the class name. If you specify a name in the decorator then you
            should also specify the same name in the call to super().
        description: A short description about the Service.
    """
    def decorate(cls: type[DecoratedService]) -> type[DecoratedService]:
        if not issubclass(cls, Service):
            raise TypeError(f'{cls} is not a subclass of {Service}')
        n = name or cls.__name__
        desc = description or ''
        services.append(ServiceInfo(cls=cls, name=n, description=desc))
        logger.debug(f'added {n!r} to the service registry')
        return cls
    return decorate


@dataclass(frozen=True)
class ServiceInfo:
    cls: type[Service]
    name: str
    description: str


services: list[ServiceInfo] = []
