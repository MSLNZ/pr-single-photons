"""
Coherent FieldMaster GS power meter.
"""
from msl.equipment import EquipmentRecord
from msl.equipment.connection_message_based import ConnectionMessageBased

from .base import BaseEquipment
from .base import equipment
from ..samples import Samples

ERRORS: dict[str, str] = {
    '7': 'Not a valid command or query',
    '9': 'Parameter value is invalid',
    '10': 'Parameter out of range',
    '11': 'No detector connected',
    '12': 'Request not valid for current detector',
    '13': 'Requested data not available'
}


@equipment(manufacturer='Coherent', model=r'Field\s*[mM]aster\s*GS')
class FieldMasterGS(BaseEquipment):

    connection: ConnectionMessageBased

    def __init__(self, record: EquipmentRecord, **kwargs) -> None:
        """Coherent FieldMaster GS power meter.

        Args:
            record: The equipment record.
            **kwargs: Keyword arguments. Can be specified as attributes
                of an XML element in a configuration file (with the tag
                of the element equal to the alias of `record`).
        """
        super().__init__(record, **kwargs)

    def detector(self) -> str:
        """Returns the detector type."""
        return self.connection.query('dt?').rstrip().strip('"')

    def get_attenuation(self) -> float:
        """Returns the attenuation factor."""
        return float(self.connection.query('at?'))

    def get_offset(self) -> float:
        """Returns the offset."""
        return float(self.connection.query('of?'))

    def get_wavelength(self) -> float:
        """Returns the wavelength (in nm)."""
        return float(self.connection.query('wv?')) * 1e9

    def power(self, nsamples: int = 1) -> Samples:
        """Returns the power readings (in Watts).

        Args:
            nsamples: The number of samples to acquire.
        """
        samples = [self.connection.query('pw?') for _ in range(nsamples)]
        return Samples(samples)

    def restart(self) -> None:
        """Restart the system."""
        self.logger.info(f'restart {self.alias!r}')
        self.connection.write('*rst')

    def set_attenuation(self, attenuation: float) -> None:
        """Sets the attenuation factor."""
        self.logger.info(f'set {self.alias!r} attenuation to {attenuation}')
        self.connection.write(f'at {attenuation}')

    def set_offset(self, enabled: bool) -> None:
        """Whether to use the current reading as the offset or to turn the offset off."""
        state = 'on' if enabled else 'off'
        self.logger.info(f'set {self.alias!r} offset {state!r}')
        self.connection.write(f'of {state}')

    def set_wavelength(self, nm: float) -> None:
        """Sets the wavelength (in nm)."""
        self.logger.info(f'set {self.alias!r} wavelength to {nm} nm')
        self.connection.write(f'wv {nm*1e-9}')
