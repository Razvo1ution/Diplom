import os
from git import Repo
from git.exc import InvalidGitRepositoryError
from radon.complexity import cc_visit
from PyQt5.QtWidgets import QApplication

def get_project_files(project_path):
    files = []
    for root, _, filenames in os.walk(project_path):
        for filename in filenames:
            if filename.endswith(('.py', '.js', '.java', '.cs', '.cpp', '.h', '.go', '.rs', '.kt', '.swift',
                                  '.json', '.yaml', '.yml', '.toml', '.env', 'Dockerfile', '.dockerignore',
                                  '.md', '.rst', 'README.md', 'LICENSE', 'CHANGELOG.md', 'CONTRIBUTING.md',
                                  'CODESTYLE.md', 'package.json', 'requirements.txt', 'pom.xml', 'build.gradle',
                                  'Cargo.toml', '.csproj', '.sln', '.css', '.scss', '.png', '.jpg', '.svg', '.html')):
                files.append(os.path.join(root, filename))
    return files

def update_code_analysis(project_path, progress_bar):
    if not project_path or not os.path.exists(project_path):
        return "Укажите путь к проекту в настройках"

    if not os.path.exists(os.path.join(project_path, '.git')):
        return "Ошибка: Указанная папка не является Git-репозиторием"

    try:
        repo = Repo(project_path)
        commits = list(repo.iter_commits(max_count=100))
        added_lines = 0
        deleted_lines = 0
        hotspots = {}
        python_files = [f for f in get_project_files(project_path) if f.endswith('.py')]

        for commit in commits:
            diff = commit.stats.total
            added_lines += diff['insertions']
            deleted_lines += diff['deletions']
            for file in commit.stats.files:
                hotspots[file] = hotspots.get(file, 0) + 1

        total_cc = 0
        complex_files = []
        progress_bar.setVisible(True)
        progress_bar.setMaximum(len(python_files) if python_files else 1)
        for i, file in enumerate(python_files):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    code = f.read()
                cc_results = cc_visit(code)
                file_cc = sum(block.complexity for block in cc_results)
                total_cc += file_cc
                if file_cc > 10:
                    complex_files.append((file, file_cc))
            except (SyntaxError, UnicodeDecodeError):
                continue
            progress_bar.setValue(i + 1)
            QApplication.processEvents()

        progress_bar.setVisible(False)
        avg_cc = total_cc / len(python_files) if python_files else 0
        hotspots_text = "\n".join(f"{file}: {count} изменений" for file, count in sorted(hotspots.items(), key=lambda x: x[1], reverse=True)[:5])

        metrics_text = (
            f"Добавлено строк: {added_lines}\n"
            f"Удалено строк: {deleted_lines}\n"
            f"Средняя цикломатическая сложность: {avg_cc:.2f}\n"
            f"Сложные файлы:\n" + "\n".join(f"{file}: {cc}" for file, cc in complex_files[:5]) + "\n"
            f"Часто изменяемые файлы:\n{hotspots_text}\n"
            f"Рекомендации: Проверить файлы с высокой сложностью для рефакторинга."
        )
        return metrics_text

    except InvalidGitRepositoryError:
        return "Ошибка: Указанная папка не является Git-репозиторием"
    except Exception as e:
        return f"Ошибка при анализе кода: {str(e)}"