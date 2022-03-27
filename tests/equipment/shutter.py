"""
Test that photons/equipment/shutter.py is working properly.
"""
from time import sleep

import connect

app, shutter = connect.device('shutter', 'Is it safe to open/close?')

shutter.open()
assert shutter.is_open()

sleep(1)

shutter.close()
assert not shutter.is_open()

sleep(1)

shutter.close()
assert not shutter.is_open()

app.disconnect_equipment()
