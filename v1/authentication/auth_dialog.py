import sys
from PyQt5.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QMessageBox, QFormLayout,
                             QRadioButton, QButtonGroup)
from PyQt5.QtCore import Qt
from .auth import Auth # Импортируем класс Auth из соседнего auth.py
from database import init_db # Для инициализации БД при необходимости

class AuthDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Авторизация")
        self.setModal(True) # Делаем окно модальным

        # Данные успешно аутентифицированного пользователя
        self.user_id = None
        self.user_role = None
        self.user_full_name = None
        self.user_email = None

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.login_input = QLineEdit(self)
        self.login_input.setPlaceholderText("Логин или Email")
        form_layout.addRow(QLabel("Логин/Email:"), self.login_input)

        self.password_input = QLineEdit(self)
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Пароль")
        form_layout.addRow(QLabel("Пароль:"), self.password_input)

        layout.addLayout(form_layout)

        buttons_layout = QHBoxLayout()
        self.login_button = QPushButton("Войти")
        self.login_button.clicked.connect(self.handle_login)
        buttons_layout.addWidget(self.login_button)

        self.register_button = QPushButton("Регистрация")
        self.register_button.clicked.connect(self.handle_register_dialog) # Открывает отдельное окно регистрации
        buttons_layout.addWidget(self.register_button)
        
        layout.addLayout(buttons_layout)
        self.setMinimumWidth(300)

    def handle_login(self):
        login = self.login_input.text().strip()
        password = self.password_input.text().strip()

        if not login or not password:
            QMessageBox.warning(self, "Ошибка входа", "Логин и пароль не могут быть пустыми.")
            return

        auth_result = Auth.login(login, password)

        if auth_result.get('success'):
            self.user_id = auth_result.get('user_id')
            self.user_role = auth_result.get('role')
            self.user_full_name = auth_result.get('full_name')
            self.user_email = auth_result.get('email')
            QMessageBox.information(self, "Успех", f"Добро пожаловать, {self.user_full_name or login}!")
            self.accept() # Закрываем диалог с результатом QDialog.Accepted
        else:
            QMessageBox.critical(self, "Ошибка входа", auth_result.get('message', "Неизвестная ошибка."))
            self.password_input.clear()

    def handle_register_dialog(self):
        # Приостанавливаем текущее диалоговое окно
        self.hide() 
        
        register_dialog = RegisterDialog(self)
        result = register_dialog.exec_() # Показываем диалог регистрации модально
        
        # Показываем снова окно логина после закрытия окна регистрации
        self.show() 
        
        if result == QDialog.Accepted:
            # Можно добавить автоматический вход или сообщение об успешной регистрации
            QMessageBox.information(self, "Регистрация", 
                                    "Регистрация прошла успешно! Теперь вы можете войти.")
            self.login_input.setText(register_dialog.login_input.text()) # Предзаполняем логин


class RegisterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Регистрация нового пользователя")
        self.setModal(True)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.login_input = QLineEdit(self)
        self.login_input.setPlaceholderText("Придумайте логин")
        form_layout.addRow(QLabel("Логин:"), self.login_input)

        self.email_input = QLineEdit(self)
        self.email_input.setPlaceholderText("Ваш Email")
        form_layout.addRow(QLabel("Email:"), self.email_input)

        self.full_name_input = QLineEdit(self)
        self.full_name_input.setPlaceholderText("Ваше полное имя")
        form_layout.addRow(QLabel("Полное имя:"), self.full_name_input)

        self.password_input = QLineEdit(self)
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Придумайте пароль")
        form_layout.addRow(QLabel("Пароль:"), self.password_input)

        self.password_confirm_input = QLineEdit(self)
        self.password_confirm_input.setEchoMode(QLineEdit.Password)
        self.password_confirm_input.setPlaceholderText("Повторите пароль")
        form_layout.addRow(QLabel("Подтвердите пароль:"), self.password_confirm_input)

        # Добавление выбора роли
        role_group_box_layout = QHBoxLayout()
        self.role_group = QButtonGroup(self) # Группа для радиокнопок

        self.radio_solo_developer = QRadioButton("Индивидуальный разработчик")
        self.radio_solo_developer.setChecked(True) # По умолчанию выбран
        self.role_group.addButton(self.radio_solo_developer)
        role_group_box_layout.addWidget(self.radio_solo_developer)

        self.radio_admin = QRadioButton("Администратор")
        self.role_group.addButton(self.radio_admin)
        role_group_box_layout.addWidget(self.radio_admin)
        
        form_layout.addRow(QLabel("Тип аккаунта:"), role_group_box_layout)
        
        layout.addLayout(form_layout)

        self.register_button = QPushButton("Зарегистрироваться")
        self.register_button.clicked.connect(self.handle_register)
        layout.addWidget(self.register_button)
        
        self.setMinimumWidth(350)

    def handle_register(self):
        login = self.login_input.text().strip()
        email = self.email_input.text().strip()
        full_name = self.full_name_input.text().strip()
        password = self.password_input.text().strip()
        password_confirm = self.password_confirm_input.text().strip()

        if not all([login, email, full_name, password, password_confirm]):
            QMessageBox.warning(self, "Ошибка регистрации", "Все поля должны быть заполнены.")
            return

        if password != password_confirm:
            QMessageBox.warning(self, "Ошибка регистрации", "Пароли не совпадают.")
            self.password_input.clear()
            self.password_confirm_input.clear()
            return
        
        selected_role = ''
        if self.radio_solo_developer.isChecked():
            selected_role = 'solo_developer'
        elif self.radio_admin.isChecked():
            selected_role = 'admin'

        if not selected_role: # На всякий случай, хотя одна всегда должна быть выбрана
            QMessageBox.warning(self, "Ошибка регистрации", "Пожалуйста, выберите тип аккаунта.")
            return
            
        try:
            user_id = Auth.register_user(
                login=login, 
                password=password, 
                email=email, 
                full_name=full_name, 
                role=selected_role # Используем выбранную роль
            )
            if user_id:
                # QMessageBox.information(self, "Успех", "Регистрация прошла успешно! Теперь вы можете войти.")
                self.accept() # Закрываем диалог регистрации
            else:
                # Ошибка уже должна была быть обработана в Auth.register_user и вызвано исключение
                 QMessageBox.critical(self, "Ошибка регистрации", "Не удалось зарегистрировать пользователя.")
        except ValueError as ve:
            QMessageBox.critical(self, "Ошибка регистрации", str(ve))
        except Exception as e:
            QMessageBox.critical(self, "Ошибка регистрации", f"Произошла непредвиденная ошибка: {str(e)}")

# Пример запуска для тестирования диалога (не будет использоваться в main.py)
if __name__ == '__main__':        
    app = QApplication(sys.argv)
    dialog = AuthDialog()
    if dialog.exec_() == QDialog.Accepted:
        print(f"Вход успешен! User ID: {dialog.user_id}, Role: {dialog.user_role}")
        # Здесь мог бы быть запуск основного окна приложения
    else:
        print("Вход отменен или не удался.")
    sys.exit(app.exec_()) 
