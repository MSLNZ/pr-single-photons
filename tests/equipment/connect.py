"""
Helper module to test equipment.
"""
import sys

from msl.qt import prompt

from photons import App


def device(alias, message):
    """Connect to a device.

    Parameters
    ----------
    alias : :class:`str`
        The alias of the device to connect to.
    message : :class:`str`
        A message to display in a prompt asking whether it is safe to proceed.

    Returns
    -------
    :class:`tuple`
        The application instance and the connection class to the device.
    """
    app = App(r'D:\config.xml')

    try:
        dev = app.connect_equipment(alias)
    except Exception as e:
        prompt.critical(str(e))
        sys.exit()

    if not prompt.yes_no(f'{message}\n\n{dev.record!r}'):
        app.disconnect_equipment()
        sys.exit()

    return app, dev
