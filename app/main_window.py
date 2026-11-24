"""Windows desktop interface with automatic removable-drive scanning."""

import csv

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QDoubleSpinBox, QHeaderView,
    QHBoxLayout, QLabel, QMainWindow, QProgressBar, QPushButton,
    QStatusBar, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.analyzer import analyze_video
from app.config import ComplianceRules, load_rules, save_rules
from app.scan_cache import ScanCache
from app.sheets import export_results
from app.usb import find_videos, get_removable_drives


class RulesDialog(QDialog):
    def __init__(self, rules, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Visual Compliance Rules")
        self.setMinimumWidth(440)
        form = QFormLayout(self)

        self.wrist_visibility = self._spin(0, 1, rules.minimum_wrist_visible_frame_ratio, 2)
        self.wrist_confidence = self._spin(0, 1, rules.minimum_wrist_visibility_confidence, 2)
        self.phone_duration = self._spin(1, 600, rules.maximum_phone_use_seconds, 0)
        self.phone_confidence = self._spin(0, 1, rules.phone_detection_confidence, 2)
        self.lighting_ratio = self._spin(0, 1, rules.minimum_well_lit_frame_ratio, 2)
        self.brightness = self._spin(0, 255, rules.minimum_average_brightness, 0)
        self.hand_absence = self._spin(0, 3600, rules.maximum_hand_absence_seconds, 0)
        self.sample_interval = self._spin(0.25, 30, rules.sample_interval_seconds, 2)

        form.addRow("Minimum both-wrist visibility ratio (0–1)", self.wrist_visibility)
        form.addRow("Minimum wrist confidence (0–1)", self.wrist_confidence)
        form.addRow("Phone-use failure limit (seconds)", self.phone_duration)
        form.addRow("Phone detection confidence (0–1)", self.phone_confidence)
        form.addRow("Minimum well-lit frame ratio (0–1)", self.lighting_ratio)
        form.addRow("Minimum average brightness (0–255)", self.brightness)
        form.addRow("Max continuous hand absence (seconds)", self.hand_absence)
        form.addRow("Frame sampling interval (seconds)", self.sample_interval)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    @staticmethod
    def _spin(minimum, maximum, value, decimals):
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setValue(value)
        return spin

    def rules(self):
        return ComplianceRules(
            minimum_wrist_visible_frame_ratio=self.wrist_visibility.value(),
            minimum_wrist_visibility_confidence=self.wrist_confidence.value(),
            maximum_phone_use_seconds=self.phone_duration.value(),
            phone_detection_confidence=self.phone_confidence.value(),
            minimum_well_lit_frame_ratio=self.lighting_ratio.value(),
            minimum_average_brightness=self.brightness.value(),
            maximum_hand_absence_seconds=self.hand_absence.value(),
            sample_interval_seconds=self.sample_interval.value(),
        )


class ScanWorker(QThread):
    progress = Signal(int, int, str)
    finished_scan = Signal(list, int, int)

    def __init__(self, root, files, rules):
        super().__init__()
        self.root = root
        self.files = files
        self.rules = rules
        self.cache = ScanCache()

    def run(self):
        new_files = [file for file in self.files if not self.cache.is_unchanged(self.root, file)]
        skipped_count = len(self.files) - len(new_files)
        results = []
        for index, file in enumerate(new_files, start=1):
            self.progress.emit(index - 1, len(new_files), f"Analyzing {file.name}")
            try:
                result = analyze_video(file, self.rules)
                results.append(result)
                if result.get("status") != "ERROR":
                    self.cache.mark_processed(self.root, file)
            except Exception as exc:
                results.append({
                    "analyzed_at": "", "file_name": file.name,
                    "source_path": str(file), "status": "ERROR", "issues": str(exc),
                })
            self.progress.emit(index, len(new_files), f"Analyzed {file.name}")
        self.finished_scan.emit(results, skipped_count, len(self.files))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Video Quality Compliance Checker")
        self.resize(1200, 700)
        self.results = []
        self.worker = None
        self.rules = load_rules()
        self.detected_drives = None
        self.pending_drive_scans = []
        self.current_scan_root = None

        central = QWidget()
        layout = QVBoxLayout(central)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("USB/Folder:"))
        self.drive_box = QComboBox()
        controls.addWidget(self.drive_box, 2)
        self.browse_button = QPushButton("Browse Folder")
        self.rules_button = QPushButton("Visual Rules")
        self.scan_button = QPushButton("Scan Videos")
        self.export_button = QPushButton("Export CSV")
        self.sheet_check = QCheckBox("Export to Google Sheets")
        self.auto_scan_check = QCheckBox("Auto-scan USB drives")
        self.auto_scan_check.setChecked(True)
        for widget in (
            self.browse_button, self.rules_button, self.scan_button,
            self.export_button, self.sheet_check, self.auto_scan_check,
        ):
            controls.addWidget(widget)
        layout.addLayout(controls)
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        self.table = QTableWidget()
        layout.addWidget(self.table)
        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())

        self.browse_button.clicked.connect(self.browse_folder)
        self.rules_button.clicked.connect(self.edit_rules)
        self.scan_button.clicked.connect(self.start_manual_scan)
        self.export_button.clicked.connect(self.export_csv)
        self.refresh_drives()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_drives)
        self.timer.start(2000)

    def edit_rules(self):
        dialog = RulesDialog(self.rules, self)
        if dialog.exec():
            self.rules = dialog.rules()
            save_rules(self.rules)
            self.statusBar().showMessage("Visual compliance rules saved")

    def refresh_drives(self):
        drives = get_removable_drives()
        current = self.drive_box.currentText()
        previous = self.detected_drives
        self.detected_drives = set(drives)

        self.drive_box.blockSignals(True)
        self.drive_box.clear()
        self.drive_box.addItems(drives)
        if current:
            index = self.drive_box.findText(current)
            if index < 0 and current not in drives:
                self.drive_box.addItem(current)
                index = self.drive_box.findText(current)
            if index >= 0:
                self.drive_box.setCurrentIndex(index)
        self.drive_box.blockSignals(False)

        # First poll scans any USB drives already connected at app launch.
        newly_available = drives if previous is None else sorted(self.detected_drives - previous)
        if self.auto_scan_check.isChecked():
            for drive in newly_available:
                if drive not in self.pending_drive_scans and drive != self.current_scan_root:
                    self.pending_drive_scans.append(drive)
            self._start_next_pending_drive()

        if not drives:
            self.statusBar().showMessage("No removable drive detected")
        elif newly_available:
            self.statusBar().showMessage(f"Detected USB drive(s): {', '.join(newly_available)}")
        else:
            self.statusBar().showMessage(f"{len(drives)} removable drive(s) detected")

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose a folder")
        if folder:
            self.drive_box.setCurrentText(folder)
            if self.drive_box.findText(folder) < 0:
                self.drive_box.addItem(folder)
                self.drive_box.setCurrentText(folder)

    def start_manual_scan(self):
        folder = self.drive_box.currentText()
        if not folder:
            self.statusBar().showMessage("Choose a USB drive or folder")
            return
        self._scan_folder(folder)

    def _scan_folder(self, folder):
        if self.worker and self.worker.isRunning():
            return
        try:
            files = find_videos(folder)
        except OSError as exc:
            self.statusBar().showMessage(f"Cannot read {folder}: {exc}")
            self._start_next_pending_drive()
            return
        if not files:
            self.statusBar().showMessage(f"No supported videos found on {folder}")
            self._start_next_pending_drive()
            return

        self.current_scan_root = folder
        self.progress.setValue(0)
        self.scan_button.setEnabled(False)
        self.statusBar().showMessage(f"Found {len(files)} video(s) on {folder}; checking scan cache…")
        self.worker = ScanWorker(folder, files, self.rules)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished_scan.connect(self.scan_finished)
        self.worker.start()

    def _start_next_pending_drive(self):
        if not self.auto_scan_check.isChecked() or (self.worker and self.worker.isRunning()):
            return
        while self.pending_drive_scans:
            drive = self.pending_drive_scans.pop(0)
            if drive in self.detected_drives:
                self._scan_folder(drive)
                return

    def update_progress(self, completed, total, message):
        self.progress.setValue(int(completed * 100 / total) if total else 0)
        self.statusBar().showMessage(message)

    def scan_finished(self, results, skipped_count, total_count):
        completed_root = self.current_scan_root
        self.current_scan_root = None
        self.results = results
        self.scan_button.setEnabled(True)
        self.progress.setValue(100)
        self.populate_table(results)
        if results:
            self.statusBar().showMessage(
                f"Completed {len(results)} new video(s); skipped {skipped_count} unchanged of {total_count}"
            )
        else:
            self.statusBar().showMessage(
                f"No new or changed videos on {completed_root}; skipped {skipped_count} unchanged"
            )

        if results and self.sheet_check.isChecked():
            try:
                count = export_results(results)
                self.statusBar().showMessage(f"Exported {count} row(s) to Google Sheets")
            except Exception as exc:
                self.statusBar().showMessage(f"Google Sheets export failed: {exc}")

        QTimer.singleShot(0, self._start_next_pending_drive)

    def populate_table(self, results):
        if not results:
            self.table.clear()
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            return
        columns = list(dict.fromkeys(key for result in results for key in result))
        self.table.setColumnCount(len(columns))
        self.table.setRowCount(len(results))
        self.table.setHorizontalHeaderLabels(columns)
        for row_index, result in enumerate(results):
            for column_index, column in enumerate(columns):
                self.table.setItem(row_index, column_index, QTableWidgetItem(str(result.get(column, ""))))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

    def export_csv(self):
        if not self.results:
            self.statusBar().showMessage("Scan videos before exporting")
            return
        output = QFileDialog.getSaveFileName(self, "Export Results", "video-compliance-results.csv", "CSV (*.csv)")[0]
        if not output:
            return
        columns = list(dict.fromkeys(key for result in self.results for key in result))
        with open(output, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(self.results)
        self.statusBar().showMessage(f"Exported CSV: {output}")


def run():
    from dotenv import load_dotenv
    load_dotenv()
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
