import os
import git
from git.exc import GitCommandError, InvalidGitRepositoryError
from PyQt5.QtWidgets import QProgressBar
import logging
from datetime import datetime # Добавим импорт datetime для работы с датами в будущем
from database import get_user_id_by_email, save_commit_code_stats

# Настройка логирования
logging.basicConfig(filename='devmetrics.log', level=logging.ERROR,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Список путей и шаблонов для исключения из анализа
EXCLUDED_PATHS = [
    'venv/',
    '.venv/',
    'env/',
    '.env/',
    '.idea/',
    '.git/',
    '__pycache__/',
    'node_modules/',
    'dist/',
    'build/',
    '.pytest_cache/',
    '.coverage',
    'coverage/',
    '.vs/',
    '.vscode/',
    'bin/',
    'obj/',
    'devmetrics.log',
    '.gitignore',
    'package-lock.json',
    '.DS_Store',
    'Thumbs.db',
    '.env',
    '.pyc',
    '.pyo',
    '.pyd',
    '.so',
    '.dll',
    '.dylib',
    'requirements.txt',
    'poetry.lock',
    'Pipfile.lock'
]

def should_exclude_path(file_path):
    """Проверяет, должен ли файл быть исключен из анализа"""
    # Проверяем прямые совпадения
    if file_path in EXCLUDED_PATHS:
        return True
    
    # Проверяем, содержит ли путь к файлу исключаемые директории
    for excluded in EXCLUDED_PATHS:
        if excluded.endswith('/'):  # Если это директория (заканчивается на '/')
            if excluded in file_path:  # Проверяем, содержится ли путь директории в пути файла
                return True
        else:  # Если это файл
            if file_path.endswith(excluded):  # Проверяем, заканчивается ли путь файла на исключаемое имя
                return True
    
    # Дополнительные проверки для специфических случаев
    _, ext = os.path.splitext(file_path)
    if ext in ['.pyc', '.pyo', '.pyd', '.so', '.dll', '.dylib']:
        return True
        
    return False

def get_repository_files(project_path):
    """Возвращает список всех файлов в последнем коммите репозитория."""
    try:
        if not project_path or not os.path.exists(project_path):
            return [] # Возвращаем пустой список в случае ошибки пути
        repo = git.Repo(project_path)
        if not repo.head.is_valid():
            return [] # Если нет HEAD, значит нет коммитов
        
        # Получаем дерево файлов последнего коммита
        tree = repo.head.commit.tree
        files = []
        for blob in tree.traverse():
            if blob.type == 'blob': # 'blob' означает файл
                if not should_exclude_path(blob.path):  # Добавляем проверку на исключение
                    files.append(blob.path)
        return files
    except InvalidGitRepositoryError:
        logging.error(f"Invalid Git repository for get_repository_files: {project_path}")
        return []
    except Exception as e:
        logging.error(f"Error in get_repository_files: {str(e)}")
        return []

def update_code_analysis(project_path, progress_bar=None, author=None, selected_files=None, date_filter=None): # Добавлены selected_files и date_filter
    """
    Анализирует Git репозиторий и возвращает структурированную статистику.
    date_filter: dict, e.g. {'year': 2023, 'month': 12, 'day': 20} or None
    selected_files: list of file paths or None
    """
    try:
        if not project_path or not os.path.exists(project_path):
            return {"error": "Ошибка: Указан неверный путь к проекту"}

        repo = git.Repo(project_path)
        if progress_bar:
            progress_bar.setVisible(True)
            progress_bar.setMaximum(100) # Начальное значение, будет обновлено
            progress_bar.setValue(0)

        # --- Логика для фильтрации коммитов по дате (пока заглушка) ---
        # Это потребует более сложной логики для определения коммитов 'since' и 'until'
        # на основе date_filter
        commits_to_analyze = list(repo.iter_commits(max_count=10000, author=author)) # Пока берем все как раньше

        if date_filter and date_filter.get('day') and date_filter.get('month') and date_filter.get('year'):
            day = date_filter['day']
            month = date_filter['month']
            year = date_filter['year']
            pass # Оставляем commits_to_analyze как есть на данном этапе


        if not commits_to_analyze:
            return {"error": "Нет данных для анализа кода (возможно, из-за фильтров)"}

        total_commits_in_range = len(commits_to_analyze)
        if progress_bar:
            progress_bar.setMaximum(total_commits_in_range if total_commits_in_range > 0 else 100)


        overall_metrics = {
            'total_files_changed': 0,
            'total_lines_added': 0,
            'total_lines_removed': 0,
            'files_by_extension': {}
        }

        files_daily_stats = {} # {'file_path': {'added': X, 'removed': Y, 'date': 'YYYY-MM-DD'}}

        # Общая статистика по выбранным файлам за указанный день (сумма)
        selected_files_summary_today = {
            'total_lines_added': 0,
            'total_lines_removed': 0,
            'total_files_changed': 0 # Добавим счетчик измененных файлов для статистики дня
        }

        for idx, commit in enumerate(commits_to_analyze):
            if progress_bar:
                progress_bar.setValue(idx + 1)

            parent = commit.parents[0] if commit.parents else None
            if not parent: # Пропускаем первый коммит, так как у него нет родителя для сравнения
                # Или обрабатываем его иначе, если нужно считать все файлы как добавленные
                continue
            
            # Фильтруем по дате коммита, если date_filter активен
            commit_date = datetime.fromtimestamp(commit.committed_date).date()
            filter_active_for_commit = False
            if date_filter and date_filter.get('day') and date_filter.get('month') and date_filter.get('year'):
                target_date = datetime(date_filter['year'], date_filter['month'], date_filter['day']).date()
                if commit_date == target_date:
                    filter_active_for_commit = True
            else: # Если фильтр даты не активен, обрабатываем все коммиты
                filter_active_for_commit = True

            diff_files_arg = selected_files if selected_files else None

            try:
                diff_args = [parent.hexsha, commit.hexsha]
                if diff_files_arg: # Если есть выбранные файлы, добавляем их к аргументам diff
                    diff_args.append('--')
                    diff_args.extend(diff_files_arg)
                
                diff_stat_output = repo.git.diff(*diff_args, numstat=True, find_renames=True)

            except GitCommandError as e:
                # Может произойти, если файл был удален или переименован специфичным образом
                logging.warning(f"Git diff command error for commit {commit.hexsha} (parent {parent.hexsha}): {str(e)}. Skipping diff for this commit.")
                continue # Пропускаем этот diff


            for line in diff_stat_output.splitlines():
                if not line.strip():
                    continue

                parts = line.split('\t')
                if len(parts) != 3:
                    continue

                added_str, removed_str, file_path = parts
                
                # Обработка переименований (numstat может показывать это так: "old_name => new_name")
                if ' => ' in file_path:
                    file_path = file_path.split(' => ')[-1].strip()

                # Используем новую функцию проверки исключений
                if should_exclude_path(file_path):
                    continue # Пропускаем исключенные файлы/директории

                if added_str == '-' or removed_str == '-': # Бинарные файлы или файлы без изменений строк
                    continue

                try:
                    added = int(added_str)
                    removed = int(removed_str)
                except ValueError:
                    logging.warning(f"Could not parse added/removed for line: {line} in commit {commit.hexsha}")
                    continue

                # Общая статистика за все время (или за период, если коммиты отфильтрованы)
                overall_metrics['total_files_changed'] += 1 # Считаем каждый файл в diff как измененный
                overall_metrics['total_lines_added'] += added
                overall_metrics['total_lines_removed'] += removed
                _, ext = os.path.splitext(file_path)
                ext = ext[1:] if ext else 'unknown'
                overall_metrics['files_by_extension'][ext] = overall_metrics['files_by_extension'].get(ext, 0) + 1
                
                # Статистика для выбранных файлов за ОПРЕДЕЛЕННЫЙ ДЕНЬ (если фильтр активен)
                if filter_active_for_commit and selected_files and file_path in selected_files:
                    if file_path not in files_daily_stats:
                        files_daily_stats[file_path] = {'added': 0, 'removed': 0}
                    files_daily_stats[file_path]['added'] += added
                    files_daily_stats[file_path]['removed'] += removed
                    
                    selected_files_summary_today['total_lines_added'] += added
                    selected_files_summary_today['total_lines_removed'] += removed
                    # Увеличиваем счетчик измененных файлов, если файл еще не учтен
                    # Это упрощенный подсчет, т.к. один файл может меняться в нескольких коммитах за день
                    # Более точный подсчет уникальных измененных файлов за день потребовал бы хранить set имен файлов
                    selected_files_summary_today['total_files_changed'] += 1 


        # Удаляем временные метрики, если они не использовались
        if not (date_filter and selected_files):
            files_daily_stats = {} # Очищаем, если не было фильтра по дате и файлам
            selected_files_summary_today = {}


        # Сохранение статистики по коду в БД, если был активен фильтр по дате и указан автор
        if author and date_filter and date_filter.get('day') and date_filter.get('month') and date_filter.get('year'):
            user_id = get_user_id_by_email(author)
            if user_id:
                target_date_obj = datetime(date_filter['year'], date_filter['month'], date_filter['day']).date()
                save_commit_code_stats(
                    user_id,
                    target_date_obj,
                    selected_files_summary_today['total_lines_added'],
                    selected_files_summary_today['total_lines_removed'],
                    selected_files_summary_today['total_files_changed'] # Используем подсчитанное количество
                )
            else:
                logging.warning(f"User with email {author} not found in DB. Code stats not saved for {date_filter}")

        # Формируем итоговый результат
        analysis_result = {
            "overall_metrics_all_time": {}, # Это будет для ВСЕХ изменений за все время
            "metrics_for_period_or_author": overall_metrics, # Это для текущего запроса (с автором/периодом)
            "files_daily_stats": files_daily_stats,
            "selected_files_summary_today": selected_files_summary_today,
            "error": None
        }
        
        all_time_commits = list(repo.iter_commits()) # Все коммиты
        all_time_total_commits = len(all_time_commits)
        
        all_time_metrics = {
            'total_files_changed': 0,
            'total_lines_added': 0,
            'total_lines_removed': 0,
            'files_by_extension': {}
        }

        if progress_bar: # Дополнительный прогресс для общей статистики
            progress_bar.setValue(0)
            progress_bar.setMaximum(all_time_total_commits if all_time_total_commits > 0 else 100)
            
        for idx, commit in enumerate(all_time_commits):
            if progress_bar:
                progress_bar.setValue(idx + 1)
            parent = commit.parents[0] if commit.parents else None
            if not parent:
                continue
            try:
                diff_stat_output_all_time = repo.git.diff(parent.hexsha, commit.hexsha, numstat=True, find_renames=True)
                for line in diff_stat_output_all_time.splitlines():
                    if not line.strip(): continue
                    parts = line.split('\t')
                    if len(parts) != 3: continue
                    added_str, removed_str, file_path = parts
                    if ' => ' in file_path: file_path = file_path.split(' => ')[-1].strip()
                    if should_exclude_path(file_path): continue
                    if added_str == '-' or removed_str == '-': continue
                    try:
                        added = int(added_str); removed = int(removed_str)
                        all_time_metrics['total_files_changed'] += 1
                        all_time_metrics['total_lines_added'] += added
                        all_time_metrics['total_lines_removed'] += removed
                        _, ext = os.path.splitext(file_path)
                        ext = ext[1:] if ext else 'unknown'
                        all_time_metrics['files_by_extension'][ext] = all_time_metrics['files_by_extension'].get(ext, 0) + 1
                    except ValueError:
                        continue
            except GitCommandError:
                continue # Пропускаем ошибки diff для общей статистики

        analysis_result["overall_metrics_all_time"] = all_time_metrics
        
        if overall_metrics['total_files_changed'] == 0 and all_time_metrics['total_files_changed'] == 0 : # если вообще нет изменений
             analysis_result["error"] = "Нет изменений в рабочих файлах для анализа."
             # Очищаем метрики, если нет ошибки, но и данных нет
             if not analysis_result["error"]:
                 analysis_result["metrics_for_period_or_author"] = { 'total_files_changed': 0, 'total_lines_added': 0, 'total_lines_removed': 0, 'files_by_extension': {}}
                 analysis_result["overall_metrics_all_time"] = { 'total_files_changed': 0, 'total_lines_added': 0, 'total_lines_removed': 0, 'files_by_extension': {}}


        return analysis_result

    except InvalidGitRepositoryError:
        logging.error(f"Invalid Git repository: {project_path}")
        return {"error": "Ошибка: Указанная папка не является Git-репозиторием"}
    except GitCommandError as e:
        logging.error(f"Git command error: {str(e)}")
        return {"error": f"Ошибка команды Git: {str(e)}"}
    except Exception as e:
        logging.error(f"Error in update_code_analysis: {str(e)}")
        return {"error": f"Непредвиденная ошибка анализа кода: {str(e)}"}
    finally:
        if progress_bar:
            progress_bar.setVisible(False)
