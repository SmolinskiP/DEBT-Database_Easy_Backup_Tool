#!/bin/bash
cd /var/www/backup_app/db_backup_tool
source /var/www/backup_app/venv/bin/activate
/var/www/backup_app/venv/bin/python manage.py runserver 0.0.0.0:8000
