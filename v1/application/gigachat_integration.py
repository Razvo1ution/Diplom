from gigachat import GigaChat
from gigachat.models import Messages, MessagesRole, Chat
from typing import List, Dict, Any
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTextEdit, QPushButton,
                           QLabel, QMessageBox, QProgressBar, QHBoxLayout,
                           QComboBox, QLineEdit)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from datetime import datetime, timedelta
import requests
import urllib3
import uuid
import git
import os
from PyQt5.QtCore import QSettings

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PROMPT_TEMPLATE = """Ты — профессиональный разработчик уровня Senior и технический рецензент.  
Твоя задача — строго и точно определить, насколько пользователь выполнил поставленную им задачу,  
основываясь **исключительно на формулировке задачи и содержимом коммитов**.

---

🔹 Формулировка задачи:
"{user_task}"

🔹 Содержимое коммитов:
{commit_list}

---

🔍 Правила анализа:
1. **Оценивай строго по формулировке задачи**. Не додумывай, что «наверное имелось в виду».  
2. Если задача требует конкретного вывода, поведения, файла или ресурса — проверяй это **буквально**.
3. **Не учитывай намерения**. Оцени только то, что реально реализовано в коде/коммитах.
4. Если задача выполнена частично — оцени **по доле сути, а не по длине кода**.
5. Не снижай оценку за стиль, структуру, тесты или документацию, если они **не требуются в задаче**.
6. Если коммиты не делают ничего осмысленного (например, `print()` без аргументов) — это 0%.

---

🔁 Формат ответа:
Оценка выполнения: [процент от 0 до 100]%

Краткий комментарий:
- Что реализовано: [перечисли ключевые элементы задачи, которые выполнены]
- Чего не хватает: [перечисли, что из формулировки отсутствует в коммитах]
- Обоснование: [объясни оценку логически, не предполагая скрытого смысла]
"""

def create_message(role: str, content: str) -> Dict[str, str]:
    return {"role": role, "content": content}

class GitAnalyzer:
    def __init__(self, repo_path="."):
        try:
            self.repo = git.Repo(repo_path)
        except git.exc.InvalidGitRepositoryError:
            try:
                self.repo = git.Repo.init(repo_path)
                if not self.repo.heads:
                    readme_path = os.path.join(repo_path, "README.md")
                    with open(readme_path, "w", encoding='utf-8') as f:
                        f.write("# Анализ производительности разработчика\n\nПроект для анализа выполнения задач разработки.")
                    self.repo.index.add(["README.md"])
                    self.repo.index.commit("Initial commit")
            except Exception as e:
                raise Exception(f"Не удалось инициализировать git репозиторий: {str(e)}")

    def get_commits_for_period(self, days=1):
        try:
            since_date = datetime.now() - timedelta(days=days)
            
            if not self.repo.heads:
                return []
                
            commits = list(self.repo.iter_commits(since=since_date))
            
            commit_info = []
            for commit in commits:
                try:
                    files_changed = []
                    if commit.parents:
                        for diff in commit.diff(commit.parents[0]):
                            if diff.a_path:
                                files_changed.append(diff.a_path)
                            if diff.b_path and diff.b_path != diff.a_path:
                                files_changed.append(diff.b_path)
                    else:
                        files_changed = [item.path for item in commit.tree.traverse()]

                    commit_info.append({
                        'hash': commit.hexsha[:8],
                        'author': commit.author.name,
                        'date': commit.committed_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                        'message': commit.message.strip(),
                        'files_changed': files_changed
                    })
                except Exception:
                    continue
            
            return commit_info
        except Exception as e:
            raise Exception(f"Ошибка при получении истории коммитов: {str(e)}")

    def get_file_content_at_commit(self, file_path, commit_hash):
        try:
            return self.repo.git.show(f'{commit_hash}:{file_path}')
        except git.exc.GitCommandError:
            return None
        except Exception as e:
            raise Exception(f"Ошибка при получении содержимого файла: {str(e)}")

class GigaChatWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, auth_key, task, period):
        super().__init__()
        self.auth_key = auth_key
        self.task = task
        self.period = period
        self.model = "GigaChat"  # Default model
        try:
            # Получаем путь к проекту из настроек
            settings = QSettings("MyCompany", "DevMetricsApp")
            project_path = settings.value("project_path", "")
            if not project_path:
                raise Exception("Путь к проекту не указан в настройках")
            
            # Инициализируем GitAnalyzer с путем из настроек
            self.git_analyzer = GitAnalyzer(project_path)
        except Exception as e:
            raise Exception(f"Ошибка при инициализации Git: {str(e)}")

    def set_model(self, model_name):
        """Устанавливает модель для использования в запросе."""
        self.model = model_name

    def get_access_token(self) -> str:
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': str(uuid.uuid4()),
            'Authorization': f'Basic {self.auth_key}'
        }
        
        payload = {
            'scope': 'GIGACHAT_API_PERS'
        }
        
        try:
            response = requests.post(url, headers=headers, data=payload, verify=False)
            response.raise_for_status()
            return response.json().get('access_token')
        except Exception as e:
            raise Exception(f"Ошибка получения access token: {str(e)}")

    def format_commits_info(self, commits):
        """Форматирует информацию только о последнем коммите, включая содержимое файлов."""
        if not commits:
            return "Нет изменений за выбранный период."
        
        last_commit = commits[0]  # Первый в списке — самый свежий
        formatted_info = "Последний коммит:\n"
        formatted_info += f"Коммит: {last_commit['hash']}\n"
        formatted_info += f"Автор: {last_commit['author']}\n"
        formatted_info += f"Дата: {last_commit['date']}\n"
        formatted_info += f"Сообщение: {last_commit['message']}\n"
        formatted_info += "Измененные файлы:\n"
        for file in last_commit['files_changed']:
            formatted_info += f"- {file}\n"
            try:
                content = self.git_analyzer.get_file_content_at_commit(file, last_commit['hash'])
                if content:
                    lines = content.splitlines()
                    preview = '\n'.join(lines[:30])
                    if len(lines) > 30:
                        preview += f"\n... (показаны первые 30 строк из {len(lines)})"
                    formatted_info += f"  Содержимое файла на момент коммита:\n{preview}\n"
            except Exception as e:
                formatted_info += f"  [Ошибка при получении содержимого файла: {str(e)}]\n"
        return formatted_info

    def run(self):
        try:
            days = self.get_period_days()
            commits = self.git_analyzer.get_commits_for_period(days)
            commits_info = self.format_commits_info(commits)

            prompt = PROMPT_TEMPLATE.format(
                user_task=self.task,
                commit_list=commits_info
            )

            access_token = self.get_access_token()
            url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
            
            payload = {
                "model": self.model,
                "messages": [
                    create_message("system", "Ты — опытный программист уровня Senior и технический эксперт. Анализируй задачи строго по их формулировке."),
                    create_message("user", prompt)
                ],
                "temperature": 0.7,
                "max_tokens": 2000
            }
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {access_token}'
            }
            
            response = requests.post(url, json=payload, headers=headers, verify=False)
            response.raise_for_status()
            
            response_data = response.json()
            if 'choices' in response_data and response_data['choices']:
                content = response_data['choices'][0]['message']['content']
            else:
                content = str(response_data)
                
            self.finished.emit(content)
        except Exception as e:
            self.error.emit(str(e))

    def get_period_days(self):
        period_mapping = {
            "Последний день": 1,
            "Последняя неделя": 7,
            "Последний месяц": 30,
            "Весь период": 365
        }
        return period_mapping.get(self.period, 1)

class GigaChatPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.auth_key = None
        self.settings = QSettings("MyCompany", "DevMetricsApp")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        settings_group = QVBoxLayout()
        
        auth_layout = QHBoxLayout()
        auth_layout.addWidget(QLabel("API Ключ GigaChat:"))
        self.auth_key_input = QLineEdit()
        self.auth_key_input.setEchoMode(QLineEdit.Password)
        self.auth_key_input.setPlaceholderText("Введите API ключ GigaChat...")
        auth_layout.addWidget(self.auth_key_input)
        settings_group.addLayout(auth_layout)

        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Модель:"))
        self.model_selector = QComboBox()
        self.model_selector.addItems(["GigaChat", "GigaChat-Pro", "GigaChat-Max"])
        model_layout.addWidget(self.model_selector)
        settings_group.addLayout(model_layout)

        init_button = QPushButton("Инициализировать GigaChat")
        init_button.clicked.connect(self.initialize_gigachat)
        settings_group.addWidget(init_button)

        layout.addLayout(settings_group)

        self.task_label = QLabel("Описание задачи:")
        layout.addWidget(self.task_label)
        
        self.task_text = QTextEdit()
        self.task_text.setPlaceholderText("Опишите задачу, которую нужно проанализировать...")
        self.task_text.setMaximumHeight(100)
        layout.addWidget(self.task_text)

        period_layout = QHBoxLayout()
        period_layout.addWidget(QLabel("Период анализа:"))
        
        self.period_selector = QComboBox()
        self.period_selector.addItems(["Последний день", "Последняя неделя", "Последний месяц", "Весь период"])
        period_layout.addWidget(self.period_selector)
        period_layout.addStretch()
        layout.addLayout(period_layout)

        self.analyze_button = QPushButton("Проанализировать выполнение")
        self.analyze_button.clicked.connect(self.analyze_task)
        self.analyze_button.setEnabled(False)
        layout.addWidget(self.analyze_button)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.response_label = QLabel("Результат анализа:")
        layout.addWidget(self.response_label)
        
        self.response_text = QTextEdit()
        self.response_text.setReadOnly(True)
        self.response_text.setPlaceholderText("Здесь появится анализ выполнения задачи...")
        layout.addWidget(self.response_text)

        # --- Новый код: автозагрузка ключа ---
        saved_key = self.settings.value("gigachat_api_key", "")
        if saved_key:
            self.auth_key_input.setText(saved_key)
            self.auth_key = saved_key
            self.analyze_button.setEnabled(True)
        else:
            self.analyze_button.setEnabled(False)

    def initialize_gigachat(self):
        auth_key = self.auth_key_input.text().strip()
        if not auth_key:
            QMessageBox.warning(self, "Предупреждение", "Пожалуйста, введите API ключ GigaChat.")
            return

        try:
            self.auth_key = auth_key
            worker = GigaChatWorker(self.auth_key, "", "")
            test_token = worker.get_access_token()
            
            if test_token:
                QMessageBox.information(self, "Успех", "GigaChat успешно инициализирован!")
                self.analyze_button.setEnabled(True)
                # --- Новый код: сохраняем ключ ---
                self.settings.setValue("gigachat_api_key", self.auth_key)
                self.settings.sync()
            else:
                raise Exception("Не удалось получить токен доступа")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось инициализировать GigaChat: {str(e)}")
            self.auth_key = None
            self.analyze_button.setEnabled(False)

    def analyze_task(self):
        if not self.auth_key:
            QMessageBox.warning(self, "Предупреждение", 
                              "GigaChat не инициализирован. Пожалуйста, проверьте API ключ.")
            return

        task = self.task_text.toPlainText().strip()
        if not task:
            QMessageBox.warning(self, "Предупреждение", "Пожалуйста, введите описание задачи.")
            return

        period = self.period_selector.currentText()
        model = self.model_selector.currentText()
        
        self.progress.setVisible(True)
        self.analyze_button.setEnabled(False)
        
        self.worker = GigaChatWorker(self.auth_key, task, period)
        self.worker.set_model(model)
        self.worker.finished.connect(self.handle_response)
        self.worker.error.connect(self.handle_error)
        self.worker.finished.connect(lambda: self.cleanup_ui())
        self.worker.error.connect(lambda: self.cleanup_ui())
        self.worker.start()

    def handle_response(self, response):
        self.response_text.setText(response)

    def handle_error(self, error_message):
        QMessageBox.critical(self, "Ошибка", f"Произошла ошибка при обработке запроса: {error_message}")

    def cleanup_ui(self):
        self.progress.setVisible(False)
        self.analyze_button.setEnabled(True)