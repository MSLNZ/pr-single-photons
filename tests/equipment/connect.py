"""
Helper module to test equipment.
"""
import sys

from photons import App
from photons.app import ConnectionClass


def device(aliases: str | tuple[str, ...], message: str) -> tuple[App, ConnectionClass]:
    """Connect to a device.

    Args:
        aliases: The alias(es) of the device to connect to.
        message: A message to display in a prompt asking whether it is safe to proceed.

    Returns:
        The application instance and the connection class to the device.
    """
    if isinstance(aliases, str):
        aliases = (aliases,)

    app = App()
    try:
        devs = app.connect_equipment(*aliases)
    except Exception as e:
        print(e)
        app.prompt.critical(e)
        sys.exit()

    if len(aliases) == 1:
        info = f'{devs.record}'
    else:
        info = '\n'.join(str(dev.record) for dev in devs)

    if not app.prompt.yes_no(f'{message}\n\n{info}'):
        app.disconnect_equipment()
        sys.exit()

    return app, devs
