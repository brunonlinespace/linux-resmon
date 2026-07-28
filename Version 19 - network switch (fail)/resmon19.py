#!/usr/bin/env python3
#
# ResMon Linux - A lightweight resource monitor
# Copyright (C) 2026 ResMon Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import sys
import time
import psutil

from PyQt6.QtCore import QTimer, Qt, QSettings
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
        
        self.btn_theme = QPushButton()
        self.btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme.clicked.connect(self.toggle_theme)
        self.tabs.setCornerWidget(self.btn_theme, Qt.Corner.TopRightCorner)
        self.is_dark_mode = True

        self.layout.addWidget(self.tabs)
        self.tabs.currentChanged.connect(lambda: self.refresh_data())

        self.prev_io = {}
        self.prev_net_io = {} # Tracker for network I/O rates[cite: 1]
        self.proc_cache = {} 
        self.ov_boxes = {} 
        
        # State to track the current network view[cite: 1, 2]
        self.net_view_mode = "interfaces" 
        self.net_toggle_buttons = [] # Keep track of both overview and tab buttons

        self.setup_overview_tab()
        self.setup_cpu_tab()
        self.setup_mem_tab()
        self.setup_disk_tab()
        self.setup_net_tab()

        self.get_active_processes()
        self.restore_settings()

        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(1000)

        self.refresh_data()

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

    def toggle_network_view(self):
        """Switches between interface metrics and process connection list."""
        if self.net_view_mode == "interfaces":
            self.net_view_mode = "processes"
            btn_text = "View: Processes"
        else:
            self.net_view_mode = "interfaces"
            btn_text = "View: Interfaces"

        # Update text on all toggle buttons
        for btn in self.net_toggle_buttons:
            btn.setText(btn_text)

        # Clear and re-initialize both network tables with correct columns[cite: 1, 2]
        for tbl in [self.ov_net_table, self.net_table]:
            tbl.clear()
            if self.net_view_mode == "interfaces":
                tbl.setColumnCount(5)
                tbl.setHorizontalHeaderLabels(["Interface", "Upload Rate", "Download Rate", "Total Uploaded", "Total Downloaded"])
            else:
                tbl.setColumnCount(6)
                tbl.setHorizontalHeaderLabels(["Process Name", "PID", "Local Address", "Remote Address", "Status", "Protocol"])
            tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.refresh_data()

    def get_active_processes(self):
        current_pids = set(psutil.pids())
        dead_pids = set(self.proc_cache.keys()) - current_pids
        for pid in dead_pids:
            del self.proc_cache[pid]
            if pid in self.prev_io:
                del self.prev_io[pid]

        active_procs = []
        for pid in list(current_pids):
            if pid not in self.proc_cache:
                try:
                    self.proc_cache[pid] = psutil.Process(pid)
                    self.proc_cache[pid].cpu_percent()
                except (psutil.Error, OSError):
                    continue
            active_procs.append((pid, self.proc_cache[pid]))
        return active_procs

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
        
        # Build custom header with the toggle button
        header_layout = self.create_panel_header("Network Activity", box, splitter)
        btn_toggle = QPushButton("View: Interfaces")
        btn_toggle.clicked.connect(self.toggle_network_view)
        self.net_toggle_buttons.append(btn_toggle)
        header_layout.insertWidget(2, btn_toggle) 
        
        layout.addLayout(header_layout)
        
        flt = QLineEdit()
        flt.setPlaceholderText("Filter Network (Interface, Process, IP, etc)...")
        
        tbl = QTableWidget(0, 5)
        tbl.setHorizontalHeaderLabels(["Interface", "Upload Rate", "Download Rate", "Total Uploaded", "Total Downloaded"])
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

    # --- SETTINGS / STATE MANAGEMENT ---
    def restore_settings(self):
        settings = QSettings("ResMonContributors", "ResMonLinux")
        if settings.contains("geometry"): self.restoreGeometry(settings.value("geometry"))
        if settings.contains("isDarkMode"): self.is_dark_mode = settings.value("isDarkMode", True, type=bool)
        self.apply_theme()
        if settings.contains("tabOrder"):
            saved_tab_order = settings.value("tabOrder")
            if isinstance(saved_tab_order, list):
                for i, tab_name in enumerate(saved_tab_order):
                    for j in range(self.tabs.count()):
                        if self.tabs.tabText(j) == tab_name:
                            self.tabs.tabBar().moveTab(j, i)
                            break
        if settings.contains("currentTab"): self.tabs.setCurrentIndex(settings.value("currentTab", 0, type=int))
        if settings.contains("panelOrder"):
            panel_order = settings.value("panelOrder")
            if isinstance(panel_order, list) and len(panel_order) == 4:
                for name in panel_order:
                    if name in self.ov_boxes: self.overview_splitter.addWidget(self.ov_boxes[name])
        if settings.contains("splitterState"): self.overview_splitter.restoreState(settings.value("splitterState"))

    def closeEvent(self, event):
        settings = QSettings("ResMonContributors", "ResMonLinux")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("isDarkMode", self.is_dark_mode)
        tab_order = [self.tabs.tabText(i) for i in range(self.tabs.count())]
        settings.setValue("tabOrder", tab_order)
        settings.setValue("currentTab", self.tabs.currentIndex())
        panel_order = [self.overview_splitter.widget(i).objectName() for i in range(self.overview_splitter.count())]
        settings.setValue("panelOrder", panel_order)
        settings.setValue("splitterState", self.overview_splitter.saveState())
        super().closeEvent(event)

    def format_bytes(self, num_bytes):
        if num_bytes < 1024: return f"{num_bytes} B"
        elif num_bytes < 1048576: return f"{num_bytes / 1024:.1f} KB"
        elif num_bytes < 1073741824: return f"{num_bytes / 1048576:.1f} MB"
        else: return f"{num_bytes / 1073741824:.2f} GB"

    def format_rate(self, bytes_per_sec):
        return f"{self.format_bytes(bytes_per_sec)}/s"

    def format_addr(self, addr):
        if not addr: return ""
        try:
            if hasattr(addr, 'ip') and hasattr(addr, 'port'): return f"{addr.ip}:{addr.port}"
            elif isinstance(addr, (tuple, list)) and len(addr) >= 2: return f"{addr[0]}:{addr[1]}"
            return str(addr)
        except Exception:
            return "Unknown"

    def update_cell(self, tbl, row, col, text, raw_val=None):
        item = tbl.item(row, col)
        if raw_val is not None:
            if isinstance(item, NumericTableWidgetItem):
                item.setText(text)
                item.raw_val = raw_val
            else:
                tbl.setItem(row, col, NumericTableWidgetItem(text, raw_val))
        else:
            if item: item.setText(text)
            else: tbl.setItem(row, col, QTableWidgetItem(text))

    def refresh_data(self):
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
        procs = []
        for pid, proc in self.get_active_processes():
            try:
                name = proc.name() or "Unknown"
                cpu_pct = proc.cpu_percent()
                threads = proc.num_threads()
                status = proc.status()
                if cpu_pct > 0 or (filter_text and (filter_text in name.lower() or filter_text in str(pid))):
                    if not filter_text or (filter_text in name.lower() or filter_text in str(pid)):
                        procs.append((name, pid, cpu_pct, threads, status))
            except (psutil.Error, AttributeError, OSError): continue
        tbl.setRowCount(len(procs))
        for row, (name, pid, cpu_pct, threads, status) in enumerate(procs):
            self.update_cell(tbl, row, 0, name)
            self.update_cell(tbl, row, 1, str(pid), pid)
            self.update_cell(tbl, row, 2, f"{cpu_pct:.1f}%", cpu_pct)
            self.update_cell(tbl, row, 3, str(threads), threads)
            self.update_cell(tbl, row, 4, status)
        tbl.setSortingEnabled(True)
        tbl.verticalScrollBar().setValue(v_scroll)

    def update_mem_data(self, flt, tbl):
        v_scroll = tbl.verticalScrollBar().value()
        tbl.setSortingEnabled(False)
        filter_text = flt.text().lower()
        procs = []
        for pid, proc in self.get_active_processes():
            try:
                name = proc.name() or "Unknown"
                mem_info = proc.memory_info()
                mem_pct = proc.memory_percent()
                rss = getattr(mem_info, 'rss', 0)
                vms = getattr(mem_info, 'vms', 0)
                if rss > 1048576 or (filter_text and (filter_text in name.lower() or filter_text in str(pid))):
                    if not filter_text or (filter_text in name.lower() or filter_text in str(pid)):
                        procs.append((name, pid, rss, mem_pct, vms))
            except (psutil.Error, AttributeError, OSError): continue
        tbl.setRowCount(len(procs))
        for row, (name, pid, rss, mem_pct, vms) in enumerate(procs):
            self.update_cell(tbl, row, 0, name)
            self.update_cell(tbl, row, 1, str(pid), pid)
            self.update_cell(tbl, row, 2, self.format_bytes(rss), rss)
            self.update_cell(tbl, row, 3, f"{mem_pct:.2f}%", mem_pct)
            self.update_cell(tbl, row, 4, self.format_bytes(vms), vms)
        tbl.setSortingEnabled(True)
        tbl.verticalScrollBar().setValue(v_scroll)

    def update_disk_data(self, flt, tbl):
        v_scroll = tbl.verticalScrollBar().value()
        tbl.setSortingEnabled(False)
        filter_text = flt.text().lower()
        active_processes = []
        now = time.time()
        for pid, proc in self.get_active_processes():
            try:
                name = proc.name() or "Unknown"
                io = proc.io_counters()
                read_bytes = getattr(io, 'read_bytes', 0)
                write_bytes = getattr(io, 'write_bytes', 0)
                if pid in self.prev_io:
                    old_read, old_write, old_time = self.prev_io[pid]
                    dt = now - old_time
                    r_rate = max(0, (read_bytes - old_read) / dt) if dt > 0 else 0
                    w_rate = max(0, (write_bytes - old_write) / dt) if dt > 0 else 0
                else: r_rate, w_rate = 0, 0
                self.prev_io[pid] = (read_bytes, write_bytes, now)
                total_rate = r_rate + w_rate
                if total_rate > 0 or (filter_text and (filter_text in name.lower() or filter_text in str(pid))):
                    if not filter_text or (filter_text in name.lower() or filter_text in str(pid)):
                        active_processes.append((name, pid, r_rate, w_rate, total_rate))
            except (psutil.Error, AttributeError, OSError): continue
        tbl.setRowCount(len(active_processes))
        for row, (name, pid, r_rate, w_rate, total_rate) in enumerate(active_processes):
            self.update_cell(tbl, row, 0, name)
            self.update_cell(tbl, row, 1, str(pid), pid)
            self.update_cell(tbl, row, 2, self.format_rate(r_rate), r_rate)
            self.update_cell(tbl, row, 3, self.format_rate(w_rate), w_rate)
            self.update_cell(tbl, row, 4, self.format_rate(total_rate), total_rate)
        tbl.setSortingEnabled(True)
        tbl.verticalScrollBar().setValue(v_scroll)

    def update_net_data(self, flt, tbl):
        v_scroll = tbl.verticalScrollBar().value()
        tbl.setSortingEnabled(False)
        filter_text = flt.text().lower()
        now = time.time()

        if self.net_view_mode == "interfaces":
            # INTERFACE LOGIC[cite: 1]
            interfaces = []
            try:
                net_io = psutil.net_io_counters(pernic=True)[cite: 1]
                for nic, io in net_io.items():
                    if filter_text and filter_text not in nic.lower():
                        continue
                    bytes_sent = io.bytes_sent[cite: 1]
                    bytes_recv = io.bytes_recv[cite: 1]
                    if nic in self.prev_net_io:
                        old_sent, old_recv, old_time = self.prev_net_io[nic][cite: 1]
                        dt = now - old_time
                        up_rate = max(0, (bytes_sent - old_sent) / dt) if dt > 0 else 0[cite: 1]
                        down_rate = max(0, (bytes_recv - old_recv) / dt) if dt > 0 else 0[cite: 1]
                    else:
                        up_rate, down_rate = 0, 0
                    self.prev_net_io[nic] = (bytes_sent, bytes_recv, now)[cite: 1]
                    interfaces.append((nic, up_rate, down_rate, bytes_sent, bytes_recv))[cite: 1]
            except (psutil.Error, OSError): pass

            tbl.setRowCount(len(interfaces))
            for row, (nic, up_rate, down_rate, total_up, total_down) in enumerate(interfaces):
                self.update_cell(tbl, row, 0, nic)[cite: 1]
                self.update_cell(tbl, row, 1, self.format_rate(up_rate), up_rate)[cite: 1]
                self.update_cell(tbl, row, 2, self.format_rate(down_rate), down_rate)[cite: 1]
                self.update_cell(tbl, row, 3, self.format_bytes(total_up), total_up)[cite: 1]
                self.update_cell(tbl, row, 4, self.format_bytes(total_down), total_down)[cite: 1]
                
        else:
            # PROCESS CONNECTIONS LOGIC[cite: 2]
            connections = []
            def parse_conn(conn, pid_hint=None):
                if not getattr(conn, 'raddr', None): return[cite: 2]
                pid = getattr(conn, 'pid', pid_hint)[cite: 2]
                name = "System/Kernel"
                if pid and pid in self.proc_cache:
                    try: name = self.proc_cache[pid].name()[cite: 2]
                    except (psutil.Error, OSError): name = "Access Denied"
                laddr = self.format_addr(conn.laddr)[cite: 2]
                raddr = self.format_addr(conn.raddr)[cite: 2]
                proto = "TCP" if conn.type == 1 else "UDP"[cite: 2]
                status = getattr(conn, 'status', 'NONE')[cite: 2]
                search_target = f"{name} {pid} {laddr} {raddr} {status} {proto}".lower()
                if not filter_text or filter_text in search_target:
                    connections.append((name, pid or 0, laddr, raddr, status, proto))[cite: 2]

            try:
                for conn in psutil.net_connections(kind='inet'):[cite: 2]
                    parse_conn(conn)[cite: 2]
            except psutil.AccessDenied:
                for pid, proc in self.get_active_processes():
                    try:
                        for conn in proc.connections(kind='inet'):[cite: 2]
                            parse_conn(conn, pid_hint=pid)[cite: 2]
                    except (psutil.Error, OSError): continue
            except (psutil.Error, OSError): pass

            tbl.setRowCount(len(connections))
            for row, (name, pid, laddr, raddr, status, proto) in enumerate(connections):
                self.update_cell(tbl, row, 0, name)[cite: 2]
                self.update_cell(tbl, row, 1, str(pid), pid)[cite: 2]
                self.update_cell(tbl, row, 2, laddr)[cite: 2]
                self.update_cell(tbl, row, 3, raddr)[cite: 2]
                self.update_cell(tbl, row, 4, status)[cite: 2]
                self.update_cell(tbl, row, 5, proto)[cite: 2]

        tbl.setSortingEnabled(True)
        tbl.verticalScrollBar().setValue(v_scroll)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ResMonLinux()
    window.show()
    sys.exit(app.exec())