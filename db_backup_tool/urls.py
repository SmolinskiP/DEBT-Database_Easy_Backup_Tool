# Zaktualizuj urls.py

from django.contrib import admin
from django.urls import path
from backup_manager.views import (
    dashboard_view, add_server_view, server_list_view,
    test_connection_view, delete_server_view,
    schedule_list_view, add_schedule_view, edit_schedule_view,
    delete_schedule_view, toggle_schedule_view, run_backup_now_view,
    backup_history_view, export_history_csv_view,
    backup_files_view, download_backup_view, restore_backup_view,
    delete_backup_view, delete_history_view
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', dashboard_view, name='dashboard'),
    
    # Serwery baz danych
    path('servers/add/', add_server_view, name='add_server'),
    path('servers/', server_list_view, name='server_list'),
    path('api/test-connection/', test_connection_view, name='test_connection'),
    path('api/servers/<int:server_id>/', delete_server_view, name='delete_server'),
    
    # Harmonogramy backupów
    path('schedules/', schedule_list_view, name='schedule_list'),
    path('schedules/add/', add_schedule_view, name='add_schedule'),
    path('schedules/edit/<int:task_id>/', edit_schedule_view, name='edit_schedule'),
    path('api/schedules/<int:task_id>/', delete_schedule_view, name='delete_schedule'),
    path('api/schedules/<int:task_id>/toggle/', toggle_schedule_view, name='toggle_schedule'),
    path('api/schedules/<int:task_id>/run-now/', run_backup_now_view, name='run_backup_now'),
    
    # Historia backupów
    path('history/', backup_history_view, name='backup_history'),
    path('history/export/', export_history_csv_view, name='export_history'),

    # Backupy
    path('backups/', backup_files_view, name='backup_files'),
    path('backups/download/<int:backup_id>/', download_backup_view, name='download_backup'),
    path('api/backups/restore/<int:backup_id>/', restore_backup_view, name='restore_backup'),
    path('api/backups/delete/<int:backup_id>/', delete_backup_view, name='delete_backup'),
    path('api/history/delete/<int:history_id>/', delete_history_view, name='delete_history'),
]