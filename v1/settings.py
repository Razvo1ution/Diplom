from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QComboBox, QPushButton,
                             QFileDialog, QLineEdit, QMessageBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor
import os

class SettingsPanel(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.themes = {
            "Светлая": self.light_theme,
            "Темная": self.dark_theme
        }
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Путь к проекту:"))
        self.project_path_input = QLineEdit()
        self.project_path_input.setPlaceholderText("Введите путь к проекту...")
        layout.addWidget(self.project_path_input)

        browse_btn = QPushButton("Обзор")
        browse_btn.clicked.connect(self.browse_project)
        layout.addWidget(browse_btn)

        layout.addWidget(QLabel("Тема:"))
        self.theme_selector = QComboBox()
        self.theme_selector.addItems(self.themes.keys())
        self.theme_selector.currentTextChanged.connect(self.change_theme)
        layout.addWidget(self.theme_selector)

        apply_btn = QPushButton("Применить")
        apply_btn.clicked.connect(self.apply_settings)
        layout.addWidget(apply_btn)

        layout.addStretch()

    def apply_settings(self):
        project_path = self.project_path_input.text()
        if project_path and os.path.exists(project_path):
            if not os.path.exists(os.path.join(project_path, '.git')):
                QMessageBox.warning(self, "Ошибка", "Указанная папка не является Git-репозиторием")
                return

        self.parent.settings.setValue("project_path", project_path)
        self.parent.settings.setValue("theme", self.theme_selector.currentText())
        self.parent.settings.sync()

        self.change_theme(self.theme_selector.currentText())
        self.parent.update_time_metrics()
        self.parent.update_code_metrics()
        self.parent.update_graph_metrics()
        self.parent.start_file_watcher(project_path)

    def change_theme(self, theme_name):
        theme_func = self.themes.get(theme_name, self.light_theme)
        self.apply_theme(theme_func)

    def light_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(240, 240, 240))
        palette.setColor(QPalette.WindowText, Qt.black)
        palette.setColor(QPalette.Base, Qt.white)
        palette.setColor(QPalette.Text, Qt.black)
        palette.setColor(QPalette.Button, QColor(240, 240, 240))
        palette.setColor(QPalette.ButtonText, Qt.black)
        palette.setColor(QPalette.Highlight, QColor(100, 149, 237).lighter())
        return palette

    def dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.Highlight, QColor(142, 45, 197).lighter())
        return palette

    def apply_theme(self, palette_func):
        palette = palette_func()
        self.parent.setPalette(palette)

        button_style = """
            QPushButton {
                padding: 5px;
                border: 1px solid #aaa;
                border-radius: 4px;
                background: %s;
                color: %s;
            }
            QPushButton:hover {
                background: %s;
            }
        """ % (
            palette.color(QPalette.Button).name(),
            palette.color(QPalette.ButtonText).name(),
            palette.color(QPalette.Button).lighter(120).name()
        )

        for btn in self.parent.findChildren(QPushButton):
            btn.setStyleSheet(button_style)

    def browse_project(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку проекта")
        if folder:
            self.project_path_input.setText(folder)
            return folder
        return None