"""
Test that photons/equipment/shutter.py is working properly.
"""
from time import sleep

from msl.qt import prompt

from photons import App

app = App(r'D:\config.xml')
shutter = app.connect_equipment('shutter')

if prompt.yes_no(f'Is it safe to open/close?\n\n{shutter}'):
    shutter.open()
    assert shutter.is_open()

    sleep(1)

    shutter.close()
    assert not shutter.is_open()

    sleep(1)

    shutter.close()
    assert not shutter.is_open()

app.disconnect_equipment()
