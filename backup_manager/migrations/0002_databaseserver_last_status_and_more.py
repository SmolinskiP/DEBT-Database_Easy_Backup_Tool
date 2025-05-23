# Generated by Django 5.2.1 on 2025-05-12 13:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backup_manager', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='databaseserver',
            name='last_status',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='databaseserver',
            name='last_status_check',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='databaseserver',
            name='last_status_message',
            field=models.TextField(blank=True),
        ),
    ]
