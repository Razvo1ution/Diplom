import os
from datetime import datetime, timedelta
from git import Repo
from git.exc import InvalidGitRepositoryError
import numpy as np
import calendar

def update_charts(project_path, selected_year=None, selected_month=None):
    """
    Обновляет данные для графиков за выбранный месяц и год.
    
    Args:
        project_path (str): Путь к Git репозиторию
        selected_year (int): Выбранный год (если None, используется текущий год)
        selected_month (int): Выбранный месяц (если None, используется текущий месяц)
    """
    if not project_path or not os.path.exists(project_path):
        return 0, [], None, None, None

    if not os.path.exists(os.path.join(project_path, '.git')):
        return 0, [], None, None, None

    try:
        repo = Repo(project_path)
        commits = list(repo.iter_commits())
        
        # Получаем имя проекта из пути
        project_name = os.path.basename(os.path.normpath(project_path))
        
        # Используем выбранный год и месяц или текущие значения
        today = datetime.now()
        target_year = selected_year if selected_year is not None else today.year
        target_month = selected_month if selected_month is not None else today.month
        
        # Данные для тренда продуктивности
        weeks = 4
        commits_per_week = [0] * weeks
        
        # Данные для гистограммы
        _, last_day = calendar.monthrange(target_year, target_month)
        days = list(range(1, last_day + 1))
        hours = [0] * len(days)
        
        # Данные для тепловой карты
        heatmap_data = np.zeros((len(days), 24))
        
        # Обработка коммитов
        for commit in commits:
            commit_time = datetime.fromtimestamp(commit.committed_date)
            
            # Для тренда продуктивности (за последние 4 недели)
            if commit_time.year == target_year and commit_time.month == target_month:
                week_of_month = (commit_time.day - 1) // 7
                if week_of_month < weeks:
                    commits_per_week[week_of_month] += 1
            
                # Для гистограммы и тепловой карты (за выбранный месяц)
                day_idx = commit_time.day - 1
                hour = commit_time.hour
                
                # Добавляем коммит в гистограмму
                hours[day_idx] += 1
                
                # Добавляем коммит в тепловую карту
                heatmap_data[day_idx][hour] += 1

        return weeks, commits_per_week, hours, heatmap_data, project_name

    except InvalidGitRepositoryError:
        return 0, [], None, None, None
    except Exception as e:
        print(f"Error in update_charts: {str(e)}")
        return 0, [], None, None, None