# DEBT - Database Easy Backup Tool

A comprehensive web-based tool for backing up MySQL/MariaDB and PostgreSQL databases, designed to work seamlessly with Debian-based systems.

![DEBT](https://github.com/user-attachments/assets/5e6b0f0b-31b9-46c5-8277-16c564f619f9)

## Features

- **Multiple Database Support**: MySQL/MariaDB and PostgreSQL backup capabilities
- **Connection Options**: Direct TCP/IP connections and SSH tunneling
- **Scheduled Backups**: Set up daily, weekly, or monthly backup schedules
- **Storage Options**: Local storage, FTP, SFTP, and Google Drive integration
- **Backup Management**: Retention policies, manual execution, and restoration
- **Email Notifications**: Get alerts on backup success/failure
- **Detailed History**: Track all backup operations with comprehensive logs
- **Dark UI**: Clean, modern interface for easy management

## Requirements

- Debian-based system (Ubuntu, Debian)
- Python 3.9+
- MySQL/MariaDB client tools
- PostgreSQL client tools (optional, for PostgreSQL backup support)
- Redis (for Celery task queue)

## Quick Installation

```bash
wget -q https://ashes.pl/static/ashes/img/install.sh && chmod +x install.sh && sudo ./install.sh
```

or just download install.sh script and execute it as root or with sudo.

The installer will:
1. Install required system dependencies
2. Create a virtual environment
3. Install Python packages
4. Configure environment variables
5. Set up database
6. Create a user account
7. Configure systemd services for Celery workers
8. Guide you through final setup steps

## Manual Installation

If you prefer manual installation or are using a non-Debian system:

1. Install required system packages:
   ```bash
   # On Debian/Ubuntu
   apt-get install python3 python3-venv python3-pip redis-server default-mysql-client postgresql-client build-essential libssl-dev libffi-dev python3-dev postgresql-client libpq-dev pkg-config default-libmysqlclient-dev
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Configure your environment:
   ```bash
   cp .env.example .env
   # Edit .env with appropriate values
   ```

4. Run database migrations:
   ```bash
   python manage.py migrate
   ```

5. Create an admin user:
   ```bash
   python manage.py create_user admin --email=your@email.com --admin
   ```

6. Start the application:
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```

7. For production, configure Celery workers and a proper web server (Nginx/Apache)

## Configuration

All sensitive settings are stored in the `.env` file:

- `SECRET_KEY`: Django secret key
- `DEBUG`: Set to False in production
- `ALLOWED_HOSTS`: Comma-separated list of allowed hostnames
- `DATABASE_*`: App database configuration
- `BACKUP_DIR`: Where backups will be stored
- `CELERY_*`: Celery worker configuration
- `EMAIL_*`: Email settings for notifications

## Production Deployment

For production environments, you should:

1. Use a proper web server (Nginx/Apache) with Gunicorn/uWSGI
2. Set up systemd services for Celery workers and beat scheduler
3. Configure proper SSL/TLS encryption
4. Set up a database other than SQLite for better performance

See the included `install.sh` script for examples of systemd service configuration.

## Non-Debian Systems

For non-Debian systems, you will need to:
- Install equivalent system dependencies according to your package manager
- Manually configure Celery and Redis
- Set up appropriate web server configurations

# Configuration Changes and Celery Restart Guide

## Important Notice

When you make changes to configuration files (`.env` or `settings.py`), those changes are **not automatically picked up** by running Celery workers. Celery workers load the configuration only once at startup.

## When to Restart Celery

Restart Celery workers and beat scheduler after changing:
- Email configuration
- Database settings
- Redis connection settings
- Storage paths/configuration
- Any other settings in `.env` or `settings.py`

## Restart Commands

```bash
# If running as systemd services (recommended)
sudo systemctl restart celery-worker.service
sudo systemctl restart celery-beat.service

# If running manually
# First, find and stop existing processes
ps aux | grep celery
kill [PID]  # replace [PID] with actual process ID

# Then start them again
cd /path/to/db_backup_tool
/path/to/venv/bin/celery -A db_backup_tool worker -l info
/path/to/venv/bin/celery -A db_backup_tool beat -l info
```

## Verification

After restarting services, check logs to confirm the new configuration has been loaded:

```bash
sudo journalctl -u celery-worker -n 50
sudo journalctl -u celery-beat -n 50
```

Or check application logs in `/var/www/backup_app/db_backup_tool/logs/debug.log`

## Common Issues

1. **Email not sent with correct sender**: Celery still using old email configuration
2. **Tasks not running at expected times**: Beat scheduler needs to be restarted
3. **Changes to backup storage not applied**: Worker needs to be restarted

Always restart both services to ensure consistent behavior across the application.

## License

[MIT License](LICENSE)