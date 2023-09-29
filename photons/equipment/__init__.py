"""
Custom classes for communicating with equipment.
"""
from .arroyo_6305 import ComboSource
from .coherent_fieldmaster import FieldMasterGS
from .dmm import DMM
from .dmm_34401a import HP34401A
from .dmm_344xxA import Keysight344XXA
from .dmm_3458A import Keysight3458A
from .dmm_6500 import Keithley6500
from .highfinesse import HighFinesse
from .hrs_monochromator import HRSMonochromator
from .idq_time_controller import IDQTimeController
from .keithley_6430 import Keithley6430
from .laser_superk import SuperK
from .nidaq import NIDAQ
from .oscilloscope_rigol import RigolOscilloscope
from .shot702_controller import OptoSigmaSHOT702
from .shutter import Shutter
from .shutter_ksc101 import KSC101Shutter
from .shutter_s25120a import S25120AShutter
from .sia_cmi import SIA3CMI
from .thorlabs_flipper import ThorlabsFlipper
from .thorlabs_stage import ThorlabsStage
from .widgets import *
