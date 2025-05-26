import os
import git
from git.exc import GitCommandError, InvalidGitRepositoryError
from PyQt5.QtWidgets import QProgressBar
import logging

# Настройка логирования
logging.basicConfig(filename='devmetrics.log', level=logging.ERROR,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def update_code_analysis(project_path, progress_bar=None, author=None):
    try:
        if not project_path or not os.path.exists(project_path):
            return "Ошибка: Указан неверный путь к проекту"

        repo = git.Repo(project_path)
        if progress_bar:
            progress_bar.setVisible(True)
            progress_bar.setMaximum(100)
            progress_bar.setValue(0)

        # Получаем все коммиты для указанного автора
        commits = list(repo.iter_commits(max_count=10000, author=author))
        if not commits:
            return "Нет данных для анализа кода"

        total_commits = len(commits)
        if progress_bar:
            progress_bar.setMaximum(total_commits)

        code_metrics = {
            'total_files_changed': 0,
            'total_lines_added': 0,
            'total_lines_removed': 0,
            'files_by_extension': {}
        }

        for idx, commit in enumerate(commits):
            if progress_bar:
                progress_bar.setValue(idx + 1)

            parent = commit.parents[0] if commit.parents else None
            if not parent:
                continue

            diff_stat = repo.git.diff(commit.hexsha + '^', commit.hexsha, numstat=True)
            for line in diff_stat.splitlines():
                if not line.strip():
                    continue

                parts = line.split('\t')
                if len(parts) != 3:
                    continue

                added, removed, file_path = parts
                if any(excluded in file_path for excluded in ['venv', '.idea']):
                    continue

                if added == '-' or removed == '-':
                    continue

                added = int(added)
                removed = int(removed)

                code_metrics['total_files_changed'] += 1
                code_metrics['total_lines_added'] += added
                code_metrics['total_lines_removed'] += removed

                _, ext = os.path.splitext(file_path)
                ext = ext[1:] if ext else 'unknown'
                code_metrics['files_by_extension'][ext] = code_metrics['files_by_extension'].get(ext, 0) + 1

        if code_metrics['total_files_changed'] == 0:
            return "Нет изменений в рабочих файлах"

        metrics_text = (
            f"Общее количество изменённых файлов: {code_metrics['total_files_changed']}\n"
            f"Добавлено строк: {code_metrics['total_lines_added']}\n"
            f"Удалено строк: {code_metrics['total_lines_removed']}\n"
            f"Распределение по расширениям: {dict(sorted(code_metrics['files_by_extension'].items()))}"
        )
        return metrics_text if author else code_metrics

    except InvalidGitRepositoryError:
        logging.error(f"Invalid Git repository: {project_path}")
        return "Ошибка: Указанная папка не является Git-репозиторием"
    except GitCommandError as e:
        logging.error(f"Git command error: {str(e)}")
        return f"Ошибка анализа кода: {str(e)}"
    except Exception as e:
        logging.error(f"Error in update_code_analysis: {str(e)}")
        return f"Ошибка анализа кода: {str(e)}"
    finally:
        if progress_bar:
            progress_bar.setVisible(False)