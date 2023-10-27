"""
Non-linear fit models.
"""
import numpy as np
from msl.nlf import InputParameters
from msl.nlf import Model


class SuperGaussian(Model):

    def __init__(self, dll: str | None = None) -> None:
        super().__init__('a1*exp(-1*(0.5*((x-a2)/a3)^2)^a4)', dll=dll)

    def guess(self, x: np.array, y: np.array, *, sigma: float = 0.1, n: int = 5) -> InputParameters:
        return InputParameters((
            ('a1', np.max(y), False, 'amplitude'),
            ('a2', np.mean(x), False, 'mu'),
            ('a3', sigma, False, 'sigma'),
            ('a4', n, False, 'n')))
