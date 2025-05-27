import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget,
                             QPushButton, QTabWidget, QHBoxLayout, QDockWidget,
                             QDesktopWidget, QLabel, QTextEdit, QProgressBar, QComboBox,
                             QGroupBox, QListWidget, QTableWidget, QTableWidgetItem)
from PyQt5.QtCore import Qt, QRect, QPropertyAnimation, QSettings, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QFont, QFontDatabase
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from settings import SettingsPanel
from OpeningHours import update_opening_hours, get_years, format_time
from CodeAnalysis import update_code_analysis, get_repository_files
from Charts import update_charts
from file_watcher import start_file_watcher
from WorkSchedule import WorkSchedulePanel
from gigachat_integration import GigaChatPanel
from datetime import datetime
import numpy as np
import calendar
import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import logging

# Настройка логирования
logging.basicConfig(filename='devmetrics.log', level=logging.ERROR,
                    format='%(asctime)s - %(levelname)s - %(message)s')

class ActivityChart(FigureCanvas):
    def __init__(self, parent=None, width=10, height=4):
        self.fig = Figure(figsize=(width, height))
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)

    def update_chart(self, day, hourly_activity, work_start, work_end, lunch_start, lunch_end):
        self.axes.clear()
        hours = list(range(24))
        activity = [int(hourly_activity[day][hour]) for hour in hours]  # Преобразуем в целые числа

        # Создаем линейный график
        self.axes.plot(hours, activity, '-o', color='blue', linewidth=2, markersize=6)

        # Добавляем вертикальные линии для рабочего времени
        if work_start and work_end:
            self.axes.axvline(x=work_start.hour + work_start.minute/60, 
                            color='green', linestyle='--', label='Начало работы')
            self.axes.axvline(x=work_end.hour + work_end.minute/60, 
                            color='red', linestyle='--', label='Конец работы')

        # Добавляем вертикальные линии для обеда
        if lunch_start and lunch_end:
            self.axes.axvline(x=lunch_start.hour + lunch_start.minute/60, 
                            color='orange', linestyle='--', label='Начало обеда')
            self.axes.axvline(x=lunch_end.hour + lunch_end.minute/60, 
                            color='orange', linestyle='--', label='Конец обеда')

        # Закрашиваем области времени
        if work_start and work_end:
            work_start_time = work_start.hour + work_start.minute/60
            work_end_time = work_end.hour + work_end.minute/60
            lunch_start_time = lunch_start.hour + lunch_start.minute/60
            lunch_end_time = lunch_end.hour + lunch_end.minute/60

            # Закрашиваем рабочее время (до обеда)
            self.axes.fill_between(hours, 0, max(activity), 
                                 where=(np.array(hours) >= work_start_time) & 
                                       (np.array(hours) <= lunch_start_time),
                                 alpha=0.1, color='blue')
            
            # Закрашиваем рабочее время (после обеда)
            self.axes.fill_between(hours, 0, max(activity),
                                 where=(np.array(hours) >= lunch_end_time) & 
                                       (np.array(hours) <= work_end_time),
                                 alpha=0.1, color='blue')

            # Закрашиваем время обеда
            self.axes.fill_between(hours, 0, max(activity),
                                 where=(np.array(hours) >= lunch_start_time) & 
                                       (np.array(hours) <= lunch_end_time),
                                 alpha=0.1, color='orange')

        self.axes.set_xlabel('Часы')
        self.axes.set_ylabel('Количество коммитов')
        self.axes.set_title(f'Активность за день {day}')
        self.axes.set_xticks(hours)
        self.axes.set_yticks(np.arange(0, max(activity) + 1, 1))  # Целочисленные деления по оси Y
        self.axes.legend()
        self.axes.grid(True, linestyle='--', alpha=0.7)
        self.fig.tight_layout()
        self.draw()

class DevMetricsApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Анализатор продуктивности")
        self.settings = QSettings("MyCompany", "DevMetricsApp")
        self.observer = None
        self.chart_data = {'weeks': 0, 'commits_per_week': []}
        self.time_data = {
            'metrics_text': '',
            'days': [],
            'hours': [],
            'weekend_days': [],
            'heatmap_data': np.array([]),
            'month_days': [],
            'daily_metrics': {},
            'hourly_activity': {},
            'work_start': None,
            'work_end': None,
            'lunch_start': None,
            'lunch_end': None
        }
        self.chart_time_data = {
            'metrics_text': '',
            'days': [],
            'hours': [],
            'weekend_days': [],
            'heatmap_data': np.array([]),
            'month_days': [],
            'daily_metrics': {}
        }
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
        self.create_gigachat_panel()
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
        self.create_gigachat_tab()
        self.main_layout.addWidget(self.tabs)

    def create_opening_hours_tab(self):
        self.time_tab = QWidget()
        time_layout = QVBoxLayout(self.time_tab)

        # Верхняя часть с метриками
        top_section = QVBoxLayout()  # Изменено на вертикальное расположение

        # Метрики
        self.time_metrics = QTextEdit()
        self.time_metrics.setReadOnly(True)
        top_section.addWidget(QLabel("Время работы:"))
        top_section.addWidget(self.time_metrics)

        time_layout.addLayout(top_section)

        # Контролы выбора периода
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

        controls_layout.addWidget(QLabel("День:"))
        self.day_selector = QComboBox()
        self.day_selector.currentIndexChanged.connect(self.update_day_metrics)
        controls_layout.addWidget(self.day_selector)

        controls_layout.addStretch()
        time_layout.addLayout(controls_layout)

        # Метрики за выбранный день
        time_layout.addWidget(QLabel("Метрики за выбранный день:"))
        self.day_metrics = QTextEdit()
        self.day_metrics.setReadOnly(True)
        self.day_metrics.setFixedHeight(150)
        time_layout.addWidget(self.day_metrics)

        # График активности внизу
        self.activity_chart = ActivityChart()
        time_layout.addWidget(self.activity_chart)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        time_layout.addWidget(self.progress_bar)

        self.tabs.addTab(self.time_tab, "Время работы")

    def create_code_analysis_tab(self):
        code_tab = QWidget()
        code_layout = QVBoxLayout(code_tab)

        # Верхняя часть с выбором файлов
        files_group = QGroupBox("Выбор файлов для анализа")
        files_layout = QVBoxLayout()
        
        # Список файлов с возможностью множественного выбора
        self.files_list = QListWidget()
        self.files_list.setSelectionMode(QListWidget.MultiSelection)
        files_layout.addWidget(self.files_list)
        
        files_group.setLayout(files_layout)
        code_layout.addWidget(files_group)

        # Группа с выбором даты
        date_group = QGroupBox("Выбор даты")
        date_layout = QHBoxLayout()

        # Селекторы даты
        date_layout.addWidget(QLabel("Год:"))
        self.code_year_selector = QComboBox()
        self.code_year_selector.currentTextChanged.connect(self.update_code_analysis_days)
        date_layout.addWidget(self.code_year_selector)

        date_layout.addWidget(QLabel("Месяц:"))
        self.code_month_selector = QComboBox()
        self.code_month_selector.addItems(["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                                         "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"])
        self.code_month_selector.currentIndexChanged.connect(self.update_code_analysis_days)
        date_layout.addWidget(self.code_month_selector)

        date_layout.addWidget(QLabel("День:"))
        self.code_day_selector = QComboBox()
        date_layout.addWidget(self.code_day_selector)

        date_group.setLayout(date_layout)
        code_layout.addWidget(date_group)

        # Кнопка анализа
        analyze_btn = QPushButton("Анализировать")
        analyze_btn.clicked.connect(self.trigger_code_analysis)
        code_layout.addWidget(analyze_btn)

        # Группа для отображения результатов анализа
        results_group = QGroupBox("Результаты анализа")
        results_layout = QVBoxLayout()

        # Текстовое поле для отображения результатов по выбранным файлам
        self.selected_files_metrics = QTextEdit()
        self.selected_files_metrics.setReadOnly(True)
        self.selected_files_metrics.setPlaceholderText("Выберите файлы и дату для анализа")
        results_layout.addWidget(QLabel("Статистика по выбранным файлам:"))
        results_layout.addWidget(self.selected_files_metrics)

        # Текстовое поле для общей статистики
        self.code_metrics = QTextEdit()
        self.code_metrics.setReadOnly(True)
        self.code_metrics.setPlaceholderText("Общая статистика проекта")
        results_layout.addWidget(QLabel("Общая статистика за все время:"))
        results_layout.addWidget(self.code_metrics)

        results_group.setLayout(results_layout)
        code_layout.addWidget(results_group)

        self.tabs.addTab(code_tab, "Анализ кода")

    def create_charts_tab(self):
        graph_tab = QWidget()
        graph_layout = QVBoxLayout(graph_tab)

        graph_layout.addWidget(QLabel("Дашборд продуктивности:"))

        self.trend_graph = MplCanvas(self, width=8, height=3, dpi=100)
        graph_layout.addWidget(QLabel("Тренд продуктивности:"))
        graph_layout.addWidget(self.trend_graph)

        self.dash_histogram = MplCanvas(self, width=8, height=3, dpi=100)
        graph_layout.addWidget(QLabel("Гистограмма отработанного времени:"))
        graph_layout.addWidget(self.dash_histogram)

        self.dash_heatmap = MplCanvas(self, width=8, height=3, dpi=100)
        graph_layout.addWidget(QLabel("Heatmap активности:"))
        graph_layout.addWidget(self.dash_heatmap)

        # Контролы для выбора года и месяца
        charts_controls_layout = QHBoxLayout()
        charts_controls_layout.addWidget(QLabel("Месяц:"))
        self.month_selector_charts = QComboBox()
        self.month_selector_charts.addItems(["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                                             "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"])
        self.month_selector_charts.currentIndexChanged.connect(self.update_charts)
        charts_controls_layout.addWidget(self.month_selector_charts)

        charts_controls_layout.addWidget(QLabel("Год:"))
        self.year_selector_charts = QComboBox()
        self.year_selector_charts.currentTextChanged.connect(self.update_charts)
        charts_controls_layout.addWidget(self.year_selector_charts)

        charts_controls_layout.addStretch()
        graph_layout.addLayout(charts_controls_layout)

        self.tabs.addTab(graph_tab, "Графики")

    def create_gigachat_tab(self):
        self.tabs.addTab(self.gigachat_panel, "GigaChat")

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

    def create_gigachat_panel(self):
        self.gigachat_panel = GigaChatPanel(self)

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

        # Загружаем тему, по умолчанию "Светлая"
        theme = self.settings.value("theme", "Светлая")
        self.settings_panel.theme_selector.setCurrentText(theme)
        self.settings_panel.change_theme(theme)

        self.update_years()
        self.update_opening_hours()
        self.update_years_charts()
        self.update_charts()
        self.update_code_analysis_years()
        self.populate_files_list()
        self.update_code_analysis()
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
        try:
            years = get_years(project_path)
            self.year_selector.clear()
            self.year_selector.addItems([str(year) for year in years])
            current_year = str(datetime.now().year)
            if current_year in [str(year) for year in years]:
                self.year_selector.setCurrentText(current_year)
        except Exception as e:
            logging.error(f"Error in update_years: {str(e)}")
            self.year_selector.clear()
            self.year_selector.addItems([str(datetime.now().year)])

    def update_years_charts(self):
        project_path = self.settings_panel.project_path_input.text()
        try:
            years = get_years(project_path)
            self.year_selector_charts.clear()
            self.year_selector_charts.addItems([str(year) for year in years])
            current_year = str(datetime.now().year)
            if current_year in [str(year) for year in years]:
                self.year_selector_charts.setCurrentText(current_year)
        except Exception as e:
            logging.error(f"Error in update_years_charts: {str(e)}")
            self.year_selector_charts.clear()
            self.year_selector_charts.addItems([str(datetime.now().year)])

    def update_opening_hours(self):
        project_path = self.settings_panel.project_path_input.text()
        month = self.month_selector.currentIndex() + 1
        year = int(self.year_selector.currentText()) if self.year_selector.currentText() else datetime.now().year
        try:
            (metrics_text, days, hours, weekend_days, heatmap_data, month_days, 
             daily_metrics, hourly_activity, work_start, work_end, lunch_start, lunch_end) = update_opening_hours(
                project_path, month, year)
            
            self.time_data = {
                'metrics_text': metrics_text,
                'days': days,
                'hours': hours,
                'weekend_days': weekend_days,
                'heatmap_data': heatmap_data,
                'month_days': month_days,
                'daily_metrics': daily_metrics,
                'hourly_activity': hourly_activity,
                'work_start': work_start,
                'work_end': work_end,
                'lunch_start': lunch_start,
                'lunch_end': lunch_end
            }
            self.time_metrics.setText(metrics_text)

            # Обновляем выпадающий список дней
            self.day_selector.clear()
            self.day_selector.addItems([f"День {day}" for day in days])
            self.day_selector.setCurrentIndex(0)

            # Обновляем метрики для выбранного дня
            self.update_day_metrics()

            self.update_dashboard()

        except Exception as e:
            logging.error(f"Error in update_opening_hours: {str(e)}")
            self.time_metrics.setText(f"Ошибка: {str(e)}")
            self.time_data = {
                'metrics_text': '',
                'days': [],
                'hours': [],
                'weekend_days': [],
                'heatmap_data': np.array([]),
                'month_days': [],
                'daily_metrics': {},
                'hourly_activity': {},
                'work_start': None,
                'work_end': None,
                'lunch_start': None,
                'lunch_end': None
            }
            self.day_selector.clear()
            self.day_metrics.setText("Нет данных")
            self.update_dashboard()

    def update_day_metrics(self):
        if not self.time_data['daily_metrics']:
            self.day_metrics.setText("Нет данных")
            self.activity_chart.axes.clear()
            self.activity_chart.draw()
            return

        selected_day_text = self.day_selector.currentText()
        if not selected_day_text:
            self.day_metrics.setText("Выберите день")
            self.activity_chart.axes.clear()
            self.activity_chart.draw()
            return

        selected_day = int(selected_day_text.split()[1])
        daily_metrics = self.time_data['daily_metrics']

        if selected_day not in daily_metrics:
            self.day_metrics.setText(f"Нет данных за День {selected_day}")
            self.activity_chart.axes.clear()
            self.activity_chart.draw()
            return

        day_data = daily_metrics[selected_day]
        work_start, work_end = day_data['work_period'] if day_data['work_period'] else (None, None)
        total_time = day_data['total_time']
        dead_periods = day_data['dead_periods']
        commits = day_data['commits']
        night_commits = day_data['night_commits']

        # Форматируем время работы с проверкой на None
        work_period = (f"с {work_start.strftime('%H:%M')} до {work_end.strftime('%H:%M')}"
                       if work_start and work_end else "Нет активности")
        total_time_str = format_time(total_time) if total_time > 0 else "0ч"

        # Форматируем мёртвые периоды
        dead_periods_str = ", ".join([f"с {start.strftime('%H:%M')} до {end.strftime('%H:%M')}"
                                     for start, end in dead_periods]) if dead_periods else "Нет мёртвых периодов"

        metrics_text = (
            f"Время работы: {work_period}\n"
            f"Общее время: {total_time_str}\n"
            f"Мёртвые периоды: {dead_periods_str}\n"
            f"Коммиты: {commits}\n"
            f"Ночные коммиты: {night_commits}"
        )
        self.day_metrics.setText(metrics_text)

        # Обновляем график активности
        self.activity_chart.update_chart(
            selected_day,
            self.time_data['hourly_activity'],
            self.time_data['work_start'],
            self.time_data['work_end'],
            self.time_data['lunch_start'],
            self.time_data['lunch_end']
        )

    def update_code_analysis_years(self):
        """Обновляет список лет в выпадающем списке для анализа кода"""
        project_path = self.settings_panel.project_path_input.text()
        try:
            years = get_years(project_path)
            self.code_year_selector.clear()
            self.code_year_selector.addItems([str(year) for year in years])
            current_year = str(datetime.now().year)
            if current_year in [str(year) for year in years]:
                self.code_year_selector.setCurrentText(current_year)
        except Exception as e:
            logging.error(f"Error in update_code_analysis_years: {str(e)}")
            self.code_year_selector.clear()
            self.code_year_selector.addItems([str(datetime.now().year)])

    def update_code_analysis_days(self):
        """Обновляет список дней в зависимости от выбранного месяца и года"""
        try:
            year = int(self.code_year_selector.currentText())
            month = self.code_month_selector.currentIndex() + 1
            _, last_day = calendar.monthrange(year, month)
            
            self.code_day_selector.clear()
            self.code_day_selector.addItems([str(day) for day in range(1, last_day + 1)])
        except Exception as e:
            logging.error(f"Error in update_code_analysis_days: {str(e)}")
            self.code_day_selector.clear()

    def populate_files_list(self):
        """Заполняет список файлов из репозитория"""
        project_path = self.settings_panel.project_path_input.text()
        try:
            files = get_repository_files(project_path)
            self.files_list.clear()
            for file in sorted(files):  # Сортируем файлы по алфавиту
                self.files_list.addItem(file)
        except Exception as e:
            logging.error(f"Error in populate_files_list: {str(e)}")
            self.files_list.clear()

    def trigger_code_analysis(self):
        """Запускает анализ кода с выбранными параметрами"""
        selected_files = [item.text() for item in self.files_list.selectedItems()]
        
        try:
            year = int(self.code_year_selector.currentText())
            month = self.code_month_selector.currentIndex() + 1
            day = int(self.code_day_selector.currentText())
            
            date_filter = {
                'year': year,
                'month': month,
                'day': day
            }
        except Exception as e:
            logging.error(f"Error preparing date filter: {str(e)}")
            date_filter = None

        self.update_code_analysis(selected_files=selected_files, date_filter=date_filter)

    def update_code_analysis(self, selected_files=None, date_filter=None):
        """Обновленный метод анализа кода с поддержкой фильтров"""
        project_path = self.settings_panel.project_path_input.text()
        if not project_path:
            self.selected_files_metrics.setText("Ошибка: Проект не найден. Укажите путь в настройках.")
            self.code_metrics.setText("Ошибка: Проект не найден. Укажите путь в настройках.")
            return

        self.progress_bar.setVisible(True)
        analysis_result = update_code_analysis(project_path, self.progress_bar, 
                                            author=None, 
                                            selected_files=selected_files, 
                                            date_filter=date_filter)
        self.progress_bar.setVisible(False)

        if analysis_result.get("error"):
            self.selected_files_metrics.setText(analysis_result["error"])
            self.code_metrics.setText(analysis_result["error"])
            return

        # Отображение статистики по выбранным файлам за конкретный день
        if selected_files and date_filter and analysis_result.get("files_daily_stats"):
            files_stats_text = "Статистика по выбранным файлам за {}.{}.{}:\n\n".format(
                date_filter['day'], date_filter['month'], date_filter['year']
            )
            
            # Статистика по каждому файлу
            for file_path, stats in analysis_result["files_daily_stats"].items():
                files_stats_text += f"Файл: {file_path}\n"
                files_stats_text += f"  Добавлено строк: {stats['added']}\n"
                files_stats_text += f"  Удалено строк: {stats['removed']}\n\n"

            # Общая статистика по выбранным файлам за день
            if analysis_result.get("selected_files_summary_today"):
                summary = analysis_result["selected_files_summary_today"]
                files_stats_text += "\nОбщая статистика по выбранным файлам за день:\n"
                files_stats_text += f"Всего добавлено строк: {summary['total_lines_added']}\n"
                files_stats_text += f"Всего удалено строк: {summary['total_lines_removed']}\n"
            
            self.selected_files_metrics.setText(files_stats_text)
        else:
            self.selected_files_metrics.setText(
                "Выберите файлы и дату для просмотра детальной статистики"
            )

        # Отображение общей статистики за все время
        if analysis_result.get("overall_metrics_all_time"):
            all_time_metrics = analysis_result["overall_metrics_all_time"]
            all_time_text = "Статистика за все время работы над проектом:\n\n"
            all_time_text += f"Общее количество изменённых файлов: {all_time_metrics['total_files_changed']}\n"
            all_time_text += f"Всего добавлено строк: {all_time_metrics['total_lines_added']}\n"
            all_time_text += f"Всего удалено строк: {all_time_metrics['total_lines_removed']}\n"
            all_time_text += f"Распределение по расширениям: {dict(sorted(all_time_metrics['files_by_extension'].items()))}\n"
            
            self.code_metrics.setText(all_time_text)
        else:
            self.code_metrics.setText("Нет данных об изменениях в проекте")

    def update_charts(self):
        project_path = self.settings_panel.project_path_input.text()
        month = self.month_selector_charts.currentIndex() + 1
        year = int(self.year_selector_charts.currentText()) if self.year_selector_charts.currentText() else datetime.now().year
        try:
            metrics_text, days, hours, weekend_days, heatmap_data, month_days, daily_metrics = update_opening_hours(project_path, month, year)
            self.chart_time_data = {
                'metrics_text': metrics_text,
                'days': days,
                'hours': hours,
                'weekend_days': weekend_days,
                'heatmap_data': heatmap_data,
                'month_days': month_days,
                'daily_metrics': daily_metrics
            }
            weeks, commits_per_week = update_charts(project_path)
            self.chart_data = {'weeks': weeks, 'commits_per_week': commits_per_week}
            self.update_dashboard()
        except Exception as e:
            logging.error(f"Error in update_charts: {str(e)}")
            self.chart_time_data = {
                'metrics_text': '',
                'days': [],
                'hours': [],
                'weekend_days': [],
                'heatmap_data': np.array([]),
                'month_days': [],
                'daily_metrics': {}
            }
            self.chart_data = {'weeks': 0, 'commits_per_week': []}
            self.update_dashboard()

    def update_dashboard(self):
        # Определяем текущую тему
        theme = self.settings_panel.theme_selector.currentText()

        # Настройки цветов для графиков в зависимости от темы
        if theme == "Светлая":
            text_color = 'black'
            bg_color = 'white'
            grid_color = 'gray'
        elif theme == "Темная":
            text_color = 'white'
            bg_color = '#353535'
            grid_color = 'lightgray'
        else:  # Темный контраст
            text_color = '#6B8E23'
            bg_color = '#000000'
            grid_color = '#6B8E23'

        # Тренд продуктивности
        self.trend_graph.axes.clear()
        weeks = self.chart_data['weeks']
        commits_per_week = self.chart_data['commits_per_week']
        if weeks and commits_per_week and any(commits_per_week):
            self.trend_graph.axes.plot(range(weeks), commits_per_week[::-1], marker='o', color='orange')
            self.trend_graph.axes.set_xticks(range(weeks))
            self.trend_graph.axes.set_xticklabels([f"Неделя {i + 1}" for i in range(weeks)], color=text_color)
            self.trend_graph.axes.set_xlabel("Недели", color=text_color)
            self.trend_graph.axes.set_ylabel("Количество коммитов", color=text_color)
            self.trend_graph.axes.set_title("Тренд продуктивности", color=text_color)
            self.trend_graph.axes.set_facecolor(bg_color)
            self.trend_graph.figure.set_facecolor(bg_color)
            self.trend_graph.axes.tick_params(colors=text_color)
            self.trend_graph.axes.grid(True, color=grid_color, linestyle='--', alpha=0.7)
        else:
            self.trend_graph.axes.text(0.5, 0.5, "Нет данных для графика", ha='center', va='center', fontsize=12, color=text_color)
            self.trend_graph.axes.set_xlabel("Недели", color=text_color)
            self.trend_graph.axes.set_ylabel("Количество коммитов", color=text_color)
            self.trend_graph.axes.set_title("Тренд продуктивности", color=text_color)
            self.trend_graph.axes.set_facecolor(bg_color)
            self.trend_graph.figure.set_facecolor(bg_color)
        self.trend_graph.draw()

        # Гистограмма отработанного времени
        self.dash_histogram.axes.clear()
        days = self.chart_time_data['days']
        hours = self.chart_time_data['hours']
        weekend_days = self.chart_time_data['weekend_days']
        if days and any(hours):
            hours_per_day = self.work_schedule_panel.get_hours_per_day()
            colors = []
            for i, day in enumerate(days):
                if day in weekend_days:
                    colors.append('red')
                elif hours[i] > hours_per_day:
                    colors.append('orange')
                else:
                    colors.append('blue')

            self.dash_histogram.axes.bar(days, hours, color=colors)
            self.dash_histogram.axes.set_xticks(days)
            labels = [str(day) for day in days]
            for i, label in enumerate(self.dash_histogram.axes.get_xticklabels()):
                label.set_color('red' if days[i] in weekend_days else text_color)
            self.dash_histogram.axes.set_xticklabels(labels, color=text_color)
            self.dash_histogram.axes.set_xlabel("Дни месяца", color=text_color)
            self.dash_histogram.axes.set_ylabel("Отработанные часы", color=text_color)
            month = self.month_selector_charts.currentText()
            year = self.year_selector_charts.currentText() or str(datetime.now().year)
            self.dash_histogram.axes.set_title(f"График отработанного времени ({month} {year})", color=text_color)
            self.dash_histogram.axes.set_facecolor(bg_color)
            self.dash_histogram.figure.set_facecolor(bg_color)
            self.dash_histogram.axes.tick_params(colors=text_color)
            self.dash_histogram.axes.grid(True, color=grid_color, linestyle='--', alpha=0.7)
            max_hours = max(int(np.ceil(max(hours, default=0))), int(hours_per_day))
            self.dash_histogram.axes.set_yticks(np.arange(0, max_hours + 1, 1))
        else:
            self.dash_histogram.axes.text(0.5, 0.5, "Нет данных", ha='center', va='center', fontsize=12, color=text_color)
            self.dash_histogram.axes.set_xlabel("Дни месяца", color=text_color)
            self.dash_histogram.axes.set_ylabel("Отработанные часы", color=text_color)
            self.dash_histogram.axes.set_title("График отработанного времени", color=text_color)
            self.dash_histogram.axes.set_facecolor(bg_color)
            self.dash_histogram.figure.set_facecolor(bg_color)
        self.dash_histogram.draw()

        # Heatmap активности
        self.dash_heatmap.figure.clear()
        self.dash_heatmap.axes = self.dash_heatmap.figure.add_subplot(111)
        self.dash_heatmap.figure.set_size_inches(8, 3)
        if hasattr(self.dash_heatmap, 'colorbar') and self.dash_heatmap.colorbar:
            try:
                self.dash_heatmap.colorbar.remove()
            except:
                pass
            self.dash_heatmap.colorbar = None
        heatmap_data = self.chart_time_data['heatmap_data']
        month_days = self.chart_time_data['month_days']
        if heatmap_data.size > 0 and heatmap_data.any():
            self.dash_heatmap.axes.set_position([0.1, 0.4, 0.7, 0.5])
            sns.heatmap(heatmap_data, ax=self.dash_heatmap.axes, cmap="YlOrRd",
                        xticklabels=[f"{i}:00" for i in range(0, 24, 3)],
                        yticklabels=[str(day) for day in month_days],
                        cbar_kws={'label': 'Количество коммитов', 'shrink': 0.8, 'pad': 0.05})
            self.dash_heatmap.axes.set_title("Heatmap активности (коммиты по дням и часам)", color=text_color)
            self.dash_heatmap.axes.set_xlabel("Часы", color=text_color)
            self.dash_heatmap.axes.set_ylabel("Дни месяца", color=text_color)
            self.dash_heatmap.axes.tick_params(axis='x', labelsize=5, rotation=90, colors=text_color)
            self.dash_heatmap.axes.tick_params(axis='y', labelsize=8, colors=text_color)
            self.dash_heatmap.axes.set_facecolor(bg_color)
            self.dash_heatmap.figure.set_facecolor(bg_color)
            self.dash_heatmap.colorbar = self.dash_heatmap.axes.collections[0].colorbar
            self.dash_heatmap.colorbar.set_label('Количество коммитов', color=text_color)
            self.dash_heatmap.colorbar.ax.yaxis.set_tick_params(color=text_color)
            self.dash_heatmap.colorbar.ax.tick_params(colors=text_color)
            for label in self.dash_heatmap.colorbar.ax.get_yticklabels():
                label.set_color(text_color)
            self.dash_heatmap.figure.tight_layout()
        else:
            self.dash_heatmap.axes.set_position([0.1, 0.4, 0.8, 0.5])
            self.dash_heatmap.axes.text(0.5, 0.5, "Нет данных", ha='center', va='center', fontsize=12, color=text_color)
            self.dash_heatmap.axes.set_xlabel("Часы", color=text_color)
            self.dash_heatmap.axes.set_ylabel("Дни месяца", color=text_color)
            self.dash_heatmap.axes.set_title("Heatmap активности (коммиты по дням и часам)", color=text_color)
            self.dash_heatmap.axes.set_facecolor(bg_color)
            self.dash_heatmap.figure.set_facecolor(bg_color)
            self.dash_heatmap.figure.tight_layout()
        self.dash_heatmap.draw()

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

    # Загрузка шрифта из файла
    font_db = QFontDatabase()
    font_path = os.path.join("TDAText", "TDAText.ttf")
    font_size = 10
    font_family = None

    try:
        if os.path.exists(font_path):
            font_id = font_db.addApplicationFont(font_path)
            if font_id != -1:
                font_families = font_db.applicationFontFamilies(font_id)
                if font_families:
                    font_family = font_families[0]
                    logging.info(f"Шрифт {font_family} успешно загружен из {font_path}")
                else:
                    logging.error(f"Не удалось получить имя шрифта из файла {font_path}")
            else:
                logging.error(f"Не удалось загрузить шрифт из файла {font_path}")
        else:
            logging.error(f"Файл шрифта {font_path} не найден")
    except Exception as e:
        logging.error(f"Ошибка при загрузке шрифта: {str(e)}")

    if font_family:
        app_font = QFont(font_family, font_size)
    else:
        logging.warning("Шрифт TDAText не загружен, используется Arial")
        app_font = QFont("Arial", font_size)
    app.setFont(app_font)

    if font_family:
        font_manager = fm.FontManager()
        font_manager.addfont(font_path)
        plt.rcParams['font.family'] = font_family
        plt.rcParams['font.size'] = font_size
    else:
        plt.rcParams['font.family'] = 'Arial'
        plt.rcParams['font.size'] = font_size

    window = DevMetricsApp()
    window.show()
    sys.exit(app.exec_())