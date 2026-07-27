#!/usr/bin/env python3
import sys
import time
import psutil

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QSplitter, QGroupBox, QPushButton, QLabel
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

        # Main Tab Widget (Movable tabs enabled)
        self.tabs = QTabWidget()
        self.tabs.setMovable(True)  # Enables drag-and-drop tab reordering
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

    # --- PANEL REORDER HELPER ---
    def move_panel(self, splitter, group_box, direction):
        idx = splitter.indexOf(group_box)
        new_idx = idx + direction
        if 0 <= new_idx < splitter.count():
            # Get current sizes before move to maintain proportional heights
            sizes = splitter.sizes()
            splitter.insertWidget(new_idx, group_box)
            # Swap sizes to match swapped positions
            sizes[idx], sizes[new_idx] = sizes[new_idx], sizes[idx]
            splitter.setSizes(sizes)

    def create_panel_header(self, title, group_box, splitter):
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(5, 2, 5, 2)

        title_label = QLabel(f"<b>{title}</b>")
        
        btn_up = QPushButton("▲ Up")
        btn_up.setFixedWidth(50)
        btn_up.clicked.connect(lambda: self.move_panel(splitter, group_box, -1))

        btn_down = QPushButton("▼ Down")
        btn_down.setFixedWidth(50)
        btn_down.clicked.connect(lambda: self.move_panel(splitter, group_box, 1))

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(btn_up)
        header_layout.addWidget(btn_down)

        return header_layout

    # --- TAB 1: CPU & MEMORY ---
    def setup_cpu_mem_tab(self):
        self.tab_cpu_mem = QWidget()
        layout = QVBoxLayout(self.tab_cpu_mem)

        self.cpu_mem_splitter = QSplitter(Qt.Orientation.Vertical)

        # 1. CPU Panel
        cpu_box = QGroupBox()
        cpu_layout = QVBoxLayout(cpu_box)
        cpu_layout.addLayout(self.create_panel_header("CPU Activity", cpu_box, self.cpu_mem_splitter))
        
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
        mem_box = QGroupBox()
        mem_layout = QVBoxLayout(mem_box)
        mem_layout.addLayout(self.create_panel_header("Memory Activity", mem_box, self.cpu_mem_splitter))

        self.mem_filter = QLineEdit()
        self.mem_filter.setPlaceholderText("Filter Memory by Process Name or PID...")
        self.mem_filter.textChanged.connect(self.update_mem_data)
        self.mem_table = QTableWidget(0, 5)
        self.mem_table.setHorizontalHeaderLabels(["Process Name", "PID", "Working Set (RAM)", "RAM %", "Virtual Memory"])
        self.mem_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.mem_table.setSortingEnabled(True)
        mem_layout.addWidget(self.mem_filter)
        mem_layout.addWidget(self.mem_table)

        self.cpu_mem_splitter.addWidget(cpu_box)
        self.cpu_mem_splitter.addWidget(mem_box)
        self.cpu_mem_splitter.setSizes([350, 350])

        layout.addWidget(self.cpu_mem_splitter)
        self.tabs.addTab(self.tab_cpu_mem, "CPU & Memory")

    # --- TAB 2: DISK & NETWORK ---
    def setup_disk_net_tab(self):
        self.tab_disk_net = QWidget()
        layout = QVBoxLayout(self.tab_disk_net)

        self.disk_net_splitter = QSplitter(Qt.Orientation.Vertical)

        # 1. Disk Panel
        disk_box = QGroupBox()
        disk_layout = QVBoxLayout(disk_box)
        disk_layout.addLayout(self.create_panel_header("Disk Activity", disk_box, self.disk_net_splitter))

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
        net_box = QGroupBox()
        net_layout = QVBoxLayout(net_box)
        net_layout.addLayout(self.create_panel_header("Network Connections", net_box, self.disk_net_splitter))

        self.net_filter = QLineEdit()
        self.net_filter.setPlaceholderText("Filter Network by Process, IP, or Port...")
        self.net_filter.textChanged.connect(self.update_net_data)
        self.net_table = QTableWidget(0, 6)
        self.net_table.setHorizontalHeaderLabels(["Process Name", "PID", "Local Address", "Remote Address", "Status", "Protocol"])
        self.net_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.net_table.setSortingEnabled(True)
        net_layout.addWidget(self.net_filter)
        net_layout.addWidget(self.net_table)

        self.disk_net_splitter.addWidget(disk_box)
        self.disk_net_splitter.addWidget(net_box)
        self.disk_net_splitter.setSizes([350, 350])

        layout.addWidget(self.disk_net_splitter)
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
        current_widget = self.tabs.currentWidget()
        if current_widget == self.tab_cpu_mem:
            self.update_cpu_data()
            self.update_mem_data()
        elif current_widget == self.tab_disk_net:
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