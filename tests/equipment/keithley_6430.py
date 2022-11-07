"""
Test that photons/equipment/keithley_6430.py is working properly.
"""
from photons import App

app = App(r'D:\config.xml')
femtoamp = app.connect_equipment('femtoamp')

femtoamp.reset()
femtoamp.clear()
assert not femtoamp.is_output_enabled()
femtoamp.configure_output(range=1e-12, cmpl_range=1, cmpl=0.1)
femtoamp.enable_output(True)
assert femtoamp.is_output_enabled()
for i in range(5):
    level = i*50e-15
    femtoamp.set_output_level(level, wait=True)
    output = femtoamp.get_output_level()
    app.logger.info(f'set={level} actual={output}')
femtoamp.enable_output(False)
assert not femtoamp.is_output_enabled()

app.disconnect_equipment()
