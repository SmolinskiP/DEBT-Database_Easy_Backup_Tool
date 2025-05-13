from django.db import models
from django.utils import timezone
import datetime
import os

class DatabaseServer(models.Model):
    CONNECTION_TYPES = (
        ('direct', 'MariaDB/MySQL (TCP/IP)'),
        ('ssh', 'MariaDB/MySQL (SSH Tunnel)'),
    )
    
    name = models.CharField(max_length=100)
    connection_type = models.CharField(max_length=10, choices=CONNECTION_TYPES)
    hostname = models.CharField(max_length=255)
    port = models.IntegerField(default=3306)
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=255)
    database_name = models.CharField(max_length=100, blank=True, null=True,
                                    help_text="Nazwa konkretnej bazy do backupu. Pozostaw puste dla wszystkich baz.")
    
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

class BackupTask(models.Model):
    FREQUENCY_CHOICES = (
        ('daily', 'Codziennie'),
        ('weekly', 'Co tydzień'),
        ('monthly', 'Co miesiąc'),
        ('custom', 'Niestandardowo'),
    )
    
    DAY_OF_WEEK_CHOICES = (
        (0, 'Poniedziałek'),
        (1, 'Wtorek'),
        (2, 'Środa'),
        (3, 'Czwartek'),
        (4, 'Piątek'),
        (5, 'Sobota'),
        (6, 'Niedziela'),
    )
    
    name = models.CharField(max_length=100)
    server = models.ForeignKey('DatabaseServer', on_delete=models.CASCADE, related_name='backup_tasks')
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES)
    time = models.TimeField(help_text="Czas wykonania (HH:MM)")
    
    # Dla weekly
    day_of_week = models.IntegerField(choices=DAY_OF_WEEK_CHOICES, null=True, blank=True)
    
    # Dla monthly
    day_of_month = models.IntegerField(null=True, blank=True, 
                                     help_text="Dzień miesiąca (1-31)")
    
    # Ogólne
    enabled = models.BooleanField(default=True)
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)
    
    # Opcje dodatkowe
    retain_count = models.IntegerField(default=10, help_text="Ile ostatnich backupów zachować")
    email_notification = models.BooleanField(default=False)
    email_address = models.EmailField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()} - {self.server.name})"
    
    def save(self, *args, **kwargs):
        # Oblicz następne uruchomienie
        self._calculate_next_run()
        super().save(*args, **kwargs)
    
    def _calculate_next_run(self):
        """Oblicza datę/czas następnego uruchomienia"""
        now = timezone.now()
        task_time = timezone.make_aware(
            datetime.datetime.combine(now.date(), self.time)
        )
        
        if self.frequency == 'daily':
            # Jeśli czas zadania na dziś już minął, ustaw na jutro
            if task_time <= now:
                self.next_run = task_time + datetime.timedelta(days=1)
            else:
                self.next_run = task_time
                
        elif self.frequency == 'weekly':
            # Oblicz dni do następnego dnia tygodnia
            days_ahead = self.day_of_week - now.weekday()
            if days_ahead <= 0 or (days_ahead == 0 and task_time <= now):
                days_ahead += 7
                
            next_date = now.date() + datetime.timedelta(days=days_ahead)
            self.next_run = timezone.make_aware(
                datetime.datetime.combine(next_date, self.time)
            )
            
        elif self.frequency == 'monthly':
            # Znajdź następny miesiąc z pasującym dniem
            month = now.month
            year = now.year
            
            # Próbujemy znaleźć kolejny miesiąc z wybranym dniem
            while True:
                try:
                    next_date = datetime.date(year, month, self.day_of_month)
                    next_datetime = timezone.make_aware(
                        datetime.datetime.combine(next_date, self.time)
                    )
                    
                    # Jeśli data jest w przyszłości, to ją używamy
                    if next_datetime > now:
                        self.next_run = next_datetime
                        break
                        
                except ValueError:
                    # Ten miesiąc nie ma tyle dni, próbujemy następny
                    pass
                    
                # Przejdź do następnego miesiąca
                month += 1
                if month > 12:
                    month = 1
                    year += 1

class BackupHistory(models.Model):
    STATUS_CHOICES = (
        ('success', 'Sukces'),
        ('error', 'Błąd'),
        ('pending', 'W trakcie'),
    )
    
    server = models.ForeignKey('DatabaseServer', on_delete=models.CASCADE)
    task = models.ForeignKey('BackupTask', on_delete=models.SET_NULL, null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    file_path = models.CharField(max_length=255, blank=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    description = models.TextField(blank=True, help_text="Opis operacji lub dodatkowe informacje")
    
    def __str__(self):
        return f"Backup {self.server.name} ({self.started_at.strftime('%Y-%m-%d %H:%M')})"

    def get_filename(self):
        """Zwraca nazwę pliku bez ścieżki"""
        if self.file_path:
            return os.path.basename(self.file_path)
        return None
    
    def is_restorable(self):
        """Sprawdza czy backup może być przywrócony"""
        return self.status == 'success' and self.file_path and os.path.exists(self.file_path)