from msl import qt

from .. import logger


class LineEdit(qt.QtWidgets.QLineEdit):

    def __init__(self, *,
                 text: str = None,
                 parent: qt.QtWidgets.QWidget = None):
        """A :class:`~QtWidgets.QLineEdit` that rescales the font size based on the size of widget.

        Parameters
        ----------
        text : :class:`str`, optional
            The initial text to display.
        parent : :class:`~QtWidgets.QWidget`, optional
            The parent widget.
        """
        super().__init__(parent=parent)
        self.setReadOnly(True)
        self.setAlignment(qt.Qt.AlignRight)
        self.setMinimumHeight(self.sizeHint().height())
        self.setSizePolicy(qt.QtWidgets.QSizePolicy.Ignored,
                           qt.QtWidgets.QSizePolicy.Ignored)

        if text:
            self.setText(text)

    def _resize_font_metrics(self) -> None:
        """Change the font size based on the size of the widget.

        This algorithm uses QFontMetrics to calculate the scaling factor.
        """
        text = self.text()
        if not text:
            return

        size = self.size()
        font = self.font()
        rect = qt.QtGui.QFontMetrics(font).boundingRect(text)
        factor_w = size.width() / max(1.0, rect.width())
        factor_h = size.height() / max(1.0, rect.height())
        factor = min(factor_w, factor_h)
        font.setPointSizeF(font.pointSizeF() * factor - 1.0)
        self.setFont(font)

    def _resize_font_newton(self) -> None:
        """Change the font size based on the size of the widget.

        This algorithm uses Newton's method to find the optimal font size.
        """
        text = self.text()
        if not text:
            return

        font = self.font()
        size = self.size()
        width, height = size.width(), size.height()

        fm = qt.QtGui.QFontMetrics

        def f(x):
            logger.info(f'x={x}')
            font.setPointSizeF(x)
            br = fm(font).boundingRect(text)
            return float(min(width - br.width(), height - br.height()))

        def fprime(x, dx):
            x = max(x, dx + 1.0)
            return (f(x + dx) - f(x - dx)) / dx

        current = font.pointSizeF()
        step = 1.0
        for i in range(100):
            previous = current
            df = fprime(current, step)
            if df == 0:
                step *= 2.0
                continue
            current -= f(current) / df
            current = max(2.0, current)
            delta = abs(previous - current) / current
            if delta < 0.01:  # within 1% of target
                break
        font.setPointSizeF(current - 1.0)  # under fill the widget
        self.setFont(font)
        logger.info(f'{current - 1.0}, {self.font().pointSizeF()}')

    def setText(self, text: str) -> None:
        """Override :meth:`~QWidget.QLineEdit.setText` to change the font size."""
        super().setText(text)
        self._resize_font_newton()

    def resizeEvent(self, event: qt.QtGui.QResizeEvent) -> None:
        """Override :meth:`~QWidget.resizeEvent` to change the font size."""
        super().resizeEvent(event)
        self._resize_font_newton()
