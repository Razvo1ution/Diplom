import os
import logging
from datetime import datetime, timedelta
from pynput import keyboard, mouse
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
import json

# Настройка логирования
logging.basicConfig(filename='activity_tracker.log', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')

class FileActivityHandler(FileSystemEventHandler):
    def __init__(self, callback):
        self.callback = callback

    def on_modified(self, event):
        if not event.is_directory:
            try:
                timestamp = datetime.now().timestamp()
                self.callback(timestamp)
                logging.debug(f"Файл изменён: {event.src_path}")
            except Exception as e:
                logging.error(f"Ошибка в on_modified: {str(e)}")

    def on_created(self, event):
        if not event.is_directory:
            try:
                timestamp = datetime.now().timestamp()
                self.callback(timestamp)
                logging.debug(f"Файл создан: {event.src_path}")
            except Exception as e:
                logging.error(f"Ошибка в on_created: {str(e)}")

class ActivityTracker:
    def __init__(self, project_path, lunch_file, update_callback=None):
        self.project_path = project_path
        self.lunch_file = lunch_file
        self.update_callback = update_callback  # Callback для уведомления
        self.lunch_data = self.load_lunch_data()
        self.activity_timestamps = []
        self.lock = threading.Lock()  # Для синхронизации доступа
        self.listener_keyboard = None
        self.listener_mouse = None
        self.observer = None
        self.running = True
        self.new_activity = False  # Флаг новых событий
        self.last_mouse_move = 0
        try:
            self.start_listeners()
            self.start_file_watcher()
            threading.Thread(target=self.clean_old_activities, daemon=True).start()
            logging.info("ActivityTracker инициализирован")
        except Exception as e:
            logging.error(f"Ошибка при инициализации ActivityTracker: {str(e)}")

    def start_listeners(self):
        """Запускает слушатели клавиатуры и мыши."""
        try:
            self.listener_keyboard = keyboard.Listener(on_press=self.on_key_press)
            self.listener_mouse = mouse.Listener(
                on_click=self.on_mouse_click,
                on_move=self.on_mouse_move
            )
            threading.Thread(target=self.listener_keyboard.start, daemon=True).start()
            threading.Thread(target=self.listener_mouse.start, daemon=True).start()
            logging.info("Слушатели клавиатуры и мыши запущены")
        except Exception as e:
            logging.error(f"Ошибка при запуске слушателей: {str(e)}")

    def stop_listeners(self):
        """Останавливает слушатели клавиатуры и мыши."""
        try:
            self.running = False
            if self.listener_keyboard:
                self.listener_keyboard.stop()
                self.listener_keyboard = None
            if self.listener_mouse:
                self.listener_mouse.stop()
                self.listener_mouse = None
            logging.info("Слушатели клавиатуры и мыши остановлены")
        except Exception as e:
            logging.error(f"Ошибка при остановке слушателей: {str(e)}")

    def on_key_press(self, key):
        """Регистрирует нажатие клавиши."""
        if not self.running:
            return
        try:
            with self.lock:
                timestamp = datetime.now().timestamp()
                self.activity_timestamps.append(timestamp)
                self.new_activity = True
                if self.update_callback:
                    self.update_callback()
            logging.debug(f"Клавиша нажата: {key}")
        except Exception as e:
            logging.error(f"Ошибка в on_key_press: {str(e)}")

    def on_mouse_click(self, x, y, button, pressed):
        """Регистрирует клик мыши."""
        if not self.running or not pressed:
            return
        try:
            with self.lock:
                timestamp = datetime.now().timestamp()
                self.activity_timestamps.append(timestamp)
                self.new_activity = True
                if self.update_callback:
                    self.update_callback()
            logging.debug(f"Клик мыши: {x}, {y}, {button}")
        except Exception as e:
            logging.error(f"Ошибка в on_mouse_click: {str(e)}")

    def on_mouse_move(self, x, y):
        """Регистрирует движение мыши с ограничением частоты."""
        if not self.running:
            return
        try:
            now = datetime.now().timestamp()
            if now - self.last_mouse_move > 0.5:  # Ограничение: 1 событие в 0.5 сек
                with self.lock:
                    self.activity_timestamps.append(now)
                    self.new_activity = True
                    if self.update_callback:
                        self.update_callback()
                self.last_mouse_move = now
                logging.debug(f"Движение мыши: {x}, {y}")
        except Exception as e:
            logging.error(f"Ошибка в on_mouse_move: {str(e)}")

    def start_file_watcher(self):
        """Запускает мониторинг файлов в project_path."""
        try:
            if os.path.exists(self.project_path):
                self.observer = Observer()
                event_handler = FileActivityHandler(self.on_file_activity)
                self.observer.schedule(event_handler, self.project_path, recursive=True)
                self.observer.start()
                logging.info(f"Мониторинг файлов начат для {self.project_path}")
            else:
                logging.warning(f"Путь проекта не существует: {self.project_path}")
        except Exception as e:
            logging.error(f"Ошибка при запуске file_watcher: {str(e)}")

    def stop_file_watcher(self):
        """Останавливает мониторинг файлов."""
        try:
            if self.observer:
                self.observer.stop()
                self.observer.join()
                self.observer = None
            logging.info("Мониторинг файлов остановлен")
        except Exception as e:
            logging.error(f"Ошибка при остановке file_watcher: {str(e)}")

    def on_file_activity(self, timestamp):
        """Регистрирует активность с файлами."""
        if not self.running:
            return
        try:
            with self.lock:
                self.activity_timestamps.append(timestamp)
                self.new_activity = True
                if self.update_callback:
                    self.update_callback()
            logging.debug(f"Файловая активность: {timestamp}")
        except Exception as e:
            logging.error(f"Ошибка в on_file_activity: {str(e)}")

    def clean_old_activities(self):
        """Очищает активности старше текущего дня каждые 60 секунд."""
        while self.running:
            try:
                current_day_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
                with self.lock:
                    self.activity_timestamps = [t for t in self.activity_timestamps if t >= current_day_start]
                threading.Event().wait(60)
            except Exception as e:
                logging.error(f"Ошибка в clean_old_activities: {str(e)}")

    def load_lunch_data(self):
        """Загружает данные об обеде."""
        try:
            if os.path.exists(self.lunch_file):
                with open(self.lunch_file, 'r') as f:
                    return json.load(f)
            logging.info("Файл обеда загружен или создан")
        except Exception as e:
            logging.error(f"Ошибка при загрузке lunch_data: {str(e)}")
        return {}

    def save_lunch_data(self):
        """Сохраняет данные об обеде."""
        try:
            with open(self.lunch_file, 'w') as f:
                json.dump(self.lunch_data, f)
            logging.info("Данные об обеде сохранены")
        except Exception as e:
            logging.error(f"Ошибка при сохранении lunch_data: {str(e)}")

    def can_take_lunch(self, today_str):
        """Проверяет, можно ли взять обед сегодня."""
        try:
            return today_str not in self.lunch_data
        except Exception as e:
            logging.error(f"Ошибка в can_take_lunch: {str(e)}")
            return False

    def record_lunch(self, today_str, start_time):
        """Регистрирует время обеда."""
        try:
            self.lunch_data[today_str] = start_time
            self.save_lunch_data()
            logging.info(f"Обед зарегистрирован: {today_str}")
        except Exception as e:
            logging.error(f"Ошибка в record_lunch: {str(e)}")

    def get_lunch_period(self, year, month, day):
        """Возвращает период обеда для указанного дня."""
        try:
            today_str = f"{year}-{month:02d}-{day:02d}"
            if today_str in self.lunch_data:
                start_time = datetime.fromtimestamp(self.lunch_data[today_str])
                end_time = start_time + timedelta(hours=1)
                return start_time, end_time
            return None, None
        except Exception as e:
            logging.error(f"Ошибка в get_lunch_period: {str(e)}")
            return None, None

    def calculate_activity(self, year, month, day, schedule):
        """Рассчитывает активное время и простой для одного рабочего дня."""
        active_hours = 0
        idle_hours = 0

        try:
            # Проверяем, рабочий ли день и не будущий ли он
            current_date = datetime.now().date()
            target_date = datetime(year, month, day).date()
            if day not in schedule or not schedule[day] or target_date > current_date:
                return active_hours, idle_hours

            lunch_start, lunch_end = self.get_lunch_period(year, month, day)
            day_start = datetime(year, month, day, 0, 0)
            day_end = day_start + timedelta(days=1)

            # Собираем активности за день
            with self.lock:
                timestamps = [
                    t for t in self.activity_timestamps
                    if day_start.timestamp() <= t < day_end.timestamp()
                ]

            # Разбиваем день на часы
            for hour in range(24):
                hour_start = day_start + timedelta(hours=hour)
                hour_end = hour_start + timedelta(hours=1)

                # Проверяем пересечение с обедом
                is_lunch_hour = False
                if lunch_start and lunch_end:
                    if lunch_start < hour_end and lunch_end > hour_start:
                        is_lunch_hour = True
                if is_lunch_hour:
                    continue

                # Считаем активности в этом часе
                hour_timestamps = [
                    t for t in timestamps
                    if hour_start.timestamp() <= t < hour_end.timestamp()
                ]

                # Активное время: 0.01 часа за каждое событие
                active_time = len(hour_timestamps) * 0.01
                active_time = min(1.0, active_time)

                # Простой: если бездействие > 15 минут
                idle_time = max(0, 1.0 - active_time)
                if idle_time > 15 / 60:
                    idle_hours += idle_time - (15 / 60)
                else:
                    active_time = 1.0

                active_hours += active_time

            logging.debug(f"Рассчитано для {year}-{month:02d}-{day:02d}: активное={active_hours:.2f}, простой={idle_hours:.2f}")
        except Exception as e:
            logging.error(f"Ошибка в calculate_activity: {str(e)}")

        return active_hours, idle_hours