"""
Test that photons/equipment/laser_superk.py is working properly.
"""
import connect

app, superk = connect.device('superk', 'Is it safe to control the laser?')

superk.emission(False)

assert not superk.is_emission_on()

assert superk.ensure_interlock_ok()

superk.set_operating_mode(superk.OperatingModes.CONSTANT_CURRENT)
assert superk.get_operating_mode() == superk.OperatingModes.CONSTANT_CURRENT
assert superk.is_constant_current_mode()
assert not superk.is_constant_power_mode()
assert not superk.is_modulated_current_mode()
assert not superk.is_modulated_power_mode()
assert not superk.is_power_lock_mode()

superk.enable_constant_current_mode()
assert superk.get_operating_mode() == superk.OperatingModes.CONSTANT_CURRENT
assert superk.is_constant_current_mode()
assert not superk.is_constant_power_mode()
assert not superk.is_modulated_current_mode()
assert not superk.is_modulated_power_mode()
assert not superk.is_power_lock_mode()

if superk.MODULE_TYPE != superk.MODULE_TYPE_0x88:  # reason: modulated-current mode not supported
    superk.set_operating_mode(superk.OperatingModes.MODULATED_CURRENT)
    assert superk.get_operating_mode() == superk.OperatingModes.MODULATED_CURRENT
    assert not superk.is_constant_current_mode()
    assert not superk.is_constant_power_mode()
    assert superk.is_modulated_current_mode()
    assert not superk.is_modulated_power_mode()
    assert not superk.is_power_lock_mode()

    superk.enable_modulated_current_mode()
    assert superk.get_operating_mode() == superk.OperatingModes.MODULATED_CURRENT
    assert not superk.is_constant_current_mode()
    assert not superk.is_constant_power_mode()
    assert superk.is_modulated_current_mode()
    assert not superk.is_modulated_power_mode()
    assert not superk.is_power_lock_mode()

superk.set_operating_mode(superk.OperatingModes.POWER_LOCK)
assert superk.get_operating_mode() == superk.OperatingModes.POWER_LOCK
assert not superk.is_constant_current_mode()
assert not superk.is_constant_power_mode()
assert not superk.is_modulated_current_mode()
assert not superk.is_modulated_power_mode()
assert superk.is_power_lock_mode()

superk.enable_power_lock_mode()
assert superk.get_operating_mode() == superk.OperatingModes.POWER_LOCK
assert not superk.is_constant_current_mode()
assert not superk.is_constant_power_mode()
assert not superk.is_modulated_current_mode()
assert not superk.is_modulated_power_mode()
assert superk.is_power_lock_mode()

assert 15 < superk.get_temperature() < 25

superk.enable_power_lock_mode()
assert superk.set_feedback_level(90) == 90
assert superk.get_feedback_level() == 90

superk.enable_constant_current_mode()
assert superk.set_current_level(10) == 10
assert superk.get_current_level() == 10

if superk.MODULE_TYPE == superk.MODULE_TYPE_0x60:
    assert superk.lock_front_panel(True) is True
    assert superk.lock_front_panel(False) is True
else:
    # front-panel (un)locking not supported (but does not raise an error)
    assert superk.lock_front_panel(True) is False
    assert superk.lock_front_panel(False) is False

assert superk.set_user_text('Hello') == 'Hello'
assert superk.get_user_text() == 'Hello'

if superk.MODULE_TYPE == superk.MODULE_TYPE_0x60:
    # 20 character limit
    assert superk.set_user_text('012345678901234567890123') == '01234567890123456789'
else:
    # 240 character limit
    assert superk.set_user_text('a'*256) == 'a'*240

expect = '' if superk.MODULE_TYPE == superk.MODULE_TYPE_0x60 else ' '
assert superk.set_user_text('') == expect

app.disconnect_equipment()
