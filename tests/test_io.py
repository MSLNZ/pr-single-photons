import os
from datetime import datetime
from tempfile import NamedTemporaryFile
from tempfile import gettempdir

import numpy as np
import pytest
from msl.io import read

from photons import io


def test_exists():
    with NamedTemporaryFile() as file:
        with pytest.raises(FileExistsError):
            io.PhotonWriter(file.name)


def test_write_read():
    file = gettempdir() + '/photons-writer-testing.json'

    if os.path.isfile(file):
        os.remove(file)

    w = io.PhotonWriter(file, log_size=10)
    w.initialize('a', 'b', 'c')
    w.append(1, 2, 3)
    w.append(4, 5, 6)
    w.append(7, 8, 9)
    w.initialize('x', 'y', name='hi', fruit='apple', types=[int, int])
    w.append(-1, 2)
    w.initialize('foo', 'bar', name='/foo/bar/baz', microseconds=True, types=[float, int])
    w.update_metadata(name='hi', taste='sweat', colour='red')
    w.append(9.9, 8)
    w.append(3, -4, name='hi')
    w.write()

    root = read(w.file)
    assert 'date_created' in root.metadata
    assert 'date_finished' in root.metadata
    assert 'software_version' in root.metadata

    assert '/equipment' not in root
    assert '/log' in root
    assert '/dataset' in root
    assert '/hi' in root
    assert '/foo' in root
    assert '/foo/bar' in root
    assert '/foo/bar/baz' in root

    assert not root.dataset.metadata
    assert not root['/foo/bar/baz'].metadata
    assert root.hi.metadata.fruit == 'apple'
    assert root.hi.metadata.taste == 'sweat'
    assert root.hi.metadata.colour == 'red'

    assert root.dataset.dtype.base == [('timestamp', '<U19'), ('a', '<f8'), ('b', '<f8'), ('c', '<f8')]
    assert root.hi.dtype.base == [('timestamp', '<U19'), ('x', '<i4'), ('y', '<i4')]
    assert root.foo.bar.baz.dtype.base == [('timestamp', '<U26'), ('foo', '<f8'), ('bar', '<i4')]

    for item1, item2 in zip(root.dataset, [(1, 2, 3), (4, 5, 6), (7, 8, 9)]):
        datetime.fromisoformat(item1[0])  # converting to datetime object does not raise an error
        assert np.array_equal(tuple(item1)[1:], item2)
    for item1, item2 in zip(root.hi, [(-1, 2), (3, -4)]):
        datetime.fromisoformat(item1[0])  # converting to datetime object does not raise an error
        assert np.array_equal(tuple(item1)[1:], item2)
    for item1, item2 in zip(root.foo.bar.baz, [(9.9, 8)]):
        datetime.fromisoformat(item1[0])  # converting to datetime object does not raise an error
        assert np.array_equal(tuple(item1)[1:], item2)

    os.remove(w.file)


def test_not_initialized():
    file = gettempdir() + '/photons-writer-testing.json'
    if os.path.isfile(file):
        os.remove(file)

    w = io.PhotonWriter(file)
    with pytest.raises(ValueError, match=r'has not been initialized'):
        w.append(1)
    with pytest.raises(ValueError, match=r'has not been initialized'):
        w.update_metadata(one=1)
