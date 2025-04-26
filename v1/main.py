import sys
import os
from datetime import datetime, timedelta
from git import Repo
from git.exc import InvalidGitRepositoryError
from radon.complexity import cc_visit
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget,
                             QPushButton, QTabWidget, QHBoxLayout, QDockWidget,
                             QDesktopWidget, QLabel, QTextEdit)
from PyQt5.QtCore import Qt, QRect, QPropertyAnimation, QSettings
from PyQt5.QtGui import QIcon
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
from settings import SettingsPanel

class DevMetricsApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Анализатор продуктивности")
        self.settings = QSettings("MyCompany", "DevMetricsApp")
        self.init_ui()

    def init_ui(self):
        self.setFixedSize(1000, 800)
        self.center_window()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.create_top_panel()
        self.create_settings_panel()
        self.create_tabs()
        self.create_menu_panel()

        self.load_settings()

    def center_window(self):
        screen = QDesktopWidget().screenGeometry()
        size = self.geometry()
        self.move((screen.width() - size.width()) // 2,
                  (screen.height() - size.height()) // 2)

    def create_top_panel(self):
        top_panel = QWidget()
        top_layout = QHBoxLayout(top_panel)

        self.menu_btn = QPushButton("Меню")
        self.menu_btn.setFixedSize(160, 30)
        self.menu_btn.setCheckable(True)
        self.menu_btn.clicked.connect(self.toggle_menu)
        top_layout.addWidget(self.menu_btn, alignment=Qt.AlignLeft)

        top_layout.addStretch()
        self.main_layout.addWidget(top_panel)

    def create_tabs(self):
        self.tabs = QTabWidget()
        self.create_time_tab()
        self.create_code_tab()
        self.create_graph_tab()
        self.main_layout.addWidget(self.tabs)

    def create_time_tab(self):
        time_tab = QWidget()
        time_layout = QVBoxLayout(time_tab)

        time_layout.addWidget(QLabel("Активное время работы:"))
        self.time_metrics = QTextEdit()
        self.time_metrics.setReadOnly(True)
        time_layout.addWidget(self.time_metrics)

        self.time_heatmap = MplCanvas(self, width=8, height=4, dpi=100)
        time_layout.addWidget(self.time_heatmap)

        self.tabs.addTab(time_tab, "Время работы")

    def create_code_tab(self):
        code_tab = QWidget()
        code_layout = QVBoxLayout(code_tab)

        code_layout.addWidget(QLabel("Анализ кода:"))
        self.code_metrics = QTextEdit()
        self.code_metrics.setReadOnly(True)
        code_layout.addWidget(self.code_metrics)

        self.tabs.addTab(code_tab, "Анализ кода")

    def create_graph_tab(self):
        graph_tab = QWidget()
        graph_layout = QVBoxLayout(graph_tab)

        graph_layout.addWidget(QLabel("Графики продуктивности:"))
        self.trend_graph = MplCanvas(self, width=8, height=4, dpi=100)
        graph_layout.addWidget(self.trend_graph)

        self.tabs.addTab(graph_tab, "Графики")

    def create_menu_panel(self):
        self.menu_dock = QDockWidget()
        self.menu_dock.setFeatures(QDockWidget.NoDockWidgetFeatures)

        menu_widget = QWidget()
        menu_layout = QVBoxLayout(menu_widget)

        settings_btn = QPushButton()
        settings_btn.setIcon(QIcon.fromTheme("configure"))
        settings_btn.setText("Настройки")
        settings_btn.clicked.connect(self.toggle_settings)
        menu_layout.addStretch()
        menu_layout.addWidget(settings_btn, alignment=Qt.AlignBottom)

        self.menu_dock.setWidget(menu_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.menu_dock)
        self.menu_dock.hide()

        self.menu_animation = QPropertyAnimation(self.menu_dock, b"geometry")
        self.menu_animation.setDuration(300)

    def create_settings_panel(self):
        self.settings_widget = QWidget()
        settings_layout = QVBoxLayout(self.settings_widget)

        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.clicked.connect(self.toggle_settings)
        close_layout.addWidget(close_btn)
        settings_layout.addLayout(close_layout)

        self.settings_panel = SettingsPanel(self)
        settings_layout.addWidget(self.settings_panel)

        self.settings_widget.hide()
        self.main_layout.addWidget(self.settings_widget)

    def toggle_menu(self):
        if self.menu_dock.isVisible():
            start_geometry = self.menu_dock.geometry()
            end_geometry = QRect(-300, start_geometry.y(), 300, start_geometry.height())
            self.menu_animation.setStartValue(start_geometry)
            self.menu_animation.setEndValue(end_geometry)
            self.menu_animation.finished.connect(self.menu_dock.hide)
            self.menu_animation.start()
            self.menu_btn.setChecked(False)
            self.menu_btn.setText("Меню")
            self.menu_btn.setStyleSheet("")
        else:
            self.menu_dock.show()
            start_geometry = QRect(-300, 0, 300, self.height())
            end_geometry = QRect(0, 0, 300, self.height())
            self.menu_animation.setStartValue(start_geometry)
            self.menu_animation.setEndValue(end_geometry)
            self.menu_animation.start()
            self.menu_btn.setChecked(True)
            self.menu_btn.setText("Закрыть меню")
            self.menu_btn.setStyleSheet("""
                QPushButton:checked {
                    background-color: #d0d0d0;
                    border: 2px solid #555;
                }
            """)

    def toggle_settings(self):
        if self.settings_widget.isVisible():
            self.settings_widget.hide()
            self.tabs.show()
        else:
            self.tabs.hide()
            self.settings_widget.show()
            if self.menu_dock.isVisible():
                self.toggle_menu()

    def load_settings(self):
        project_path = self.settings.value("project_path", "")
        self.settings_panel.project_path_input.setText(project_path)

        theme = self.settings.value("theme", "Светлая")
        self.settings_panel.theme_selector.setCurrentText(theme)
        self.settings_panel.change_theme(theme)

        self.update_time_metrics()
        self.update_code_metrics()
        self.update_graph_metrics()

    def closeEvent(self, event):
        self.settings.setValue("project_path", self.settings_panel.project_path_input.text())
        self.settings.setValue("theme", self.settings_panel.theme_selector.currentText())
        event.accept()

    def update_time_metrics(self):
        project_path = self.settings_panel.project_path_input.text()
        if not project_path or not os.path.exists(project_path):
            self.time_metrics.setText("Укажите путь к проекту в настройках")
            self.time_heatmap.axes.clear()
            self.time_heatmap.draw()
            return

        if not os.path.exists(os.path.join(project_path, '.git')):
            self.time_metrics.setText("Ошибка: Указанная папка не является Git-репозиторием")
            self.time_heatmap.axes.clear()
            self.time_heatmap.draw()
            return

        try:
            repo = Repo(project_path)
            commits = list(repo.iter_commits(max_count=100))
            if not commits:
                self.time_metrics.setText("В репозитории нет коммитов")
                self.time_heatmap.axes.clear()
                self.time_heatmap.draw()
                return

            today = datetime.now()
            week_ago = today - timedelta(days=7)
            daily_hours = 0
            weekly_hours = 0
            session_times = []
            last_commit_time = None

            for commit in commits:
                commit_time = datetime.fromtimestamp(commit.committed_date)
                if commit_time.date() == today.date():
                    daily_hours += 1 / 60
                if commit_time >= week_ago:
                    weekly_hours += 1 / 60
                if last_commit_time:
                    session_times.append((last_commit_time - commit_time).total_seconds() / 3600)
                last_commit_time = commit_time

            avg_session = sum(session_times) / len(session_times) if session_times else 0

            norm_hours = 8
            overtime = max(0, daily_hours - norm_hours)
            underwork = max(0, norm_hours - daily_hours)

            metrics_text = (
                f"Часы кодинга сегодня: {daily_hours:.2f} ч\n"
                f"Часы кодинга за неделю: {weekly_hours:.2f} ч\n"
                f"Средняя продолжительность сессии: {avg_session:.2f} ч\n"
                f"Овертайм: {overtime:.2f} ч\n"
                f"Недоработка: {underwork:.2f} ч"
            )
            self.time_metrics.setText(metrics_text)

            hours = np.zeros((7, 24))
            for commit in commits:
                commit_time = datetime.fromtimestamp(commit.committed_date)
                if commit_time >= week_ago:
                    day = commit_time.weekday()
                    hour = commit_time.hour
                    hours[day, hour] += 1

            self.time_heatmap.axes.clear()
            self.time_heatmap.axes.imshow(hours, cmap='hot', interpolation='nearest')
            self.time_heatmap.axes.set_xticks(range(24))
            self.time_heatmap.axes.set_yticks(range(7))
            self.time_heatmap.axes.set_yticklabels(['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'])
            self.time_heatmap.axes.set_xlabel("Часы")
            self.time_heatmap.axes.set_ylabel("Дни недели")
            self.time_heatmap.axes.set_title("Heatmap активности")
            self.time_heatmap.draw()

        except InvalidGitRepositoryError:
            self.time_metrics.setText("Ошибка: Указанная папка не является Git-репозиторием")
            self.time_heatmap.axes.clear()
            self.time_heatmap.draw()
        except Exception as e:
            self.time_metrics.setText(f"Ошибка при анализе репозитория: {str(e)}")
            self.time_heatmap.axes.clear()
            self.time_heatmap.draw()

    def update_code_metrics(self):
        project_path = self.settings_panel.project_path_input.text()
        if not project_path or not os.path.exists(project_path):
            self.code_metrics.setText("Укажите путь к проекту в настройках")
            return

        if not os.path.exists(os.path.join(project_path, '.git')):
            self.code_metrics.setText("Ошибка: Указанная папка не является Git-репозиторием")
            return

        try:
            repo = Repo(project_path)
            commits = list(repo.iter_commits(max_count=100))
            added_lines = 0
            deleted_lines = 0
            hotspots = {}
            python_files = [f for f in self.get_project_files(project_path) if f.endswith('.py')]

            for commit in commits:
                diff = commit.stats.total
                added_lines += diff['insertions']
                deleted_lines += diff['deletions']
                for file in commit.stats.files:
                    hotspots[file] = hotspots.get(file, 0) + 1

            total_cc = 0
            complex_files = []
            for file in python_files:
                with open(file, 'r', encoding='utf-8') as f:
                    code = f.read()
                cc_results = cc_visit(code)
                file_cc = sum(block.complexity for block in cc_results)
                total_cc += file_cc
                if file_cc > 10:
                    complex_files.append((file, file_cc))

            avg_cc = total_cc / len(python_files) if python_files else 0
            hotspots_text = "\n".join(f"{file}: {count} изменений" for file, count in sorted(hotspots.items(), key=lambda x: x[1], reverse=True)[:5])

            metrics_text = (
                f"Добавлено строк: {added_lines}\n"
                f"Удалено строк: {deleted_lines}\n"
                f"Средняя цикломатическая сложность: {avg_cc:.2f}\n"
                f"Сложные файлы:\n" + "\n".join(f"{file}: {cc}" for file, cc in complex_files[:5]) + "\n"
                f"Часто изменяемые файлы:\n{hotspots_text}\n"
                f"Рекомендации: Проверить файлы с высокой сложностью для рефакторинга."
            )
            self.code_metrics.setText(metrics_text)

        except InvalidGitRepositoryError:
            self.code_metrics.setText("Ошибка: Указанная папка не является Git-репозиторием")
        except Exception as e:
            self.code_metrics.setText(f"Ошибка при анализе кода: {str(e)}")

    def update_graph_metrics(self):
        project_path = self.settings_panel.project_path_input.text()
        if not project_path or not os.path.exists(project_path):
            self.trend_graph.axes.clear()
            self.trend_graph.draw()
            return

        if not os.path.exists(os.path.join(project_path, '.git')):
            self.trend_graph.axes.clear()
            self.trend_graph.draw()
            return

        try:
            repo = Repo(project_path)
            commits = list(repo.iter_commits(max_count=100))
            weeks = 4
            commits_per_week = [0] * weeks
            today = datetime.now()
            for commit in commits:
                commit_time = datetime.fromtimestamp(commit.committed_date)
                weeks_ago = (today - commit_time).days // 7
                if weeks_ago < weeks:
                    commits_per_week[weeks_ago] += 1

            self.trend_graph.axes.clear()
            self.trend_graph.axes.plot(range(weeks), commits_per_week[::-1], marker='o')
            self.trend_graph.axes.set_xticks(range(weeks))
            self.trend_graph.axes.set_xticklabels([f"Неделя {i+1}" for i in range(weeks)])
            self.trend_graph.axes.set_xlabel("Недели")
            self.trend_graph.axes.set_ylabel("Количество коммитов")
            self.trend_graph.axes.set_title("Тренд продуктивности")
            self.trend_graph.draw()

        except InvalidGitRepositoryError:
            self.trend_graph.axes.clear()
            self.trend_graph.draw()
        except Exception as e:
            self.trend_graph.axes.clear()
            self.trend_graph.draw()

    def get_project_files(self, project_path):
        files = []
        for root, _, filenames in os.walk(project_path):
            for filename in filenames:
                if filename.endswith(('.py', '.js', '.java', '.cs', '.cpp', '.h', '.go', '.rs', '.kt', '.swift',
                                      '.json', '.yaml', '.yml', '.toml', '.env', 'Dockerfile', '.dockerignore',
                                      '.md', '.rst', 'README.md', 'LICENSE', 'CHANGELOG.md', 'CONTRIBUTING.md',
                                      'CODESTYLE.md', 'package.json', 'requirements.txt', 'pom.xml', 'build.gradle',
                                      'Cargo.toml', '.csproj', '.sln', '.css', '.scss', '.png', '.jpg', '.svg', '.html')):
                    files.append(os.path.join(root, filename))
        return files

class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super().__init__(fig)
        self.setParent(parent)







if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = DevMetricsApp()
    window.show()
    sys.exit(app.exec_())