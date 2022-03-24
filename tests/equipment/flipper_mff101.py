"""
Test that photons/equipment/flipper_mff101.py is working properly.
"""
from time import sleep

from msl.qt import prompt

from photons import App

app = App(r'D:\config.xml')
flipper = app.connect_equipment('flipper-1')

info = flipper.info()
assert 1 in info, str(info)
assert 2 in info, str(info)

if prompt.yes_no(f'Is it safe to move?\n\n{flipper}\n{info}'):
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
