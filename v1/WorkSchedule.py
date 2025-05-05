from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                             QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                             QMessageBox)
from PyQt5.QtCore import Qt
from datetime import datetime, date
from calendar import monthrange, weekday
import os

class WorkSchedulePanel(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.schedule_file = os.path.join(os.path.expanduser("~"), ".devmetrics_schedule")
        self.hours_file = os.path.join(os.path.expanduser("~"), ".devmetrics_hours")
        self.temp_schedule = {}  # Временное хранение графика
        self.temp_hours = None  # Временное хранение часов
        self.temp_template = None  # Временное хранение шаблона
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Шаблоны
        layout.addWidget(QLabel("Шаблоны:"))
        self.template_selector = QComboBox()
        self.template_selector.addItems(["5/2 (8 часов)", "2/2 (12 часов)", "Пользовательский"])
        self.template_selector.currentTextChanged.connect(self.update_temp_template)
        layout.addWidget(self.template_selector)

        # Рабочие часы в день
        hours_layout = QHBoxLayout()
        hours_layout.addWidget(QLabel("Рабочие часы в день:"))
        self.hours_input = QLineEdit()
        self.hours_input.setPlaceholderText("Введите часы (1-24)")
        self.hours_input.setText(self.load_hours())
        self.hours_input.textChanged.connect(self.update_temp_hours)
        hours_layout.addWidget(self.hours_input)
        hours_layout.addStretch()
        layout.addLayout(hours_layout)

        # Выбор месяца для настройки графика
        layout.addWidget(QLabel("Месяц:"))
        self.month_selector = QComboBox()
        self.month_selector.addItems(["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                                     "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"])
        self.month_selector.setCurrentIndex(datetime.now().month - 1)
        self.month_selector.currentIndexChanged.connect(self.update_schedule_table)
        layout.addWidget(self.month_selector)

        # Таблица графика
        self.schedule_table = QTableWidget()
        self.schedule_table.setColumnCount(7)
        self.schedule_table.setHorizontalHeaderLabels(['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'])
        self.schedule_table.cellClicked.connect(self.toggle_day)
        layout.addWidget(self.schedule_table)

        # Кнопка "Применить"
        apply_btn = QPushButton("Применить")
        apply_btn.clicked.connect(self.apply_settings)
        layout.addWidget(apply_btn)

        layout.addStretch()

        self.update_schedule_table()

    def update_temp_template(self, template):
        self.temp_template = template
        month = self.month_selector.currentIndex() + 1
        year = datetime.now().year
        days_in_month = monthrange(year, month)[1]
        schedule = {}

        if template == "5/2 (8 часов)":
            self.hours_input.setText("8")
            self.temp_hours = "8"
            for day in range(1, days_in_month + 1):
                wday = weekday(year, month, day)  # 0=Пн, 6=Вс
                is_workday = wday < 5  # Пн-Пт рабочие
                schedule[day] = is_workday
        elif template == "2/2 (12 часов)":
            self.hours_input.setText("12")
            self.temp_hours = "12"
            for day in range(1, days_in_month + 1):
                is_workday = (day % 4) in [1, 2]  # Два рабочих, два выходных
                schedule[day] = is_workday
        else:
            schedule = self.load_schedule(year, month)
            self.hours_input.setText(self.load_hours())
            self.temp_hours = self.load_hours()

        self.temp_schedule[(year, month)] = schedule
        self.update_schedule_table()

    def update_temp_hours(self, text):
        self.temp_hours = text

    def apply_settings(self):
        try:
            # Сохраняем часы
            if self.temp_hours:
                hours = float(self.temp_hours)
                if not 1 <= hours <= 24:
                    raise ValueError("Часы должны быть от 1 до 24")
                with open(self.hours_file, 'w') as f:
                    f.write(str(hours))

            # Сохраняем график
            if self.temp_schedule:
                schedules = {}
                if os.path.exists(self.schedule_file):
                    try:
                        with open(self.schedule_file, 'r') as f:
                            schedules = eval(f.read())
                    except:
                        pass
                schedules.update(self.temp_schedule)
                with open(self.schedule_file, 'w') as f:
                    f.write(str(schedules))

            QMessageBox.information(self, "Успех", "Рабочий график успешно применён")
            self.parent.update_opening_hours()  # Обновляем гистограмму
        except ValueError as e:
            QMessageBox.warning(self, "Ошибка", str(e))

    def load_hours(self):
        try:
            if os.path.exists(self.hours_file):
                with open(self.hours_file, 'r') as f:
                    return f.read().strip()
            return "8"  # По умолчанию 8 часов
        except:
            return "8"

    def save_schedule(self, year, month, schedule):
        schedules = {}
        if os.path.exists(self.schedule_file):
            try:
                with open(self.schedule_file, 'r') as f:
                    schedules = eval(f.read())
            except:
                pass

        schedules[(year, month)] = schedule
        with open(self.schedule_file, 'w') as f:
            f.write(str(schedules))

    def load_schedule(self, year, month):
        if os.path.exists(self.schedule_file):
            try:
                with open(self.schedule_file, 'r') as f:
                    schedules = eval(f.read())
                return schedules.get((year, month), {})
            except:
                pass
        days_in_month = monthrange(year, month)[1]
        return {day: True for day in range(1, days_in_month + 1)}  # По умолчанию все дни рабочие

    def update_schedule_table(self):
        month = self.month_selector.currentIndex() + 1
        year = datetime.now().year
        days_in_month = monthrange(year, month)[1]
        schedule = self.temp_schedule.get((year, month), self.load_schedule(year, month))

        # Определяем количество строк в таблице
        weeks = (days_in_month + monthrange(year, month)[0]) // 7 + 1
        self.schedule_table.setRowCount(weeks)

        # Заполняем таблицу
        day = 1
        for row in range(weeks):
            for col in range(7):
                if day > days_in_month:
                    self.schedule_table.setItem(row, col, QTableWidgetItem(""))
                    continue
                wday = weekday(year, month, day)
                if col == wday:
                    item = QTableWidgetItem(str(day))
                    is_workday = schedule.get(day, True)
                    item.setBackground(Qt.red if not is_workday else Qt.green)
                    if date(year, month, day) < date.today():
                        item.setFlags(item.flags() & ~Qt.ItemIsEnabled)  # Нельзя редактировать прошедшие дни
                    self.schedule_table.setItem(row, col, item)
                    day += 1
                else:
                    self.schedule_table.setItem(row, col, QTableWidgetItem(""))

        self.schedule_table.resizeColumnsToContents()

    def toggle_day(self, row, col):
        item = self.schedule_table.item(row, col)
        if not item or not item.text() or item.flags() & Qt.ItemIsEnabled == 0:
            return

        day = int(item.text())
        month = self.month_selector.currentIndex() + 1
        year = datetime.now().year
        schedule = self.temp_schedule.get((year, month), self.load_schedule(year, month))
        schedule[day] = not schedule.get(day, True)
        self.temp_schedule[(year, month)] = schedule
        self.update_schedule_table()

    def get_hours_per_day(self):
        try:
            if self.temp_hours:
                return float(self.temp_hours)
            if os.path.exists(self.hours_file):
                with open(self.hours_file, 'r') as f:
                    return float(f.read().strip())
            return 8
        except:
            return 8

def get_schedule(year, month):
    schedule_file = os.path.join(os.path.expanduser("~"), ".devmetrics_schedule")
    if os.path.exists(schedule_file):
        try:
            with open(schedule_file, 'r') as f:
                schedules = eval(f.read())
            return schedules.get((year, month), {})
        except:
            pass
    days_in_month = monthrange(year, month)[1]
    return {day: True for day in range(1, days_in_month + 1)}

def get_hours_per_day():
    hours_file = os.path.join(os.path.expanduser("~"), ".devmetrics_hours")
    try:
        if os.path.exists(hours_file):
            with open(hours_file, 'r') as f:
                return float(f.read().strip())
        return 8
    except:
        return 8