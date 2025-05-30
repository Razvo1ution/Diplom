import sys
import os
import json
import git
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget, QHBoxLayout,
                             QLabel, QComboBox, QTableWidget, QTableWidgetItem, QPushButton,
                             QFileDialog, QMessageBox, QInputDialog, QLineEdit)
from PyQt5.QtCore import Qt
from OpeningHours import update_opening_hours, format_time
from CodeAnalysis import update_code_analysis
import logging

# Настройка логирования
logging.basicConfig(filename='admin_devmetrics.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

class AdminApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Админ-панель: Анализ продуктивности")
        self.users_file = os.path.join(os.path.expanduser("~"), "admin.json")  # Изменено на admin.json
        self.project_path = ""
        self.current_user = None
        self.init_ui()
        self.check_admin()

    def init_ui(self):
        self.setFixedSize(1000, 800)
        self.center_window()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Путь к проекту:"))
        self.project_path_input = QLineEdit()
        self.project_path_input.setPlaceholderText("Введите путь к проекту...")
        path_layout.addWidget(self.project_path_input)
        browse_btn = QPushButton("Обзор")
        browse_btn.clicked.connect(self.browse_project)
        path_layout.addWidget(browse_btn)
        self.main_layout.addLayout(path_layout)

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("Месяц:"))
        self.month_selector = QComboBox()
        self.month_selector.addItems(["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                                     "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"])
        self.month_selector.setCurrentIndex(datetime.now().month - 1)
        controls_layout.addWidget(self.month_selector)

        controls_layout.addWidget(QLabel("Год:"))
        self.year_selector = QComboBox()
        self.update_years()
        controls_layout.addWidget(self.year_selector)
        controls_layout.addStretch()
        self.main_layout.addLayout(controls_layout)

        self.main_layout.addWidget(QLabel("Аналитика по пользователям:"))
        self.users_table = QTableWidget()
        self.users_table.setColumnCount(6)
        self.users_table.setHorizontalHeaderLabels([
            "Пользователь", "Коммиты", "Часы работы", "Мёртвое время (%)",
            "Ночные коммиты", "Изменённые файлы"
        ])
        self.main_layout.addWidget(self.users_table)

        update_btn = QPushButton("Обновить аналитику")
        update_btn.clicked.connect(self.update_users_analytics)
        self.main_layout.addWidget(update_btn)

        access_layout = QHBoxLayout()
        access_layout.addWidget(QLabel("Управление ролями:"))
        self.user_selector = QComboBox()
        access_layout.addWidget(self.user_selector)
        self.access_toggle = QPushButton("Сделать администратором")
        self.access_toggle.clicked.connect(self.toggle_user_access)
        access_layout.addWidget(self.access_toggle)
        access_layout.addStretch()
        self.main_layout.addLayout(access_layout)

        self.main_layout.addStretch()

    def center_window(self):
        screen = self.screen().geometry()
        size = self.geometry()
        self.move((screen.width() - size.width()) // 2, 0)

    def browse_project(self):
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку проекта")
        if folder:
            self.project_path_input.setText(folder)
            self.project_path = folder
            self.update_years()
            self.update_users_list()
            self.update_users_analytics()

    def update_years(self):
        try:
            repo = git.Repo(self.project_path)
            commits = list(repo.iter_commits(max_count=10000))
            years = set(datetime.fromtimestamp(commit.committed_date).year for commit in commits)
            self.year_selector.clear()
            self.year_selector.addItems([str(year) for year in sorted(years)])
            current_year = str(datetime.now().year)
            if current_year in [str(year) for year in years]:
                self.year_selector.setCurrentText(current_year)
        except Exception as e:
            logging.error(f"Error updating years: {str(e)}")
            self.year_selector.clear()
            self.year_selector.addItems([str(datetime.now().year)])

    def update_users_list(self):
        if not self.project_path or not os.path.exists(os.path.join(self.project_path, '.git')):
            self.user_selector.clear()
            return
        try:
            repo = git.Repo(self.project_path)
            commits = list(repo.iter_commits(max_count=10000))
            authors = set(commit.author.email for commit in commits)
            self.user_selector.clear()
            self.user_selector.addItems(authors)
        except Exception as e:
            logging.error(f"Error updating users list: {str(e)}")
            self.user_selector.clear()

    def update_users_analytics(self):
        if not self.project_path or not os.path.exists(os.path.join(self.project_path, '.git')):
            QMessageBox.warning(self, "Ошибка", "Укажите действующий Git-репозиторий")
            self.users_table.setRowCount(0)
            return

        month = self.month_selector.currentIndex() + 1
        year = int(self.year_selector.currentText()) if self.year_selector.currentText() else datetime.now().year

        try:
            repo = git.Repo(self.project_path)
            commits = list(repo.iter_commits(max_count=10000))
            authors = set(commit.author.email for commit in commits)
            self.users_table.setRowCount(len(authors))

            for row, author in enumerate(authors):
                metrics_text, _, hours, _, _, _, daily_metrics, hourly_activity, work_start, work_end, lunch_start, lunch_end = update_opening_hours(
                    self.project_path, month, year, max_count=10000, author=author
                )
                total_hours = sum(hours) if hours else 0
                total_commits = sum(day_data['commits'] for day_data in daily_metrics.values())
                night_commits = sum(day_data['night_commits'] for day_data in daily_metrics.values())
                dead_time_percent = sum(day_data['dead_time'] for day_data in daily_metrics.values()) / len(daily_metrics) if daily_metrics else 0

                code_metrics = update_code_analysis(self.project_path, author=author)
                total_files_changed = 0
                if isinstance(code_metrics, dict):
                    total_files_changed = code_metrics.get('total_files_changed', 0)
                elif isinstance(code_metrics, str):
                    for line in code_metrics.splitlines():
                        if line.startswith("Общее количество изменённых файлов:"):
                            total_files_changed = int(line.split(":")[1].strip())
                            break

                self.users_table.setItem(row, 0, QTableWidgetItem(author))
                self.users_table.setItem(row, 1, QTableWidgetItem(str(total_commits)))
                self.users_table.setItem(row, 2, QTableWidgetItem(format_time(total_hours)))
                self.users_table.setItem(row, 3, QTableWidgetItem(f"{dead_time_percent:.2f}%"))
                self.users_table.setItem(row, 4, QTableWidgetItem(str(night_commits)))
                self.users_table.setItem(row, 5, QTableWidgetItem(str(total_files_changed)))

            self.users_table.resizeColumnsToContents()
            logging.info("Users analytics updated successfully")

        except Exception as e:
            logging.error(f"Error updating users analytics: {str(e)}")
            self.users_table.setRowCount(0)
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить аналитику: {str(e)}")

    def toggle_user_access(self):
        selected_user = self.user_selector.currentText()
        if not selected_user:
            QMessageBox.warning(self, "Ошибка", "Выберите пользователя")
            return

        users_config = {}
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, 'r') as f:
                    users_config = json.load(f)
            except:
                pass

        is_admin = users_config.get(selected_user, {}).get('role', 'user') == 'admin'
        new_role = 'user' if is_admin else 'admin'
        users_config[selected_user] = {'role': new_role}
        with open(self.users_file, 'w') as f:
            json.dump(users_config, f)

        self.access_toggle.setText("Снять права администратора" if new_role == 'admin' else "Сделать администратором")
        QMessageBox.information(self, "Успех", f"Роль пользователя {selected_user} изменена на {new_role}")
        logging.info(f"User {selected_user} role changed to {new_role}")

    def check_admin(self):
        # Проверяем или создаём admin.json при первом запуске
        if not os.path.exists(self.users_file):
            default_users = {"admin@example.com": {"role": "admin"}}
            try:
                with open(self.users_file, 'w') as f:
                    json.dump(default_users, f)
                logging.info(f"Created default admin.json at {self.users_file}")
            except Exception as e:
                logging.error(f"Failed to create admin.json: {str(e)}")
                QMessageBox.critical(self, "Ошибка", f"Не удалось создать admin.json: {str(e)}")
                sys.exit(1)

        email, ok = QInputDialog.getText(self, "Авторизация", "Введите ваш email:")
        if not ok or not email:
            QMessageBox.critical(self, "Ошибка", "Требуется email для доступа")
            sys.exit(1)

        users_config = {}
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, 'r') as f:
                    users_config = json.load(f)
            except:
                pass

        if users_config.get(email, {}).get('role', 'user') != 'admin':
            QMessageBox.critical(self, "Ошибка", "У вас нет прав администратора")
            sys.exit(1)
        self.current_user = email

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = AdminApp()
    window.show()
    sys.exit(app.exec_())