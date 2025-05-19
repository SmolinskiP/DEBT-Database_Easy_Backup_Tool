#!/bin/bash
set -e
# Configuration variables
APP_PATH="/var/www/backup_app"
APP_USER="$(whoami)"
APP_GROUP="www-data"
VENV_PATH="$APP_PATH/venv"
REPO_URL="https://github.com/SmolinskiP/DEBT-Database_Easy_Backup_Tool.git"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== DEBT - Database Easy Backup Tool - Installer ===${NC}"
echo -e "Installation path: ${YELLOW}$APP_PATH${NC}"
echo -e "User: ${YELLOW}$APP_USER${NC}"

# Check for root privileges
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Please run this script with root privileges (sudo)${NC}"
  exit 1
fi

# Install system dependencies
echo -e "\n${GREEN}Installing system dependencies...${NC}"
apt-get update
apt-get install -y python3 python3-venv python3-pip redis-server default-mysql-client \
                   build-essential libssl-dev libffi-dev python3-dev git postgresql-client libpq-dev \
                   postgresql-client libpq-dev pkg-config default-libmysqlclient-dev

# Create application directory
echo -e "\n${GREEN}Creating application directories...${NC}"
mkdir -p $APP_PATH
chown $APP_USER:$APP_GROUP $APP_PATH

# Clone repository or copy files
if [ -d "$APP_PATH/db_backup_tool" ]; then
  echo -e "${YELLOW}Application directory already exists. Skipping clone.${NC}"
else
  echo -e "\n${GREEN}Cloning repository...${NC}"
  cd $APP_PATH
  if [ -n "$REPO_URL" ]; then
    su -c "git clone $REPO_URL db_backup_tool" $APP_USER
  else
    # Add alternative logic for copying files here
    echo -e "${RED}No repository URL provided. Please copy the files manually to $APP_PATH/db_backup_tool${NC}"
    mkdir -p $APP_PATH/db_backup_tool
    chown $APP_USER:$APP_GROUP $APP_PATH/db_backup_tool
  fi
fi

mkdir -p $APP_PATH/db_backup_tool/logs
touch $APP_PATH/db_backup_tool/logs/debug.log
chmod 777 $APP_PATH/db_backup_tool/logs/debug.log

# Setup virtual environment
echo -e "\n${GREEN}Creating virtual environment...${NC}"
su -c "python3 -m venv $VENV_PATH" $APP_USER

# Install Python dependencies
echo -e "\n${GREEN}Installing Python dependencies...${NC}"
su -c "$VENV_PATH/bin/pip install -U pip" $APP_USER
su -c "$VENV_PATH/bin/pip install -r $APP_PATH/db_backup_tool/requirements.txt" $APP_USER

# Create .env file
echo -e "\n${GREEN}Configuring environment variables...${NC}"
if [ ! -f "$APP_PATH/db_backup_tool/.env" ]; then
  SECRET_KEY=$(openssl rand -base64 32)
  
  cat > $APP_PATH/db_backup_tool/.env << EOF
SECRET_KEY=$SECRET_KEY
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,*
DATABASE_ENGINE=django.db.backends.sqlite3
DATABASE_NAME=$APP_PATH/db_backup_tool/db.sqlite3
BACKUP_DIR=$APP_PATH/backups
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_TIMEZONE=Europe/Warsaw
EMAIL_HOST=server.server.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your_email@example.com
EMAIL_HOST_PASSWORD=your_email_password
DEFAULT_FROM_EMAIL=DEBT <your_email@example.com>
EOF

  chown $APP_USER:$APP_GROUP $APP_PATH/db_backup_tool/.env
  echo -e "${GREEN}.env file created${NC}"
else
  echo -e "${YELLOW}.env file already exists. Keeping current configuration.${NC}"
fi

# Create backup directory
echo -e "\n${GREEN}Creating backup directory...${NC}"
mkdir -p $APP_PATH/backups
chown $APP_USER:$APP_GROUP $APP_PATH/backups
chmod 755 $APP_PATH/backups

# Run migrations
echo -e "\n${GREEN}Running Django migrations...${NC}"
cd $APP_PATH/db_backup_tool
su -c "$VENV_PATH/bin/python manage.py migrate" $APP_USER

# Collect static files
echo -e "\n${GREEN}Collecting static files...${NC}"
su -c "$VENV_PATH/bin/python manage.py collectstatic --noinput" $APP_USER

# Create system user if running as service
echo -e "\n${GREEN}Creating application user...${NC}"
DJANGO_SUPERUSER_PASSWORD=VeryStrongPassword su -c "$VENV_PATH/bin/python manage.py createsuperuser --username=admin --email=admin@example.com --noinput" $APP_USER
echo -e "${GREEN}Admin user created successfully with username 'admin' and password 'VeryStrongPassword'${NC}"

# Create systemd service files
echo -e "\n${GREEN}Configuring system services...${NC}"

# Celery Worker Service
cat > /etc/systemd/system/celery-worker.service << EOF
[Unit]
Description=Celery Worker for DB Backup Tool
After=network.target

[Service]
User=$APP_USER
Group=$APP_GROUP
WorkingDirectory=$APP_PATH/db_backup_tool
ExecStart=$VENV_PATH/bin/celery -A db_backup_tool worker -l info
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# Celery Beat Service
cat > /etc/systemd/system/celery-beat.service << EOF
[Unit]
Description=Celery Beat for DB Backup Tool
After=network.target

[Service]
User=$APP_USER
Group=$APP_GROUP
WorkingDirectory=$APP_PATH/db_backup_tool
ExecStart=$VENV_PATH/bin/celery -A db_backup_tool beat -l info
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# Enable and start services
systemctl daemon-reload
systemctl enable celery-worker.service
systemctl enable celery-beat.service
systemctl start celery-worker.service
systemctl start celery-beat.service

echo -e "\n${GREEN}Celery services enabled and started${NC}"

# Web server configuration hint
echo -e "\n${YELLOW}=== NEXT STEPS ===${NC}"
echo -e "1. Configure a web server (Nginx/Apache) to serve the application"
echo -e "2. Example Nginx configuration:"
echo -e "${GREEN}
server {
    listen 80;
    server_name backup.example.com;

    location /static/ {
        alias $APP_PATH/db_backup_tool/static/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
${NC}"

echo -e "\n${GREEN}Creating application startup script...${NC}"

cat > $APP_PATH/start_app.sh << EOF
#!/bin/bash
cd $APP_PATH/db_backup_tool
$VENV_PATH/bin/python manage.py runserver 0.0.0.0:8000
EOF

SERVER_IP=$(hostname -I | awk '{print $1}')

# Set execution permissions
chmod +x $APP_PATH/start_app.sh
chown $APP_USER:$APP_GROUP $APP_PATH/start_app.sh

echo -e "\n${GREEN}Startup script created!${NC}"
echo -e "${YELLOW}WARNING: Django runserver is NOT recommended for production use. Use only for development purposes!${NC}"

echo -e "\n${YELLOW}=== IMPORTANT INFORMATION ===${NC}"
echo -e "To run the application, execute: ${YELLOW}sudo $APP_PATH/start_app.sh${NC}"
echo -e "Then open a web browser and go to: ${YELLOW}http://$SERVER_IP:8000${NC}"
echo -e "${GREEN}Admin user credentials:${NC}"
echo -e "Username: ${YELLOW}admin${NC}"
echo -e "Password: ${YELLOW}VeryStrongPassword${NC}"
echo -e "\n${RED}NOTE: This script must be run with sudo privileges!${NC}"