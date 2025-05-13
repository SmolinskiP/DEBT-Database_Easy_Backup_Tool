from django.db import models
from django.utils import timezone

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
    
    # Dane do SSH tunelowania
    ssh_hostname = models.CharField(max_length=255, blank=True, null=True)
    ssh_port = models.IntegerField(default=22, blank=True, null=True)
    ssh_username = models.CharField(max_length=100, blank=True, null=True)
    ssh_password = models.CharField(max_length=255, blank=True, null=True)
    ssh_key_file = models.FileField(upload_to='ssh_keys/', blank=True, null=True)
    
    # Status serwera
    last_status = models.BooleanField(default=False)
    last_status_check = models.DateTimeField(null=True, blank=True)
    last_status_message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_connection_type_display()})"