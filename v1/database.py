import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv
import os
import logging

# Настройка логирования
logging.basicConfig(filename='database.log', level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')

# Загрузка переменных окружения
load_dotenv()

def get_db_connection():
    """Создает и возвращает соединение с базой данных"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=os.getenv('DB_PORT')
        )
        return conn
    except Exception as e:
        logging.error(f"Database connection error: {str(e)}")
        raise

def init_db():
    """Инициализирует базу данных, создавая необходимые таблицы"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Создание таблицы пользователей
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                login VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                full_name VARCHAR(100) NOT NULL,
                user_role VARCHAR(20) NOT NULL CHECK (user_role IN ('admin', 'team_developer', 'solo_developer')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER REFERENCES users(user_id),
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT true
            )
        """)

        # Создание таблицы связей команды
        cur.execute("""
            CREATE TABLE IF NOT EXISTS team_relations (
                relation_id SERIAL PRIMARY KEY,
                admin_id INTEGER REFERENCES users(user_id),
                developer_id INTEGER REFERENCES users(user_id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(admin_id, developer_id)
            )
        """)

        # Создание таблицы информации о Git
        cur.execute("""
            CREATE TABLE IF NOT EXISTS git_info (
                git_info_id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(user_id),
                repository_path VARCHAR(255) NOT NULL,
                git_email VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, git_email)
            )
        """)

        # Создание таблицы для метрик коммитов
        cur.execute("""
            CREATE TABLE IF NOT EXISTS commit_metrics (
                metric_id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(user_id),
                date DATE NOT NULL,
                commit_count INTEGER DEFAULT 0,
                lines_added INTEGER DEFAULT 0,
                lines_deleted INTEGER DEFAULT 0,
                files_changed INTEGER DEFAULT 0,
                commit_time TIME[]
            )
        """)

        # Создание таблицы для метрик рабочего времени
        cur.execute("""
            CREATE TABLE IF NOT EXISTS work_time_metrics (
                metric_id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(user_id),
                date DATE NOT NULL,
                work_start TIME,
                work_end TIME,
                lunch_start TIME,
                lunch_end TIME,
                total_work_hours DECIMAL(5,2),
                productive_hours DECIMAL(5,2),
                dead_time_percentage DECIMAL(5,2)
            )
        """)

        # Создание таблицы почасовой активности
        cur.execute("""
            CREATE TABLE IF NOT EXISTS hourly_activity (
                activity_id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(user_id),
                date DATE NOT NULL,
                hour INTEGER CHECK (hour >= 0 AND hour < 24),
                commit_count INTEGER DEFAULT 0,
                activity_level INTEGER DEFAULT 0,
                UNIQUE(user_id, date, hour)
            )
        """)

        # Создание индексов
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_login ON users(login)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(user_role)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_commit_metrics_user_date ON commit_metrics(user_id, date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_work_time_metrics_user_date ON work_time_metrics(user_id, date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_hourly_activity_user_date ON hourly_activity(user_id, date)")

        conn.commit()
        logging.info("Database initialized successfully")
    except Exception as e:
        conn.rollback()
        logging.error(f"Database initialization error: {str(e)}")
        raise
    finally:
        cur.close()
        conn.close()

# Функции для работы с Git-информацией
def save_git_info(user_id, repository_path, git_email):
    """Сохраняет информацию о Git-репозитории пользователя"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO git_info (user_id, repository_path, git_email)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, git_email) 
            DO UPDATE SET repository_path = EXCLUDED.repository_path
        """, (user_id, repository_path, git_email))
        conn.commit()
        logging.info(f"Git info saved for user {user_id}")
    except Exception as e:
        conn.rollback()
        logging.error(f"Error saving git info: {str(e)}")
        raise
    finally:
        cur.close()
        conn.close()

def get_git_info(user_id):
    """Получает информацию о Git-репозиториях пользователя"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    try:
        cur.execute("""
            SELECT repository_path, git_email, created_at
            FROM git_info
            WHERE user_id = %s
        """, (user_id,))
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()

# Функции для работы с командными отношениями
def add_team_relation(admin_id, developer_id):
    """Добавляет связь между администратором и разработчиком"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO team_relations (admin_id, developer_id)
            VALUES (%s, %s)
            ON CONFLICT (admin_id, developer_id) DO NOTHING
        """, (admin_id, developer_id))
        conn.commit()
        logging.info(f"Team relation added: admin {admin_id} - developer {developer_id}")
    except Exception as e:
        conn.rollback()
        logging.error(f"Error adding team relation: {str(e)}")
        raise
    finally:
        cur.close()
        conn.close()

def get_team_members(admin_id):
    """Получает список разработчиков в команде администратора"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=DictCursor)
    try:
        cur.execute("""
            SELECT u.user_id, u.login, u.email, u.full_name, u.created_at, u.last_login, u.is_active
            FROM users u
            JOIN team_relations tr ON u.user_id = tr.developer_id
            WHERE tr.admin_id = %s
            ORDER BY u.full_name
        """, (admin_id,))
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()

def get_user_id_by_email(email_str: str) -> int | None:
    """Возвращает user_id по email или None, если пользователь не найден."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT user_id FROM users WHERE email = %s", (email_str,))
        user = cur.fetchone()
        if user:
            return user[0]
        return None
    except Exception as e:
        logging.error(f"Error fetching user_id by email {email_str}: {str(e)}")
        return None
    finally:
        cur.close()
        conn.close()

def delete_user_by_id(user_id: int) -> bool:
    """Удаляет пользователя по его ID. 
    Возвращает True в случае успеха, False в случае ошибки (например, FK violation).
    Более детальная ошибка будет залогирована.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Попытка удалить пользователя
        # ВНИМАНИЕ: Это может не сработать, если есть FK constraints без ON DELETE CASCADE
        cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        conn.commit()
        if cur.rowcount > 0:
            logging.info(f"User with ID {user_id} deleted successfully.")
            return True
        else:
            logging.warning(f"Attempted to delete user with ID {user_id}, but user not found.")
            return False # Пользователь не найден
    except psycopg2.Error as e: # Ловим специфичные ошибки psycopg2, включая FK violations
        conn.rollback()
        logging.error(f"Error deleting user with ID {user_id}: {str(e)}")
        # Проверка на foreign_key_violation (код 23503 для PostgreSQL)
        if e.pgcode == '23503': 
            raise ValueError(f"Невозможно удалить пользователя (ID: {user_id}), так как на него ссылаются другие записи. Сначала удалите или измените связанные данные.")
        raise # Перевыбрасываем другие ошибки psycopg2 или общие ошибки
    except Exception as e:
        conn.rollback()
        logging.error(f"Generic error deleting user with ID {user_id}: {str(e)}")
        raise
    finally:
        cur.close()
        conn.close()

# Функции для сохранения метрик
def save_work_time_metrics(user_id: int, date_obj, work_start_time, work_end_time, lunch_start_time, lunch_end_time, total_work_hours: float, productive_hours: float, dead_time_percentage: float):
    """Сохраняет или обновляет метрики рабочего времени пользователя за определенную дату."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO work_time_metrics (user_id, date, work_start, work_end, lunch_start, lunch_end, total_work_hours, productive_hours, dead_time_percentage)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, date) DO UPDATE SET
                work_start = EXCLUDED.work_start,
                work_end = EXCLUDED.work_end,
                lunch_start = EXCLUDED.lunch_start,
                lunch_end = EXCLUDED.lunch_end,
                total_work_hours = EXCLUDED.total_work_hours,
                productive_hours = EXCLUDED.productive_hours,
                dead_time_percentage = EXCLUDED.dead_time_percentage;
        """, (user_id, date_obj, work_start_time, work_end_time, lunch_start_time, lunch_end_time, total_work_hours, productive_hours, dead_time_percentage))
        conn.commit()
        logging.info(f"Work time metrics saved for user_id {user_id} on {date_obj}")
    except Exception as e:
        conn.rollback()
        logging.error(f"Error saving work time metrics for user_id {user_id} on {date_obj}: {str(e)}")
    finally:
        cur.close()
        conn.close()

def save_hourly_activity(user_id: int, date_obj, hour: int, commit_count: int, activity_level: int):
    """Сохраняет или обновляет почасовую активность пользователя."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO hourly_activity (user_id, date, hour, commit_count, activity_level)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id, date, hour) DO UPDATE SET
                commit_count = EXCLUDED.commit_count,
                activity_level = EXCLUDED.activity_level;
        """, (user_id, date_obj, hour, commit_count, activity_level))
        conn.commit()
        # logging.info(f"Hourly activity saved for user_id {user_id} on {date_obj} at {hour}h") # Может быть слишком много логов
    except Exception as e:
        conn.rollback()
        logging.error(f"Error saving hourly activity for user_id {user_id} on {date_obj} at {hour}h: {str(e)}")
    finally:
        cur.close()
        conn.close()

def save_commit_temporal_data(user_id: int, date_obj, commit_count: int, commit_times_list):
    """Сохраняет или обновляет временные данные коммитов (количество и время)."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Если commit_times_list пуст, передаем NULL в базу данных
        db_commit_times = commit_times_list if commit_times_list else None
        cur.execute("""
            INSERT INTO commit_metrics (user_id, date, commit_count, commit_time)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id, date) DO UPDATE SET
                commit_count = EXCLUDED.commit_count,
                commit_time = EXCLUDED.commit_time;
        """, (user_id, date_obj, commit_count, db_commit_times))
        conn.commit()
        logging.info(f"Commit temporal data saved for user_id {user_id} on {date_obj}")
    except Exception as e:
        conn.rollback()
        logging.error(f"Error saving commit temporal data for user_id {user_id} on {date_obj}: {str(e)}")
    finally:
        cur.close()
        conn.close()

def save_commit_code_stats(user_id: int, date_obj, lines_added: int, lines_deleted: int, files_changed: int):
    """Сохраняет или обновляет статистику по коду в коммитах (строки, файлы)."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO commit_metrics (user_id, date, lines_added, lines_deleted, files_changed)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id, date) DO UPDATE SET
                lines_added = EXCLUDED.lines_added,
                lines_deleted = EXCLUDED.lines_deleted,
                files_changed = EXCLUDED.files_changed;
        """, (user_id, date_obj, lines_added, lines_deleted, files_changed))
        conn.commit()
        logging.info(f"Commit code stats saved for user_id {user_id} on {date_obj}")
    except Exception as e:
        conn.rollback()
        logging.error(f"Error saving commit code stats for user_id {user_id} on {date_obj}: {str(e)}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    # Инициализация базы данных при запуске файла
    init_db() 