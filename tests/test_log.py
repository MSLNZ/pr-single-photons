import os
import logging

import pytest

from photons import log

ENV_NAME = 'LEVEL'


def test_key_does_not_exist():
    assert ENV_NAME not in os.environ
    assert log.env_level(ENV_NAME) == logging.DEBUG
    assert log.env_level('') == logging.DEBUG


def test_raises():
    os.environ[ENV_NAME] = 'invalid'
    with pytest.raises(ValueError, match=r'Invalid log level \'INVALID\''):
        log.env_level(ENV_NAME)


@pytest.mark.parametrize('value', ['10', 'DEBUG', 'debug'])
def test_debug(value):
    os.environ[ENV_NAME] = value
    assert log.env_level(ENV_NAME) == logging.DEBUG


@pytest.mark.parametrize('value', ['20', 'INFO', 'info'])
def test_info(value):
    os.environ[ENV_NAME] = value
    assert log.env_level(ENV_NAME) == logging.INFO


@pytest.mark.parametrize('value', ['30', 'WARNING', 'WARN', 'warning', 'warn'])
def test_warning(value):
    os.environ[ENV_NAME] = value
    assert log.env_level(ENV_NAME) == logging.WARNING


@pytest.mark.parametrize('value', ['40', 'ERROR', 'error'])
def test_error(value):
    os.environ[ENV_NAME] = value
    assert log.env_level(ENV_NAME) == logging.ERROR


@pytest.mark.parametrize('value', ['50', 'CRITICAL', 'FATAL', 'critical', 'fatal'])
def test_critical(value):
    os.environ[ENV_NAME] = value
    assert log.env_level(ENV_NAME) == logging.CRITICAL
