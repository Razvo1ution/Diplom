import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget,
                             QPushButton, QTabWidget, QHBoxLayout, QDockWidget,
                             QDesktopWidget, QLabel, QTextEdit, QProgressBar, QComboBox,
                             QMessageBox)
from PyQt5.QtCore import Qt, QRect, QPropertyAnimation, QSettings, QTimer
from PyQt5.QtGui import QIcon
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from settings import SettingsPanel
from OpeningHours import update_opening_hours, get_years
from CodeAnalysis import update_code_analysis
from Charts import update_charts
from WorkSchedule import WorkSchedulePanel
from ActivityTracker import ActivityTracker
from datetime import datetime
import numpy as np
import os
import logging

# Настройка логирования
logging.basicConfig(filename='app.log', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')

class DevMetricsApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Анализатор продуктивности")
        self.settings = QSettings("MyCompany", "DevMetricsApp")
        self.lunch_file = os.path.join(os.path.expanduser("~"), ".devmetrics_lunch")
        self.activity_tracker = None
        self.update_timer = None
        try:
            self.init_ui()
            logging.info("Приложение инициализировано")
        except Exception as e:
            logging.error(f"Ошибка при инициализации приложения: {str(e)}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось запустить приложение: {str(e)}")

    def init_ui(self):
        self.setFixedSize(1000, 800)
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

        # Таймер для обновления интерфейса
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.check_and_update)
        self.update_timer.start(2000)  # Проверка каждые 2 секунды

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

        time_layout.addWidget(QLabel("Активное время работы:"))
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

        # Кнопка "Обед"
        self.lunch_btn = QPushButton("Обед")
        self.lunch_btn.clicked.connect(self.take_lunch)
        controls_layout.addWidget(self.lunch_btn)

        controls_layout.addStretch()
        time_layout.addLayout(controls_layout)

        self.time_histogram = MplCanvas(self, width=8, height=4, dpi=100)
        time_layout.addWidget(self.time_histogram)

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
        try:
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
        except Exception as e:
            logging.error(f"Ошибка в toggle_menu: {str(e)}")

    def toggle_settings(self):
        try:
            if self.settings_widget.isVisible():
                self.settings_widget.hide()
                self.tabs.show()
            else:
                self.tabs.hide()
                self.work_schedule_widget.hide()
                self.settings_widget.show()
                if self.menu_dock.isVisible():
                    self.toggle_menu()
        except Exception as e:
            logging.error(f"Ошибка в toggle_settings: {str(e)}")

    def toggle_work_schedule(self):
        try:
            if self.work_schedule_widget.isVisible():
                self.work_schedule_widget.hide()
                self.tabs.show()
            else:
                self.tabs.hide()
                self.settings_widget.hide()
                self.work_schedule_widget.show()
                if self.menu_dock.isVisible():
                    self.toggle_menu()
        except Exception as e:
            logging.error(f"Ошибка в toggle_work_schedule: {str(e)}")

    def take_lunch(self):
        """Обрабатывает нажатие кнопки 'Обед'."""
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            project_path = self.settings_panel.project_path_input.text()
            if not project_path or not os.path.exists(project_path):
                QMessageBox.warning(self, "Ошибка", "Укажите корректный путь к проекту в настройках")
                return
            tracker = ActivityTracker(project_path, self.lunch_file, self.set_new_activity)
            if tracker.can_take_lunch(today_str):
                tracker.record_lunch(today_str, datetime.now().timestamp())
                self.lunch_btn.setEnabled(False)
                self.update_opening_hours()
                QMessageBox.information(self, "Обед", "Обед зарегистрирован (1 час)")
            else:
                QMessageBox.warning(self, "Ошибка", "Обед уже был взят сегодня!")
        except Exception as e:
            logging.error(f"Ошибка в take_lunch: {str(e)}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось зарегистрировать обед: {str(e)}")

    def load_settings(self):
        try:
            project_path = self.settings.value("project_path", "")
            self.settings_panel.project_path_input.setText(project_path)

            theme = self.settings.value("theme", "Светлая")
            self.settings_panel.theme_selector.setCurrentText(theme)
            self.settings_panel.change_theme(theme)

            self.update_years()
            self.update_opening_hours()
            self.update_code_analysis()
            self.update_charts()
            self.start_activity_tracker(project_path)
        except Exception as e:
            logging.error(f"Ошибка в load_settings: {str(e)}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки настроек: {str(e)}")

    def closeEvent(self, event):
        try:
            if self.activity_tracker:
                self.activity_tracker.stop_listeners()
                self.activity_tracker.stop_file_watcher()
            if self.update_timer:
                self.update_timer.stop()
            self.settings.setValue("project_path", self.settings_panel.project_path_input.text())
            self.settings.setValue("theme", self.settings_panel.theme_selector.currentText())
            event.accept()
        except Exception as e:
            logging.error(f"Ошибка в closeEvent: {str(e)}")

    def stop_activity_tracker(self):
        try:
            if self.activity_tracker:
                self.activity_tracker.stop_listeners()
                self.activity_tracker.stop_file_watcher()
                self.activity_tracker = None
            if self.update_timer:
                self.update_timer.stop()
        except Exception as e:
            logging.error(f"Ошибка в stop_activity_tracker: {str(e)}")

    def start_activity_tracker(self, project_path):
        try:
            self.stop_activity_tracker()
            if project_path and os.path.exists(project_path):
                self.activity_tracker = ActivityTracker(project_path, self.lunch_file, self.set_new_activity)
                self.update_timer.start(2000)
                logging.info(f"ActivityTracker запущен для {project_path}")
            else:
                logging.warning("Не указан или некорректен путь к проекту")
        except Exception as e:
            logging.error(f"Ошибка в start_activity_tracker: {str(e)}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось запустить отслеживание: {str(e)}")

    def set_new_activity(self):
        """Устанавливает флаг новой активности."""
        try:
            if self.activity_tracker:
                self.activity_tracker.new_activity = True
            logging.debug("Флаг new_activity установлен")
        except Exception as e:
            logging.error(f"Ошибка в set_new_activity: {str(e)}")

    def check_and_update(self):
        """Проверяет флаг new_activity и обновляет интерфейс."""
        try:
            if self.activity_tracker and self.activity_tracker.new_activity:
                self.update_opening_hours()
                self.activity_tracker.new_activity = False
                logging.debug("Интерфейс обновлён из-за новой активности")
        except Exception as e:
            logging.error(f"Ошибка в check_and_update: {str(e)}")

    def update_years(self):
        try:
            project_path = self.settings_panel.project_path_input.text()
            years = get_years(project_path)
            self.year_selector.clear()
            self.year_selector.addItems([str(year) for year in years])
            current_year = str(datetime.now().year)
            if current_year in [str(year) for year in years]:
                self.year_selector.setCurrentText(current_year)
        except Exception as e:
            logging.error(f"Ошибка в update_years: {str(e)}")

    def update_opening_hours(self):
        try:
            project_path = self.settings_panel.project_path_input.text()
            if not project_path or not os.path.exists(project_path):
                self.time_metrics.setText("Укажите корректный путь к проекту в настройках")
                self.time_histogram.axes.clear()
                self.time_histogram.draw()
                return
            month = self.month_selector.currentIndex() + 1
            year = int(self.year_selector.currentText()) if self.year_selector.currentText() else datetime.now().year
            metrics_text, days, hours, weekend_days = update_opening_hours(project_path, month, year, self.lunch_file)
            self.time_metrics.setText(metrics_text)

            self.time_histogram.axes.clear()
            if days and hours:
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

            self.time_histogram.draw()

            today_str = datetime.now().strftime("%Y-%m-%d")
            tracker = ActivityTracker(project_path, self.lunch_file, self.set_new_activity)
            self.lunch_btn.setEnabled(tracker.can_take_lunch(today_str))

        except Exception as e:
            logging.error(f"Ошибка в update_opening_hours: {str(e)}")
            self.time_metrics.setText(f"Ошибка: {str(e)}")
            self.time_histogram.axes.clear()
            self.time_histogram.draw()

    def update_code_analysis(self):
        try:
            project_path = self.settings_panel.project_path_input.text()
            if not project_path or not os.path.exists(project_path):
                self.code_metrics.setText("Укажите корректный путь к проекту в настройках")
                return
            metrics_text = update_code_analysis(project_path, self.progress_bar)
            self.code_metrics.setText(metrics_text)
        except Exception as e:
            logging.error(f"Ошибка в update_code_analysis: {str(e)}")
            self.code_metrics.setText(f"Ошибка: {str(e)}")
        finally:
            self.progress_bar.setVisible(False)

    def update_charts(self):
        try:
            project_path = self.settings_panel.project_path_input.text()
            if not project_path or not os.path.exists(project_path):
                self.trend_graph.axes.clear()
                self.trend_graph.draw()
                return
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
            logging.error(f"Ошибка в update_charts: {str(e)}")
            self.trend_graph.axes.clear()
            self.trend_graph.draw()

class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super().__init__(fig)
        self.setParent(parent)

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        window = DevMetricsApp()
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        logging.error(f"Ошибка при запуске приложения: {str(e)}")