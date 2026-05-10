from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget


class StartupSplash(QWidget):
    finished = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(380, 170)
        self._value = 0

        self.panel = QWidget(self)
        self.panel.setObjectName("splashPanel")
        self.panel.setGeometry(0, 0, self.width(), self.height())
        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        title = QLabel("LocalHost")
        title.setObjectName("splashTitle")
        status = QLabel("Loading workspace")
        status.setObjectName("splashStatus")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setObjectName("splashProgress")

        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(status)
        layout.addWidget(self.progress)
        layout.addStretch()

        self.setStyleSheet(
            """
            QWidget#splashPanel {
              background: #0e0e0e;
              border: 1px solid #2a2a2a;
              border-radius: 8px;
            }
            QLabel#splashTitle {
              color: #ededed;
              font-family: "Segoe UI";
              font-size: 20pt;
              font-weight: 650;
            }
            QLabel#splashStatus {
              color: #a1a1a1;
              font-family: "Segoe UI";
              font-size: 9pt;
            }
            QProgressBar#splashProgress {
              background: #171717;
              border: 1px solid #2a2a2a;
              border-radius: 5px;
              min-height: 8px;
              max-height: 8px;
            }
            QProgressBar#splashProgress::chunk {
              background: #ededed;
              border-radius: 4px;
            }
            """
        )

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._center()
        self.show()
        self.timer.start(24)

    def _center(self) -> None:
        screen = self.screen()
        if not screen:
            return
        geo = screen.availableGeometry()
        self.move(
            geo.x() + (geo.width() - self.width()) // 2,
            geo.y() + (geo.height() - self.height()) // 2,
        )

    def _tick(self) -> None:
        if self._value < 72:
            self._value += 4
        elif self._value < 94:
            self._value += 2
        else:
            self._value += 1

        self.progress.setValue(min(self._value, 100))
        if self._value >= 100:
            self.timer.stop()
            self._fade_out()

    def _fade_out(self) -> None:
        self.anim = QPropertyAnimation(self, b"windowOpacity", self)
        self.anim.setDuration(160)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.finished.connect(self.finished.emit)
        self.anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
