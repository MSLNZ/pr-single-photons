"""
Test that photons/equipment/flipper_mff101.py is working properly.
"""
from time import sleep

import connect

app, flipper = connect.device('flipper-1', 'Is it safe to move?')

info = flipper.info()
assert 1 in info, str(info)
assert 2 in info, str(info)

flipper.set_position(2)
assert flipper.get_position() == 2

sleep(1)

flipper.set_position(2)
assert flipper.get_position() == 2

sleep(1)

flipper.set_position(1)
assert flipper.get_position() == 1

sleep(1)

flipper.set_position(2)
assert flipper.get_position() == 2

sleep(1)

flipper.set_position(1)
assert flipper.get_position() == 1

sleep(1)

flipper.set_position(2, wait=False)
while flipper.is_moving():
    app.logger.info(f'moving to position 2, at position {flipper.get_position()}')
    sleep(0.05)
assert flipper.get_position() == 2

sleep(1)

flipper.set_position(1, wait=False)
while flipper.is_moving():
    app.logger.info(f'moving to position 1, at position {flipper.get_position()}')
    sleep(0.05)
assert flipper.get_position() == 1

sleep(1)

flipper.set_position(1, wait=False)
while flipper.is_moving():
    app.logger.info(f'moving to position 1, at position {flipper.get_position()}')
    sleep(0.05)
assert flipper.get_position() == 1

app.disconnect_equipment()
