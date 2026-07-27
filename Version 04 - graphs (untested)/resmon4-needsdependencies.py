#!/usr/bin/env python3
import sys
import time
import sqlite3
import psutil
from collections import deque
from datetime import datetime

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QPushButton, QSplitter, QGroupBox
)
import pyqtgraph as pg

# Configure PyQtGraph global styling
pg.setConfigOption('background', '#1e1e1e')
pg.setConfigOption('foreground', '#dcdcdc')

DB_FILE = "resmon_history.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS disk_history (
            timestamp TEXT, pid INTEGER, name TEXT, read_rate_bps REAL, write_rate_bps REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS net_history (
            timestamp TEXT, pid INTEGER, name TEXT, local_addr TEXT, remote_addr TEXT, status TEXT, protocol TEXT
        )
    ''')
    conn.commit()
    conn.close()

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
        self.resize(1280, 800)

        init_db()

        # Ring buffers for 60 seconds of historical graph data
        self.history_len = 60
        self.disk_time_data = deque(maxlen=self.history_len)
        self.disk_rate_data = deque(maxlen=self.history_len)
        self.net_time_data = deque(maxlen=self.history_len)
        self.net_conn_data = deque(maxlen=self.history_len)

        for i in range(self.history_len):
            self.disk_time_data.append(-self.history_len + i)
            self.disk_rate_data.append(0.0)
            self.net_time_data.append(-self.history_len + i)
            self.net_conn_data.append(0)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.main_tabs = QTabWidget()
        self.main_layout.addWidget(self.main_tabs)

        # Tab 1: Live Overview (Tables + Real-time Graphs)
        self.live_view_widget = QWidget()
        self.setup_live_view()
        self.main_tabs.addTab(self.live_view_widget, "Live Overview (Disk + Network)")

        # Tab 2: History & Logs
        self.hist_tab = QWidget()
        self.setup_history_tab()
        self.main_tabs.addTab(self.hist_tab, "History & Logs")

        self.prev_io = {}

        # 1 second refresh timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_live_data)
        self.timer.start(1000)

        self.refresh_live_data()

    def setup_live_view(self):
        layout = QVBoxLayout(self.live_view_widget)

        # Main horizontal splitter: Left = Tables, Right = Real-Time Graphs
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- LEFT SIDE: TABLES ---
        left_splitter = QSplitter(Qt.Orientation.Vertical)

        # 1. Disk Table Panel
        disk_box = QGroupBox("Disk Activity")
        disk_layout = QVBoxLayout(disk_box)
        self.disk_filter = QLineEdit()
        self.disk_filter.setPlaceholderText("Filter disk activity by Process or PID...")
        self.disk_filter.textChanged.connect(self.update_disk_data)
        self.disk_table = QTableWidget(0, 5)
        self.disk_table.setHorizontalHeaderLabels(["Process Name", "PID", "Read Rate", "Write Rate", "Total I/O Rate"])
        self.disk_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.disk_table.setSortingEnabled(True)
        disk_layout.addWidget(self.disk_filter)
        disk_layout.addWidget(self.disk_table)

        # 2. Network Table Panel
        net_box = QGroupBox("Network Connections")
        net_layout = QVBoxLayout(net_box)
        self.net_filter = QLineEdit()
        self.net_filter.setPlaceholderText("Filter network connections by Process, IP, Port...")
        self.net_filter.textChanged.connect(self.update_net_data)
        self.net_table = QTableWidget(0, 6)
        self.net_table.setHorizontalHeaderLabels(["Process Name", "PID", "Local Address", "Remote Address", "Status", "Protocol"])
        self.net_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.net_table.setSortingEnabled(True)
        net_layout.addWidget(self.net_filter)
        net_layout.addWidget(self.net_table)

        left_splitter.addWidget(disk_box)
        left_splitter.addWidget(net_box)

        # --- RIGHT SIDE: GRAPHS ---
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        # 1. Disk Graph Box
        disk_graph_box = QGroupBox("Real-Time Disk Activity (Total System I/O)")
        disk_graph_layout = QVBoxLayout(disk_graph_box)
        self.disk_plot_widget = pg.PlotWidget()
        self.disk_plot_widget.setLabel('left', 'I/O Rate (MB/s)')
        self.disk_plot_widget.setLabel('bottom', 'Seconds Ago')
        self.disk_plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.disk_curve = self.disk_plot_widget.plot(
            list(self.disk_time_data), list(self.disk_rate_data),
            pen=pg.mkPen(color='#ff5555', width=2), fillLevel=0, fillBrush=(255, 85, 85, 50)
        )
        disk_graph_layout.addWidget(self.disk_plot_widget)

        # 2. Network Graph Box
        net_graph_box = QGroupBox("Real-Time Network Activity (Active Sockets)")
        net_graph_layout = QVBoxLayout(net_graph_box)
        self.net_plot_widget = pg.PlotWidget()
        self.net_plot_widget.setLabel('left', 'Active Connections')
        self.net_plot_widget.setLabel('bottom', 'Seconds Ago')
        self.net_plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.net_curve = self.net_plot_widget.plot(
            list(self.net_time_data), list(self.net_conn_data),
            pen=pg.mkPen(color='#50fa7b', width=2), fillLevel=0, fillBrush=(80, 250, 123, 50)
        )
        net_graph_layout.addWidget(self.net_plot_widget)

        right_splitter.addWidget(disk_graph_box)
        right_splitter.addWidget(net_graph_box)

        # Add Left (Tables) and Right (Graphs) to Main Splitter
        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(right_splitter)

        # Set 60/40 width ratio between tables and graphs
        main_splitter.setSizes([750, 450])
        layout.addWidget(main_splitter)

    def setup_history_tab(self):
        layout = QVBoxLayout(self.hist_tab)
        controls = QHBoxLayout()

        self.hist_filter = QLineEdit()
        self.hist_filter.setPlaceholderText("Search history logs (e.g., 'firefox' or IP address)...")
        btn_search = QPushButton("Query Logs")
        btn_search.clicked.connect(self.query_history)

        controls.addWidget(self.hist_filter)
        controls.addWidget(btn_search)

        self.hist_table = QTableWidget(0, 6)
        self.hist_table.setHorizontalHeaderLabels(["Timestamp", "Type", "Process", "PID", "Details / Address", "Rate / Status"])
        self.hist_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.hist_table.setSortingEnabled(True)

        layout.addLayout(controls)
        layout.addWidget(self.hist_table)

    def format_rate(self, bytes_per_sec):
        if bytes_per_sec < 1024:
            return f"{bytes_per_sec:.0f} B/s"
        elif bytes_per_sec < 1024 * 1024:
            return f"{bytes_per_sec / 1024:.1f} KB/s"
        else:
            return f"{bytes_per_sec / (1024 * 1024):.2f} MB/s"

    def refresh_live_data(self):
        if self.main_tabs.currentIndex() == 0:
            total_disk_bps = self.update_disk_data()
            active_sockets_count = self.update_net_data()

            # Update Graphs
            self.disk_rate_data.append(total_disk_bps / (1024 * 1024))  # Convert B/s to MB/s
            self.net_conn_data.append(active_sockets_count)

            self.disk_curve.setData(list(self.disk_time_data), list(self.disk_rate_data))
            self.net_curve.setData(list(self.net_time_data), list(self.net_conn_data))

    def update_disk_data(self):
        self.disk_table.setSortingEnabled(False)
        filter_text = self.disk_filter.text().lower()
        active_processes = []
        now = time.time()
        iso_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db_records = []
        total_system_disk_rate = 0.0

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
                total_system_disk_rate += total_rate

                if total_rate > 0:
                    db_records.append((iso_time, pid, name, r_rate, w_rate))

                if total_rate > 0 or (filter_text and (filter_text in name.lower() or filter_text in str(pid))):
                    if not filter_text or (filter_text in name.lower() or filter_text in str(pid)):
                        active_processes.append((name, pid, r_rate, w_rate, total_rate))

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if db_records:
            conn = sqlite3.connect(DB_FILE)
            conn.executemany("INSERT INTO disk_history VALUES (?,?,?,?,?)", db_records)
            conn.commit()
            conn.close()

        self.disk_table.setRowCount(len(active_processes))
        for row, (name, pid, r_rate, w_rate, total_rate) in enumerate(active_processes):
            self.disk_table.setItem(row, 0, QTableWidgetItem(name))
            self.disk_table.setItem(row, 1, NumericTableWidgetItem(str(pid), pid))
            self.disk_table.setItem(row, 2, NumericTableWidgetItem(self.format_rate(r_rate), r_rate))
            self.disk_table.setItem(row, 3, NumericTableWidgetItem(self.format_rate(w_rate), w_rate))
            self.disk_table.setItem(row, 4, NumericTableWidgetItem(self.format_rate(total_rate), total_rate))

        self.disk_table.setSortingEnabled(True)
        return total_system_disk_rate

    def update_net_data(self):
        self.net_table.setSortingEnabled(False)
        filter_text = self.net_filter.text().lower()
        connections = []
        db_records = []
        iso_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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

                db_records.append((iso_time, pid or 0, name, laddr, raddr, status, proto))

                search_target = f"{name} {pid} {laddr} {raddr} {status} {proto}".lower()
                if not filter_text or filter_text in search_target:
                    connections.append((name, pid or 0, laddr, raddr, status, proto))

        except psutil.AccessDenied:
            pass

        if db_records:
            conn = sqlite3.connect(DB_FILE)
            conn.executemany("INSERT INTO net_history VALUES (?,?,?,?,?,?,?)", db_records)
            conn.commit()
            conn.close()

        self.net_table.setRowCount(len(connections))
        for row, (name, pid, laddr, raddr, status, proto) in enumerate(connections):
            self.net_table.setItem(row, 0, QTableWidgetItem(name))
            self.net_table.setItem(row, 1, NumericTableWidgetItem(str(pid), pid))
            self.net_table.setItem(row, 2, QTableWidgetItem(laddr))
            self.net_table.setItem(row, 3, QTableWidgetItem(raddr))
            self.net_table.setItem(row, 4, QTableWidgetItem(status))
            self.net_table.setItem(row, 5, QTableWidgetItem(proto))

        self.net_table.setSortingEnabled(True)
        return len(connections)

    def query_history(self):
        self.hist_table.setSortingEnabled(False)
        query_text = f"%{self.hist_filter.text().lower()}%"

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT timestamp, 'Disk', name, pid, 'Read/Write',
                   PRINTF('%.1f KB/s', (read_rate_bps + write_rate_bps)/1024)
            FROM disk_history
            WHERE LOWER(name) LIKE ? OR CAST(pid AS TEXT) LIKE ?
            ORDER BY timestamp DESC LIMIT 200
        ''', (query_text, query_text))
        disk_logs = cursor.fetchall()

        cursor.execute('''
            SELECT timestamp, 'Network', name, pid, remote_addr, status
            FROM net_history
            WHERE LOWER(name) LIKE ? OR CAST(pid AS TEXT) LIKE ? OR LOWER(remote_addr) LIKE ?
            ORDER BY timestamp DESC LIMIT 200
        ''', (query_text, query_text, query_text))
        net_logs = cursor.fetchall()

        conn.close()

        all_logs = sorted(disk_logs + net_logs, key=lambda x: x[0], reverse=True)

        self.hist_table.setRowCount(len(all_logs))
        for row, (ts, log_type, name, pid, details, val) in enumerate(all_logs):
            self.hist_table.setItem(row, 0, QTableWidgetItem(ts))
            self.hist_table.setItem(row, 1, QTableWidgetItem(log_type))
            self.hist_table.setItem(row, 2, QTableWidgetItem(name))
            self.hist_table.setItem(row, 3, NumericTableWidgetItem(str(pid), pid))
            self.hist_table.setItem(row, 4, QTableWidgetItem(details))
            self.hist_table.setItem(row, 5, QTableWidgetItem(str(val)))

        self.hist_table.setSortingEnabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ResMonLinux()
    window.show()
    sys.exit(app.exec())
