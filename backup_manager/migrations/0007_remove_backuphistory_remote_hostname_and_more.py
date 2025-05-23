# Generated by Django 5.2.1 on 2025-05-13 12:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backup_manager', '0006_backuphistory_remote_hostname_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='backuphistory',
            name='remote_hostname',
        ),
        migrations.RemoveField(
            model_name='backuphistory',
            name='remote_key_file',
        ),
        migrations.RemoveField(
            model_name='backuphistory',
            name='remote_password',
        ),
        migrations.RemoveField(
            model_name='backuphistory',
            name='remote_path',
        ),
        migrations.RemoveField(
            model_name='backuphistory',
            name='remote_port',
        ),
        migrations.RemoveField(
            model_name='backuphistory',
            name='remote_username',
        ),
        migrations.RemoveField(
            model_name='backuphistory',
            name='storage_type',
        ),
        migrations.AddField(
            model_name='backuptask',
            name='remote_hostname',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='backuptask',
            name='remote_key_file',
            field=models.FileField(blank=True, null=True, upload_to='remote_keys/'),
        ),
        migrations.AddField(
            model_name='backuptask',
            name='remote_password',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='backuptask',
            name='remote_path',
            field=models.CharField(blank=True, help_text='Path on remote server where backups will be stored', max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='backuptask',
            name='remote_port',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='backuptask',
            name='remote_username',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='backuptask',
            name='storage_type',
            field=models.CharField(choices=[('local', 'Local Storage'), ('ftp', 'FTP Server'), ('sftp', 'SFTP Server')], default='local', max_length=10),
        ),
    ]
