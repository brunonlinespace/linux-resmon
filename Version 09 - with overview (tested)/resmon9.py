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
        self.resize(1200, 850)

        # Central Layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Main Tab Widget (Movable tabs enabled natively)
        self.tabs = QTabWidget()
        self.tabs.setMovable(True)
        self.layout.addWidget(self.tabs)

        # State tracking for disk delta rates
        self.prev_io = {}

        # Prime psutil CPU tracking across processes
        for proc in psutil.process_iter(['pid']):
            try:
                proc.cpu_percent()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Build UI Tabs
        self.setup_overview_tab()
        self.setup_cpu_tab()
        self.setup_mem_tab()
        self.setup_disk_tab()
        self.setup_net_tab()

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
            sizes = splitter.sizes()
            splitter.insertWidget(new_idx, group_box)
            sizes[idx], sizes[new_idx] = sizes[new_idx], sizes[idx]
            splitter.setSizes(sizes)

    def create_panel_header(self, title, group_box, splitter=None):
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(5, 2, 5, 2)

        title_label = QLabel(f"<b>{title}</b>")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        # Only add Up/Down buttons if the panel is inside a reorderable splitter
        if splitter is not None:
            btn_up = QPushButton("▲ Up")
            btn_up.setFixedWidth(50)
            btn_up.clicked.connect(lambda: self.move_panel(splitter, group_box, -1))

            btn_down = QPushButton("▼ Down")
            btn_down.setFixedWidth(50)
            btn_down.clicked.connect(lambda: self.move_panel(splitter, group_box, 1))

            header_layout.addWidget(btn_up)
            header_layout.addWidget(btn_down)

        return header_layout

    # --- WIDGET CREATORS (Reusable across Overview and Dedicated Tabs) ---
    def create_cpu_widget(self, splitter=None):
        box = QGroupBox()
        layout = QVBoxLayout(box)
        layout.addLayout(self.create_panel_header("CPU Activity", box, splitter))

        flt = QLineEdit()
        flt.setPlaceholderText("Filter CPU by Process Name or PID...")
        
        tbl = QTableWidget(0, 5)
        tbl.setHorizontalHeaderLabels(["Process Name", "PID", "CPU %", "Threads", "Status"])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tbl.setSortingEnabled(True)

        layout.addWidget(flt)
        layout.addWidget(tbl)
        return box, flt, tbl

    def create_mem_widget(self, splitter=None):
        box = QGroupBox()
        layout = QVBoxLayout(box)
        layout.addLayout(self.create_panel_header("Memory Activity", box, splitter))

        flt = QLineEdit()
        flt.setPlaceholderText("Filter Memory by Process Name or PID...")

        tbl = QTableWidget(0, 5)
        tbl.setHorizontalHeaderLabels(["Process Name", "PID", "Working Set (RAM)", "RAM %", "Virtual Memory"])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tbl.setSortingEnabled(True)

        layout.addWidget(flt)
        layout.addWidget(tbl)
        return box, flt, tbl

    def create_disk_widget(self, splitter=None):
        box = QGroupBox()
        layout = QVBoxLayout(box)
        layout.addLayout(self.create_panel_header("Disk Activity", box, splitter))

        flt = QLineEdit()
        flt.setPlaceholderText("Filter Disk by Process Name or PID...")

        tbl = QTableWidget(0, 5)
        tbl.setHorizontalHeaderLabels(["Process Name", "PID", "Read Rate", "Write Rate", "Total I/O Rate"])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tbl.setSortingEnabled(True)

        layout.addWidget(flt)
        layout.addWidget(tbl)
        return box, flt, tbl

    def create_net_widget(self, splitter=None):
        box = QGroupBox()
        layout = QVBoxLayout(box)
        layout.addLayout(self.create_panel_header("Network Connections", box, splitter))

        flt = QLineEdit()
        flt.setPlaceholderText("Filter Network by Process, IP, or Port...")

        tbl = QTableWidget(0, 6)
        tbl.setHorizontalHeaderLabels(["Process Name", "PID", "Local Address", "Remote Address", "Status", "Protocol"])
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tbl.setSortingEnabled(True)

        layout.addWidget(flt)
        layout.addWidget(tbl)
        return box, flt, tbl

    # --- TAB SETUP METHODS ---
    def setup_overview_tab(self):
        self.tab_overview = QWidget()
        layout = QVBoxLayout(self.tab_overview)

        self.overview_splitter = QSplitter(Qt.Orientation.Vertical)

        cpu_box, self.ov_cpu_filter, self.ov_cpu_table = self.create_cpu_widget(self.overview_splitter)
        mem_box, self.ov_mem_filter, self.ov_mem_table = self.create_mem_widget(self.overview_splitter)
        disk_box, self.ov_disk_filter, self.ov_disk_table = self.create_disk_widget(self.overview_splitter)
        net_box, self.ov_net_filter, self.ov_net_table = self.create_net_widget(self.overview_splitter)

        self.ov_cpu_filter.textChanged.connect(lambda: self.update_cpu_data(self.ov_cpu_filter, self.ov_cpu_table))
        self.ov_mem_filter.textChanged.connect(lambda: self.update_mem_data(self.ov_mem_filter, self.ov_mem_table))
        self.ov_disk_filter.textChanged.connect(lambda: self.update_disk_data(self.ov_disk_filter, self.ov_disk_table))
        self.ov_net_filter.textChanged.connect(lambda: self.update_net_data(self.ov_net_filter, self.ov_net_table))

        self.overview_splitter.addWidget(cpu_box)
        self.overview_splitter.addWidget(mem_box)
        self.overview_splitter.addWidget(disk_box)
        self.overview_splitter.addWidget(net_box)
        self.overview_splitter.setSizes([200, 200, 200, 200])

        layout.addWidget(self.overview_splitter)
        self.tabs.addTab(self.tab_overview, "Overview")

    def setup_cpu_tab(self):
        self.tab_cpu = QWidget()
        layout = QVBoxLayout(self.tab_cpu)
        cpu_box, self.cpu_filter, self.cpu_table = self.create_cpu_widget()
        self.cpu_filter.textChanged.connect(lambda: self.update_cpu_data(self.cpu_filter, self.cpu_table))
        layout.addWidget(cpu_box)
        self.tabs.addTab(self.tab_cpu, "CPU")

    def setup_mem_tab(self):
        self.tab_mem = QWidget()
        layout = QVBoxLayout(self.tab_mem)
        mem_box, self.mem_filter, self.mem_table = self.create_mem_widget()
        self.mem_filter.textChanged.connect(lambda: self.update_mem_data(self.mem_filter, self.mem_table))
        layout.addWidget(mem_box)
        self.tabs.addTab(self.tab_mem, "Memory")

    def setup_disk_tab(self):
        self.tab_disk = QWidget()
        layout = QVBoxLayout(self.tab_disk)
        disk_box, self.disk_filter, self.disk_table = self.create_disk_widget()
        self.disk_filter.textChanged.connect(lambda: self.update_disk_data(self.disk_filter, self.disk_table))
        layout.addWidget(disk_box)
        self.tabs.addTab(self.tab_disk, "Disk")

    def setup_net_tab(self):
        self.tab_net = QWidget()
        layout = QVBoxLayout(self.tab_net)
        net_box, self.net_filter, self.net_table = self.create_net_widget()
        self.net_filter.textChanged.connect(lambda: self.update_net_data(self.net_filter, self.net_table))
        layout.addWidget(net_box)
        self.tabs.addTab(self.tab_net, "Network")

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

    # --- SMART REFRESH ROUTER ---
    def refresh_data(self):
        current_widget = self.tabs.currentWidget()

        if current_widget == self.tab_overview:
            self.update_cpu_data(self.ov_cpu_filter, self.ov_cpu_table)
            self.update_mem_data(self.ov_mem_filter, self.ov_mem_table)
            self.update_disk_data(self.ov_disk_filter, self.ov_disk_table)
            self.update_net_data(self.ov_net_filter, self.ov_net_table)
        elif current_widget == self.tab_cpu:
            self.update_cpu_data(self.cpu_filter, self.cpu_table)
        elif current_widget == self.tab_mem:
            self.update_mem_data(self.mem_filter, self.mem_table)
        elif current_widget == self.tab_disk:
            self.update_disk_data(self.disk_filter, self.disk_table)
        elif current_widget == self.tab_net:
            self.update_net_data(self.net_filter, self.net_table)

    # --- UPDATE DATA LOGIC ---
    def update_cpu_data(self, flt, tbl):
        tbl.setSortingEnabled(False)
        filter_text = flt.text().lower()
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

        tbl.setRowCount(len(procs))
        for row, (name, pid, cpu_pct, threads, status) in enumerate(procs):
            tbl.setItem(row, 0, QTableWidgetItem(name))
            tbl.setItem(row, 1, NumericTableWidgetItem(str(pid), pid))
            tbl.setItem(row, 2, NumericTableWidgetItem(f"{cpu_pct:.1f}%", cpu_pct))
            tbl.setItem(row, 3, NumericTableWidgetItem(str(threads), threads))
            tbl.setItem(row, 4, QTableWidgetItem(status))

        tbl.setSortingEnabled(True)

    def update_mem_data(self, flt, tbl):
        tbl.setSortingEnabled(False)
        filter_text = flt.text().lower()
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

        tbl.setRowCount(len(procs))
        for row, (name, pid, rss, mem_pct, vms) in enumerate(procs):
            tbl.setItem(row, 0, QTableWidgetItem(name))
            tbl.setItem(row, 1, NumericTableWidgetItem(str(pid), pid))
            tbl.setItem(row, 2, NumericTableWidgetItem(self.format_bytes(rss), rss))
            tbl.setItem(row, 3, NumericTableWidgetItem(f"{mem_pct:.2f}%", mem_pct))
            tbl.setItem(row, 4, NumericTableWidgetItem(self.format_bytes(vms), vms))

        tbl.setSortingEnabled(True)

    def update_disk_data(self, flt, tbl):
        tbl.setSortingEnabled(False)
        filter_text = flt.text().lower()
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

        tbl.setRowCount(len(active_processes))
        for row, (name, pid, r_rate, w_rate, total_rate) in enumerate(active_processes):
            tbl.setItem(row, 0, QTableWidgetItem(name))
            tbl.setItem(row, 1, NumericTableWidgetItem(str(pid), pid))
            tbl.setItem(row, 2, NumericTableWidgetItem(self.format_rate(r_rate), r_rate))
            tbl.setItem(row, 3, NumericTableWidgetItem(self.format_rate(w_rate), w_rate))
            tbl.setItem(row, 4, NumericTableWidgetItem(self.format_rate(total_rate), total_rate))

        tbl.setSortingEnabled(True)

    def update_net_data(self, flt, tbl):
        tbl.setSortingEnabled(False)
        filter_text = flt.text().lower()
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

        tbl.setRowCount(len(connections))
        for row, (name, pid, laddr, raddr, status, proto) in enumerate(connections):
            tbl.setItem(row, 0, QTableWidgetItem(name))
            tbl.setItem(row, 1, NumericTableWidgetItem(str(pid), pid))
            tbl.setItem(row, 2, QTableWidgetItem(laddr))
            tbl.setItem(row, 3, QTableWidgetItem(raddr))
            tbl.setItem(row, 4, QTableWidgetItem(status))
            tbl.setItem(row, 5, QTableWidgetItem(proto))

        tbl.setSortingEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ResMonLinux()
    window.show()
    sys.exit(app.exec())