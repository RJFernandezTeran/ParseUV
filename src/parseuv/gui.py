"""
PyQt6 Drag-and-Drop GUI application for parseUV spectrometer binary file reader.
"""

import os
import sys
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QDragEnterEvent, QDropEvent, QFont, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .__about__ import __author__, __email__, __version__
from .parser import CaryFile, parse_uv
from .spectrum import Spectrum
from .style import apply_style


class DropZoneWidget(QFrame):
    """
    Drag-and-Drop zone widget accepting Varian/Agilent Cary (.BSW, .DSW) and Shimadzu (.SPC) files.
    """

    file_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        self.setLineWidth(2)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(30, 30, 30, 30)

        self.label_icon = QLabel("📁", self)
        font_icon = QFont("Segoe UI", 36)
        self.label_icon.setFont(font_icon)
        self.label_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.label_text = QLabel(
            "Drag & Drop a Varian/Agilent Cary (*.DSW, *.BSW)\nor Shimadzu UV-Vis-NIR (*.SPC) File Here",
            self,
        )
        font_text = QFont("Segoe UI", 11, QFont.Weight.Bold)
        self.label_text.setFont(font_text)
        self.label_text.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_browse = QPushButton("Browse File...", self)
        self.btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse.clicked.connect(self._on_browse_clicked)

        layout.addWidget(self.label_icon)
        layout.addWidget(self.label_text)
        layout.addSpacing(10)
        layout.addWidget(self.btn_browse, alignment=Qt.AlignmentFlag.AlignCenter)

        self._set_idle_style()

    def _set_idle_style(self):
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #007acc;
                border-radius: 12px;
                background-color: #f8fafc;
            }
            QLabel {
                color: #334155;
            }
            QPushButton {
                background-color: #007acc;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 8px 18px;
            }
            QPushButton:hover {
                background-color: #005999;
            }
        """)

    def _set_hover_style(self):
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #16a34a;
                border-radius: 12px;
                background-color: #f0fdf4;
            }
            QLabel {
                color: #15803d;
            }
        """)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                fn = url.toLocalFile()
                ext = os.path.splitext(fn)[1].upper()
                if ext in [".BSW", ".DSW", ".SPC"]:
                    event.acceptProposedAction()
                    self._set_hover_style()
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._set_idle_style()

    def dropEvent(self, event: QDropEvent):
        self._set_idle_style()
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                filepath = url.toLocalFile()
                ext = os.path.splitext(filepath)[1].upper()
                if ext in [".BSW", ".DSW", ".SPC"]:
                    self.file_dropped.emit(filepath)
                    event.acceptProposedAction()
                    return

    def _on_browse_clicked(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select Spectrometer Data File",
            "",
            "All Supported Files (*.DSW *.BSW *.SPC *.dsw *.bsw *.spc);;"
            "Varian/Agilent Cary (*.DSW *.BSW *.dsw *.bsw);;"
            "Shimadzu UV-Vis-NIR (*.SPC *.spc);;"
            "All Files (*)",
        )
        if filepath:
            self.file_dropped.emit(filepath)


class MplPlotWidget(QWidget):
    """
    Encapsulates Matplotlib Canvas and PyQt Navigation Toolbar.
    Features a 2-row layout with 3:1 height ratio for absorption spectra vs baselines.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        apply_style("regular")
        self.fig = plt.figure(figsize=(8, 5))
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        # Metadata display text block below plot
        self.metadata_group = QFrame(self)
        self.metadata_group.setObjectName("MetadataPanel")
        self.metadata_group.setStyleSheet("""
            QFrame#MetadataPanel {
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                background-color: #f8fafc;
            }
        """)

        meta_layout = QVBoxLayout(self.metadata_group)
        meta_layout.setContentsMargins(10, 8, 10, 8)
        meta_layout.setSpacing(6)

        self.lbl_metadata_title = QLabel("File & Acquisition Metadata", self.metadata_group)
        self.lbl_metadata_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.lbl_metadata_title.setStyleSheet("color: #334155; font-weight: bold;")

        self.txt_metadata = QTextEdit(self.metadata_group)
        self.txt_metadata.setReadOnly(True)
        self.txt_metadata.setMinimumHeight(80)
        self.txt_metadata.setMaximumHeight(160)
        self.txt_metadata.setFont(QFont("Segoe UI", 9))
        self.txt_metadata.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.txt_metadata.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.txt_metadata.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 6px 8px;
                color: #1e293b;
            }
        """)
        meta_layout.addWidget(self.lbl_metadata_title)
        meta_layout.addWidget(self.txt_metadata)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, stretch=1)
        layout.addWidget(self.metadata_group)

        self.clear_plot()

    def clear_plot(self):
        apply_style("regular")
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        ax.axhline(0, color="0.75", linewidth=0.75, linestyle="-")
        ax.set_xlabel("Wavelength (nm)", fontweight="bold")
        ax.set_ylabel("Absorbance", fontweight="bold")
        ax.set_title("No Data Loaded", color="#64748b")
        self.fig.tight_layout()
        self.canvas.draw()
        self.txt_metadata.setHtml(
            "<span style='color: #64748b; font-style: italic;'>No additional metadata available</span>"
        )

    def update_metadata_display(self, cary_file: CaryFile):
        header = cary_file.header
        fields = []

        label_map = [
            ("software", "Software"),
            ("instrument", "Instrument"),
            ("instrument_type", "Instrument Model"),
            ("date_time", "Acquisition Date/Time"),
            ("scan_rate", "Scan Rate"),
            ("scan_speed", "Scan Speed"),
            ("ave_time", "Ave. Time"),
            ("slit_width", "Slit Width / SBW"),
            ("path_length", "Path Length"),
            ("scan_mode", "Scan Mode"),
            ("measuring_mode", "Measuring Mode"),
            ("default_start_wavelength", "Start Wavelength"),
            ("default_end_wavelength", "End Wavelength"),
            ("default_num_points", "Data Points"),
            ("default_step_size", "Step Size"),
            ("history", "History"),
        ]

        seen_keys = set()
        for key, label in label_map:
            if key in header and header[key] is not None:
                val = header[key]
                if isinstance(val, float):
                    val_str = (
                        f"{val:.2f} nm" if "wavelength" in key or "step" in key else f"{val:.2f}"
                    )
                elif isinstance(val, list):
                    val_str = ", ".join(str(v) for v in val[:5])
                else:
                    val_str = str(val)
                fields.append(f"<b>{label}:</b> {val_str}")
                seen_keys.add(key)

        # Check spectrum metadata if available
        if cary_file.spectra:
            s0 = cary_file.spectra[0]
            s_meta = s0.metadata
            for k in ["scan_rate", "ave_time", "slit_width", "date_time", "instrument", "software"]:
                if k not in seen_keys and k in s_meta and s_meta[k]:
                    label = k.replace("_", " ").title()
                    fields.append(f"<b>{label}:</b> {s_meta[k]}")
                    seen_keys.add(k)

        if not fields:
            self.txt_metadata.setHtml(
                "<span style='color: #64748b; font-style: italic;'>No additional metadata available</span>"
            )
        else:
            chunk_size = 3
            lines = []
            for i in range(0, len(fields), chunk_size):
                lines.append(" &bull; ".join(fields[i : i + chunk_size]))
            self.txt_metadata.setHtml("<br>".join(lines))

    def plot_cary_file(
        self,
        cary_file: CaryFile,
        sample_spectra: list[Spectrum],
        bg_spectra: list[Spectrum],
    ):
        apply_style("regular")
        self.fig.clear()

        sample_colors = [
            "#1f77b4",
            "#ff7f0e",
            "#d62728",
            "#9467bd",
            "#8c564b",
            "#e377c2",
            "#17becf",
        ]
        bg_colors = ["#2ca02c", "#7f7f7f", "#bcbd22", "#4b5563"]

        if bg_spectra:
            # 2-row subplot with 3:1 height ratio and shared X axis
            gs = self.fig.add_gridspec(2, 1, height_ratios=[3, 1], hspace=0.08)
            ax1 = self.fig.add_subplot(gs[0])
            ax2 = self.fig.add_subplot(gs[1], sharex=ax1)

            # Top subplot: Main absorption spectra
            for idx, s in enumerate(sample_spectra):
                color = sample_colors[idx % len(sample_colors)]
                ax1.plot(s.wavelengths, s.absorbances, label=s.title, color=color, linewidth=1.8)

            ax1.axhline(0, color="0.75", linewidth=0.75, linestyle="-")
            ax1.set_ylabel("Absorbance", fontweight="bold")
            ax1.set_title(
                f"{cary_file.file_type} Spectra - {cary_file.header['filename']}",
                fontweight="bold",
            )
            if sample_spectra:
                ax1.legend(loc="best")
            plt.setp(ax1.get_xticklabels(), visible=False)

            # Bottom subplot: Baseline / Background spectra
            for idx, s in enumerate(bg_spectra):
                color = bg_colors[idx % len(bg_colors)]
                ax2.plot(
                    s.wavelengths,
                    s.absorbances,
                    label=s.title,
                    color=color,
                    linestyle="--",
                    linewidth=1.4,
                )

            ax2.axhline(0, color="0.75", linewidth=0.75, linestyle="-")
            ax2.set_xlabel("Wavelength (nm)", fontweight="bold")
            ax2.set_ylabel("Baseline Abs.", fontweight="bold")
            ax2.legend(loc="best")

            self.fig.subplots_adjust(top=0.93, bottom=0.150, left=0.1, right=0.96, hspace=0.08)
            self.fig.align_ylabels([ax1, ax2])

        else:
            # Single plot if no background spectra exist
            ax1 = self.fig.add_subplot(111)
            for idx, s in enumerate(sample_spectra):
                color = sample_colors[idx % len(sample_colors)]
                ax1.plot(s.wavelengths, s.absorbances, label=s.title, color=color, linewidth=1.8)

            ax1.axhline(0, color="0.75", linewidth=0.75, linestyle="-")
            ax1.set_xlabel("Wavelength (nm)", fontweight="bold")
            ax1.set_ylabel("Absorbance", fontweight="bold")
            ax1.set_title(
                f"{cary_file.file_type} Spectra - {cary_file.header['filename']}",
                fontweight="bold",
            )
            if sample_spectra:
                ax1.legend(loc="best")

            self.fig.subplots_adjust(top=0.93, bottom=0.150, left=0.1, right=0.96)

        self.canvas.draw()
        self.update_metadata_display(cary_file)


def get_app_icon() -> QIcon:
    """Helper to locate and return the prism application QIcon."""
    res_dir = os.path.join(os.path.dirname(__file__), "resources")
    for fname in ["icon.png", "icon.ico", "icon.jpg"]:
        ipath = os.path.join(res_dir, fname)
        if os.path.isfile(ipath):
            return QIcon(ipath)
    return QIcon()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("parseUV Spectrometer File Reader")
        self.setWindowIcon(get_app_icon())
        self.resize(1050, 850)

        self.current_file: Optional[CaryFile] = None
        self.sample_spectra: list[Spectrum] = []
        self.bg_spectra: list[Spectrum] = []

        self._init_ui()

    def _init_ui(self):
        self._create_menu_bar()
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        self.lbl_file_info = QLabel(
            "No file loaded. Drag & drop a Varian/Agilent Cary (*.DSW, *.BSW) or Shimadzu (*.SPC) file below.",
            self,
        )
        font_banner = QFont("Segoe UI", 11, QFont.Weight.Bold)
        self.lbl_file_info.setFont(font_banner)
        self.lbl_file_info.setStyleSheet(
            "padding: 8px; background-color: #e2e8f0; border-radius: 6px; color: #1e293b;"
        )

        self.drop_zone = DropZoneWidget(self)
        self.drop_zone.file_dropped.connect(self.load_file)

        self.plot_widget = MplPlotWidget(self)

        btn_layout = QHBoxLayout()

        self.btn_export_spectra = QPushButton("📊 Export Spectra as CSV", self)
        self.btn_export_spectra.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.btn_export_spectra.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export_spectra.setStyleSheet("""
            QPushButton {
                background-color: #2563eb; color: white; border-radius: 6px; padding: 10px 16px;
            }
            QPushButton:hover { background-color: #1d4ed8; }
            QPushButton:disabled { background-color: #94a3b8; }
        """)
        self.btn_export_spectra.setEnabled(False)
        self.btn_export_spectra.clicked.connect(self.export_spectra_csv)

        self.btn_export_bg = QPushButton("🧪 Export Background as CSV", self)
        self.btn_export_bg.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.btn_export_bg.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export_bg.setStyleSheet("""
            QPushButton {
                background-color: #059669; color: white; border-radius: 6px; padding: 10px 16px;
            }
            QPushButton:hover { background-color: #047857; }
            QPushButton:disabled { background-color: #94a3b8; }
        """)
        self.btn_export_bg.setEnabled(False)
        self.btn_export_bg.clicked.connect(self.export_bg_csv)

        self.btn_reset = QPushButton("🔄 Reset", self)
        self.btn_reset.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset.setStyleSheet("""
            QPushButton {
                background-color: #dc2626; color: white; border-radius: 6px; padding: 10px 16px;
            }
            QPushButton:hover { background-color: #b91c1c; }
        """)
        self.btn_reset.clicked.connect(self.reset_all)

        btn_layout.addWidget(self.btn_export_spectra)
        btn_layout.addWidget(self.btn_export_bg)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_reset)

        self.content_stack = QWidget(self)
        stack_layout = QVBoxLayout(self.content_stack)
        stack_layout.setContentsMargins(0, 0, 0, 0)

        stack_layout.addWidget(self.drop_zone)
        stack_layout.addWidget(self.plot_widget)
        self.plot_widget.hide()

        main_layout.addWidget(self.lbl_file_info)
        main_layout.addWidget(self.content_stack, stretch=1)
        main_layout.addLayout(btn_layout)

        self.statusBar = QStatusBar(self)
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready. Drop a .BSW, .DSW, or .SPC file to begin.")

    def _create_menu_bar(self):
        menu_bar = self.menuBar()

        # File Menu
        file_menu = menu_bar.addMenu("&File")

        self.action_open = QAction("&Open File...", self)
        self.action_open.setShortcut(QKeySequence.StandardKey.Open)
        self.action_open.setStatusTip("Open a spectrometer file (.DSW, .BSW, .SPC)")
        self.action_open.triggered.connect(self.open_file_dialog)
        file_menu.addAction(self.action_open)

        file_menu.addSeparator()

        self.action_export_spectra = QAction("Export &Sample Spectra as CSV...", self)
        self.action_export_spectra.setStatusTip("Export sample spectra to a CSV file")
        self.action_export_spectra.setEnabled(False)
        self.action_export_spectra.triggered.connect(self.export_spectra_csv)
        file_menu.addAction(self.action_export_spectra)

        self.action_export_bg = QAction("Export &Background Spectra as CSV...", self)
        self.action_export_bg.setStatusTip("Export background/baseline spectra to a CSV file")
        self.action_export_bg.setEnabled(False)
        self.action_export_bg.triggered.connect(self.export_bg_csv)
        file_menu.addAction(self.action_export_bg)

        file_menu.addSeparator()

        self.action_reset = QAction("&Reset Data", self)
        self.action_reset.setShortcut("Ctrl+R")
        self.action_reset.setStatusTip("Clear loaded spectra and reset interface")
        self.action_reset.triggered.connect(self.reset_all)
        file_menu.addAction(self.action_reset)

        file_menu.addSeparator()

        self.action_quit = QAction("&Quit", self)
        self.action_quit.setShortcut(QKeySequence.StandardKey.Quit)
        self.action_quit.setStatusTip("Exit the application")
        self.action_quit.triggered.connect(self.close)
        file_menu.addAction(self.action_quit)

        # Help Menu
        help_menu = menu_bar.addMenu("&Help")

        self.action_about = QAction("&About parseUV...", self)
        self.action_about.setStatusTip("Show information about parseUV")
        self.action_about.triggered.connect(self.show_about_dialog)
        help_menu.addAction(self.action_about)

    def load_file(self, filepath: str):
        try:
            cary_file = parse_uv(filepath)
            self.current_file = cary_file

            self.sample_spectra = []
            self.bg_spectra = []

            for s in cary_file.spectra:
                title_lower = s.title.lower()
                if (
                    "baseline" in title_lower
                    or "background" in title_lower
                    or "dark" in title_lower
                ):
                    self.bg_spectra.append(s)
                else:
                    self.sample_spectra.append(s)

            filename = cary_file.header["filename"]
            n_sample = len(self.sample_spectra)
            n_bg = len(self.bg_spectra)
            self.lbl_file_info.setText(
                f"File: {filename} ({cary_file.file_type}) | "
                f"Total Spectra: {len(cary_file.spectra)} | "
                f"Samples: {n_sample} | Backgrounds: {n_bg}"
            )

            self.btn_export_spectra.setEnabled(len(self.sample_spectra) > 0)
            self.btn_export_bg.setEnabled(len(self.bg_spectra) > 0)
            self.action_export_spectra.setEnabled(len(self.sample_spectra) > 0)
            self.action_export_bg.setEnabled(len(self.bg_spectra) > 0)

            self.drop_zone.hide()
            self.plot_widget.show()
            self.plot_widget.plot_cary_file(cary_file, self.sample_spectra, self.bg_spectra)

            self.statusBar.showMessage(
                f"Loaded '{filename}' with {len(cary_file.spectra)} spectra successfully."
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Reading File",
                f"Failed to parse file '{os.path.basename(filepath)}':\n{e}",
            )
            self.statusBar.showMessage("Error loading file.")

    def open_file_dialog(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select Spectrometer Data File",
            "",
            "All Supported Files (*.DSW *.BSW *.SPC *.dsw *.bsw *.spc);;"
            "Varian/Agilent Cary (*.DSW *.BSW *.dsw *.bsw);;"
            "Shimadzu UV-Vis-NIR (*.SPC *.spc);;"
            "All Files (*)",
        )
        if filepath:
            self.load_file(filepath)

    def show_about_dialog(self):
        about_html = (
            f"<h3>parseUV Spectrometer File Reader</h3>"
            f"<p><b>Version:</b> {__version__}</p>"
            f"<p><b>Author:</b> {__author__} (&lt;{__email__}&gt;)</p>"
            f"<p><b>License:</b> BSD 3-Clause License</p>"
            f"<hr>"
            f"<p><b>Description:</b><br>"
            f"A Python library and PyQt6 desktop application for reading, visualizing, "
            f"and exporting proprietary binary spectrometer files from:</p>"
            f"<ul>"
            f"<li><b>Varian / Agilent Cary</b> UV-Vis-NIR spectrophotometers (<code>.DSW</code>, <code>.BSW</code>)</li>"
            f"<li><b>Shimadzu</b> UV-Vis-NIR spectrophotometers (<code>.SPC</code>)</li>"
            f"</ul>"
            f"<p>Features publication-ready Matplotlib plot styling, automated TeX Gyre Heros / Helvetica font installation, "
            f"and batch folder CSV export tools.</p>"
        )
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("About parseUV")
        msg_box.setTextFormat(Qt.TextFormat.RichText)
        msg_box.setText(about_html)
        icon = get_app_icon()
        if not icon.isNull():
            msg_box.setIconPixmap(icon.pixmap(64, 64))
        msg_box.exec()

    def _spectra_to_df(self, spectra: list[Spectrum]) -> pd.DataFrame:
        if not spectra:
            return pd.DataFrame()
        df = spectra[0].to_dataframe()
        for s in spectra[1:]:
            df = pd.merge(df, s.to_dataframe(), on="Wavelength (nm)", how="outer")
        ascending = spectra[0].start_wavelength < spectra[0].end_wavelength
        df = df.sort_values(by="Wavelength (nm)", ascending=ascending).reset_index(drop=True)
        return df

    def export_spectra_csv(self):
        if not self.sample_spectra or not self.current_file:
            return

        default_name = (
            f"{os.path.splitext(self.current_file.header['filename'])[0]}_sample_spectra.csv"
        )
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Sample Spectra as CSV",
            default_name,
            "CSV Files (*.csv);;All Files (*)",
        )
        if filepath:
            df = self._spectra_to_df(self.sample_spectra)
            df.to_csv(filepath, index=False)
            QMessageBox.information(
                self, "Export Successful", f"Saved sample spectra to:\n{filepath}"
            )
            self.statusBar.showMessage(f"Exported sample spectra to {os.path.basename(filepath)}")

    def export_bg_csv(self):
        if not self.bg_spectra or not self.current_file:
            return

        default_name = f"{os.path.splitext(self.current_file.header['filename'])[0]}_background.csv"
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Background Spectra as CSV",
            default_name,
            "CSV Files (*.csv);;All Files (*)",
        )
        if filepath:
            df = self._spectra_to_df(self.bg_spectra)
            df.to_csv(filepath, index=False)
            QMessageBox.information(
                self, "Export Successful", f"Saved background spectra to:\n{filepath}"
            )
            self.statusBar.showMessage(
                f"Exported background spectra to {os.path.basename(filepath)}"
            )

    def reset_all(self):
        self.current_file = None
        self.sample_spectra = []
        self.bg_spectra = []

        self.lbl_file_info.setText(
            "No file loaded. Drag & drop a Varian/Agilent Cary (*.DSW, *.BSW) or Shimadzu (*.SPC) file below."
        )
        self.btn_export_spectra.setEnabled(False)
        self.btn_export_bg.setEnabled(False)
        self.action_export_spectra.setEnabled(False)
        self.action_export_bg.setEnabled(False)

        self.plot_widget.clear_plot()
        self.plot_widget.hide()
        self.drop_zone.show()

        self.statusBar.showMessage("Reset. Drop a .BSW, .DSW, or .SPC file to begin.")


def launch_gui():
    """Main GUI launcher entry point."""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "parseuv.spectrometer.gui.1.0"
            )
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    app.setWindowIcon(get_app_icon())
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    launch_gui()
