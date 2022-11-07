"""
Test that photons/equipment/highfinesse.py is working properly for a Laser Spectrum Analyser.
"""
import connect

app, w = connect.device('lsa', 'Is it safe to control the LSA?')

w.start_measurement()
w.set_auto_exposure_mode(True)
w.set_analysis_mode(False)
w.set_linewidth_mode(True)
w.set_pulse_mode(False)
w.set_wavelength_range(w.Range.nm410_610)
w.set_wide_mode(False)
w.wait(1)

print('version info', w.get_wlm_version())
print('wavelength range', w.get_wavelength_range())
print(f'wavelength[vac] = {w.wavelength(in_air=False):.3f} nm')
print(f'wavelength[air] = {w.wavelength(in_air=True):.3f} nm')
print(f'linewidth[vac] = {w.linewidth(in_air=False):.4f} nm')
print(f'linewidth[air] = {w.linewidth(in_air=True):.4f} nm')
print(f'exposure time = {w.get_exposure_time()} ms')
print('Analysis mode enabled?', w.get_analysis_mode())
print('Auto-exposure mode enabled?', w.get_auto_exposure_mode())
print('Linewidth mode enabled?', w.get_linewidth_mode())
print('Pulse mode enabled?', w.get_pulse_mode())
print('Wide mode enabled?', w.get_wide_mode())
print(f'temperature = {w.temperature():.3f} C')
app.plot(w.get_pattern_data())
app.plot(w.get_pattern_data(1))
w.stop_measurement()

app.disconnect_equipment()
