import os
import git
from datetime import datetime, timedelta
from WorkSchedule import get_schedule, get_hours_per_day, get_work_hours
import calendar
import numpy as np

def update_opening_hours(project_path, month, year, max_count=10000):
    try:
        repo = git.Repo(project_path)
        commits = list(repo.iter_commits(max_count=max_count))
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
        dead_time_periods = []
        commits_per_hour = []
        hour_counts = [0] * 24
        heatmap_data = np.zeros((7, 24))  # Дни недели (0-6) x часы (0-23)

        # Собираем коммиты по дням
        for commit in commits:
            commit_time = datetime.fromtimestamp(commit.committed_date)
            if commit_time.year == year and commit_time.month == month:
                day = commit_time.day
                day_commits[day].append(commit_time)
                total_commits += 1
                hour = commit_time.hour
                weekday = commit_time.weekday()
                hour_counts[hour] += 1
                heatmap_data[weekday, hour] += 1
                if 23 <= hour or hour < 6:
                    night_commits += 1

        # Подсчёт метрик
        for day in days:
            if day not in schedule or not schedule[day]:
                weekend_days.append(day)
            commits = day_commits[day]
            if commits:
                active_days += 1
                commits.sort()
                start_time = commits[0]
                end_time = commits[-1]
                day_hours = (end_time - start_time).total_seconds() / 3600
                hours[day - 1] = day_hours

                # Средний интервал между коммитами
                if len(commits) > 1:
                    intervals = [(commits[i+1] - commits[i]).total_seconds() / 60 for i in range(len(commits)-1)]
                    commit_intervals.extend(intervals)

                # Мёртвое время (в рабочие часы)
                if day not in weekend_days:
                    work_start_time = datetime(year, month, day, work_start.hour, work_start.minute)
                    work_end_time = datetime(year, month, day, work_end.hour, work_end.minute)
                    current_time = work_start_time
                    while current_time < work_end_time and current_time < end_time:
                        next_commit = next((c for c in commits if c >= current_time + timedelta(hours=2)), None)
                        if not next_commit or next_commit > current_time + timedelta(hours=2):
                            dead_time_periods.append((current_time, min(current_time + timedelta(hours=2), work_end_time)))
                        current_time += timedelta(hours=2)
                        if current_time >= end_time:
                            break

        # Коммиты в час
        active_hours = sum(1 for count in hour_counts if count > 0)
        commits_per_hour_avg = total_commits / active_hours if active_hours > 0 else 0

        # Пиковые часы активности
        peak_hours = []
        for i in range(0, 24, 2):
            count = sum(hour_counts[i:i+2])
            if count > 0:
                peak_hours.append((f"{i:02d}:00–{i+2:02d}:00", count))
        peak_hours.sort(key=lambda x: x[1], reverse=True)
        peak_hours_text = peak_hours[0][0] if peak_hours else "Нет данных"

        # Ночные коммиты
        night_commit_ratio = (night_commits / total_commits * 100) if total_commits > 0 else 0

        # Средний интервал между коммитами
        avg_commit_interval = sum(commit_intervals) / len(commit_intervals) if commit_intervals else 0

        # Мёртвое время
        workdays = [day for day in days if day not in weekend_days]
        total_work_hours = sum((work_end.hour - work_start.hour) for day in workdays)
        dead_time_hours = sum((end - start).total_seconds() / 3600 for start, end in dead_time_periods)
        dead_time_percent = (dead_time_hours / total_work_hours * 100) if total_work_hours > 0 else 0

        # Соответствие расписанию
        workday_hours = sum(h for i, h in enumerate(hours) if days[i] in workdays)
        expected_hours = len(workdays) * hours_per_day
        schedule_compliance = (workday_hours / expected_hours * 100) if expected_hours > 0 else 0

        # Формируем текст метрик
        total_hours = sum(hours)
        if total_commits == 0:
            metrics_text = "Нет активности в выбранном месяце"
        else:
            metrics_text = (
                f"Общее время работы: {total_hours:.2f} часов\n"
                f"Активные дни: {active_days}\n"
                f"Рабочие дни: {len(workdays)}\n"
                f"Отработано в рабочие дни: {workday_hours:.2f} часов\n"
                f"Переработка: {sum(max(0, h - hours_per_day) for i, h in enumerate(hours) if days[i] in workdays):.2f} часов\n"
                f"Коммитов в час: {commits_per_hour_avg:.2f}\n"
                f"Пиковые часы активности: {peak_hours_text}\n"
                f"Ночные коммиты: {night_commits} ({night_commit_ratio:.2f}%)\n"
                f"Средний интервал между коммитами: {avg_commit_interval:.2f} минут\n"
                f"Мёртвое время: {dead_time_percent:.2f}%\n"
                f"Соответствие расписанию: {schedule_compliance:.2f}%"
            )

        return metrics_text, days, hours, weekend_days, heatmap_data

    except Exception as e:
        return f"Ошибка при анализе репозитория: {str(e)}", [], [], [], np.zeros((7, 24))

def get_years(project_path):
    try:
        repo = git.Repo(project_path)
        commits = list(repo.iter_commits(max_count=10000))
        years = set(datetime.fromtimestamp(commit.committed_date).year for commit in commits)
        return sorted(years)
    except:
        return [datetime.now().year]