"""
Custom file writer.
"""
import os
from datetime import datetime

import numpy as np
from msl.equipment import EquipmentRecord
from msl.io import JSONWriter
from msl.io import git_head
from msl.io import is_file_readable
from msl.io import remove_write_permissions

from .equipment.base import BaseEquipment
from .log import logger


class PhotonWriter(JSONWriter):

    def __init__(self,
                 file: str,
                 *,
                 log_size: int = None) -> None:
        """A custom file writer.

        Args:
            file: The path of the file to create.
            log_size: The initial size of :class:`~msl.io.dataset_logging.DatasetLogging`.
                If None or 0 then do not include log messages in the writer.
        """
        super().__init__(file=file)

        if os.path.isfile(file) or is_file_readable(file):
            raise FileExistsError(f'Will not overwrite {file!r}')

        self._log = self.create_dataset_logging('log', size=log_size) if log_size else None

        self._name: str = ''
        self._ignore_microsecond: dict[str, bool] = {}
        self._meta: dict[str, dict] = {}
        self._indices: dict[str, int] = {}
        self._arrays: dict[str, np.ndarray] = {}

        self.add_metadata(date_created=PhotonWriter.now_iso())
        head = git_head(os.path.dirname(__file__))
        if head:
            self.add_metadata(git=head['hash'])

        # import here to avoid circular imports
        from photons import __version__
        self.add_metadata(software_version=__version__)

    def add_equipment(self, *records: EquipmentRecord | BaseEquipment) -> None:
        """Add equipment records to an 'equipment' :class:`~msl.io.group.Group`.

        Automatically creates the 'equipment' Group if it does not already exist.
        """
        group = self.require_group('equipment')
        for r in records:
            if isinstance(r, EquipmentRecord):
                group.add_metadata(**{r.alias: r.to_json()})
            else:
                group.add_metadata(**{r.alias: r.record_to_json()})

    def append(self, *data, name: str = None) -> None:
        """Append data to a dataset.

        Args:
            data: The data to append. The timestamp when this method is called is
                automatically added to the dataset.
            name: The name of the dataset to append the data to. If not specified
                then appends to the latest dataset that was initialized.
        """
        key = name or self._name
        if key not in self._arrays:
            raise ValueError(f'A dataset with name {key!r} has not been initialized')

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

        row = (self.now_iso(self._ignore_microsecond[key]),) + data
        self._arrays[key][self._indices[key]] = row
        self._indices[key] += 1
        logger.debug(f'appended {row} to {key!r}')

    def data(self, name: str = None) -> np.ndarray:
        """Return the current data of a dataset.

        Args:
            name: The name of the dataset. If not specified then uses the name
                of the latest dataset that was initialized.
        """
        key = name or self._name
        if key not in self._arrays:
            raise ValueError(f'A dataset with name {key!r} has not been initialized')
        return self._arrays[key][:self._indices[key]]

    def initialize(self,
                   *header: str,
                   microseconds: bool = False,
                   name: str = 'dataset',
                   size: int = 100,
                   types: list[type] = None,
                   **metadata) -> None:
        """Initialize a dataset.

        Args:
            *header: The names of the header fields. The first field name
                is ``timestamp`` and it is automatically created.
            microseconds: Whether to include microseconds in the ``timestamp``.
            name: The name of the dataset to initialize. Can contain
                ``/`` to specify a subgroup (relative to the root Group).
            size: The initial size of the dataset. The dataset will
                automatically increase in size when it needs to.
            types: The data types of each header field. If not specified
                then uses `float` for each field.
            **metadata: The metadata to associate with the dataset.
        """
        if types is None:
            types = [float] * len(header)

        if len(header) != len(types):
            raise ValueError(
                f'len(header) [{len(header)}] != len(types) [{len(types)}]')

        if name in self._indices:
            raise ValueError(f'A {name!r} dataset already exists')

        type_timestamp = '<U26' if microseconds else '<U19'
        types_header = [(h, t) for h, t in zip(header, types)]
        self._name = name
        self._ignore_microsecond[name] = not microseconds
        self._indices[name] = 0
        self._meta[name] = metadata
        self._arrays[name] = np.empty((size,), dtype=np.dtype(
            [('timestamp', type_timestamp)] + types_header  # noqa: Mixing datatypes str and float
        ))
        logger.debug(f'initialized a {name!r} dataset')

    def meta(self, name: str = None) -> dict:
        """Return the current metadata of a dataset.

        Args:
            name: The name of the dataset. If not specified then uses the name
                of the latest dataset that was initialized.
        """
        key = name or self._name
        if key not in self._meta:
            raise ValueError(f'A dataset with name {key!r} has not been initialized')
        return self._meta[key]

    @staticmethod
    def now_iso(ignore_microsecond: bool = True) -> str:
        """Get the current time in ISO-8601 format.

        Args:
            ignore_microsecond: Whether to ignore the microsecond part.
        """
        now = datetime.now()
        if ignore_microsecond:
            now = now.replace(microsecond=0)
        return now.isoformat(sep='T')

    def update_metadata(self, name: str = None, **metadata) -> None:
        """Update the metadata for a dataset.

        Args:
            name: The name of the dataset to append the data to. If not specified
                then appends to the latest dataset that was initialized.
            **metadata: The metadata to associate with the dataset.
        """
        key = name or self._name
        if key not in self._meta:
            raise ValueError(f'A dataset with name {key!r} has not been initialized')
        self._meta[key].update(**metadata)

    def write(self, **kwargs) -> None:
        """Overrides the :meth:`~msl.io.writers.json_.JSONWriter.write` method."""
        if self._log is not None:
            self._log.remove_empty_rows()
        for name, array in self._arrays.items():
            self.create_dataset(name, data=array[:self._indices[name]], **self._meta[name])
        self.add_metadata(date_finished=self.now_iso())
        super().write(**kwargs)
        file = kwargs.get('file') or self.file
        remove_write_permissions(file)
        logger.debug(f'data written to {file}')
