"""
Test that photons/equipment/coherent_fieldmaster.py is working properly.
"""
import connect

app, m = connect.device('power-meter', 'Is it safe to control the power meter?')

m.set_wavelength(532)
m.set_attenuation(10)
m.set_offset(False)

assert m.detector() == 'LM-2 SILICON HD'
assert m.get_offset() == 0.0
assert m.get_attenuation() == 10.0
assert m.get_wavelength() == 532.0

assert m.power().size == 1
assert m.power(nsamples=10).size == 10
app.logger.info(m.power(nsamples=25))

m.set_offset(True)
assert m.get_offset() > 0.0

m.set_attenuation(1)
m.set_wavelength(633)
m.set_offset(False)

app.disconnect_equipment()
