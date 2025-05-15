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
- **User Authentication**: Multi-user support with permissions
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
# Clone the repository
git clone https://github.com/SmolinskiP/DEBT-Database_Easy_Backup_Tool.git
cd DEBT

# Run the installer script with root privileges
sudo ./install.sh
```

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

## License

[MIT License](LICENSE)