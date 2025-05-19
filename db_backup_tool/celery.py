# db_backup_tool/celery.py
import os
from celery import Celery
from celery.signals import worker_ready

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'db_backup_tool.settings')

app = Celery('db_backup_tool')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Add scheduled tasks
app.conf.beat_schedule = {
    'check-scheduled-backups': {
        'task': 'backup_manager.tasks.run_scheduled_backups',
        'schedule': 60.0,  # Check every minute
        'options': {'expires': 50}  # Task expires after 50 seconds to prevent overlap
    },
}

# Add rate limiting to reduce task duplication
app.conf.task_default_rate_limit = '1/m'  # Limit task to once per minute

# Set task serialization format
app.conf.task_serializer = 'json'
app.conf.result_serializer = 'json'
app.conf.accept_content = ['json']

# Enable dedicated task logging
app.conf.worker_hijack_root_logger = False

# Add optimization for single worker
app.conf.worker_prefetch_multiplier = 1
app.conf.task_acks_late = True

@worker_ready.connect
def at_start(sender, **kwargs):
    """Print worker status when starting"""
    print("DEBT Worker Started. Waiting for backup tasks...")