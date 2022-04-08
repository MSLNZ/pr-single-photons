"""
Test that photons/equipment/sia_cmi.py is working properly.
"""
import connect

app, sia = connect.device('sia-cmi', 'Is it safe to change the integration time?')

assert sia.get_integration_time() == sia.Integration.TIME_1m

sia.set_integration_time(sia.Integration.TIME_100u)
assert sia.get_integration_time() == sia.Integration.TIME_100u

sia.set_integration_time('10m')
assert sia.get_integration_time() == sia.Integration.TIME_10m

sia.set_integration_time(7)
assert sia.get_integration_time() == sia.Integration.TIME_1m

app.disconnect_equipment()
