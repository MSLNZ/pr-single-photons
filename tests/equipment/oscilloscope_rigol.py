"""
Test that photons/equipment/oscilloscope_rigol.py is working properly.
"""
import connect

app, scope = connect.device('scope-rigol', 'Is it safe to control the oscilloscope?')

scope.clear()
scope.configure_channel(1)
scope.configure_timebase()
scope.configure_trigger()
scope.run()
scope.single()
scope.trigger()
scope.stop()

data = scope.waveform(1, 'chan2', 'channel3', 4)
app.plot(data)

app.disconnect_equipment()
