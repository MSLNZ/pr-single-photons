import os
from datetime import datetime
from tempfile import (
    gettempdir,
    NamedTemporaryFile,
)

import pytest
import numpy as np
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

    w = io.PhotonWriter(file)
    w.initialize('a', 'b', 'c')
    w.append(1, 2, 3)
    w.append(4, 5, 6)
    w.append(7, 8, 9)
    w.initialize('x', 'y', name='hi', fruit='apple', types=[int, int])
    w.append(-1, 2)
    w.append(3, -4)
    w.write()

    root = read(w.file)
    assert 'date_created' in root.metadata
    assert 'date_finished' in root.metadata
    assert 'software_version' in root.metadata

    assert '/equipment' not in root
    assert '/log' in root
    assert '/dataset' in root
    assert '/hi' in root

    assert not root.dataset.metadata
    assert root.hi.metadata.fruit == 'apple'

    assert root.dataset.dtype.base == [('timestamp', '<U26'), ('a', '<f8'), ('b', '<f8'), ('c', '<f8')]
    assert root.hi.dtype.base == [('timestamp', '<U26'), ('x', '<i4'), ('y', '<i4')]

    for item1, item2 in zip(root.dataset, [(1, 2, 3), (4, 5, 6), (7, 8, 9)]):
        datetime.fromisoformat(item1[0])  # converting to datetime object does not raise an error
        assert np.array_equal(tuple(item1)[1:], item2)
    for item1, item2 in zip(root.hi, [(-1, 2), (3, -4)]):
        datetime.fromisoformat(item1[0])  # converting to datetime object does not raise an error
        assert np.array_equal(tuple(item1)[1:], item2)

    os.remove(w.file)


def test_not_initialized():
    file = gettempdir() + '/photons-writer-testing.json'
    if os.path.isfile(file):
        os.remove(file)

    w = io.PhotonWriter(file)
    with pytest.raises(ValueError, match=r'Invalid dataset name'):
        w.append(1)
