import os
import git
from datetime import datetime
from WorkSchedule import get_schedule, get_hours_per_day
import calendar


def update_opening_hours(project_path, month, year, max_count=10000):
    try:
        repo = git.Repo(project_path)
        commits = list(repo.iter_commits(max_count=max_count))
        hours_per_day = get_hours_per_day()
        schedule = get_schedule(year, month)
        days_in_month = calendar.monthrange(year, month)[1]
        days = list(range(1, days_in_month + 1))
        hours = [0] * days_in_month
        weekend_days = []

        # Собираем статистику по дням
        day_hours = {}
        for commit in commits:
            commit_time = datetime.fromtimestamp(commit.committed_date)
            if commit_time.year == year and commit_time.month == month:
                day = commit_time.day
                day_hours[day] = day_hours.get(day, 0) + 1  # 1 минута за коммит

        # Заполняем часы для дней с коммитами
        for day in day_hours:
            hours[day - 1] = day_hours[day] / 60  # Переводим минуты в часы

        # Определяем выходные дни
        for day in range(1, days_in_month + 1):
            if day not in schedule or not schedule[day]:
                weekend_days.append(day)

        # Формируем текст метрик
        total_hours = sum(hours)
        workdays = [day for day in days if day not in weekend_days]
        workday_hours = sum(h for i, h in enumerate(hours) if days[i] in workdays)
        overtime_hours = sum(max(0, h - hours_per_day) for i, h in enumerate(hours) if days[i] in workdays)

        metrics_text = (
            f"Общее время работы: {total_hours:.2f} часов\n"
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