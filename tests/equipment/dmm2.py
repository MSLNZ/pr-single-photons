"""
Test that the timing between two DMMs is working properly.
"""
from time import perf_counter

import connect

app, (dmm1, dmm2) = connect.device(
    ('dmm-mon', 'dmm-sia'),
    'Is it safe to communicate with these DMMs?'
)

dmm1.configure()
dmm2.configure()

for i in range(3):
    t0 = perf_counter()
    dmm1.initiate()
    dmm2.initiate()
    assert perf_counter() - t0 < 0.05  # both DMMs must be triggered at nearly the same time
    av1, std1 = dmm1.fetch()
    av2, std2 = dmm2.fetch()
    app.logger.info(f'dmm1: {av1} {std1}')
    app.logger.info(f'dmm2: {av2} {std2}')

app.disconnect_equipment()
