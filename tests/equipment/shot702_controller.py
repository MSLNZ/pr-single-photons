"""
Test that photons/equipment/shot702_controller.py is working properly.
"""
from time import sleep

import connect

app, dev = connect.device('wheel-cv', 'Is it safe to control the ND filter wheel?')

assert dev.is_moving() is False

dev.home(wait=False)
while True:
    position, is_moving = dev.status()
    if not is_moving:
        break
    degrees = dev.position_to_degrees(position)
    app.logger.info(f'at {degrees} degrees [Encoder: {position}]')
    sleep(0.1)

dev.set_angle(5.12)
assert dev.get_angle() == 5.12


two_pi = dev.NUM_PULSES_PER_360_DEGREES
assert dev.position_to_degrees(0, bound=True) == 0.
assert dev.position_to_degrees(-0, bound=True) == 0.
assert dev.position_to_degrees(two_pi / 16., bound=True) == 22.5
assert dev.position_to_degrees(-two_pi / 16., bound=True) == 337.5
assert dev.position_to_degrees(two_pi / 8., bound=True) == 45.
assert dev.position_to_degrees(-two_pi / 8., bound=True) == 315.
assert dev.position_to_degrees(two_pi / 6., bound=True) == 60.
assert dev.position_to_degrees(-two_pi / 6., bound=True) == 300.
assert dev.position_to_degrees(two_pi / 4., bound=True) == 90.
assert dev.position_to_degrees(-two_pi / 4., bound=True) == 270.
assert dev.position_to_degrees(two_pi / 2., bound=True) == 180.
assert dev.position_to_degrees(-two_pi / 2., bound=True) == 180.
assert dev.position_to_degrees(two_pi, bound=True) == 0.
assert dev.position_to_degrees(-two_pi, bound=True) == 0.
assert dev.position_to_degrees(3 * two_pi / 2., bound=True) == 180.
assert dev.position_to_degrees(-3 * two_pi / 2., bound=True) == 180.
assert dev.position_to_degrees(3 * two_pi / 2.) == 540.
assert dev.position_to_degrees(-3 * two_pi / 2.) == -540.
assert dev.position_to_degrees(10 * two_pi, bound=True) == 0.
assert dev.position_to_degrees(two_pi - 1, bound=True) == 359.9975
assert dev.position_to_degrees(-two_pi + 1, bound=True) == 0.0025
assert dev.position_to_degrees(two_pi + 1, bound=False) == 360.0025

app.disconnect_equipment()
