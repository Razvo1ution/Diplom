import bcrypt
import logging
import os # Добавим os для работы с путями
from database import get_db_connection, delete_user_by_id
from datetime import datetime

# Определим путь к директории v1 (где находится main.py и куда должен писаться лог)
# Предполагается, что auth.py находится в v1/authentication/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE_PATH = os.path.join(BASE_DIR, 'auth.log')

# Настройка логирования с абсолютным путем
logging.basicConfig(filename=LOG_FILE_PATH, level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')

class Auth:
    @staticmethod
    def hash_password(password):
        """Хеширует пароль"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt)

    @staticmethod
    def check_password(password, hashed):
        """Проверяет пароль"""
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

    @staticmethod
    def register_user(login, password, email, full_name, role, created_by=None):
        """Регистрирует нового пользователя"""
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            # Проверяем, не существует ли уже пользователь с таким логином или email
            cur.execute("SELECT login, email FROM users WHERE login = %s OR email = %s", (login, email))
            existing = cur.fetchone()
            if existing:
                if existing[0] == login:
                    raise ValueError("Пользователь с таким логином уже существует")
                else:
                    raise ValueError("Пользователь с таким email уже существует")

            # Хешируем пароль
            hashed_password = Auth.hash_password(password)

            # Добавляем пользователя
            cur.execute("""
                INSERT INTO users (login, password_hash, email, full_name, user_role, created_by)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING user_id
            """, (login, hashed_password.decode('utf-8'), email, full_name, role, created_by))
            
            user_id = cur.fetchone()[0]
            conn.commit()
            logging.info(f"User registered successfully: {login}")
            return user_id
        except Exception as e:
            conn.rollback()
            logging.error(f"Registration error: {str(e)}")
            raise
        finally:
            cur.close()
            conn.close()

    @staticmethod
    def login(login, password):
        """Авторизует пользователя"""
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            # Получаем данные пользователя
            cur.execute("""
                SELECT user_id, password_hash, user_role, is_active, full_name, email 
                FROM users WHERE login = %s
            """, (login,))
            
            user = cur.fetchone()
            if not user:
                logging.warning(f"Login attempt failed: user not found - {login}")
                return {'success': False, 'message': 'Неверный логин или пароль'}

            if not user[3]:  # проверяем is_active
                logging.warning(f"Login attempt failed: account inactive - {login}")
                return {'success': False, 'message': 'Аккаунт неактивен'}

            if Auth.check_password(password, user[1]):
                # Обновляем время последнего входа
                cur.execute("""
                    UPDATE users SET last_login = %s WHERE user_id = %s
                """, (datetime.now(), user[0]))
                conn.commit()

                logging.info(f"User logged in successfully: {login}")
                return {
                    'success': True,
                    'user_id': user[0],
                    'role': user[2],
                    'full_name': user[4],
                    'email': user[5]
                }
            else:
                logging.warning(f"Login attempt failed: invalid password - {login}")
                return {'success': False, 'message': 'Неверный логин или пароль'}
        except Exception as e:
            logging.error(f"Login error: {str(e)}")
            print(f"LOGIN EXCEPTION: {str(e)}") # Добавим вывод в консоль
            return {'success': False, 'message': 'Ошибка авторизации'}
        finally:
            cur.close()
            conn.close()

    @staticmethod
    def create_team_developer(admin_id, login, password, email, full_name):
        """Создает аккаунт разработчика (только для администраторов)"""
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            # Проверяем, является ли создатель администратором
            cur.execute("SELECT user_role FROM users WHERE user_id = %s", (admin_id,))
            admin = cur.fetchone()
            if not admin or admin[0] != 'admin':
                raise ValueError("Только администратор может создавать аккаунты разработчиков")

            # Создаем аккаунт разработчика
            return Auth.register_user(
                login=login,
                password=password,
                email=email,
                full_name=full_name,
                role='team_developer',
                created_by=admin_id
            )
        except Exception as e:
            logging.error(f"Error creating team developer: {str(e)}")
            raise
        finally:
            cur.close()
            conn.close()

    @staticmethod
    def get_user_info(user_id):
        """Получает информацию о пользователе"""
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT user_id, login, email, full_name, user_role, created_at, last_login, is_active
                FROM users WHERE user_id = %s
            """, (user_id,))
            user = cur.fetchone()
            if user:
                return {
                    'user_id': user[0],
                    'login': user[1],
                    'email': user[2],
                    'full_name': user[3],
                    'role': user[4],
                    'created_at': user[5],
                    'last_login': user[6],
                    'is_active': user[7]
                }
            return None
        finally:
            cur.close()
            conn.close()

    @staticmethod
    def get_team_developers(admin_id):
        """Получает список разработчиков команды для администратора"""
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT user_id, login, email, full_name, created_at, last_login, is_active
                FROM users 
                WHERE created_by = %s AND user_role = 'team_developer'
                ORDER BY full_name
            """, (admin_id,))
            developers = cur.fetchall()
            return [{
                'user_id': dev[0],
                'login': dev[1],
                'email': dev[2],
                'full_name': dev[3],
                'created_at': dev[4],
                'last_login': dev[5],
                'is_active': dev[6]
            } for dev in developers]
        finally:
            cur.close()
            conn.close()

    @staticmethod
    def delete_user(user_id_to_delete: int, performing_admin_id: int):
        """Удаляет пользователя. Только администратор может удалять других пользователей.
           Администратор не может удалить сам себя через этот метод.
        """
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            # Проверяем, является ли исполняющий пользователь администратором
            cur.execute("SELECT user_role FROM users WHERE user_id = %s", (performing_admin_id,))
            admin_check = cur.fetchone()
            if not admin_check or admin_check[0] != 'admin':
                logging.warning(f"User ID {performing_admin_id} attempted to delete user ID {user_id_to_delete} without admin rights.")
                raise ValueError("Только администратор может удалять пользователей.")

            # Проверяем, не пытается ли администратор удалить самого себя
            if user_id_to_delete == performing_admin_id:
                logging.warning(f"Admin ID {performing_admin_id} attempted to delete their own account.")
                raise ValueError("Администратор не может удалить свой собственный аккаунт через эту функцию.")
            
            # Получаем информацию о пользователе для логгирования перед удалением (опционально, но полезно)
            cur.execute("SELECT login, email, user_role FROM users WHERE user_id = %s", (user_id_to_delete,))
            user_to_delete_info = cur.fetchone()
            if not user_to_delete_info:
                raise ValueError(f"Пользователь с ID {user_id_to_delete} не найден.")

            # Вызываем функцию удаления из database.py
            success = delete_user_by_id(user_id_to_delete)
            
            if success:
                logging.info(f"Admin ID {performing_admin_id} successfully deleted user ID {user_id_to_delete} (Login: {user_to_delete_info[0]}, Email: {user_to_delete_info[1]}).")
                return True # Или можно вернуть словарь с деталями
            else:
                # Эта ветка может быть достигнута, если delete_user_by_id вернул False (пользователь не найден там)
                # но мы уже проверили выше. Оставим на всякий случай.
                logging.error(f"Admin ID {performing_admin_id} failed to delete user ID {user_id_to_delete} - user not found by delete_user_by_id.")
                return False

        except ValueError as ve: # Перехватываем ValueError от delete_user_by_id или наши собственные
            logging.error(f"Error during user deletion by Admin ID {performing_admin_id} for User ID {user_id_to_delete}: {str(ve)}")
            raise # Передаем ValueError дальше, чтобы UI мог его показать
        except Exception as e:
            logging.error(f"Unexpected error during user deletion by Admin ID {performing_admin_id} for User ID {user_id_to_delete}: {str(e)}")
            # Для UI лучше не передавать общие Exception, а специфичную ошибку или сообщение
            raise ValueError(f"Произошла непредвиденная ошибка при удалении пользователя: {str(e)}")
        finally:
            cur.close()
            conn.close() 