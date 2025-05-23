# Generated by Django 5.2.1 on 2025-05-15 07:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backup_manager', '0010_storageconfig_gdrive_credentials_file_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='databaseserver',
            name='connection_type',
            field=models.CharField(choices=[('direct_mysql', 'MariaDB/MySQL (TCP/IP)'), ('ssh_mysql', 'MariaDB/MySQL (SSH Tunnel)'), ('direct_postgresql', 'PostgreSQL (TCP/IP)'), ('ssh_postgresql', 'PostgreSQL (SSH Tunnel)')], max_length=20),
        ),
        migrations.AlterField(
            model_name='databaseserver',
            name='port',
            field=models.IntegerField(default=0),
        ),
    ]
