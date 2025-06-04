import os
import git
from git.exc import GitCommandError, InvalidGitRepositoryError
from datetime import datetime, timedelta
from .WorkSchedule import get_schedule, get_hours_per_day, get_work_hours
import calendar
import numpy as np
import logging
from database import get_user_id_by_email, save_work_time_metrics, save_hourly_activity, save_commit_temporal_data

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

def update_opening_hours(project_path, month, year, max_count=10000, author=None):
    try:
        repo = git.Repo(project_path)
        try:
            commits = list(repo.iter_commits(max_count=max_count, author=author))
        except GitCommandError as e:
            logging.error(f"Git command error while fetching commits: {str(e)}")
            raise Exception(f"Ошибка Git при получении коммитов: {str(e)}")

        hours_per_day = get_hours_per_day()
        work_start, work_end, lunch_start, lunch_end = get_work_hours()
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
        hour_counts = [0] * 24
        heatmap_data = np.zeros((days_in_month, 8))
        
        # Добавляем отслеживание почасовой активности для каждого дня
        hourly_activity = {day: [0] * 24 for day in days}

        daily_metrics = {day: {
            'work_period': None,
            'total_time': 0,
            'dead_periods': [],
            'commits': 0,
            'night_commits': 0,
            'dead_time': 0,
            'lunch_period': (lunch_start, lunch_end),
            'hourly_activity': [0] * 24  # Добавляем почасовую активность в метрики
        } for day in days}

        logging.debug(f"Processing commits for month {month}, year {year}, author {author or 'all'}")
        for commit in commits:
            commit_time = datetime.fromtimestamp(commit.committed_date)
            if commit_time.year == year and commit_time.month == month:
                day = commit_time.day
                hour = commit_time.hour
                day_commits[day].append(commit_time)
                total_commits += 1
                hour_counts[hour] += 1
                hourly_activity[day][hour] += 1  # Увеличиваем счетчик для конкретного часа
                daily_metrics[day]['hourly_activity'][hour] += 1  # Обновляем почасовую активность в метриках
                interval_index = hour // 3
                heatmap_data[day - 1, interval_index] += 1
                if 23 <= hour or hour < 6:
                    night_commits += 1
                    daily_metrics[day]['night_commits'] += 1

        for day in days:
            if day not in schedule or not schedule[day]:
                weekend_days.append(day)
            commits = day_commits[day]
            daily_metrics[day]['commits'] = len(commits)
            if commits:
                active_days += 1
                commits.sort()
                start_time = commits[0]
                end_time = commits[-1]
                day_hours = (end_time - start_time).total_seconds() / 3600
                hours[day - 1] = day_hours
                daily_metrics[day]['work_period'] = (start_time, end_time)
                daily_metrics[day]['total_time'] = day_hours

                if len(commits) > 1:
                    intervals = [(commits[i + 1] - commits[i]).total_seconds() / 60 for i in range(len(commits) - 1)]
                    commit_intervals.extend(intervals)

                if day not in weekend_days:
                    work_start_time = datetime(year, month, day, work_start.hour, work_start.minute)
                    work_end_time = datetime(year, month, day, work_end.hour, work_end.minute)
                    lunch_start_time = datetime(year, month, day, lunch_start.hour, lunch_start.minute)
                    lunch_end_time = datetime(year, month, day, lunch_end.hour, lunch_end.minute)
                    
                    current_time = work_start_time
                    commit_index = 0
                    
                    while current_time < work_end_time:
                        # Пропускаем время обеда
                        if current_time >= lunch_start_time and current_time < lunch_end_time:
                            current_time = lunch_end_time
                            continue
                            
                        while commit_index < len(commits) and commits[commit_index] < current_time:
                            commit_index += 1
                            
                        if commit_index >= len(commits):
                            if current_time < work_end_time:
                                # Не учитываем обеденное время как мертвое время
                                if current_time < lunch_start_time and work_end_time > lunch_end_time:
                                    if lunch_start_time > current_time:
                                        daily_metrics[day]['dead_periods'].append((current_time, lunch_start_time))
                                    if work_end_time > lunch_end_time:
                                        daily_metrics[day]['dead_periods'].append((lunch_end_time, work_end_time))
                                else:
                                    # Если текущее время после обеда или до него
                                    end_time = work_end_time
                                    if current_time < lunch_start_time and work_end_time > lunch_start_time:
                                        end_time = lunch_start_time
                                    elif current_time >= lunch_end_time:
                                        end_time = work_end_time
                                    daily_metrics[day]['dead_periods'].append((current_time, end_time))
                            break
                            
                        next_commit = commits[commit_index]
                        # Проверяем, не попадает ли следующий коммит в обеденное время
                        if next_commit >= lunch_start_time and next_commit < lunch_end_time:
                            if current_time < lunch_start_time:
                                daily_metrics[day]['dead_periods'].append((current_time, lunch_start_time))
                            current_time = lunch_end_time
                            continue
                            
                        if (next_commit - current_time).total_seconds() / 3600 >= 2:
                            dead_end = min(current_time + timedelta(hours=2), work_end_time)
                            if next_commit and next_commit < dead_end:
                                dead_end = next_commit
                            # Проверяем, не пересекается ли мертвое время с обедом
                            if dead_end > lunch_start_time and current_time < lunch_end_time:
                                if current_time < lunch_start_time:
                                    daily_metrics[day]['dead_periods'].append((current_time, lunch_start_time))
                                current_time = lunch_end_time
                            else:
                                daily_metrics[day]['dead_periods'].append((current_time, dead_end))
                                current_time = dead_end
                        else:
                            current_time = next_commit
                            commit_index += 1

        for day in days:
            if day not in weekend_days:
                # Вычисляем общее рабочее время с учетом обеда
                total_work_minutes = ((work_end.hour - work_start.hour) * 60 + 
                                   (work_end.minute - work_start.minute))
                lunch_minutes = ((lunch_end.hour - lunch_start.hour) * 60 + 
                               (lunch_end.minute - lunch_start.minute))
                total_work_hours = (total_work_minutes - lunch_minutes) / 60
                
                day_dead_time = sum(
                    (end - start).total_seconds() / 3600 for start, end in daily_metrics[day]['dead_periods'])
                daily_metrics[day]['dead_time'] = (
                    day_dead_time / total_work_hours * 100) if total_work_hours > 0 else 0

        active_hours = sum(1 for count in hour_counts if count > 0)
        commits_per_hour_avg = total_commits / active_hours if active_hours > 0 else 0

        peak_hours = []
        for i in range(0, 24, 2):
            count = sum(hour_counts[i:i + 2])
            if count > 0:
                peak_hours.append((f"{i:02d}:00–{i + 2:02d}:00", count))
        peak_hours.sort(key=lambda x: x[1], reverse=True)
        peak_hours_text = peak_hours[0][0] if peak_hours else "Нет данных"

        night_commit_ratio = (night_commits / total_commits * 100) if total_commits > 0 else 0

        avg_commit_interval = sum(commit_intervals) / len(commit_intervals) if commit_intervals else 0

        workdays = [day for day in days if day not in weekend_days]
        # Вычисляем общее рабочее время с учетом обеда для всех рабочих дней
        total_work_minutes = ((work_end.hour - work_start.hour) * 60 + 
                           (work_end.minute - work_start.minute))
        lunch_minutes = ((lunch_end.hour - lunch_start.hour) * 60 + 
                       (lunch_end.minute - lunch_start.minute))
        total_work_hours = len(workdays) * (total_work_minutes - lunch_minutes) / 60
        
        dead_time_hours = sum(
            sum((end - start).total_seconds() / 3600 for start, end in daily_metrics[day]['dead_periods']) for day in
            workdays)
        dead_time_percent = (dead_time_hours / total_work_hours * 100) if total_work_hours > 0 else 0

        workday_hours = sum(h for i, h in enumerate(hours) if days[i] in workdays)
        expected_hours = len(workdays) * hours_per_day
        schedule_compliance = (workday_hours / expected_hours * 100) if expected_hours > 0 else 0

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
        logging.debug(f"Completed processing for month {month}, year {year}, author {author or 'all'}")

        # Сохранение метрик в базу данных, если указан автор
        if author:
            user_id = get_user_id_by_email(author)
            if user_id:
                # Сохранение почасовой активности и коммитов по дням
                for day_num in days:
                    current_date = datetime(year, month, day_num).date()
                    day_metric_data = daily_metrics.get(day_num, {})
                    
                    # Сохранение commit_metrics (количество и время)
                    commits_for_day = day_commits.get(day_num, [])
                    commit_times_for_db = [c.time() for c in commits_for_day] if commits_for_day else None
                    save_commit_temporal_data(user_id, current_date, len(commits_for_day), commit_times_for_db)

                    # Сохранение hourly_activity
                    hourly_data_for_day = hourly_activity.get(day_num, [0]*24)
                    for hour_idx, activity_count in enumerate(hourly_data_for_day):
                        # Предполагаем, что activity_level это просто commit_count для данного часа
                        save_hourly_activity(user_id, current_date, hour_idx, activity_count, activity_count) 

                for day_num, day_data_val in daily_metrics.items():
                    current_date_for_work = datetime(year, month, day_num).date()
                    ws, we = day_data_val.get('work_period', (None, None))
                    ls, le = day_data_val.get('lunch_period', (work_start, work_end)) # Используем общие, если нет дневных
                    
                    # Преобразуем datetime.datetime в datetime.time, если они не None
                    ws_time = ws.time() if ws else None
                    we_time = we.time() if we else None
                    ls_time = ls.time() if isinstance(ls, datetime) else ls # ls может быть уже time
                    le_time = le.time() if isinstance(le, datetime) else le # le может быть уже time
                    
                    total_w_h = day_data_val.get('total_time', 0)
                    # productive_hours - это total_time минус dead_time. Dead_time у нас в процентах.
                    dead_time_p = day_data_val.get('dead_time', 0)
                    prod_h = total_w_h * (1 - dead_time_p / 100.0) if total_w_h > 0 else 0

                    if ws_time and we_time: # Сохраняем только если был рабочий период
                        save_work_time_metrics(
                            user_id, current_date_for_work,
                            ws_time, we_time,
                            ls_time, le_time,
                            round(total_w_h, 2),
                            round(prod_h, 2),
                            round(dead_time_p, 2)
                        )
            else:
                logging.warning(f"User with email {author} not found. Metrics not saved.")

        return metrics_text, days, hours, weekend_days, heatmap_data, month_days, daily_metrics, hourly_activity, work_start, work_end, lunch_start, lunch_end

    except InvalidGitRepositoryError:
        logging.error(f"Invalid Git repository: {project_path}")
        empty_hourly = {day: [0] * 24 for day in range(1, days_in_month + 1)}
        return ("Ошибка: Указанная папка не является Git-репозиторием", [], [], [], 
                np.zeros((days_in_month, 8)), [], {}, empty_hourly, None, None, None, None)
    except Exception as e:
        logging.error(f"Error in update_opening_hours: {str(e)}")
        empty_hourly = {day: [0] * 24 for day in range(1, days_in_month + 1)}
        return (f"Ошибка при анализе репозитория: {str(e)}", [], [], [], 
                np.zeros((days_in_month, 8)), [], {}, empty_hourly, None, None, None, None)

def get_years(project_path):
    try:
        repo = git.Repo(project_path)
        commits = list(repo.iter_commits(max_count=10000))
        years = set(datetime.fromtimestamp(commit.committed_date).year for commit in commits)
        return sorted(years)
    except Exception:
        return [datetime.now().year]

def get_work_hours():
    work_hours_file = os.path.join(os.path.expanduser("~"), ".devmetrics_work_hours")
    try:
        if os.path.exists(work_hours_file):
            with open(work_hours_file, 'r') as f:
                work_hours = eval(f.read())
                start = datetime.strptime(work_hours['start'], "%H:%M")
                end = datetime.strptime(work_hours['end'], "%H:%M")
                lunch_start = datetime.strptime(work_hours.get('lunch_start', "13:00"), "%H:%M")
                lunch_end = datetime.strptime(work_hours.get('lunch_end', "14:00"), "%H:%M")
                return start, end, lunch_start, lunch_end
        return (datetime.strptime("09:00", "%H:%M"), 
                datetime.strptime("17:00", "%H:%M"),
                datetime.strptime("13:00", "%H:%M"),
                datetime.strptime("14:00", "%H:%M"))
    except:
        return (datetime.strptime("09:00", "%H:%M"), 
                datetime.strptime("17:00", "%H:%M"),
                datetime.strptime("13:00", "%H:%M"),
                datetime.strptime("14:00", "%H:%M"))
