import pathlib
import sys
from typing import Literal
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                              QVBoxLayout, QLabel, QStackedWidget,
                              QPushButton, QFrame, QButtonGroup, 
                              QScrollArea, QHBoxLayout, QListWidget)
from PySide6.QtCore import Qt, QTimer, QObject, Signal, QThread, Slot
from PySide6.QtGui import QPixmap

from helpers import extract_all_addons_data, get_addons_folder_windows

COLOR_1 = '212327'  # Dark background
COLOR_2 = '904eaf'  # Purple accent
COLOR_3 = '2d2d43'  # Hover color
COLOR_4 = '31262e'  # Main background


class InstalledAddonsWorker(QObject):
    finished = Signal()
    progress = Signal(dict)

    def run(self):
        addons = extract_all_addons_data(get_addons_folder_windows('live'))
        
        for addon in addons:
            if not addon['ok']:
                continue
           
            self.progress.emit(addon)

        self.finished.emit()


class ErrorAddonsWorker(QObject):
    finished = Signal()
    progress = Signal(dict)

    def run(self):
        addons = extract_all_addons_data(get_addons_folder_windows('live'))
        
        for addon in addons:
            if addon['ok']:
                continue
           
            self.progress.emit(addon)

        self.finished.emit()


class AddonRow(QFrame):
    def __init__(self, addon):
        super().__init__()

        self.setFixedHeight(72)
        self.setStyleSheet(f"""
            QFrame {{
                border-bottom: 3px solid #{COLOR_1};
                background: transparent;
                margin-right: 0;
            }}
            QFrame:hover {{
                background: #{COLOR_3};
            }}
            QFrame:hover > QWidget {{
                background: transparent;
                color: inherit;
            }}
            QLabel {{
                border-bottom: none;
            }}
        """)
        
        item_layout = QHBoxLayout(self)
        item_layout.setContentsMargins(15, 0, 15, 0)
        item_layout.setSpacing(15)
        
        icon = QLabel()
        icon.setPixmap(QPixmap('nothing.png').scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(48, 48)
        item_layout.addWidget(icon)
        
        text_widget = QWidget()
        text_layout = QVBoxLayout(text_widget)
        text_layout.setContentsMargins(5, 5, 5, 5)
        text_layout.setSpacing(2)
        
        name = QLabel(addon.get("title", "?"))
        name.setStyleSheet(f"color: #eeeeff; font-weight: 600; font-size: 16px;")
        name.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        text_layout.addWidget(name)
        
        meta = QLabel(f"v{addon.get('version', '?')} ({addon.get('addonVersion', '?')}) • {addon.get('author', '?')}")
        meta.setStyleSheet("color: #d3b8e0; font-size: 12px;")
        meta.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        text_layout.addWidget(meta)

        path = QLabel(f"{addon.get('relative_path', '/?')}")
        path.setStyleSheet("color: #d3b8e0; font-size: 12px;")
        path.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        text_layout.addWidget(path)
        
        text_layout.addStretch()
        item_layout.addWidget(text_widget)


class AddonScroll(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: #{COLOR_1};
                width: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: #{COLOR_2};
                min-height: 20px;
                border-radius: 0px;
            }}
            QScrollBar::add-line:vertical, 
            QScrollBar::sub-line:vertical {{
                height: 0px;
                background: none;
            }}
            QScrollBar::add-page:vertical, 
            QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """)

        container = QWidget()
        self.setWidget(container)
    
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.layout = layout

    def get_layout(self):
        return self.layout


class Main(QMainWindow):
    def __init__(self):
        super().__init__()

        # self.setWindowFlag(Qt.FramelessWindowHint)
        # self.setAttribute(Qt.WA_TranslucentBackground)

        self.setup_ui()
        self.setup_tabs()
        self.setup_connections()

        self.add_installed_addons()
        self.add_errors()
        
    def setup_ui(self):
        self.setWindowTitle('ESO Addon Helper')
        self.setMinimumSize(800, 400)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setStyleSheet(f"background-color: #{COLOR_4};")

        self.main_layout = QHBoxLayout(central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.setup_sidebar()
        self.setup_content_area()
        
    def setup_sidebar(self):
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(150)
        self.sidebar.setStyleSheet(f"background-color: #{COLOR_1};")

        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(10, 10, 10, 10)
        self.sidebar_layout.setSpacing(4)
        self.sidebar_layout.setAlignment(Qt.AlignTop)

        self.button_group = QButtonGroup()
        self.button_group.setExclusive(True)
        
        self.btn_installed = QPushButton("Addons")
        self.btn_errors = QPushButton("Errors")
        self.btn_search = QPushButton("Search")
        self.btn_options = QPushButton("Options")
        
        button_style = f"""
            QPushButton {{
                padding: 0 10px;
                height: 32px;
                text-align: left;
                border: none;
                border-radius: 12px;
                font-size: 14px;
                font-family: 'Roboto Mono';
            }}
            QPushButton:hover {{
                background-color: #{COLOR_3};
            }}
            QPushButton:focus {{
                outline: 0;
            }}
            QPushButton:checked {{
                background-color: #{COLOR_2};
            }}
        """

        for btn in [self.btn_installed, self.btn_errors, self.btn_options]:  # self.btn_search, 
            btn.setCheckable(True)
            btn.setStyleSheet(button_style)
            btn.setCursor(Qt.PointingHandCursor)
            self.button_group.addButton(btn)
            self.sidebar_layout.addWidget(btn)

        self.sidebar_layout.addStretch()

        version_label = QLabel("v0.0.1 | @imPDA")
        version_label.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        version_label.setStyleSheet("""
            QLabel {
                color: rgba(150, 150, 150, 120);
                font-size: 10px;
                padding: 2px 5px;
            }
        """)
        self.sidebar_layout.addWidget(version_label)

        self.main_layout.addWidget(self.sidebar)
        
    def setup_content_area(self):
        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)

        self.loading_screen = QLabel('Loading...')
        self.stacked_widget.addWidget(self.loading_screen)
        
    def setup_tabs(self):
        self.setup_installed_tab()
        self.setup_errors_tab()
        self.setup_search_tab()
        self.setup_options_tab()

    def add_installed_addons(self):
        # TODO: refresh, delete addons
        
        # self.start_button.setEnabled(False)
        # self.status_label.setText("Task running...")

        thread = QThread()
        worker = InstalledAddonsWorker()

        self.installed_addons_thred = thread
        self.installed_addons_worker = worker

        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(self.installed_addons_added)
        worker.progress.connect(self.add_installed_addon)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        thread.start()
    
    @Slot(dict)
    def add_installed_addon(self, addon_data):
        self.addons_layout.addWidget(AddonRow(addon_data))
    
    def installed_addons_added(self):
        # self.status_label.setText("Task completed!")
        # self.start_button.setEnabled(True)
        self.installed_addons_ready = True
        self.switch_tab(1)
        self.addons_layout.addStretch()
    
    def add_errors(self):
        # TODO: refresh, delete addons
        
        # self.start_button.setEnabled(False)
        # self.status_label.setText("Task running...")

        thread = QThread()
        worker = ErrorAddonsWorker()

        self.errors_thread = thread
        self.errors_worker = worker

        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(self.errors_added)
        worker.progress.connect(self.add_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        thread.start()
    
    @Slot(dict)
    def add_error(self, addon_data):
        self.errors_layout.addWidget(AddonRow(addon_data))
    
    def errors_added(self):
        # self.status_label.setText("Task completed!")
        # self.start_button.setEnabled(True)
        self.errors_layout.addStretch()
        
    def setup_installed_tab(self):
        scroll = AddonScroll()
        self.installed_addons_ready = False

        self.stacked_widget.addWidget(scroll)
        self.addons_layout = scroll.get_layout()
        
    def setup_errors_tab(self):
        scroll = AddonScroll()

        self.stacked_widget.addWidget(scroll)
        self.errors_layout = scroll.get_layout()
        
    def setup_search_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        label = QLabel("Search Tab Content")
        label.setStyleSheet("color: white;")
        layout.addWidget(label)
        self.stacked_widget.addWidget(tab)
        
    def setup_options_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        label = QLabel("Options Tab Content")
        label.setStyleSheet("color: white;")
        layout.addWidget(label)
        self.stacked_widget.addWidget(tab)
        
    def setup_connections(self):
        self.btn_installed.clicked.connect(lambda: self.switch_tab(1))
        self.btn_errors.clicked.connect(lambda: self.switch_tab(2))
        self.btn_search.clicked.connect(lambda: self.switch_tab(3))
        self.btn_options.clicked.connect(lambda: self.switch_tab(4))
        
        self.btn_installed.setChecked(True)
        self.switch_tab(0)
        
    def switch_tab(self, index):
        if index == 1 and self.installed_addons_ready:
            self.stacked_widget.setCurrentIndex(index)
        else:
            self.stacked_widget.setCurrentIndex(0)

        # Update button states
        # buttons = [self.btn_installed, self.btn_errors, self.btn_search, self.btn_options]
        # for i, btn in enumerate(buttons):
        #     btn.setChecked(i == index)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Main()
    window.show()
    sys.exit(app.exec())
