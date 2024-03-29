"""
Test that photons/equipment/thorlabs_stage.py is working properly.
"""
from time import sleep

import connect

app, stage = connect.device('stage-y', 'Is it safe to move?')

info = stage.info()
assert info == {'unit': ' mm', 'minimum': 0.0, 'maximum': 13.0}, str(info)

stage.home(wait=False)
while stage.is_moving():
    app.logger.info(f'homing, at position {stage.get_position()}')
    sleep(0.05)
assert stage.get_position() == 0.0

sleep(1)

stage.home()
assert stage.get_position() == 0.0

sleep(1)

stage.set_position(5)
assert stage.get_position() == 5

sleep(1)

stage.set_position(5.01)
assert stage.get_position() == 5.01

sleep(1)

stage.set_position(5.01)
assert stage.get_position() == 5.01

sleep(1)

stage.set_position(2.0, wait=False)
while stage.is_moving():
    app.logger.info(f'moving stage to position 2.0, at position {stage.get_position()}')
    sleep(0.05)
assert stage.get_position() == 2.0

sleep(1)

stage.set_position(2.0, wait=False)
while stage.is_moving():
    app.logger.info(f'moving stage to position 2.0, at position {stage.get_position()}')
    sleep(0.05)
assert stage.get_position() == 2.0

sleep(1)

stage.set_position(1.99, wait=False)
while stage.is_moving():
    app.logger.info(f'moving stage to position 1.99, at position {stage.get_position()}')
    sleep(0.05)
assert stage.get_position() == 1.99

app.disconnect_equipment()
