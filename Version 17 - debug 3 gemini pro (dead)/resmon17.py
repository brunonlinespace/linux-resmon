#!/usr/bin/env python3
#
# ResMon Linux - A lightweight resource monitor
# Copyright (C) 2026 ResMon Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import sys
import time
import psutil

from PyQt6.QtCore import QTimer, Qt, QSettings, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QSplitter, QGroupBox, QPushButton, QLabel
)

# Dark Mode Stylesheet (QSS)
DARK_STYLESHEET = """
QMainWindow, QWidget { background-color: #1e1e1e; color: #dcdcdc; font-family: "Segoe UI", Ubuntu, sans-serif; font-size: 10pt; }
QTabWidget::pane { border: 1px solid #333333; background-color: #1e1e1e; }
QTabBar::tab { background-color: #2d2d2d; color: #aaaaaa; padding: 8px 16px; border: 1px solid #333333; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }
QTabBar::tab:selected { background-color: #007acc; color: #ffffff; font-weight: bold; }
QTabBar::tab:hover:!selected { background-color: #3e3e42; color: #ffffff; }
QGroupBox { border: 1px solid #333333; border-radius: 6px; margin-top: 6px; padding-top: 10px; background-color: #252526; }
QLineEdit { background-color: #333333; color: #ffffff; border: 1px solid #454545; border-radius: 4px; padding: 4px 8px; selection-background-color: #007acc; }
QLineEdit:focus { border: 1px solid #007acc; }
QTableWidget { background-color: #1e1e1e; color: #dcdcdc; gridline-color: #2d2d2d; border: 1px solid #333333; border-radius: 4px; }
QTableWidget::item:selected { background-color: #094771; color: #ffffff; }
QHeaderView::section { background-color: #2d2d2d; color: #ffffff; padding: 5px; border: 1px solid #333333; font-weight: bold; }
QPushButton { background-color: #333333; color: #ffffff; border: 1px solid #454545; border-radius: 3px; padding: 4px 8px; }
QPushButton:hover { background-color: #007acc; border-color: #007acc; }
QPushButton:pressed { background-color: #005999; }
QSplitter::handle { background-color: #2d2d2d; height: 3px; }
QScrollBar:vertical, QScrollBar:horizontal { background: #1e1e1e; border: none; width: 10px; height: 10px; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal { background: #424242; border-radius: 5px; }
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover { background: #686868; }
"""

# Light Mode Stylesheet (QSS)
LIGHT_STYLESHEET = """
QMainWindow, QWidget { background-color: #f0f0f0; color: #333333; font-family: "Segoe UI", Ubuntu, sans-serif; font-size: 10pt; }
QTabWidget::pane { border: 1px solid #cccccc; background-color: #ffffff; }
QTabBar::tab { background-color: #e0e0e0; color: #333333; padding: 8px 16px; border: 1px solid #cccccc; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }
QTabBar::tab:selected { background-color: #ffffff; color: #000000; font-weight: bold; border-bottom: 1px solid #ffffff; }
QTabBar::tab:hover:!selected { background-color: #d0d0d0; }
QGroupBox { border: 1px solid #cccccc; border-radius: 6px; margin-top: 6px; padding-top: 10px; background-color: #f9f9f9; }
QLineEdit { background-color: #ffffff; color: #333333; border: 1px solid #aaaaaa; border-radius: 4px; padding: 4px 8px; selection-background-color: #007acc; selection-color: #ffffff; }
QLineEdit:focus { border: 1px solid #007acc; }
QTableWidget { background-color: #ffffff; color: #333333; gridline-color: #dddddd; border: 1px solid #cccccc; border-radius: 4px; }
QTableWidget::item:selected { background-color: #007acc; color: #ffffff; }
QHeaderView::section { background-color: #e0e0e0; color: #333333; padding: 5px; border: 1px solid #cccccc; font-weight: bold; }
QPushButton { background-color: #e0e0e0; color: #333333; border: 1px solid #aaaaaa; border-radius: 3px; padding: 4px 8px; }
QPushButton:hover { background-color: #d0d0d0; border-color: #888888; }
QPushButton:pressed { background-color: #c0c0c0; }
QSplitter::handle { background-color: #cccccc; height: 3px; }
QScrollBar:vertical, QScrollBar:horizontal { background: #f0f0f0; border: none; width: 10px; height: 10px; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal { background: #aaaaaa; border-radius: 5px; }
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover { background: #888888; }
"""

class NumericTableWidgetItem(QTableWidgetItem):
    def __init__(self, text, raw_val=0):
        super().__init__(text)
        self.raw_val = raw_val
    def __lt__(self, other):
        if isinstance(other, NumericTableWidgetItem):
            return self.raw_val < other.raw_val
        return super().__lt__(other)


class SystemDataWorker(QThread):
    """Background thread to fetch system data without blocking the GUI."""
    data_ready = pyqtSignal(list, list)

    def __init__(self):
        super().__init__()
        self.running = True
        self.prev_io = {}

    def format_addr(self, addr):
        if not addr: return ""
        try:
            if hasattr(addr, 'ip') and hasattr(addr, 'port'): return f"{addr.ip}:{addr.port}"
            elif isinstance(addr, (tuple, list)) and len(addr) >= 2: return f"{addr[0]}:{addr[1]}"
            return str(addr)
        except Exception:
            return "Unknown"

    def run(self):
        while self.running:
            active_processes = []
            connections = []
            now = time.time()
            
            # 1. Fetch Process Data (CPU, Memory, Disk) in a single optimized pass
            # We use process_iter to fetch all required fields efficiently
            proc_attributes = ['pid', 'name', 'cpu_percent', 'num_threads', 'status', 'memory_info', 'io_counters']
            
            current_pids = set()

            for proc in psutil.process_iter(attrs=proc_attributes):
                try:
                    pinfo = proc.info
                    pid = pinfo['pid']
                    current_pids.add(pid)
                    
                    # Disk I/O delta calculation
                    r_rate = 0
                    w_rate = 0
                    if pinfo['io_counters']:
                        read_bytes = pinfo['io_counters'].read_bytes
                        write_bytes = pinfo['io_counters'].write_bytes
                        if pid in self.prev_io:
                            old_read, old_write, old_time = self.prev_io[pid]
                            dt = now - old_time
                            r_rate = max(0, (read_bytes - old_read) / dt) if dt > 0 else 0
                            w_rate = max(0, (write_bytes - old_write) / dt) if dt > 0 else 0
                        self.prev_io[pid] = (read_bytes, write_bytes, now)

                    proc_data = {
                        'pid': pid,
                        'name': pinfo['name'] or "Unknown",
                        'cpu': pinfo['cpu_percent'] or 0.0,
                        'threads': pinfo['num_threads'] or 0,
                        'status': pinfo['status'] or "Unknown",
                        'rss': pinfo['memory_info'].rss if pinfo['memory_info'] else 0,
                        'vms': pinfo['memory_info'].vms if pinfo['memory_info'] else 0,
                        'mem_pct': proc.memory_percent() if pinfo['memory_info'] else 0.0,
                        'r_rate': r_rate,
                        'w_rate': w_rate,
                        'total_rate': r_rate + w_rate
                    }
                    active_processes.append(proc_data)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass

            # Cleanup dead processes from IO cache
            dead_pids = set(self.prev_io.keys()) - current_pids
            for dead_pid in dead_pids:
                del self.prev_io[dead_pid]

            # 2. Fetch Network Connections
            try:
                for conn in psutil.net_connections(kind='inet'):
                    if not getattr(conn, 'raddr', None): continue
                    
                    pid = conn.pid
                    name = "System/Kernel"
                    
                    if pid:
                        # Find name from our already cached process list
                        match = next((p['name'] for p in active_processes if p['pid'] == pid), None)
                        if match: name = match
                        else: name = "Access Denied"

                    connections.append({
                        'name': name,
                        'pid': pid or 0,
                        'laddr': self.format_addr(conn.laddr),
                        'raddr': self.format_addr(conn.raddr),
                        'status': getattr(conn, 'status', 'NONE'),
                        'proto': "TCP" if conn.type == 1 else "UDP"
                    })
            except psutil.AccessDenied:
                # Graceful degradation on Linux without root privileges.
                pass 
            except Exception:
                pass

            # Send batch data back to main thread
            self.data_ready.emit(active_processes, connections)
            
            # Sleep outside of GUI thread
            time.sleep(1.0) 

    def stop(self):
        self.running = False
        self.wait()


class ResMonLinux(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Resource Monitor (ResMon) - Fedora Edition")
        self.resize(1200, 850)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.tabs = QTabWidget()
        self.tabs.setMovable(True)
        
        # Add Theme Switcher to Corner of Tabs
        self.btn_theme = QPushButton()
        self.btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme.clicked.connect(self.toggle_theme)
        self.tabs.setCornerWidget(self.btn_theme, Qt.Corner.TopRightCorner)
        self.is_dark_mode = True

        self.layout.addWidget(self.tabs)

        self.ov_boxes = {} # To keep references to overview boxes for re-ordering

        # Build UI Tabs
        self.setup_overview_tab()
        self.setup_cpu_tab()
        self.setup_mem_tab()
        self.setup_disk_tab()
        self.setup_net_tab()

        # Restore Settings (Includes initial Theme application)
        self.restore_settings()

        # Start Background Data Fetcher
        self.worker = SystemDataWorker()
        self.worker.data_ready.connect(self.on_data_ready)
        self.worker.start()

        # Wire up filters to trigger instantaneous visual update on currently cached data
        self.latest_procs = []
        self.latest_conns = []
        
        self.ov_cpu_filter.textChanged.connect(self.refresh_ui)
        self.ov_mem_filter.textChanged.connect(self.refresh_ui)
        self.ov_disk_filter.textChanged.connect(self.refresh_ui)
        self.ov_net_filter.textChanged.connect(self.refresh_ui)
        
        self.cpu_filter.textChanged.connect(self.refresh_ui)
        self.mem_filter.textChanged.connect(self.refresh_ui)
        self.disk_filter.textChanged.connect(self.refresh_ui)
        self.net_filter.textChanged.connect(self.refresh_ui)
        
        self.tabs.currentChanged.connect(self.refresh_ui)

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.apply_theme()

    def apply_theme(self):
        app = QApplication.instance()
        if self.is_dark_mode:
            app.setStyleSheet(DARK_STYLESHEET)
            self.btn_theme.setText("☀️ Light Mode")
        else:
            app.setStyleSheet(LIGHT_STYLESHEET)
            self.btn_theme.setText("🌙 Dark Mode")

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

        if splitter is not None:
            btn_up = QPushButton("▲ Up")
            btn_up.setFixedWidth(70)
            btn_up.clicked.connect(lambda: self.move_panel(splitter, group_box, -1))
            
            btn_down = QPushButton("▼ Down")
            btn_down.setFixedWidth(70)
            btn_down.clicked.connect(lambda: self.move_panel(splitter, group_box, 1))
            
            header_layout.addWidget(btn_up)
            header_layout.addWidget(btn_down)

        return header_layout

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

    def setup_overview_tab(self):
        self.tab_overview = QWidget()
        layout = QVBoxLayout(self.tab_overview)
        self.overview_splitter = QSplitter(Qt.Orientation.Vertical)
        
        cpu_box, self.ov_cpu_filter, self.ov_cpu_table = self.create_cpu_widget(self.overview_splitter)
        mem_box, self.ov_mem_filter, self.ov_mem_table = self.create_mem_widget(self.overview_splitter)
        disk_box, self.ov_disk_filter, self.ov_disk_table = self.create_disk_widget(self.overview_splitter)
        net_box, self.ov_net_filter, self.ov_net_table = self.create_net_widget(self.overview_splitter)

        cpu_box.setObjectName("cpu_box")
        mem_box.setObjectName("mem_box")
        disk_box.setObjectName("disk_box")
        net_box.setObjectName("net_box")

        self.ov_boxes = {
            "cpu_box": cpu_box,
            "mem_box": mem_box,
            "disk_box": disk_box,
            "net_box": net_box
        }

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
        layout.addWidget(cpu_box)
        self.tabs.addTab(self.tab_cpu, "CPU")

    def setup_mem_tab(self):
        self.tab_mem = QWidget()
        layout = QVBoxLayout(self.tab_mem)
        mem_box, self.mem_filter, self.mem_table = self.create_mem_widget()
        layout.addWidget(mem_box)
        self.tabs.addTab(self.tab_mem, "Memory")

    def setup_disk_tab(self):
        self.tab_disk = QWidget()
        layout = QVBoxLayout(self.tab_disk)
        disk_box, self.disk_filter, self.disk_table = self.create_disk_widget()
        layout.addWidget(disk_box)
        self.tabs.addTab(self.tab_disk, "Disk")

    def setup_net_tab(self):
        self.tab_net = QWidget()
        layout = QVBoxLayout(self.tab_net)
        net_box, self.net_filter, self.net_table = self.create_net_widget()
        layout.addWidget(net_box)
        self.tabs.addTab(self.tab_net, "Network")

    # --- SETTINGS / STATE MANAGEMENT ---
    def restore_settings(self):
        settings = QSettings("ResMonContributors", "ResMonLinux")

        if settings.contains("geometry"):
            self.restoreGeometry(settings.value("geometry"))

        if settings.contains("isDarkMode"):
            self.is_dark_mode = settings.value("isDarkMode", True, type=bool)
        self.apply_theme()

        if settings.contains("tabOrder"):
            saved_tab_order = settings.value("tabOrder")
            if isinstance(saved_tab_order, list):
                for i, tab_name in enumerate(saved_tab_order):
                    for j in range(self.tabs.count()):
                        if self.tabs.tabText(j) == tab_name:
                            self.tabs.tabBar().moveTab(j, i)
                            break

        if settings.contains("currentTab"):
            self.tabs.setCurrentIndex(settings.value("currentTab", 0, type=int))

        if settings.contains("panelOrder"):
            panel_order = settings.value("panelOrder")
            if isinstance(panel_order, list) and len(panel_order) == 4:
                for name in panel_order:
                    if name in self.ov_boxes:
                        self.overview_splitter.addWidget(self.ov_boxes[name])
        
        if settings.contains("splitterState"):
            self.overview_splitter.restoreState(settings.value("splitterState"))

    def closeEvent(self, event):
        self.worker.stop() # Gracefully kill the background thread
        settings = QSettings("ResMonContributors", "ResMonLinux")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("isDarkMode", self.is_dark_mode)
        settings.setValue("tabOrder", [self.tabs.tabText(i) for i in range(self.tabs.count())])
        settings.setValue("currentTab", self.tabs.currentIndex())
        settings.setValue("panelOrder", [self.overview_splitter.widget(i).objectName() for i in range(self.overview_splitter.count())])
        settings.setValue("splitterState", self.overview_splitter.saveState())
        super().closeEvent(event)

    # --- FORMATTING HELPERS ---
    def format_bytes(self, num_bytes):
        if num_bytes < 1024: return f"{num_bytes} B"
        elif num_bytes < 1048576: return f"{num_bytes / 1024:.1f} KB"
        elif num_bytes < 1073741824: return f"{num_bytes / 1048576:.1f} MB"
        else: return f"{num_bytes / 1073741824:.2f} GB"

    def format_rate(self, bytes_per_sec):
        return f"{self.format_bytes(bytes_per_sec)}/s"

    def update_cell(self, tbl, row, col, text, raw_val=None):
        item = tbl.item(row, col)
        if raw_val is not None:
            if isinstance(item, NumericTableWidgetItem):
                item.setText(text)
                item.raw_val = raw_val
            else:
                tbl.setItem(row, col, NumericTableWidgetItem(text, raw_val))
        else:
            if item:
                item.setText(text)
            else:
                tbl.setItem(row, col, QTableWidgetItem(text))

    # --- DATA ROUTING ---
    def on_data_ready(self, active_processes, connections):
        """Slot triggered safely on GUI thread when worker completes a loop."""
        self.latest_procs = active_processes
        self.latest_conns = connections
        self.refresh_ui()

    def refresh_ui(self):
        """Redraws only the currently visible tables using pre-cached data."""
        if not self.latest_procs: return # Wait for first fetch

        current_widget = self.tabs.currentWidget()
        if current_widget == self.tab_overview:
            self.update_cpu_data(self.ov_cpu_filter, self.ov_cpu_table)
            self.update_mem_data(self.ov_mem_filter, self.ov_mem_table)
            self.update_disk_data(self.ov_disk_filter, self.ov_disk_table)
            self.update_net_data(self.ov_net_filter, self.ov_net_table)
        elif current_widget == self.tab_cpu: self.update_cpu_data(self.cpu_filter, self.cpu_table)
        elif current_widget == self.tab_mem: self.update_mem_data(self.mem_filter, self.mem_table)
        elif current_widget == self.tab_disk: self.update_disk_data(self.disk_filter, self.disk_table)
        elif current_widget == self.tab_net: self.update_net_data(self.net_filter, self.net_table)

    def update_cpu_data(self, flt, tbl):
        v_scroll = tbl.verticalScrollBar().value()
        tbl.setSortingEnabled(False)
        filter_text = flt.text().lower()
        
        filtered = [p for p in self.latest_procs if (p['cpu'] > 0 or not filter_text) and 
                   (not filter_text or filter_text in p['name'].lower() or filter_text in str(p['pid']))]

        tbl.setRowCount(len(filtered))
        for row, p in enumerate(filtered):
            self.update_cell(tbl, row, 0, p['name'])
            self.update_cell(tbl, row, 1, str(p['pid']), p['pid'])
            self.update_cell(tbl, row, 2, f"{p['cpu']:.1f}%", p['cpu'])
            self.update_cell(tbl, row, 3, str(p['threads']), p['threads'])
            self.update_cell(tbl, row, 4, p['status'])

        tbl.setSortingEnabled(True)
        tbl.verticalScrollBar().setValue(v_scroll)

    def update_mem_data(self, flt, tbl):
        v_scroll = tbl.verticalScrollBar().value()
        tbl.setSortingEnabled(False)
        filter_text = flt.text().lower()

        filtered = [p for p in self.latest_procs if (p['rss'] > 1048576 or not filter_text) and 
                   (not filter_text or filter_text in p['name'].lower() or filter_text in str(p['pid']))]

        tbl.setRowCount(len(filtered))
        for row, p in enumerate(filtered):
            self.update_cell(tbl, row, 0, p['name'])
            self.update_cell(tbl, row, 1, str(p['pid']), p['pid'])
            self.update_cell(tbl, row, 2, self.format_bytes(p['rss']), p['rss'])
            self.update_cell(tbl, row, 3, f"{p['mem_pct']:.2f}%", p['mem_pct'])
            self.update_cell(tbl, row, 4, self.format_bytes(p['vms']), p['vms'])

        tbl.setSortingEnabled(True)
        tbl.verticalScrollBar().setValue(v_scroll)

    def update_disk_data(self, flt, tbl):
        v_scroll = tbl.verticalScrollBar().value()
        tbl.setSortingEnabled(False)
        filter_text = flt.text().lower()

        filtered = [p for p in self.latest_procs if (p['total_rate'] > 0 or not filter_text) and 
                   (not filter_text or filter_text in p['name'].lower() or filter_text in str(p['pid']))]

        tbl.setRowCount(len(filtered))
        for row, p in enumerate(filtered):
            self.update_cell(tbl, row, 0, p['name'])
            self.update_cell(tbl, row, 1, str(p['pid']), p['pid'])
            self.update_cell(tbl, row, 2, self.format_rate(p['r_rate']), p['r_rate'])
            self.update_cell(tbl, row, 3, self.format_rate(p['w_rate']), p['w_rate'])
            self.update_cell(tbl, row, 4, self.format_rate(p['total_rate']), p['total_rate'])

        tbl.setSortingEnabled(True)
        tbl.verticalScrollBar().setValue(v_scroll)

    def update_net_data(self, flt, tbl):
        v_scroll = tbl.verticalScrollBar().value()
        tbl.setSortingEnabled(False)
        filter_text = flt.text().lower()

        filtered = []
        for c in self.latest_conns:
            search_target = f"{c['name']} {c['pid']} {c['laddr']} {c['raddr']} {c['status']} {c['proto']}".lower()
            if not filter_text or filter_text in search_target:
                filtered.append(c)

        tbl.setRowCount(len(filtered))
        for row, c in enumerate(filtered):
            self.update_cell(tbl, row, 0, c['name'])
            self.update_cell(tbl, row, 1, str(c['pid']), c['pid'])
            self.update_cell(tbl, row, 2, c['laddr'])
            self.update_cell(tbl, row, 3, c['raddr'])
            self.update_cell(tbl, row, 4, c['status'])
            self.update_cell(tbl, row, 5, c['proto'])

        tbl.setSortingEnabled(True)
        tbl.verticalScrollBar().setValue(v_scroll)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ResMonLinux()
    window.show()
    sys.exit(app.exec())