import os
from datetime import datetime

import numpy as np
from msl.io import (
    git_head,
    is_file_readable,
    JSONWriter,
)
from msl.equipment import EquipmentRecord

from . import (
    __version__,
    logger,
)


class PhotonWriter(JSONWriter):

    def __init__(self, file, *, app=None, dataset_logging_size=1000):
        """A custom writer.

        Parameters
        ----------
        file : :class:`str`
            The name of a file to create.
        app : :class:`~photons.app.App`, optional
            The application instance.
        dataset_logging_size : :class:`int`, optional
            The initial size of the :class:`~msl.io.dataset.Dataset` that
            handles :mod:`logging` records.
        """
        super(PhotonWriter, self).__init__(file=file)

        if os.path.isfile(file) or is_file_readable(file):
            raise FileExistsError(f'Will not overwrite {file!r}')

        self._name = ''
        self._arrays = {}
        self._indices = {}
        self._meta = {}

        self.add_metadata(date_created=PhotonWriter.now_iso(ignore_microsecond=True))
        head = git_head(os.path.dirname(__file__))
        if head:
            self.add_metadata(git=head['hash'])
        self.add_metadata(software_version=__version__)

        if app is not None:
            lab_monitoring = app.lab_monitoring(strict=False)
            if lab_monitoring:
                key, values = next(iter(lab_monitoring.items()))
                self.add_metadata(
                    lab_temperature=values['temperature'],
                    lab_humidity=values['humidity'],
                    lab_iserver_serial=key,
                )

        self.create_dataset_logging('log', size=dataset_logging_size)

    def add_equipment(self, *records):
        """Add the :class:`msl.equipment.record_types.EquipmentRecord`\\s to a :class:`~msl.io.group.Group`."""
        group = self.require_group('equipment')
        for r in records:
            if isinstance(r, EquipmentRecord):
                group.add_metadata(**{r.alias: r.to_json()})
            else:  # assume that its a :class:`photons.equipment.BaseEquipment` object
                group.add_metadata(**{r.alias: r.record_to_json()})

    def initialize(self, *header, name='dataset', types=None, size=0, **metadata):
        """Initialize a dataset.

        Parameters
        ----------
        header : :class:`str`
            The names of the header field. The first field is
            ``timestamp`` and it is automatically created.
        name : :class:`str`
            The name of the dataset.
        types : :class:`list`, optional
            The data type of each field. If not specified then uses :class:`float`.
        size : :class:`int`, optional
            The initial size of the dataset. The dataset will automatically
            increase in size when it needs to.
        **metadata
            The metadata to associate with this dataset.
        """
        if types is None:
            types = [float] * len(header)

        if len(header) != len(types):
            raise ValueError(f'len(names) != len(types) -- {len(header)} != {len(types)}')

        if name in self._indices:
            raise ValueError(f'A {name!r} dataset already exists')

        self._name = name
        self._indices[name] = 0
        self._meta[name] = metadata
        self._arrays[name] = np.empty((size,), dtype=np.dtype(
            [('timestamp', '<U26')] + [(h, t) for h, t in zip(header, types)]
        ))

    def append(self, *data, name=None):
        """Append data to a dataset.

        Parameters
        ----------
        data
            The data to append. The timestamp when this method is called is
            automatically added to the dataset.
        name : :class:`str`, optional
            The name of the dataset to append the data to. If not specified
            then appends to the latest dataset that was initialized.
        """
        key = name or self._name
        if key not in self._arrays:
            raise ValueError(f'Invalid dataset name {key!r}')

        current_size = self._arrays[key].size
        if self._indices[key] >= current_size:
            # Over-allocate proportional to the size of the ndarray, making room
            # for additional growth. This follows the over-allocating procedure that
            # Python uses when appending to a list object, see `list_resize` in
            # https://github.com/python/cpython/blob/main/Objects/listobject.c
            append_size = current_size + 1
            new_size = (append_size + (append_size >> 3) + 6) & ~3
            if append_size - current_size > new_size - append_size:
                new_size = (append_size + 3) & ~3
            self._arrays[key].resize(new_size, refcheck=False)

        row = (self.now_iso(),) + data
        self._arrays[key][self._indices[key]] = row
        self._indices[key] += 1
        logger.debug(f'appended data {row}')

    def write(self, file=None, root=None, **kwargs):
        """Overrides the :meth:`~msl.io.writers.json_.JSONWriter.write` method."""
        self.log.remove_empty_rows()
        for name, array in self._arrays.items():
            self.create_dataset(name, data=array[:self._indices[name]], **self._meta[name])
        self.add_metadata(date_finished=PhotonWriter.now_iso(ignore_microsecond=True))
        super(PhotonWriter, self).write(file=file, root=root, **kwargs)
        logger.debug(f'data written to {file or self.file!s}')

    @staticmethod
    def now_iso(ignore_microsecond=False):
        """Get the current time in ISO-8601 format.

        Parameters
        ----------
        ignore_microsecond : :class:`bool`, optional
            Whether to ignore the microsecond part.

        Returns
        -------
        :class:`str`
            The current time.
        """
        now = datetime.now()
        if ignore_microsecond:
            now = now.replace(microsecond=0)
        return now.isoformat(sep='T')
