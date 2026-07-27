#!/usr/bin/env python3
import sys
import psutil
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit
)

class ResMonLinux(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Resource Monitor (ResMon) - Linux")
        self.resize(1000, 650)

        # Central Widget & Tabs
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # 1. Disk Tab
        self.disk_tab = QWidget()
        self.disk_layout = QVBoxLayout(self.disk_tab)
        self.disk_filter = QLineEdit()
        self.disk_filter.setPlaceholderText("Filter by Process Name or PID...")
        self.disk_filter.textChanged.connect(self.update_disk_tab)
        self.disk_table = QTableWidget(0, 5)
        self.disk_table.setHorizontalHeaderLabels(["Process Name", "PID", "Read Rate", "Write Rate", "Total I/O Rate"])
        self.disk_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.disk_layout.addWidget(self.disk_filter)
        self.disk_layout.addWidget(self.disk_table)
        self.tabs.addTab(self.disk_tab, "Disk Activity")

        # 2. Network Tab
        self.net_tab = QWidget()
        self.net_layout = QVBoxLayout(self.net_tab)
        self.net_filter = QLineEdit()
        self.net_filter.setPlaceholderText("Filter by Process, IP, or Port...")
        self.net_filter.textChanged.connect(self.update_net_tab)
        self.net_table = QTableWidget(0, 6)
        self.net_table.setHorizontalHeaderLabels(["Process Name", "PID", "Local Address", "Remote Address", "Status", "Protocol"])
        self.net_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.net_layout.addWidget(self.net_filter)
        self.net_layout.addWidget(self.net_table)
        self.tabs.addTab(self.net_tab, "Network Connections")

        # State tracking for delta rates (Bytes/sec calculation)
        self.prev_io = {} # {pid: (read_bytes, write_bytes, timestamp)}

        # Refresh Timer (1 second interval)
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
        current_tab = self.tabs.currentIndex()
        if current_tab == 0:
            self.update_disk_tab()
        elif current_tab == 1:
            self.update_net_tab()

    def update_disk_tab(self):
        filter_text = self.disk_filter.text().lower()
        active_processes = []
        import time
        now = time.time()

        for proc in psutil.process_iter(['pid', 'name']):
            try:
                io = proc.io_counters()
                pid = proc.info['pid']
                name = proc.info['name'] or "Unknown"

                # Calculate delta rate
                if pid in self.prev_io:
                    old_read, old_write, old_time = self.prev_io[pid]
                    dt = now - old_time
                    if dt > 0:
                        r_rate = max(0, (io.read_bytes - old_read) / dt)
                        w_rate = max(0, (io.write_bytes - old_write) / dt)
                    else:
                        r_rate, w_rate = 0, 0
                else:
                    r_rate, w_rate = 0, 0

                self.prev_io[pid] = (io.read_bytes, io.write_bytes, now)

                # Only display processes actively performing I/O or matching search filter
                total_rate = r_rate + w_rate
                if total_rate > 0 or (filter_text and (filter_text in name.lower() or filter_text in str(pid))):
                    if not filter_text or (filter_text in name.lower() or filter_text in str(pid)):
                        active_processes.append((name, pid, r_rate, w_rate, total_rate))

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Sort processes by highest total I/O rate first
        active_processes.sort(key=lambda x: x[4], reverse=True)

        self.disk_table.setRowCount(len(active_processes))
        for row, (name, pid, r_rate, w_rate, total_rate) in enumerate(active_processes):
            self.disk_table.setItem(row, 0, QTableWidgetItem(name))
            self.disk_table.setItem(row, 1, QTableWidgetItem(str(pid)))
            self.disk_table.setItem(row, 2, QTableWidgetItem(self.format_rate(r_rate)))
            self.disk_table.setItem(row, 3, QTableWidgetItem(self.format_rate(w_rate)))
            self.disk_table.setItem(row, 4, QTableWidgetItem(self.format_rate(total_rate)))

    def update_net_tab(self):
        filter_text = self.net_filter.text().lower()
        connections = []

        try:
            # Query active socket connections across system
            for conn in psutil.net_connections(kind='inet'):
                if not conn.raddr:  # Skip sockets with no remote endpoint
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

                # Apply filter matching
                search_target = f"{name} {pid} {laddr} {raddr} {status} {proto}".lower()
                if filter_text in search_target:
                    connections.append((name, pid, laddr, raddr, status, proto))

        except psutil.AccessDenied:
            pass

        self.net_table.setRowCount(len(connections))
        for row, (name, pid, laddr, raddr, status, proto) in enumerate(connections):
            self.net_table.setItem(row, 0, QTableWidgetItem(name))
            self.net_table.setItem(row, 1, QTableWidgetItem(str(pid) if pid else "N/A"))
            self.net_table.setItem(row, 2, QTableWidgetItem(laddr))
            self.net_table.setItem(row, 3, QTableWidgetItem(raddr))
            self.net_table.setItem(row, 4, QTableWidgetItem(status))
            self.net_table.setItem(row, 5, QTableWidgetItem(proto))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ResMonLinux()
    window.show()
    sys.exit(app.exec())
