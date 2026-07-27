#!/usr/bin/env python3
import sys
import time
import psutil

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QSplitter, QGroupBox
)

# Custom Table Item to ensure numeric sorting works mathematically (not alphabetically)
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

        # Main Tab Widget
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # State tracking for disk delta rates
        self.prev_io = {}

        # Prime psutil CPU tracking across processes
        for proc in psutil.process_iter(['pid']):
            try:
                proc.cpu_percent()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Build Tab 1 and Tab 2
        self.setup_cpu_mem_tab()
        self.setup_disk_net_tab()

        # Refresh Timer (1-second updates)
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(1000)

        self.refresh_data()

    # --- TAB 1: CPU & MEMORY ---
    def setup_cpu_mem_tab(self):
        self.tab_cpu_mem = QWidget()
        layout = QVBoxLayout(self.tab_cpu_mem)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # 1. CPU Panel
        cpu_box = QGroupBox("CPU Activity")
        cpu_layout = QVBoxLayout(cpu_box)
        self.cpu_filter = QLineEdit()
        self.cpu_filter.setPlaceholderText("Filter CPU by Process Name or PID...")
        self.cpu_filter.textChanged.connect(self.update_cpu_data)
        self.cpu_table = QTableWidget(0, 5)
        self.cpu_table.setHorizontalHeaderLabels(["Process Name", "PID", "CPU %", "Threads", "Status"])
        self.cpu_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cpu_table.setSortingEnabled(True)
        cpu_layout.addWidget(self.cpu_filter)
        cpu_layout.addWidget(self.cpu_table)

        # 2. Memory Panel
        mem_box = QGroupBox("Memory Activity")
        mem_layout = QVBoxLayout(mem_box)
        self.mem_filter = QLineEdit()
        self.mem_filter.setPlaceholderText("Filter Memory by Process Name or PID...")
        self.mem_filter.textChanged.connect(self.update_mem_data)
        self.mem_table = QTableWidget(0, 5)
        self.mem_table.setHorizontalHeaderLabels(["Process Name", "PID", "Working Set (RAM)", "RAM %", "Virtual Memory"])
        self.mem_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.mem_table.setSortingEnabled(True)
        mem_layout.addWidget(self.mem_filter)
        mem_layout.addWidget(self.mem_table)

        splitter.addWidget(cpu_box)
        splitter.addWidget(mem_box)
        splitter.setSizes([350, 350])

        layout.addWidget(splitter)
        self.tabs.addTab(self.tab_cpu_mem, "CPU & Memory")

    # --- TAB 2: DISK & NETWORK ---
    def setup_disk_net_tab(self):
        self.tab_disk_net = QWidget()
        layout = QVBoxLayout(self.tab_disk_net)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # 1. Disk Panel
        disk_box = QGroupBox("Disk Activity")
        disk_layout = QVBoxLayout(disk_box)
        self.disk_filter = QLineEdit()
        self.disk_filter.setPlaceholderText("Filter Disk by Process Name or PID...")
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
        self.net_filter.setPlaceholderText("Filter Network by Process, IP, or Port...")
        self.net_filter.textChanged.connect(self.update_net_data)
        self.net_table = QTableWidget(0, 6)
        self.net_table.setHorizontalHeaderLabels(["Process Name", "PID", "Local Address", "Remote Address", "Status", "Protocol"])
        self.net_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.net_table.setSortingEnabled(True)
        net_layout.addWidget(self.net_filter)
        net_layout.addWidget(self.net_table)

        splitter.addWidget(disk_box)
        splitter.addWidget(net_box)
        splitter.setSizes([350, 350])

        layout.addWidget(splitter)
        self.tabs.addTab(self.tab_disk_net, "Disk & Network")

    # --- HELPER FORMATTERS ---
    def format_bytes(self, num_bytes):
        if num_bytes < 1024:
            return f"{num_bytes} B"
        elif num_bytes < 1024 * 1024:
            return f"{num_bytes / 1024:.1f} KB"
        elif num_bytes < 1024 * 1024 * 1024:
            return f"{num_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"

    def format_rate(self, bytes_per_sec):
        return f"{self.format_bytes(bytes_per_sec)}/s"

    # --- REFRESH DATA BASED ON ACTIVE TAB ---
    def refresh_data(self):
        current_idx = self.tabs.currentIndex()
        if current_idx == 0:
            self.update_cpu_data()
            self.update_mem_data()
        elif current_idx == 1:
            self.update_disk_data()
            self.update_net_data()

    # --- UPDATE LOGIC ---
    def update_cpu_data(self):
        self.cpu_table.setSortingEnabled(False)
        filter_text = self.cpu_filter.text().lower()
        procs = []

        for proc in psutil.process_iter(['pid', 'name', 'status', 'num_threads']):
            try:
                cpu_pct = proc.cpu_percent()
                pid = proc.info['pid']
                name = proc.info['name'] or "Unknown"
                threads = proc.info['num_threads'] or 0
                status = proc.info['status'] or "unknown"

                if cpu_pct > 0 or (filter_text and (filter_text in name.lower() or filter_text in str(pid))):
                    if not filter_text or (filter_text in name.lower() or filter_text in str(pid)):
                        procs.append((name, pid, cpu_pct, threads, status))

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        self.cpu_table.setRowCount(len(procs))
        for row, (name, pid, cpu_pct, threads, status) in enumerate(procs):
            self.cpu_table.setItem(row, 0, QTableWidgetItem(name))
            self.cpu_table.setItem(row, 1, NumericTableWidgetItem(str(pid), pid))
            self.cpu_table.setItem(row, 2, NumericTableWidgetItem(f"{cpu_pct:.1f}%", cpu_pct))
            self.cpu_table.setItem(row, 3, NumericTableWidgetItem(str(threads), threads))
            self.cpu_table.setItem(row, 4, QTableWidgetItem(status))

        self.cpu_table.setSortingEnabled(True)

    def update_mem_data(self):
        self.mem_table.setSortingEnabled(False)
        filter_text = self.mem_filter.text().lower()
        procs = []

        for proc in psutil.process_iter(['pid', 'name']):
            try:
                mem_info = proc.memory_info()
                mem_pct = proc.memory_percent()
                pid = proc.info['pid']
                name = proc.info['name'] or "Unknown"

                rss = mem_info.rss
                vms = mem_info.vms

                if rss > 1024 * 1024 or (filter_text and (filter_text in name.lower() or filter_text in str(pid))):
                    if not filter_text or (filter_text in name.lower() or filter_text in str(pid)):
                        procs.append((name, pid, rss, mem_pct, vms))

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        self.mem_table.setRowCount(len(procs))
        for row, (name, pid, rss, mem_pct, vms) in enumerate(procs):
            self.mem_table.setItem(row, 0, QTableWidgetItem(name))
            self.mem_table.setItem(row, 1, NumericTableWidgetItem(str(pid), pid))
            self.mem_table.setItem(row, 2, NumericTableWidgetItem(self.format_bytes(rss), rss))
            self.mem_table.setItem(row, 3, NumericTableWidgetItem(f"{mem_pct:.2f}%", mem_pct))
            self.mem_table.setItem(row, 4, NumericTableWidgetItem(self.format_bytes(vms), vms))

        self.mem_table.setSortingEnabled(True)

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
                if not conn.raddr:
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