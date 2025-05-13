# db_backup_tool/celery.py
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'db_backup_tool.settings')

app = Celery('db_backup_tool')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Dodaj zaplanowane zadania
app.conf.beat_schedule = {
    'check-scheduled-backups': {
        'task': 'backup_manager.tasks.run_scheduled_backups',
        'schedule': 60.0,  # Co minutę sprawdzaj
    },
}