"""Transport controls bar (play/pause/stop + seek + volume + info)."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget,
)

from core.player import AudioPlayer
from ui.widgets.waveform_view import WaveformView


def _fmt_time(seconds: float) -> str:
    s = int(seconds)
    m, s = divmod(s, 60)
    return f"{m:02d}:{s:02d}"


class PlayerBar(QWidget):
    """Bottom transport bar: waveform + controls + metadata snippet."""

    load_file = Signal(str)

    def __init__(self, player: AudioPlayer, parent=None):
        super().__init__(parent)
        self.player = player
        self._duration = 0.0
        self._build_ui()
        self._connect()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 4)
        root.setSpacing(4)

        # Waveform
        self.waveform = WaveformView(self)
        root.addWidget(self.waveform)

        # Controls row
        ctrl = QHBoxLayout()
        ctrl.setSpacing(8)

        self.btn_stop = QPushButton("■")
        self.btn_stop.setObjectName("icon_btn")
        self.btn_stop.setFixedSize(32, 32)
        self.btn_stop.setToolTip("Stop")

        self.btn_play = QPushButton("▶")
        self.btn_play.setObjectName("icon_btn")
        self.btn_play.setFixedSize(36, 36)
        self.btn_play.setToolTip("Play / Pause")

        self.lbl_pos = QLabel("00:00")
        self.lbl_pos.setStyleSheet("color:#888; font-family: \"Consolas\", \"Courier New\", monospace;")
        self.lbl_pos.setFixedWidth(40)

        self.lbl_dur = QLabel("00:00")
        self.lbl_dur.setStyleSheet("color:#555; font-family: \"Consolas\", \"Courier New\", monospace;")
        self.lbl_dur.setFixedWidth(40)

        self.lbl_name = QLabel("No sample loaded")
        self.lbl_name.setStyleSheet("color:#888; font-size:12px;")

        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.setFixedWidth(80)
        self.vol_slider.setToolTip("Volume")

        lbl_vol = QLabel("🔊")
        lbl_vol.setStyleSheet("color:#555; font-size:12px;")

        ctrl.addWidget(self.btn_stop)
        ctrl.addWidget(self.btn_play)
        ctrl.addWidget(self.lbl_pos)
        ctrl.addWidget(QLabel("/"))
        ctrl.addWidget(self.lbl_dur)
        ctrl.addSpacing(8)
        ctrl.addWidget(self.lbl_name, 1)
        ctrl.addWidget(lbl_vol)
        ctrl.addWidget(self.vol_slider)

        root.addLayout(ctrl)

    def _connect(self):
        self.btn_play.clicked.connect(self.player.toggle_play_pause)
        self.btn_stop.clicked.connect(self.player.stop)
        self.vol_slider.valueChanged.connect(lambda v: self.player.set_volume(v / 100))

        self.player.waveform_ready.connect(self.waveform.set_peaks)
        self.player.duration_changed.connect(self._on_duration)
        self.player.position_changed.connect(self._on_position)
        self.player.state_changed.connect(self._on_state)

        self.waveform.seek_requested.connect(
            lambda p: self.player.seek(p * self._duration)
        )

    def load_sample(self, file_path: str, display_name: str = ""):
        self.player.load(file_path)
        self.player.play()
        self.lbl_name.setText(display_name or file_path.split("/")[-1])

    def _on_duration(self, dur: float):
        self._duration = dur
        self.waveform.set_duration(dur)
        self.lbl_dur.setText(_fmt_time(dur))

    def _on_position(self, pos: float):
        self.waveform.set_position(pos)
        self.lbl_pos.setText(_fmt_time(pos))

    def _on_state(self, state: str):
        self.btn_play.setText("⏸" if state == "playing" else "▶")
