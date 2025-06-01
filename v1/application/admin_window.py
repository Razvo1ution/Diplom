from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QDesktopWidget, QFormLayout, QLineEdit, QPushButton, 
                               QMessageBox, QGroupBox, QListWidget, QListWidgetItem)
from PyQt5.QtCore import Qt
from authentication.auth import Auth # Изменяем относительный импорт на прямой

class AdminAppWindow(QMainWindow):
    def __init__(self, user_id, user_role, user_email, user_full_name):
        super().__init__()
        self.setWindowTitle(f"Панель администратора - {user_full_name}")
        self.current_user_id = user_id
        self.current_user_role = user_role
        self.current_user_email = user_email
        self.current_user_full_name = user_full_name

        self.init_ui()

    def init_ui(self):
        self.resize(800, 700) # Немного увеличим высоту для списка
        self.center_window()
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        welcome_label = QLabel(f"Добро пожаловать, администратор {self.current_user_full_name}! (ID: {self.current_user_id})")
        welcome_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(welcome_label)

        # Секция для создания разработчиков
        create_dev_group = QGroupBox("Создать нового разработчика команды")
        create_dev_layout = QFormLayout()

        self.dev_login_input = QLineEdit()
        self.dev_login_input.setPlaceholderText("Логин разработчика")
        create_dev_layout.addRow(QLabel("Логин:"), self.dev_login_input)

        self.dev_email_input = QLineEdit()
        self.dev_email_input.setPlaceholderText("Email разработчика")
        create_dev_layout.addRow(QLabel("Email:"), self.dev_email_input)

        self.dev_fullname_input = QLineEdit()
        self.dev_fullname_input.setPlaceholderText("Полное имя разработчика")
        create_dev_layout.addRow(QLabel("Полное имя:"), self.dev_fullname_input)

        self.dev_password_input = QLineEdit()
        self.dev_password_input.setEchoMode(QLineEdit.Password)
        self.dev_password_input.setPlaceholderText("Пароль разработчика")
        create_dev_layout.addRow(QLabel("Пароль:"), self.dev_password_input)

        create_button = QPushButton("Создать разработчика")
        create_button.clicked.connect(self.handle_create_developer)
        create_dev_layout.addRow(create_button)

        create_dev_group.setLayout(create_dev_layout)
        main_layout.addWidget(create_dev_group)

        # Секция для отображения списка разработчиков
        team_list_group = QGroupBox("Разработчики в вашей команде")
        team_list_layout = QVBoxLayout()
        self.team_list_widget = QListWidget()
        team_list_layout.addWidget(self.team_list_widget)

        # Кнопка для удаления выбранного разработчика
        self.delete_dev_button = QPushButton("Удалить выбранного разработчика")
        self.delete_dev_button.clicked.connect(self.handle_delete_developer)
        team_list_layout.addWidget(self.delete_dev_button)

        team_list_group.setLayout(team_list_layout)
        main_layout.addWidget(team_list_group)
        
        main_layout.addStretch() 
        self.load_team_developers() # Загружаем список при инициализации

    def handle_create_developer(self):
        login = self.dev_login_input.text().strip()
        email = self.dev_email_input.text().strip()
        full_name = self.dev_fullname_input.text().strip()
        password = self.dev_password_input.text().strip()

        if not all([login, email, full_name, password]):
            QMessageBox.warning(self, "Ошибка ввода", "Все поля должны быть заполнены.")
            return

        try:
            new_user_id = Auth.create_team_developer(
                admin_id=self.current_user_id,
                login=login,
                password=password,
                email=email,
                full_name=full_name
            )
            if new_user_id:
                QMessageBox.information(self, "Успех", f"Разработчик '{full_name}' (ID: {new_user_id}) успешно создан.")
                self.dev_login_input.clear()
                self.dev_email_input.clear()
                self.dev_fullname_input.clear()
                self.dev_password_input.clear()
                self.load_team_developers() # Обновляем список разработчиков
            else:
                # Эта ветка не должна сработать, если create_team_developer либо возвращает ID, либо кидает исключение
                QMessageBox.critical(self, "Ошибка", "Не удалось создать разработчика. Метод не вернул ID.")
        except ValueError as ve:
            QMessageBox.critical(self, "Ошибка создания", str(ve))
        except Exception as e:
            QMessageBox.critical(self, "Непредвиденная ошибка", f"Произошла ошибка при создании разработчика: {str(e)}")

    def load_team_developers(self):
        self.team_list_widget.clear()
        try:
            developers = Auth.get_team_developers(self.current_user_id)
            if developers:
                for dev in developers:
                    # Отображаем полное имя и логин для информации
                    item_text = f"{dev['full_name']} (Логин: {dev['login']}, Email: {dev['email']}) - ID: {dev['user_id']}"
                    list_item = QListWidgetItem(item_text)
                    # Можно сохранить ID пользователя в данных элемента для будущего использования
                    list_item.setData(Qt.UserRole, dev['user_id'])
                    self.team_list_widget.addItem(list_item)
            else:
                self.team_list_widget.addItem("В вашей команде пока нет разработчиков.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка загрузки команды", f"Не удалось загрузить список разработчиков: {str(e)}")
            self.team_list_widget.addItem("Ошибка при загрузке списка.")

    def handle_delete_developer(self):
        selected_items = self.team_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Ошибка", "Пожалуйста, выберите разработчика из списка для удаления.")
            return

        # Предполагаем, что всегда выбран только один элемент (QListWidget по умолчанию так и работает)
        selected_item = selected_items[0]
        developer_id_to_delete = selected_item.data(Qt.UserRole) # Получаем ID из данных элемента
        developer_display_text = selected_item.text() # Для сообщения пользователю

        if developer_id_to_delete is None: # На всякий случай, если ID не был сохранен
            QMessageBox.critical(self, "Ошибка", "Не удалось получить ID выбранного разработчика.")
            return

        reply = QMessageBox.question(self, "Подтверждение удаления", 
                                     f"Вы уверены, что хотите удалить разработчика: {developer_display_text}?\nЭто действие необратимо!",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                success = Auth.delete_user(user_id_to_delete=developer_id_to_delete, 
                                            performing_admin_id=self.current_user_id)
                if success:
                    QMessageBox.information(self, "Успех", f"Разработчик {developer_display_text} успешно удален.")
                    self.load_team_developers() # Обновляем список
                else:
                    # Эта ветка маловероятна, если delete_user либо возвращает True, либо кидает исключение
                    QMessageBox.warning(self, "Не удалось удалить", "Удаление не было выполнено (пользователь мог быть не найден). Проверьте логи.")
            except ValueError as ve: # Перехватываем ошибки (включая FK violation из database.py или проверки из Auth.delete_user)
                QMessageBox.critical(self, "Ошибка удаления", str(ve))
            except Exception as e:
                QMessageBox.critical(self, "Непредвиденная ошибка", f"Произошла ошибка при удалении: {str(e)}")

    def center_window(self):
        screen = self.screen().geometry()
        size = self.geometry()
        self.move((screen.width() - size.width()) // 2,
                  (screen.height() - size.height()) // 2) 