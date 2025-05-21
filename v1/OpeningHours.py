import os
import git
from git.exc import GitCommandError, InvalidGitRepositoryError
from datetime import datetime, timedelta
from WorkSchedule import get_schedule, get_hours_per_day, get_work_hours
import calendar
import numpy as np
import logging

# Настройка логирования
logging.basicConfig(filename='devmetrics.log', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')


def format_time(hours):
    """Форматирует время из X.XXч в Xч или Xч Yмин."""
    if hours == 0:
        return "0ч"
    int_part = int(hours)
    frac_part = hours - int_part
    if frac_part == 0:
        return f"{int_part}ч"
    else:
        minutes = int(frac_part * 60)
        return f"{int_part}ч {minutes}мин"


def update_opening_hours(project_path, month, year, max_count=10000):
    try:
        repo = git.Repo(project_path)
        try:
            commits = list(repo.iter_commits(max_count=max_count))
        except GitCommandError as e:
            logging.error(f"Git command error while fetching commits: {str(e)}")
            raise Exception(f"Ошибка Git при получении коммитов: {str(e)}")

        hours_per_day = get_hours_per_day()
        work_start, work_end = get_work_hours()
        schedule = get_schedule(year, month)
        days_in_month = calendar.monthrange(year, month)[1]
        days = list(range(1, days_in_month + 1))
        hours = [0] * days_in_month
        weekend_days = []
        day_commits = {day: [] for day in days}
        active_days = 0
        total_commits = 0
        night_commits = 0
        commit_intervals = []
        commits_per_hour = []
        hour_counts = [0] * 24
        heatmap_data = np.zeros((days_in_month, 8))

        # Словарь для хранения дневных метрик
        daily_metrics = {day: {
            'work_period': None,  # Период времени работы (начало, конец)
            'total_time': 0,  # Общее время в часах
            'dead_periods': [],  # Список мёртвых периодов (начало, конец)
            'commits': 0,
            'night_commits': 0,
            'dead_time': 0
        } for day in days}

        # Собираем коммиты по дням
        logging.debug(f"Processing commits for month {month}, year {year}")
        for commit in commits:
            commit_time = datetime.fromtimestamp(commit.committed_date)
            if commit_time.year == year and commit_time.month == month:
                day = commit_time.day
                day_commits[day].append(commit_time)
                total_commits += 1
                hour = commit_time.hour
                hour_counts[hour] += 1
                interval_index = hour // 3
                heatmap_data[day - 1, interval_index] += 1
                if 23 <= hour or hour < 6:
                    night_commits += 1
                    daily_metrics[day]['night_commits'] += 1

        # Подсчёт метрик
        for day in days:
            if day not in schedule or not schedule[day]:
                weekend_days.append(day)
            commits = day_commits[day]
            daily_metrics[day]['commits'] = len(commits)
            if commits:
                active_days += 1
                commits.sort()  # Сортировка по времени
                start_time = commits[0]
                end_time = commits[-1]
                day_hours = (end_time - start_time).total_seconds() / 3600
                hours[day - 1] = day_hours
                daily_metrics[day]['work_period'] = (start_time, end_time)
                daily_metrics[day]['total_time'] = day_hours

                # Средний интервал между коммитами
                if len(commits) > 1:
                    intervals = [(commits[i + 1] - commits[i]).total_seconds() / 60 for i in range(len(commits) - 1)]
                    commit_intervals.extend(intervals)

                # Мёртвые периоды (в рабочие часы)
                if day not in weekend_days:
                    work_start_time = datetime(year, month, day, work_start.hour, work_start.minute)
                    work_end_time = datetime(year, month, day, work_end.hour, work_end.minute)
                    current_time = work_start_time
                    commit_index = 0  # Индекс для перебора коммитов
                    while current_time < work_end_time:
                        # Ищем следующий коммит после current_time
                        while commit_index < len(commits) and commits[commit_index] < current_time:
                            commit_index += 1
                        if commit_index >= len(commits):
                            # Нет больше коммитов — весь оставшийся период мёртвый
                            if current_time < work_end_time:
                                daily_metrics[day]['dead_periods'].append((current_time, work_end_time))
                            break
                        next_commit = commits[commit_index] if commit_index < len(commits) else None
                        if not next_commit or (next_commit - current_time).total_seconds() / 3600 >= 2:
                            dead_end = min(current_time + timedelta(hours=2), work_end_time)
                            if next_commit and next_commit < dead_end:
                                dead_end = next_commit
                            daily_metrics[day]['dead_periods'].append((current_time, dead_end))
                            current_time = dead_end
                        else:
                            current_time = next_commit
                            commit_index += 1

        # Расчёт мёртвого времени по дням
        for day in days:
            if day not in weekend_days:
                total_day_work_hours = (work_end.hour - work_start.hour)
                day_dead_time = sum(
                    (end - start).total_seconds() / 3600 for start, end in daily_metrics[day]['dead_periods'])
                daily_metrics[day]['dead_time'] = (
                            day_dead_time / total_day_work_hours * 100) if total_day_work_hours > 0 else 0

        # Коммиты в час
        active_hours = sum(1 for count in hour_counts if count > 0)
        commits_per_hour_avg = total_commits / active_hours if active_hours > 0 else 0

        # Пиковые часы активности
        peak_hours = []
        for i in range(0, 24, 2):
            count = sum(hour_counts[i:i + 2])
            if count > 0:
                peak_hours.append((f"{i:02d}:00–{i + 2:02d}:00", count))
        peak_hours.sort(key=lambda x: x[1], reverse=True)
        peak_hours_text = peak_hours[0][0] if peak_hours else "Нет данных"

        # Ночные коммиты
        night_commit_ratio = (night_commits / total_commits * 100) if total_commits > 0 else 0

        # Средний интервал между коммитами
        avg_commit_interval = sum(commit_intervals) / len(commit_intervals) if commit_intervals else 0

        # Мёртвое время (общее)
        workdays = [day for day in days if day not in weekend_days]
        total_work_hours = sum((work_end.hour - work_start.hour) for day in workdays)
        dead_time_hours = sum(
            sum((end - start).total_seconds() / 3600 for start, end in daily_metrics[day]['dead_periods']) for day in
            workdays)
        dead_time_percent = (dead_time_hours / total_work_hours * 100) if total_work_hours > 0 else 0

        # Соответствие расписанию
        workday_hours = sum(h for i, h in enumerate(hours) if days[i] in workdays)
        expected_hours = len(workdays) * hours_per_day
        schedule_compliance = (workday_hours / expected_hours * 100) if expected_hours > 0 else 0

        # Формируем текст метрик с новым форматированием времени
        total_hours = sum(hours)
        overtime = sum(max(0, h - hours_per_day) for i, h in enumerate(hours) if days[i] in workdays)
        if total_commits == 0:
            metrics_text = "Нет активности в выбранном месяце"
        else:
            metrics_text = (
                f"Общее время работы: {format_time(total_hours)}\n"
                f"Активные дни: {active_days}\n"
                f"Рабочие дни: {len(workdays)}\n"
                f"Отработано в рабочие дни: {format_time(workday_hours)}\n"
                f"Переработка: {format_time(overtime)}\n"
                f"Коммитов в час: {commits_per_hour_avg:.2f}\n"
                f"Пиковые часы активности: {peak_hours_text}\n"
                f"Ночные коммиты: {night_commits} ({night_commit_ratio:.2f}%)\n"
                f"Средний интервал между коммитами: {avg_commit_interval:.2f} минут\n"
                f"Мёртвое время: {dead_time_percent:.2f}%\n"
                f"Соответствие расписанию: {schedule_compliance:.2f}%"
            )

        month_days = days
        logging.debug(f"Completed processing for month {month}, year {year}")
        return metrics_text, days, hours, weekend_days, heatmap_data, month_days, daily_metrics

    except InvalidGitRepositoryError:
        logging.error(f"Invalid Git repository: {project_path}")
        return "Ошибка: Указанная папка не является Git-репозиторием", [], [], [], np.zeros((days_in_month, 8)), [], {}
    except Exception as e:
        logging.error(f"Error in update_opening_hours: {str(e)}")
        days_in_month = calendar.monthrange(year, month)[1]
        return f"Ошибка при анализе репозитория: {str(e)}", [], [], [], np.zeros((days_in_month, 8)), [], {}


def get_years(project_path):
    try:
        repo = git.Repo(project_path)
        commits = list(repo.iter_commits(max_count=10000))
        years = set(datetime.fromtimestamp(commit.committed_date).year for commit in commits)
        return sorted(years)
    except Exception:
        return [datetime.now().year]