import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget,
                             QPushButton, QTabWidget, QHBoxLayout, QDockWidget,
                             QDesktopWidget, QLabel, QTextEdit, QProgressBar, QComboBox)
from PyQt5.QtCore import Qt, QRect, QPropertyAnimation, QSettings
from PyQt5.QtGui import QIcon
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from settings import SettingsPanel
from OpeningHours import update_opening_hours, get_years
from CodeAnalysis import update_code_analysis
from Charts import update_charts
from file_watcher import start_file_watcher
from WorkSchedule import WorkSchedulePanel
from datetime import datetime
import numpy as np
import calendar
import seaborn as sns
import matplotlib.pyplot as plt

class DevMetricsApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Анализатор продуктивности")
        self.settings = QSettings("MyCompany", "DevMetricsApp")
        self.observer = None
        self.init_ui()

    def init_ui(self):
        self.setFixedSize(1000, 1000)
        self.center_window()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.create_top_panel()
        self.create_settings_panel()
        self.create_work_schedule_panel()
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
        self.create_opening_hours_tab()
        self.create_code_analysis_tab()
        self.create_charts_tab()
        self.main_layout.addWidget(self.tabs)

    def create_opening_hours_tab(self):
        self.time_tab = QWidget()
        time_layout = QVBoxLayout(self.time_tab)

        time_layout.addWidget(QLabel("Время работы:"))
        self.time_metrics = QTextEdit()
        self.time_metrics.setReadOnly(True)
        time_layout.addWidget(self.time_metrics)

        # Выбор месяца и года
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("Месяц:"))
        self.month_selector = QComboBox()
        self.month_selector.addItems(["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                                      "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"])
        self.month_selector.currentIndexChanged.connect(self.update_opening_hours)
        controls_layout.addWidget(self.month_selector)

        controls_layout.addWidget(QLabel("Год:"))
        self.year_selector = QComboBox()
        self.year_selector.currentTextChanged.connect(self.update_opening_hours)
        controls_layout.addWidget(self.year_selector)

        controls_layout.addStretch()
        time_layout.addLayout(controls_layout)

        # Гистограмма
        self.time_histogram = MplCanvas(self, width=8, height=4, dpi=100)
        time_layout.addWidget(self.time_histogram)

        # Heatmap
        self.time_heatmap = MplCanvas(self, width=8, height=4, dpi=100)
        time_layout.addWidget(self.time_heatmap)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        time_layout.addWidget(self.progress_bar)

        self.tabs.addTab(self.time_tab, "Время работы")

    def create_code_analysis_tab(self):
        code_tab = QWidget()
        code_layout = QVBoxLayout(code_tab)

        code_layout.addWidget(QLabel("Анализ кода:"))
        self.code_metrics = QTextEdit()
        self.code_metrics.setReadOnly(True)
        code_layout.addWidget(self.code_metrics)

        self.tabs.addTab(code_tab, "Анализ кода")

    def create_charts_tab(self):
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
        menu_layout.addWidget(settings_btn)

        schedule_btn = QPushButton()
        schedule_btn.setIcon(QIcon.fromTheme("calendar"))
        schedule_btn.setText("Рабочий график")
        schedule_btn.clicked.connect(self.toggle_work_schedule)
        menu_layout.addWidget(schedule_btn)

        menu_layout.addStretch()
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

    def create_work_schedule_panel(self):
        self.work_schedule_widget = QWidget()
        schedule_layout = QVBoxLayout(self.work_schedule_widget)

        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.clicked.connect(self.toggle_work_schedule)
        close_layout.addWidget(close_btn)
        schedule_layout.addLayout(close_layout)

        self.work_schedule_panel = WorkSchedulePanel(self)
        schedule_layout.addWidget(self.work_schedule_panel)

        self.work_schedule_widget.hide()
        self.main_layout.addWidget(self.work_schedule_widget)

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
            self.work_schedule_widget.hide()
            self.settings_widget.show()
            if self.menu_dock.isVisible():
                self.toggle_menu()

    def toggle_work_schedule(self):
        if self.work_schedule_widget.isVisible():
            self.work_schedule_widget.hide()
            self.tabs.show()
        else:
            self.tabs.hide()
            self.settings_widget.hide()
            self.work_schedule_widget.show()
            if self.menu_dock.isVisible():
                self.toggle_menu()

    def load_settings(self):
        project_path = self.settings.value("project_path", "")
        self.settings_panel.project_path_input.setText(project_path)

        theme = self.settings.value("theme", "Светлая")
        self.settings_panel.theme_selector.setCurrentText(theme)
        self.settings_panel.change_theme(theme)

        self.update_years()
        self.update_opening_hours()
        self.update_code_analysis()
        self.update_charts()
        self.start_file_watcher(project_path)

    def closeEvent(self, event):
        if self.observer:
            self.observer.stop()
            self.observer.join()
        self.settings.setValue("project_path", self.settings_panel.project_path_input.text())
        self.settings.setValue("theme", self.settings_panel.theme_selector.currentText())
        event.accept()

    def stop_file_watcher(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

    def start_file_watcher(self, project_path):
        self.stop_file_watcher()
        self.observer = start_file_watcher(self, project_path)

    def update_years(self):
        project_path = self.settings_panel.project_path_input.text()
        years = get_years(project_path)
        self.year_selector.clear()
        self.year_selector.addItems([str(year) for year in years])
        current_year = str(datetime.now().year)
        if current_year in [str(year) for year in years]:
            self.year_selector.setCurrentText(current_year)

    def update_opening_hours(self):
        project_path = self.settings_panel.project_path_input.text()
        month = self.month_selector.currentIndex() + 1
        year = int(self.year_selector.currentText()) if self.year_selector.currentText() else datetime.now().year
        try:
            metrics_text, days, hours, weekend_days, heatmap_data = update_opening_hours(project_path, month, year)
            self.time_metrics.setText(metrics_text)

            # Гистограмма
            self.time_histogram.axes.clear()
            if days and any(hours):  # Проверяем, есть ли ненулевые часы
                hours_per_day = self.work_schedule_panel.get_hours_per_day()
                colors = []
                for i, day in enumerate(days):
                    if day in weekend_days:
                        colors.append('red')
                    elif hours[i] > hours_per_day:
                        colors.append('orange')
                    else:
                        colors.append('blue')

                self.time_histogram.axes.bar(days, hours, color=colors)
                self.time_histogram.axes.set_xticks(days)
                labels = [str(day) for day in days]
                for i, label in enumerate(self.time_histogram.axes.get_xticklabels()):
                    label.set_color('red' if days[i] in weekend_days else 'blue')

                self.time_histogram.axes.set_xticklabels(labels)
                self.time_histogram.axes.set_xlabel("Дни месяца")
                self.time_histogram.axes.set_ylabel("Отработанные часы")
                self.time_histogram.axes.set_title(
                    f"График отработанного времени ({self.month_selector.currentText()} {year})")
                max_hours = max(int(np.ceil(max(hours, default=0))), int(hours_per_day))
                self.time_histogram.axes.set_yticks(np.arange(0, max_hours + 1, 1))
            else:
                self.time_histogram.axes.text(0.5, 0.5, "Нет данных", ha='center', va='center', fontsize=12)
                self.time_histogram.axes.set_xlabel("Дни месяца")
                self.time_histogram.axes.set_ylabel("Отработанные часы")
                self.time_histogram.axes.set_title(
                    f"График отработанного времени ({self.month_selector.currentText()} {year})")

            # Heatmap
            try:
                # Пересоздаём оси для полного сброса
                self.time_heatmap.figure.clear()
                self.time_heatmap.axes = self.time_heatmap.figure.add_subplot(111)
                self.time_heatmap.figure.set_size_inches(8, 4)  # Фиксируем размер фигуры
                if hasattr(self.time_heatmap, 'colorbar') and self.time_heatmap.colorbar:
                    try:
                        self.time_heatmap.colorbar.remove()
                    except:
                        pass
                    self.time_heatmap.colorbar = None
                if heatmap_data.any():
                    # Увеличиваем нижний отступ для меток часов
                    self.time_heatmap.axes.set_position([0.1, 0.25, 0.7, 0.65])  # [left, bottom, width, height]
                    sns.heatmap(heatmap_data, ax=self.time_heatmap.axes, cmap="YlOrRd",
                                xticklabels=[f"{i}:00" for i in range(24)],  # Все 24 часа
                                yticklabels=["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
                                cbar_kws={'label': 'Количество коммитов', 'shrink': 0.8, 'pad': 0.05})
                    self.time_heatmap.axes.set_title("Heatmap активности (коммиты по дням и часам)")
                    self.time_heatmap.axes.set_xlabel("Часы")
                    self.time_heatmap.axes.set_ylabel("Дни недели")
                    # Настраиваем метки
                    self.time_heatmap.axes.tick_params(axis='x', labelsize=8, rotation=90)
                    self.time_heatmap.axes.tick_params(axis='y', labelsize=10)
                    self.time_heatmap.colorbar = self.time_heatmap.axes.collections[0].colorbar
                else:
                    self.time_heatmap.axes.set_position([0.1, 0.25, 0.8, 0.65])  # Без colorbar больше места
                    self.time_heatmap.axes.text(0.5, 0.5, "Нет данных", ha='center', va='center', fontsize=12)
                    self.time_heatmap.axes.set_xlabel("Часы")
                    self.time_heatmap.axes.set_ylabel("Дни недели")
                    self.time_heatmap.axes.set_title("Heatmap активности (коммиты по дням и часам)")
            except Exception as e:
                self.time_heatmap.figure.clear()
                self.time_heatmap.axes = self.time_heatmap.figure.add_subplot(111)
                self.time_heatmap.axes.set_position([0.1, 0.25, 0.8, 0.65])
                self.time_heatmap.axes.text(0.5, 0.5, f"Ошибка heatmap: {str(e)}", ha='center', va='center', fontsize=12)
                if hasattr(self.time_heatmap, 'colorbar') and self.time_heatmap.colorbar:
                    try:
                        self.time_heatmap.colorbar.remove()
                    except:
                        pass
                    self.time_heatmap.colorbar = None

            self.time_histogram.draw()
            self.time_heatmap.draw()

        except Exception as e:
            self.time_metrics.setText(f"Ошибка: {str(e)}")
            self.time_histogram.axes.clear()
            self.time_histogram.axes.text(0.5, 0.5, "Ошибка данных", ha='center', va='center', fontsize=12)
            self.time_histogram.draw()
            self.time_heatmap.figure.clear()
            self.time_heatmap.axes = self.time_heatmap.figure.add_subplot(111)
            self.time_heatmap.axes.set_position([0.1, 0.25, 0.8, 0.65])
            self.time_heatmap.axes.text(0.5, 0.5, "Ошибка данных", ha='center', va='center', fontsize=12)
            if hasattr(self.time_heatmap, 'colorbar') and self.time_heatmap.colorbar:
                try:
                    self.time_heatmap.colorbar.remove()
                except:
                    pass
                self.time_heatmap.colorbar = None
            self.time_heatmap.draw()

    def update_code_analysis(self):
        project_path = self.settings_panel.project_path_input.text()
        try:
            metrics_text = update_code_analysis(project_path, self.progress_bar)
            self.code_metrics.setText(metrics_text)
        except Exception as e:
            self.code_metrics.setText(f"Ошибка: {str(e)}")
        finally:
            self.progress_bar.setVisible(False)

    def update_charts(self):
        project_path = self.settings_panel.project_path_input.text()
        try:
            weeks, commits_per_week = update_charts(project_path)
            self.trend_graph.axes.clear()
            if weeks and commits_per_week:
                self.trend_graph.axes.plot(range(weeks), commits_per_week[::-1], marker='o')
                self.trend_graph.axes.set_xticks(range(weeks))
                self.trend_graph.axes.set_xticklabels([f"Неделя {i + 1}" for i in range(weeks)])
                self.trend_graph.axes.set_xlabel("Недели")
                self.trend_graph.axes.set_ylabel("Количество коммитов")
                self.trend_graph.axes.set_title("Тренд продуктивности")
            self.trend_graph.draw()
        except Exception as e:
            self.trend_graph.axes.clear()
            self.trend_graph.axes.text(0.5, 0.5, f"Ошибка: {str(e)}", ha='center', va='center', fontsize=12)
            self.trend_graph.draw()

class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=100)
        self.axes = fig.add_subplot(111)
        self.colorbar = None
        super().__init__(fig)
        self.setParent(parent)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = DevMetricsApp()
    window.show()
    sys.exit(app.exec_())