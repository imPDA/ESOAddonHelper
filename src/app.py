from functools import partial
import sys
from typing import Literal
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, 
                              QVBoxLayout, QLabel, QStackedWidget,
                              QPushButton, QFrame, QButtonGroup, 
                              QScrollArea, QHBoxLayout, QLineEdit)
from PySide6.QtCore import Qt, QTimer, QObject, Signal, QThread, Slot
from PySide6.QtGui import QPixmap

from helpers import extract_all_addons_data, get_addons_folder_windows

COLOR_1 = '212327'  # Dark background
COLOR_2 = '904eaf'  # Purple accent
COLOR_3 = '2d2d43'  # Hover color
COLOR_4 = '31262e'  # Main background


class AddonRepository:
    def __init__(self):
        self.addons = extract_all_addons_data(get_addons_folder_windows('live'))

    def get_addons(self):
        for addon in self.addons:
            yield addon


addon_repository = AddonRepository()


class AddonWorker(QObject):
    progress = Signal(dict)
    finished = Signal()
    error = Signal(str)

    def __init__(self, filters):
        super().__init__()
        self.filters = filters

    def run(self):
        try:
            for addon in addon_repository.addons:
                for filter_ in self.filters:
                    if not filter_(addon):
                        break
                else:
                    self.progress.emit(addon)

            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class AddonTab(QWidget):
    refresh_started = Signal()
    refresh_completed = Signal()

    def __init__(self, filters):
        super().__init__()

        self.filters = filters

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.addon_scroll = AddonScroll()
        layout.addWidget(self.addon_scroll)
        self.list_layout = self.addon_scroll.get_layout()

        self.dirty = True
        self.ready = False
        self.updating = False
        self.current_thread = None
        self.current_worker = None

        self.is_loaded = False

    @Slot(dict)
    def handle_addon_progress(self, addon_data: dict):
        self.addon_scroll.add_addon(addon_data)
        # self.list_layout.addWidget(AddonRow(addon_data))

    @Slot()
    def handle_refresh_finished(self):
        self.list_layout.addStretch()  # TODO: do I need it?

        self.dirty = False
        self.ready = True
        self.updating = False
        # self.current_thread = None
        # self.current_worker = None

        self.is_loaded = True
        self.addon_scroll.visible_count_changed.emit(self.addon_scroll.visible_count)

        self.refresh_completed.emit()

    @Slot(str)
    def handle_error(self, error_msg):
        print(f"Error loading addons: {error_msg}")
        self.handle_refresh_finished()

    def clear_addons(self):
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def refresh(self):
        self.is_loaded = False
        self.refresh_started.emit()

        if self.updating:
            return

        self.clear_addons()

        self.updating = True
        self.ready = False

        thread = QThread()
        worker = AddonWorker(self.filters)

        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)

        worker.progress.connect(self.handle_addon_progress)
        worker.error.connect(self.handle_error)
        worker.finished.connect(self.handle_refresh_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)

        self.current_thread = thread
        self.current_worker = worker

        thread.start()

    def cancel_refresh(self):
        if self.current_thread and self.current_thread.isRunning():
            self.current_thread.quit()
            self.current_thread.wait()
            self.handle_refresh_finished()


class AddonRow(QFrame):
    def __init__(self, addon):
        super().__init__()

        self.addon = addon

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
        # icon.setPixmap(QPixmap('nothing.png').scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
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
    visible_count_changed = Signal(int)

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
                background: #{COLOR_4};
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

        self.visible_count = 0

        self.addons_container = QWidget()
        self.addons_layout = QVBoxLayout(self.addons_container)
        self.addons_layout.setContentsMargins(0, 0, 0, 0)
        self.addons_layout.setSpacing(0)

        layout.addWidget(self.addons_container)

        # self.layout = layout

    def add_addon(self, addon_data: dict):
        # TODO: add filtering here
        self.addons_layout.addWidget(AddonRow(addon_data))
        self.visible_count += 1

    def filter_addons(self, search_string: str):
        self.visible_count = 0

        for i in range(self.addons_layout.count()):
            item = self.addons_layout.itemAt(i)
            widget = item.widget()

            if not widget or not isinstance(widget, AddonRow):
                continue

            title = widget.addon.get("title", "").lower()
            author = widget.addon.get("author", "").lower()
            path = widget.addon.get("relative_path", "").lower().replace('\\', '/')
            bundled = widget.addon.get('bundled', False)

            isVisible = lambda x: (
                x in title
                or (x.startswith('@') and x[1:] in author)
                or (x.startswith('/') and bundled and x in path)
            )

            filters = search_string.split()
            visible = all([isVisible(f) for f in filters if not f.startswith('~')]) and all([not isVisible(f[1:]) for f in filters if f.startswith('~')])

            widget.setVisible(visible)

            if visible:
                self.visible_count += 1
            
        self.visible_count_changed.emit(self.visible_count)

    def get_layout(self):
        return self.addons_layout
        # return self.layout


class Main(QMainWindow):
    def __init__(self):
        super().__init__()

        # self.setWindowFlag(Qt.FramelessWindowHint)
        # self.setAttribute(Qt.WA_TranslucentBackground)

        self.tabs = [
            {'name': 'Addons', 'tab': partial(AddonTab, [lambda x: x.get('ok'), lambda x: not x.get('isLibrary')])},
            {'name': 'Libraries', 'tab': partial(AddonTab, [lambda x: x.get('ok'), lambda x: x.get('isLibrary')])},
            {'name': 'Errors', 'tab': partial(AddonTab, [lambda x: not x.get('ok')])},
        ]
        self.current_loading_index = -1

        self.__tabs = []
        self.__buttons = []

        self.setup_ui()
        self.setup_sidebar()
        self.setup_content_area()

        for i, tab in enumerate(self.__tabs):
            # tab.refresh_started.connect(lambda idx=i: self.show_loading(idx))
            tab.refresh_completed.connect(partial(self.show_tab_content, i))

        for tab in self.__tabs:
            tab.refresh()

        self.switch_tab(0)
    
    def filter_all_tabs(self):
        search_text = self.search_line.text().lower()
        for tab in self.__tabs:
            # if hasattr(tab, 'addon_scroll'):
            tab.addon_scroll.filter_addons(search_text)

    def setup_search_bar(self):
        self.search_line = QLineEdit()
        self.search_line.setPlaceholderText("Search addons...")
        self.search_line.setStyleSheet(f"""
            QLineEdit {{
                background: #{COLOR_1};
                border: 2px solid #{COLOR_1};
                color: white;
                padding: 8px;
                margin: 10px;
                border-radius: 4px;
                height: 24px;
            }}

            QLineEdit:focus {{
                border: 2px solid #{COLOR_2};
            }}
        """)
        self.search_line.textChanged.connect(self.filter_all_tabs)
        
        search_container = QWidget()
        search_layout = QVBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.addWidget(self.search_line)
        
        self.content_layout.addWidget(search_container)

    def show_loading(self, tab_index):
        self.current_loading_index = tab_index
        self.stacked_widget.setCurrentWidget(self.loading_screen)
    
    def show_tab_content(self, tab_index):
        if tab_index == self.current_loading_index:
            self.stacked_widget.setCurrentWidget(self.__tabs[tab_index])

    def setup_ui(self):
        self.setWindowTitle('ESO Addon Helper')
        self.setMinimumSize(800, 400)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setStyleSheet(f"background-color: #{COLOR_4};")

        self.main_layout = QHBoxLayout(central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
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

        for i, tab in enumerate(self.tabs):
            button = QPushButton(tab['name'])
            button.setCheckable(True)
            button.setStyleSheet(button_style)
            button.setCursor(Qt.PointingHandCursor)

            self.button_group.addButton(button)
            self.sidebar_layout.addWidget(button)

            button.clicked.connect(partial(self.switch_tab, i))

            self.__buttons.append(button)

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
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)

        self.main_layout.addWidget(self.content)

        self.setup_search_bar()

        self.stacked_widget = QStackedWidget()
        self.content_layout.addWidget(self.stacked_widget)

        for i, tab in enumerate(self.tabs):
            tab_widget = tab['tab']()
            self.stacked_widget.addWidget(tab_widget)
            self.__tabs.append(tab_widget)

            tab_widget.addon_scroll.visible_count_changed.connect(lambda count, idx=i: self.update_tab_count(idx, count))

        self.loading_screen = QLabel("Loading...")
        self.loading_screen.setStyleSheet("""
            QLabel {
                color: #""" + COLOR_2 + """;
                font-size: 24px;
                font-weight: bold;
                qproperty-alignment: AlignCenter;
            }
        """)
        self.stacked_widget.addWidget(self.loading_screen)
    
    def update_tab_count(self, tab_index, count):
        text = self.tabs[tab_index]['name']
        self.__buttons[tab_index].setText(f"{text} ({count})")

    # def setup_search_tab(self):
    #     tab = QWidget()
    #     layout = QVBoxLayout(tab)
    #     label = QLabel("Search Tab Content")
    #     label.setStyleSheet("color: white;")
    #     layout.addWidget(label)
    #     self.stacked_widget.addWidget(tab)
        
    def setup_options_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        label = QLabel("Options Tab Content")
        label.setStyleSheet("color: white;")
        layout.addWidget(label)
        self.stacked_widget.addWidget(tab)
    
    def switch_tab(self, index):
        if not (0 <= index < len(self.__tabs)):
            return
        
        self.__buttons[index].setChecked(True)

        if self.__tabs[index].is_loaded:
            self.stacked_widget.setCurrentWidget(self.__tabs[index])
        else:
            self.show_loading(index)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Main()
    window.show()
    sys.exit(app.exec())
