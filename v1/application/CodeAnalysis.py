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
            # Фильтрация коммитов по дате - это сложная задача, требующая аккуратной работы
            # с датами коммитов. GitPython позволяет фильтровать по since/until,
            # но нужно будет правильно сформировать эти параметры из date_filter.
            # Для одного дня это будет диапазон от начала до конца дня.
            # ПОКА ЭТА ЧАСТЬ НЕ РЕАЛИЗОВАНА ПОЛНОСТЬЮ
            
            # Примерная логика (требует доработки и тестирования):
            # from_date = datetime(year, month, day, 0, 0, 0)
            # to_date = datetime(year, month, day, 23, 59, 59)
            # commits_to_analyze = list(repo.iter_commits(author=author, since=from_date.isoformat(), until=to_date.isoformat()))
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
        
        # Статистика по выбранным файлам за указанный день (если указаны)
        # Это будет агрегированная статистика, если selected_files не None и date_filter не None
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


            # diff_stat = repo.git.diff(parent.hexsha, commit.hexsha, numstat=True) # Сравнение с родителем
            # Если selected_files указаны, нужно получить diff только для них
            diff_files_arg = selected_files if selected_files else None
            
            # Если selected_files - пустой список, это может вызвать ошибку или неожиданное поведение в git.diff
            # Поэтому, если selected_files пуст, но предполагается анализ (например, по дате),
            # мы можем либо анализировать все файлы (diff_files_arg=None), либо ничего не делать (зависит от требований).
            # Пока оставим None, если selected_files пуст, что приведет к анализу всех файлов в коммите.

            try:
                # Чтобы получить изменения для конкретных файлов, передаем их в diff
                # Если selected_files это None, то git.diff возьмет все файлы
                # Если selected_files это [], то могут быть проблемы, лучше None
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

        # --- Расчет "всех изменений в проекте ЗА всё время работы" ---
        # Для этого нам нужно выполнить еще один проход по всем коммитам без фильтра по автору/дате,
        # если текущий запрос был с фильтрами.
        # Чтобы не усложнять, пока overall_metrics_all_time будет таким же, как metrics_for_period_or_author,
        # если не было фильтров. Если были фильтры, его нужно будет вычислить отдельно.
        # Для простоты, если есть автор или date_filter, то overall_metrics_all_time будет пустым,
        # и UI должен будет запросить его отдельно без фильтров.
        # Или, мы можем всегда вычислять его. Давайте пока так:
        
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

# Старая функция, если вдруг понадобится для обратной совместимости или отладки
# def одиночная_строка_вывода_старой_функции... (закомментировано, так как мы меняем формат вывода)
# ... (остальной код старой функции update_code_analysis закомментирован или удален, так как мы его переписали)

# Пример использования (для тестирования):
# if __name__ == '__main__':
#     project_repo_path = '.' # Укажите путь к вашему репозиторию
#     
#     # Тест 1: Получение списка файлов
#     # files = get_repository_files(project_repo_path)
#     # print("Files in repository:", files)
#     
#     # Тест 2: Общий анализ (без фильтров)
#     # analysis_data = update_code_analysis(project_repo_path)
#     # print("\nOverall Analysis (all time):")
#     # if analysis_data.get("error"):
#     #     print(f"Error: {analysis_data['error']}")
#     # else:
#     #     print(f"  Total files changed (all time): {analysis_data.get('overall_metrics_all_time', {}).get('total_files_changed')}")
#     #     print(f"  Total lines added (all time): {analysis_data.get('overall_metrics_all_time', {}).get('total_lines_added')}")
#     #     print(f"  Total lines removed (all time): {analysis_data.get('overall_metrics_all_time', {}).get('total_lines_removed')}")
#     #     print(f"  Current query (no filter) - Added: {analysis_data.get('metrics_for_period_or_author', {}).get('total_lines_added')}")
#
#     # Тест 3: Анализ с фильтром по дате и файлам
#     # specific_date = {'year': 2024, 'month': 5, 'day': 20} # Пример даты
#     # specific_files = ['v1/CodeAnalysis.py'] # Пример файла
#     # analysis_data_specific = update_code_analysis(project_repo_path, selected_files=specific_files, date_filter=specific_date)
#     # print(f"\nAnalysis for {specific_date} and files {specific_files}:")
#     # if analysis_data_specific.get("error"):
#     #     print(f"Error: {analysis_data_specific['error']}")
#     # else:
#     #     print(f"  Daily stats for files: {analysis_data_specific.get('files_daily_stats')}")
#     #     print(f"  Summary for selected files today: Added: {analysis_data_specific.get('selected_files_summary_today', {}).get('total_lines_added')}, Removed: {analysis_data_specific.get('selected_files_summary_today', {}).get('total_lines_removed')}")
#     #     print(f"  Metrics for this specific query: Added: {analysis_data_specific.get('metrics_for_period_or_author', {}).get('total_lines_added')}")

# Удаляем старый return, который был ниже
# metrics_text = (
# ...
# )
# #return metrics_text if author else code_metrics
# if author:
# return metrics_text
# else:
# # Форматируем словарь code_metrics в строку
# formatted_metrics = (
# f"Общее количество изменённых файлов: {code_metrics['total_files_changed']}\n"
# f"Добавлено строк: {code_metrics['total_lines_added']}\n"
# f"Удалено строк: {code_metrics['total_lines_removed']}\n"
# f"Распределение по расширениям: {dict(sorted(code_metrics['files_by_extension'].items()))}"
# )
# return formatted_metrics