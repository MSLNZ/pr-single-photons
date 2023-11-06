"""
Non-linear fit models.
"""
import os

import numpy as np
from msl.nlf import InputParameters
from msl.nlf import Model
from msl.nlf.models import *  # noqa

USER_DIR = os.path.join(os.path.dirname(__file__), 'user')


class SuperGaussian(Model):

    def __init__(self, **kwargs) -> None:
        """A flat-top, 1-dimensional, Gaussian.

        :param kwargs: All keyword arguments are passed to :class:`Model`.
        """
        super().__init__('a1*exp(-1*(0.5*((x-a2)/a3)^2)^a4) + a5', **kwargs)

    def guess(self,
              x: np.array,
              y: np.array,
              *,
              sigma: float = 0.1,
              n: float = 5) -> InputParameters:
        """Generate an initial guess.

        :param x: The independent variable (stimulus) data
        :param y: The dependent variable (response) data.
        :param sigma: Standard deviation of the distribution.
        :param n: Shape factor (i.e., the exponent, 2*n).
        :return: Initial guess.
        """
        return InputParameters((
            ('a1', np.max(y), False, 'amplitude'),
            ('a2', np.mean(x), False, 'mu'),
            ('a3', sigma, False, 'sigma'),
            ('a4', n, False, 'n'),
            ('a5', 0, False, 'offset'),
        ))


class GaussianCDF(Model):

    def __init__(self, **kwargs) -> None:
        """Gaussian cumulative distribution function.

        :param kwargs: All keyword arguments are passed to :class:`Model`.
        """
        super().__init__('f1', user_dir=USER_DIR, **kwargs)

    def guess(self,
              x: np.array,
              y: np.array,
              *,
              sigma: float = 0.1,
              offset: int = 0) -> InputParameters:
        """Generate an initial guess.

        :param x: The independent variable (stimulus) data
        :param y: The dependent variable (response) data.
        :param sigma: Standard deviation of the distribution.
        :param offset: A dc offset (background).
        :return: Initial guess.
        """
        return InputParameters((
            ('a1', np.max(y), False, 'amplitude'),
            ('a2', np.mean(x), False, 'mu'),
            ('a3', sigma, False, 'sigma'),
            ('a4', offset, False, 'offset')))


class SPADDetectionEfficiency(Model):

    def __init__(self, **kwargs) -> None:
        """Detection efficiency of a single-photon avalanche diode.

        :param kwargs: All keyword arguments are passed to :class:`Model`.
        """
        super().__init__('(-a1*a2*x)/ln(1-a2*x)', **kwargs)

    def guess(self,
              x: np.array,
              y: np.array,
              *,
              de: float = 0.5,
              toff: float = 100e-9) -> InputParameters:
        """Generate an initial guess.

        :param x: The independent variable (stimulus) data
        :param y: The dependent variable (response) data.
        :param de: Ideal detection efficiency in the absence of artifacts (i.e., afterpulsing).
        :param toff: Detector off time (i.e., sum of the dead time plus the reset time).
        :return: Initial guess.
        """
        return InputParameters((
            ('a1', de, False, 'de'),
            ('a2', toff, False, 'toff')))
