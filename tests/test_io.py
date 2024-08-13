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
        os.chmod(file, 0o777)
        os.remove(file)

    w = io.PhotonWriter(file, log_size=10)
    w.initialize('a', 'b', 'c')
    w.append(1, 2, 3)
    assert np.array_equal(w.data()['a'], [1])
    assert np.array_equal(w.data()['b'], [2])
    assert np.array_equal(w.data(name='dataset')['c'], [3])
    w.append(4, 5, 6)
    w.append(7, 8, 9)
    assert np.array_equal(w.data()['a'], [1, 4, 7])
    assert np.array_equal(w.data(name='dataset')['b'], [2, 5, 8])
    assert np.array_equal(w.data()['c'], [3, 6, 9])
    assert len(w.meta()) == 0
    w.initialize('x', 'y', name='hi', fruit='apple', types=[int, int])
    w.append(-1, 2)
    assert np.array_equal(w.data(name='dataset')['a'], [1, 4, 7])
    assert np.array_equal(w.data()['x'], [-1])
    assert np.array_equal(w.data(name='hi')['y'], [2])
    assert w.meta(name='dataset') == {}
    assert w.meta() == {'fruit': 'apple'}
    assert w.meta(name='hi') == {'fruit': 'apple'}
    w.initialize('foo', 'bar', name='/foo/bar/baz', microseconds=True, types=[float, int])
    w.update_metadata(name='hi', taste='sweat', colour='red')
    w.append(9.9, 8)
    assert np.array_equal(w.data()['foo'], [9.9])
    assert np.array_equal(w.data(name='/foo/bar/baz')['bar'], [8])
    assert w.meta() == {}
    assert w.meta(name='hi') == {'fruit': 'apple', 'taste': 'sweat', 'colour': 'red'}
    w.append(3, -4, name='hi')
    assert np.array_equal(w.data(name='dataset')['b'], [2, 5, 8])
    assert np.array_equal(w.data(name='hi')['y'], [2, -4])
    assert np.array_equal(w.data(name='/foo/bar/baz')['foo'], [9.9])
    assert np.array_equal(w.data()['bar'], [8])
    assert w.meta(name='/foo/bar/baz') == {}
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
    assert root.hi.dtype.base == [('timestamp', '<U19'), ('x', '<i8'), ('y', '<i8')]
    assert root.foo.bar.baz.dtype.base == [('timestamp', '<U26'), ('foo', '<f8'), ('bar', '<i8')]

    for item1, item2 in zip(root.dataset, [(1, 2, 3), (4, 5, 6), (7, 8, 9)]):
        datetime.fromisoformat(item1[0])  # converting to datetime object does not raise an error
        assert np.array_equal(tuple(item1)[1:], item2)
    for item1, item2 in zip(root.hi, [(-1, 2), (3, -4)]):
        datetime.fromisoformat(item1[0])  # converting to datetime object does not raise an error
        assert np.array_equal(tuple(item1)[1:], item2)
    for item1, item2 in zip(root.foo.bar.baz, [(9.9, 8)]):
        datetime.fromisoformat(item1[0])  # converting to datetime object does not raise an error
        assert np.array_equal(tuple(item1)[1:], item2)

    os.chmod(w.file, 0o777)
    os.remove(w.file)


def test_not_initialized():
    file = gettempdir() + '/photons-writer-testing.json'
    if os.path.isfile(file):
        os.chmod(file, 0o777)
        os.remove(file)

    w = io.PhotonWriter(file)
    with pytest.raises(ValueError, match=r'has not been initialized'):
        w.append(1)
    with pytest.raises(ValueError, match=r'has not been initialized'):
        w.update_metadata(one=1)
    with pytest.raises(ValueError, match=r'has not been initialized'):
        w.data()
    with pytest.raises(ValueError, match=r'has not been initialized'):
        w.meta()


def test_remove_write_permission():
    file = gettempdir() + '/photons-writer-testing.json'

    if os.path.isfile(file):
        # ensure it is not in read-only mode (from a previously-failed test)
        os.chmod(file, 0o777)
        os.remove(file)

    # create file
    w = io.PhotonWriter(file)
    w.initialize('a', 'b', 'c')
    w.append(0.761, -54.752, 3.628e8)
    w.write()

    # cannot open the file to modify it
    for m in ['wb', 'ab', 'wt', 'at', 'w+', 'w+b']:
        with pytest.raises(PermissionError):
            open(file, mode=m)

    # cannot delete the file
    with pytest.raises(PermissionError):
        os.remove(file)

    # can still read it
    root = read(file)
    assert root.dataset['b'] == [-54.752]

    # make it deletable
    os.chmod(file, 0o777)

    # clean up
    os.remove(file)
