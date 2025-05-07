import os
from datetime import datetime
from git import Repo
from git.exc import InvalidGitRepositoryError

def update_charts(project_path):
    if not project_path or not os.path.exists(project_path):
        return 0, []

    if not os.path.exists(os.path.join(project_path, '.git')):
        return 0, []

    try:
        repo = Repo(project_path)
        commits = list(repo.iter_commits(max_count=100))
        weeks = 4
        commits_per_week = [0] * weeks
        today = datetime.now()
        for commit in commits:
            commit_time = datetime.fromtimestamp(commit.committed_date)
            weeks_ago = (today - commit_time).days // 7
            if weeks_ago < weeks:
                commits_per_week[weeks_ago] += 1

        return weeks, commits_per_week

    except InvalidGitRepositoryError:
        return 0, []
    except Exception as e:
        return 0, []