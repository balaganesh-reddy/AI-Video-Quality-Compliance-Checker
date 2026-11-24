"""Windows desktop interface."""

import csv

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QHeaderView,
    QHBoxLayout, QLabel, QMainWindow, QProgressBar, QPushButton,
    QStatusBar, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.analyzer import analyze_video
from app.sheets import export_results
from app.usb import find_videos, get_removable_drives


class ScanWorker(QThread):
    progress = Signal(int, int, str)
    finished_scan = Signal(list)

    def __init__(self, files, rules):
        super().__init__()
        self.files = files
        self.rules = rules

    def run(self):
        results = []
        for index, file in enumerate(self.files, start=1):
            self.progress.emit(index - 1, len(self.files), f"Analyzing {file.name}")
            try:
                results.append(analyze_video(file, self.rules))
            except Exception as exc:
                results.append({
                    "analyzed_at": "", "file_name": file.name,
                    "source_path": str(file), "status": "ERROR", "issues": str(exc),
                })
            self.progress.emit(index, len(self.files), f"Analyzed {file.name}")
        self.finished_scan.emit(results)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Video Quality Compliance Checker")
        self.resize(1200, 700)
        self.results = []
        self.worker = None
        from app.config import load_rules
        self.rules = load_rules()

        central = QWidget()
        layout = QVBoxLayout(central)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("USB/Folder:"))
        self.drive_box = QComboBox()
        controls.addWidget(self.drive_box, 2)
        self.browse_button = QPushButton("Browse Folder")
        controls.addWidget(self.browse_button)
        self.scan_button = QPushButton("Scan Videos")
        controls.addWidget(self.scan_button)
        self.export_button = QPushButton("Export CSV")
        controls.addWidget(self.export_button)
        self.sheet_check = QCheckBox("Export to Google Sheets")
        controls.addWidget(self.sheet_check)
        layout.addLayout(controls)

        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        self.table = QTableWidget()
        layout.addWidget(self.table)
        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())

        self.browse_button.clicked.connect(self.browse_folder)
        self.scan_button.clicked.connect(self.start_scan)
        self.export_button.clicked.connect(self.export_csv)
        self.refresh_drives()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_drives)
        self.timer.start(2000)

    def refresh_drives(self):
        drives = get_removable_drives()
        current = self.drive_box.currentText()
        self.drive_box.blockSignals(True)
        self.drive_box.clear()
        self.drive_box.addItems(drives)
        if current:
            index = self.drive_box.findText(current)
            if index >= 0:
                self.drive_box.setCurrentIndex(index)
        self.drive_box.blockSignals(False)
        self.statusBar().showMessage(f"{len(drives)} removable drive(s) detected" if drives else "No removable drive detected")

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose a folder")
        if folder:
            self.drive_box.clear()
            self.drive_box.addItem(folder)

    def start_scan(self):
        folder = self.drive_box.currentText()
        if not folder:
            self.statusBar().showMessage("Choose a USB drive or folder")
            return
        files = find_videos(folder)
        if not files:
            self.statusBar().showMessage("No supported videos found")
            return
        self.progress.setValue(0)
        self.scan_button.setEnabled(False)
        self.worker = ScanWorker(files, self.rules)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished_scan.connect(self.scan_finished)
        self.worker.start()

    def update_progress(self, completed, total, message):
        self.progress.setValue(int(completed * 100 / total) if total else 0)
        self.statusBar().showMessage(message)

    def scan_finished(self, results):
        self.results = results
        self.scan_button.setEnabled(True)
        self.progress.setValue(100)
        self.populate_table(results)
        self.statusBar().showMessage(f"Completed: {len(results)} video(s)")
        if self.sheet_check.isChecked():
            try:
                count = export_results(results)
                self.statusBar().showMessage(f"Exported {count} row(s); flagged rows sent to NSFW sheet")
            except Exception as exc:
                self.statusBar().showMessage(f"Google Sheets export failed: {exc}")

    def populate_table(self, results):
        if not results:
            self.table.clear()
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
