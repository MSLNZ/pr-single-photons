"""
Base class for an oscilloscope.
"""
import numpy as np
from msl.equipment import EquipmentRecord
from msl.equipment.connection_message_based import ConnectionMessageBased

from .base import BaseEquipment


class Oscilloscope(BaseEquipment):

    connection: ConnectionMessageBased

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """Base class for an oscilloscope.

        Args:
            record: The equipment record.
            **kwargs: Keyword arguments. Can be specified as attributes
                of an XML element in a configuration file (with the tag
                of the element equal to the alias of `record`).
        """
        super().__init__(record, **kwargs)

    def configure_channel(self, channel: int | str, **kwargs) -> None:
        """Configure a channel."""
        raise NotImplementedError

    def configure_timebase(self, **kwargs) -> None:
        """Configure the timebase."""
        raise NotImplementedError

    def configure_trigger(self, **kwargs) -> None:
        """Configure the trigger."""
        raise NotImplementedError

    def run(self) -> None:
        """Start acquiring waveform data."""
        raise NotImplementedError

    def single(self) -> None:
        """Capture and display a single acquisition."""
        raise NotImplementedError

    def software_trigger(self) -> None:
        """Send a trigger signal."""
        raise NotImplementedError

    def stop(self) -> None:
        """Stop acquiring waveform data."""
        raise NotImplementedError

    def waveform(self, *channels: int | str, **kwargs) -> np.ndarray:
        """Get the waveform data."""
        raise NotImplementedError
