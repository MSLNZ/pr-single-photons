"""
Test that photons/equipment/highfinesse.py is working properly for a Wavemeter.
"""
import connect

app, w = connect.device('wavemeter', 'Is it safe to control the wavemeter?')

w.start_measurement()
w.set_auto_exposure_mode(True)
w.set_pulse_mode(False)
w.set_wide_mode(False)
w.wait(1)
print('version info', w.get_wlm_version())
print(f'wavelength[vac] = {w.wavelength(in_air=False):.3f} nm')
print(f'wavelength[air] = {w.wavelength(in_air=True):.3f} nm')
print(f'exposure time = {w.get_exposure_time()} ms')
print('Auto-exposure mode enabled?', w.get_auto_exposure_mode())
print('Pulse mode enabled?', w.get_pulse_mode())
print('Wide mode enabled?', w.get_wide_mode())
print(f'temperature = {w.temperature():.3f} C')
app.plot(w.get_pattern_data())
w.stop_measurement()

app.disconnect_equipment()
