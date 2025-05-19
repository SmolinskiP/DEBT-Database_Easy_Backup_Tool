from django.db import models
from django.utils import timezone
from django.conf import settings
import datetime
import os

def file_log(message):
    """Log message to a file in logs directory"""
    try:
        log_dir = os.path.join(settings.BASE_DIR, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'debug.log')

        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_file, 'a') as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        try:
            error_file = "/tmp/debt_backup_error.log"
            with open(error_file, 'a') as f:
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"[{timestamp}] ERROR LOGGING: {str(e)}, Original message: {message}\n")
        except:
            pass

class DatabaseServer(models.Model):
    CONNECTION_TYPES = (
        ('direct', 'MariaDB/MySQL (TCP/IP)'),
        ('ssh', 'MariaDB/MySQL (SSH Tunnel)'),
        ('direct_postgresql', 'PostgreSQL (TCP/IP)'),
        ('ssh_postgresql', 'PostgreSQL (SSH Tunnel)'),
    )
    
    name = models.CharField(max_length=100)
    connection_type = models.CharField(max_length=20, choices=CONNECTION_TYPES)
    hostname = models.CharField(max_length=255)
    port = models.IntegerField(default=0)
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=255)
    database_name = models.CharField(max_length=100, blank=True, null=True,
                                    help_text="Specific database to backup. Leave empty for all databases.")
    
    # SSH tunneling data
    ssh_hostname = models.CharField(max_length=255, blank=True, null=True)
    ssh_port = models.IntegerField(default=22, blank=True, null=True)
    ssh_username = models.CharField(max_length=100, blank=True, null=True)
    ssh_password = models.CharField(max_length=255, blank=True, null=True)
    ssh_key_file = models.FileField(upload_to='ssh_keys/', blank=True, null=True)
    
    # Server status
    last_status = models.BooleanField(default=False)
    last_status_check = models.DateTimeField(null=True, blank=True)
    last_status_message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_connection_type_display()})"

    def get_default_port(self):
        """Return default port based on connection type"""
        if 'mysql' in self.connection_type:
            return 3306
        elif 'postgresql' in self.connection_type:
            return 5432
        return 0
        
    def save(self, *args, **kwargs):
        # Set default port if not provided
        if not self.port:
            self.port = self.get_default_port()
        super().save(*args, **kwargs)

class BackupTask(models.Model):
    FREQUENCY_CHOICES = (
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('custom', 'Custom'),
    )
    
    DAY_OF_WEEK_CHOICES = (
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    )
    STORAGE_CHOICES = (
        ('local', 'Local Storage'),
        ('ftp', 'FTP Server'),
        ('sftp', 'SFTP Server'),
        ('gdrive', 'Google Drive'),
    )
    
    name = models.CharField(max_length=100)
    server = models.ForeignKey('DatabaseServer', on_delete=models.CASCADE, related_name='backup_tasks')
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES)
    time = models.TimeField(help_text="Execution time (HH:MM)")
    
    day_of_week = models.IntegerField(choices=DAY_OF_WEEK_CHOICES, null=True, blank=True)
    day_of_month = models.IntegerField(null=True, blank=True, 
                                     help_text="Day of month (1-31)")
    enabled = models.BooleanField(default=True)
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)
    
    retain_count = models.IntegerField(default=10, help_text="Number of recent backups to keep")
    email_notification = models.BooleanField(default=False)
    email_address = models.EmailField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    storage_config = models.ForeignKey('StorageConfig', on_delete=models.SET_NULL, null=True, blank=True)
    storage_type = models.CharField(max_length=10, choices=STORAGE_CHOICES, default='local')

    remote_hostname = models.CharField(max_length=255, blank=True, null=True)
    remote_port = models.IntegerField(blank=True, null=True)
    remote_username = models.CharField(max_length=100, blank=True, null=True)
    remote_password = models.CharField(max_length=255, blank=True, null=True)
    remote_path = models.CharField(max_length=255, blank=True, null=True, 
                                   help_text="Path on remote server where backups will be stored")
    remote_key_file = models.FileField(upload_to='remote_keys/', blank=True, null=True)

    gdrive_folder_id = models.CharField(max_length=255, blank=True, null=True,
                                   help_text="Google Drive folder ID (optional)")
    gdrive_credentials_file = models.FileField(upload_to='gdrive_creds/', blank=True, null=True,
                                         help_text="JSON credentials file")

    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()} - {self.server.name})"
    
    def save(self, *args, **kwargs):
        # Obliczanie następnego uruchomienia
        self._calculate_next_run()
        
        # Synchronizacja danych storage_config z polami remote_*
        if self.storage_config:
            self.storage_type = self.storage_config.storage_type
            self.remote_hostname = self.storage_config.hostname
            self.remote_port = self.storage_config.port
            self.remote_username = self.storage_config.username
            if self.storage_config.password and not self.remote_password:  # Nie nadpisuj hasła jeśli już jest
                self.remote_password = self.storage_config.password
            self.remote_path = self.storage_config.path or self.remote_path
            
        super().save(*args, **kwargs)
    
    def _calculate_next_run(self):
        file_log("DEBUG: _calculate_next_run CALLED")
        now_utc = timezone.now()
        # Convert to local time
        now_local = timezone.localtime(now_utc)
        
        # Create task time in local timezone
        local_date = now_local.date()
        local_task_time = timezone.make_aware(
            datetime.datetime.combine(local_date, self.time),
            timezone.get_current_timezone()
        )

        if self.frequency == 'daily':
            file_log(f"DEBUG: Comparing times (now_local) - {now_local}")
            file_log(f"DEBUG: Comparing times (task_time) - {local_task_time}")
            # Both times are in local timezone, comparison is correct
            if local_task_time <= now_local:
                self.next_run = local_task_time + datetime.timedelta(days=1)
            else:
                self.next_run = local_task_time

        elif self.frequency == 'weekly':
            days_ahead = self.day_of_week - now_local.weekday()
            if days_ahead <= 0 or (days_ahead == 0 and task_time <= now):
                days_ahead += 7
                
            next_date = now_local.date() + datetime.timedelta(days=days_ahead)
            self.next_run = timezone.make_aware(
                datetime.datetime.combine(next_date, self.time)
            )
            
        elif self.frequency == 'monthly':
            month = now_local.month
            year = now_local.year
            
            while True:
                try:
                    next_date = datetime.date(year, month, self.day_of_month)
                    next_datetime = timezone.make_aware(
                        datetime.datetime.combine(next_date, self.time)
                    )
                    
                    if next_datetime > now_local:
                        self.next_run = next_datetime
                        break
                        
                except ValueError:
                    pass
                    
                month += 1
                if month > 12:
                    month = 1
                    year += 1

class BackupHistory(models.Model):
    STATUS_CHOICES = (
        ('success', 'Success'),
        ('error', 'Error'),
        ('pending', 'In progress'),
    )
    
    server = models.ForeignKey('DatabaseServer', on_delete=models.CASCADE)
    task = models.ForeignKey('BackupTask', on_delete=models.SET_NULL, null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    file_path = models.CharField(max_length=255, blank=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    description = models.TextField(blank=True, help_text="Operation description or additional information")
    
    def __str__(self):
        return f"Backup {self.server.name} ({self.started_at.strftime('%Y-%m-%d %H:%M')})"

    def get_filename(self):
        if self.file_path:
            return os.path.basename(self.file_path)
        return None
    
    def is_restorable(self):
        return self.status == 'success' and self.file_path and os.path.exists(self.file_path)

    def has_file(self):
        return bool(self.file_path and os.path.exists(self.file_path))

class StorageConfig(models.Model):
    """Model for storage configuration"""
    STORAGE_CHOICES = (
        ('local', 'Local Storage'),
        ('ftp', 'FTP Server'),
        ('sftp', 'SFTP Server'),
        ('gdrive', 'Google Drive'),
    )
    
    name = models.CharField(max_length=100)
    storage_type = models.CharField(max_length=10, choices=STORAGE_CHOICES, default='local')
    is_default = models.BooleanField(default=False)
    
    # FTP/SFTP settings
    hostname = models.CharField(max_length=255, blank=True, null=True)
    port = models.IntegerField(blank=True, null=True)
    username = models.CharField(max_length=100, blank=True, null=True)
    password = models.CharField(max_length=255, blank=True, null=True)
    path = models.CharField(max_length=255, blank=True, null=True, 
                           help_text="Path on remote server where backups will be stored")
    key_file = models.FileField(upload_to='storage_keys/', blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    gdrive_folder_id = models.CharField(max_length=255, blank=True, null=True,
                                   help_text="Google Drive folder ID (optional)")
    gdrive_credentials_file = models.FileField(upload_to='gdrive_creds/', blank=True, null=True,
                                         help_text="JSON credentials file")

    
    def __str__(self):
        return f"{self.name} ({self.get_storage_type_display()})"
    
    def save(self, *args, **kwargs):
        # Ensure only one default configuration
        if self.is_default:
            StorageConfig.objects.filter(is_default=True).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)

class AppSettings(models.Model):
    """Model for application settings"""
    key = models.CharField(max_length=50, unique=True)
    value = models.TextField()
    
    @classmethod
    def get(cls, key, default=None):
        try:
            setting = cls.objects.get(key=key)
            return setting.value
        except cls.DoesNotExist:
            return default
    
    @classmethod
    def set(cls, key, value):
        obj, created = cls.objects.update_or_create(
            key=key,
            defaults={'value': value}
        )
        return obj
