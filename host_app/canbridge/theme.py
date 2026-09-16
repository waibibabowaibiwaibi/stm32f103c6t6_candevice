"""Shared application colors and live system appearance tracking."""

from __future__ import annotations

from string import Template

from PySide6.QtCore import QObject, QSettings, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


THEME_MODES = (("跟随系统", "system"), ("亮色", "light"), ("暗色", "dark"))

COLORS = {
    "dark": {
        "window": "#0f172a", "text": "#e2e8f0", "border": "#334155",
        "title": "#93c5fd", "input": "#1e293b", "input_border": "#475569",
        "focus": "#38bdf8", "button": "#1e40af", "button_border": "#3b82f6",
        "hover": "#2563eb", "pressed": "#1d4ed8", "button_text": "#ffffff",
        "disabled": "#334155", "muted": "#94a3b8", "danger": "#7f1d1d",
        "danger_border": "#ef4444", "base": "#111827", "alternate": "#172033",
        "grid": "#273449", "header_text": "#cbd5e1", "stat": "#67e8f9",
        "connected": "#4ade80", "disconnected": "#f87171",
        "rx": "#38bdf8", "tx": "#fbbf24",
    },
    "light": {
        "window": "#f1f5f9", "text": "#0f172a", "border": "#cbd5e1",
        "title": "#1e40af", "input": "#ffffff", "input_border": "#94a3b8",
        "focus": "#0284c7", "button": "#1d4ed8", "button_border": "#1d4ed8",
        "hover": "#2563eb", "pressed": "#1e40af", "button_text": "#ffffff",
        "disabled": "#e2e8f0", "muted": "#475569", "danger": "#b91c1c",
        "danger_border": "#991b1b", "base": "#ffffff", "alternate": "#f8fafc",
        "grid": "#e2e8f0", "header_text": "#334155", "stat": "#0e7490",
        "connected": "#15803d", "disconnected": "#b91c1c",
        "rx": "#0369a1", "tx": "#92400e",
    },
}

STYLE_TEMPLATE = Template("""
QMainWindow, QWidget { background: $window; color: $text; }
QLabel { background: transparent; }
QGroupBox {
    border: 1px solid $border; border-radius: 8px; margin-top: 12px;
    padding: 10px 8px 8px 8px; font-weight: 600;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; color: $title; }
QLineEdit, QComboBox, QSpinBox {
    background: $input; border: 1px solid $input_border; border-radius: 5px;
    padding: 6px; selection-background-color: $pressed; selection-color: $button_text;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: $focus; }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled { background: $disabled; color: $muted; }
QPushButton {
    background: $button; color: $button_text; border: 1px solid $button_border;
    border-radius: 5px; padding: 7px 14px; font-weight: 600;
}
QPushButton:hover { background: $hover; }
QPushButton:pressed { background: $pressed; }
QPushButton:disabled { background: $disabled; border-color: $input_border; color: $muted; }
QPushButton#dangerButton { background: $danger; border-color: $danger_border; }
QPushButton#quietButton { background: $input; border-color: $input_border; color: $text; }
QPushButton#quietButton:hover { background: $alternate; border-color: $focus; }
QPushButton#quietButton:disabled { background: $disabled; color: $muted; }
QTableView, QComboBox QAbstractItemView {
    background: $base; alternate-background-color: $alternate; border: 1px solid $border;
    border-radius: 6px; gridline-color: $grid;
    selection-background-color: $pressed; selection-color: $button_text;
}
QHeaderView::section {
    background: $input; color: $header_text; border: 0; border-right: 1px solid $border;
    border-bottom: 1px solid $border; padding: 7px; font-weight: 600;
}
QFrame#statCard { background: $base; border: 1px solid $border; border-radius: 7px; }
QLabel#statValue { color: $stat; font-size: 17px; font-weight: 700; }
QLabel#muted { color: $muted; }
QLabel#connected { color: $connected; font-weight: 700; }
QLabel#disconnected { color: $disconnected; font-weight: 700; }
QStatusBar { background: $base; color: $muted; }
QSplitter::handle { background: $border; height: 2px; }
QToolTip { background: $input; color: $text; border: 1px solid $border; padding: 4px; }
""")


def make_palette(theme: str) -> QPalette:
    colors = COLORS[theme]
    palette = QPalette()
    roles = {
        QPalette.Window: "window", QPalette.WindowText: "text",
        QPalette.Base: "base", QPalette.AlternateBase: "alternate",
        QPalette.Text: "text", QPalette.Button: "input", QPalette.ButtonText: "text",
        QPalette.ToolTipBase: "input", QPalette.ToolTipText: "text",
        QPalette.Highlight: "pressed", QPalette.HighlightedText: "button_text",
        QPalette.Link: "rx", QPalette.LinkVisited: "title",
        QPalette.PlaceholderText: "muted", QPalette.Light: "input_border",
        QPalette.Midlight: "border", QPalette.Mid: "border",
        QPalette.Dark: "input_border", QPalette.Shadow: "border",
        QPalette.Accent: "focus",
    }
    for role, key in roles.items():
        palette.setColor(role, QColor(colors[key]))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, QColor(colors["muted"]))
    for role in (QPalette.Base, QPalette.Button):
        palette.setColor(QPalette.Disabled, role, QColor(colors["disabled"]))
    return palette


class ThemeController(QObject):
    theme_changed = Signal(str)

    def __init__(self, app: QApplication, settings: QSettings) -> None:
        super().__init__(app)
        self.setObjectName("themeController")
        self._app = app
        self._settings = settings
        self._system_scheme = app.styleHints().colorScheme()
        saved_mode = settings.value("appearance/theme", "system", type=str)
        self.mode = saved_mode if saved_mode in ("system", "light", "dark") else "system"
        self.theme = ""
        # Keep Qt's system hint unmodified even in manual mode, so switching
        # back to system uses the latest appearance rather than a stale value.
        app.styleHints().colorSchemeChanged.connect(self._system_scheme_changed)
        self._apply_theme()

    def set_mode(self, mode: str) -> None:
        if mode not in ("system", "light", "dark"):
            raise ValueError(f"Unknown theme mode: {mode}")
        self.mode = mode
        self._settings.setValue("appearance/theme", mode)
        self._apply_theme()

    def _system_scheme_changed(self, scheme: Qt.ColorScheme) -> None:
        self._system_scheme = scheme
        if self.mode == "system":
            self._apply_theme()

    def _apply_theme(self) -> None:
        theme = self.mode
        if theme == "system":
            # Some desktops do not publish an appearance preference.
            theme = "dark" if self._system_scheme == Qt.ColorScheme.Dark else "light"
        if theme == self.theme:
            return
        self.theme = theme
        self._app.setPalette(make_palette(theme))
        self._app.setStyleSheet(STYLE_TEMPLATE.substitute(COLORS[theme]))
        self.theme_changed.emit(theme)
