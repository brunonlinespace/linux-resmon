#!/usr/bin/env python3
import sys
import time
import psutil

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QSplitter, QGroupBox
)

# Custom Table Item to ensure numeric sorting works mathematically (not as strings)
class NumericTableWidgetItem(QTableWidgetItem):
    def __init__(self, text, raw_val=0):
        super().__init__(text)
        self.raw_val = raw_val

    def __lt__(self, other):
        if isinstance(other, NumericTableWidgetItem):
            return self.raw_val < other.raw_val
        return super().__lt__(other)


class ResMonLinux(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Resource Monitor (ResMon) - Fedora Edition")
        self.resize(1100, 750)

        # Central Layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Vertical QSplitter lets you drag and adjust heights between panels
        self.splitter = QSplitter(Qt.Orientation.Vertical)

        # 1. Disk Panel
        disk_box = QGroupBox("Disk Activity")
        disk_layout = QVBoxLayout(disk_box)

        self.disk_filter = QLineEdit()
        self.disk_filter.setPlaceholderText("Filter disk activity by Process Name or PID...")
        self.disk_filter.textChanged.connect(self.update_disk_data)

        self.disk_table = QTableWidget(0, 5)
        self.disk_table.setHorizontalHeaderLabels(["Process Name", "PID", "Read Rate", "Write Rate", "Total I/O Rate"])
        self.disk_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.disk_table.setSortingEnabled(True)

        disk_layout.addWidget(self.disk_filter)
        disk_layout.addWidget(self.disk_table)

        # 2. Network Panel
        net_box = QGroupBox("Network Connections")
        net_layout = QVBoxLayout(net_box)

        self.net_filter = QLineEdit()
        self.net_filter.setPlaceholderText("Filter network connections by Process, IP, or Port...")
        self.net_filter.textChanged.connect(self.update_net_data)

        self.net_table = QTableWidget(0, 6)
        self.net_table.setHorizontalHeaderLabels(["Process Name", "PID", "Local Address", "Remote Address", "Status", "Protocol"])
        self.net_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.net_table.setSortingEnabled(True)

        net_layout.addWidget(self.net_filter)
        net_layout.addWidget(self.net_table)

        # Add both to the vertical splitter
        self.splitter.addWidget(disk_box)
        self.splitter.addWidget(net_box)
        self.splitter.setSizes([350, 350])  # Equal initial heights

        self.layout.addWidget(self.splitter)

        # State tracking for delta rates calculation
        self.prev_io = {}

        # Refresh Timer (1-second updates)
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(1000)

        self.refresh_data()

    def format_rate(self, bytes_per_sec):
        if bytes_per_sec < 1024:
            return f"{bytes_per_sec:.0f} B/s"
        elif bytes_per_sec < 1024 * 1024:
            return f"{bytes_per_sec / 1024:.1f} KB/s"
        else:
            return f"{bytes_per_sec / (1024 * 1024):.2f} MB/s"

    def refresh_data(self):
        self.update_disk_data()
        self.update_net_data()

    def update_disk_data(self):
        self.disk_table.setSortingEnabled(False)
        filter_text = self.disk_filter.text().lower()
        active_processes = []
        now = time.time()

        for proc in psutil.process_iter(['pid', 'name']):
            try:
                io = proc.io_counters()
                pid = proc.info['pid']
                name = proc.info['name'] or "Unknown"

                # Calculate byte deltas over time
                if pid in self.prev_io:
                    old_read, old_write, old_time = self.prev_io[pid]
                    dt = now - old_time
                    r_rate = max(0, (io.read_bytes - old_read) / dt) if dt > 0 else 0
                    w_rate = max(0, (io.write_bytes - old_write) / dt) if dt > 0 else 0
                else:
                    r_rate, w_rate = 0, 0

                self.prev_io[pid] = (io.read_bytes, io.write_bytes, now)
                total_rate = r_rate + w_rate

                if total_rate > 0 or (filter_text and (filter_text in name.lower() or filter_text in str(pid))):
                    if not filter_text or (filter_text in name.lower() or filter_text in str(pid)):
                        active_processes.append((name, pid, r_rate, w_rate, total_rate))

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        self.disk_table.setRowCount(len(active_processes))
        for row, (name, pid, r_rate, w_rate, total_rate) in enumerate(active_processes):
            self.disk_table.setItem(row, 0, QTableWidgetItem(name))
            self.disk_table.setItem(row, 1, NumericTableWidgetItem(str(pid), pid))
            self.disk_table.setItem(row, 2, NumericTableWidgetItem(self.format_rate(r_rate), r_rate))
            self.disk_table.setItem(row, 3, NumericTableWidgetItem(self.format_rate(w_rate), w_rate))
            self.disk_table.setItem(row, 4, NumericTableWidgetItem(self.format_rate(total_rate), total_rate))

        self.disk_table.setSortingEnabled(True)

    def update_net_data(self):
        self.net_table.setSortingEnabled(False)
        filter_text = self.net_filter.text().lower()
        connections = []

        try:
            for conn in psutil.net_connections(kind='inet'):
                if not conn.raddr:  # Skip sockets with no active remote target
                    continue

                pid = conn.pid
                name = "System/Kernel"
                if pid:
                    try:
                        p = psutil.Process(pid)
                        name = p.name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        name = "Access Denied"

                laddr = f"{conn.laddr.ip}:{conn.laddr.port}"
                raddr = f"{conn.raddr.ip}:{conn.raddr.port}"
                proto = "TCP" if conn.type == 1 else "UDP"
                status = conn.status

                search_target = f"{name} {pid} {laddr} {raddr} {status} {proto}".lower()
                if not filter_text or filter_text in search_target:
                    connections.append((name, pid or 0, laddr, raddr, status, proto))

        except psutil.AccessDenied:
            pass

        self.net_table.setRowCount(len(connections))
        for row, (name, pid, laddr, raddr, status, proto) in enumerate(connections):
            self.net_table.setItem(row, 0, QTableWidgetItem(name))
            self.net_table.setItem(row, 1, NumericTableWidgetItem(str(pid), pid))
            self.net_table.setItem(row, 2, QTableWidgetItem(laddr))
            self.net_table.setItem(row, 3, QTableWidgetItem(raddr))
            self.net_table.setItem(row, 4, QTableWidgetItem(status))
            self.net_table.setItem(row, 5, QTableWidgetItem(proto))

        self.net_table.setSortingEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ResMonLinux()
    window.show()
    sys.exit(app.exec())
