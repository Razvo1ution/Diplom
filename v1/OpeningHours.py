import os
import git
from datetime import datetime
from WorkSchedule import get_schedule, get_hours_per_day
from ActivityTracker import ActivityTracker
import calendar

def update_opening_hours(project_path, month, year, lunch_file, max_count=10000):
    try:
        repo = git.Repo(project_path)
        commits = list(repo.iter_commits(max_count=max_count))
        hours_per_day = get_hours_per_day()
        schedule = get_schedule(year, month)
        days_in_month = calendar.monthrange(year, month)[1]
        days = list(range(1, days_in_month + 1))
        hours = [0] * days_in_month
        idle_hours = [0] * days_in_month
        weekend_days = []

        # Инициализируем трекер активности
        tracker = ActivityTracker(project_path, lunch_file)

        # Рассчитываем активное время и простой
        for day in days:
            if day in schedule and schedule[day]:
                active, idle = tracker.calculate_activity(year, month, day, schedule)
                hours[day - 1] = active
                idle_hours[day - 1] = idle
            if day not in schedule or not schedule[day]:
                weekend_days.append(day)

        # Учитываем коммиты из Git (1 коммит = 1 минута)
        for commit in commits:
            commit_time = datetime.fromtimestamp(commit.committed_date)
            if commit_time.year == year and commit_time.month == month:
                day = commit_time.day
                if day in schedule and schedule[day]:
                    hours[day - 1] += 1 / 60

        # Формируем текст метрик
        total_hours = sum(hours)
        total_idle = sum(idle_hours)
        workdays = [day for day in days if day not in weekend_days]
        workday_hours = sum(h for i, h in enumerate(hours) if days[i] in workdays)
        overtime_hours = sum(max(0, h - hours_per_day) for i, h in enumerate(hours) if days[i] in workdays)

        metrics_text = (
            f"Общее время работы: {total_hours:.2f} часов\n"
            f"Общий простой: {total_idle:.2f} часов\n"
            f"Рабочие дни: {len(workdays)}\n"
            f"Отработано в рабочие дни: {workday_hours:.2f} часов\n"
            f"Переработка: {overtime_hours:.2f} часов"
        )

        return metrics_text, days, hours, weekend_days
    except Exception as e:
        return f"Ошибка при анализе репозитория: {str(e)}", [], [], []

def get_years(project_path):
    try:
        repo = git.Repo(project_path)
        commits = list(repo.iter_commits(max_count=10000))
        years = set(datetime.fromtimestamp(commit.committed_date).year for commit in commits)
        return sorted(years)
    except:
        return [datetime.now().year]