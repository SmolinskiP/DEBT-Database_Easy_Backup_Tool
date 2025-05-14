# Zaktualizuj urls.py

from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from backup_manager.views import (
    dashboard_view, add_server_view, server_list_view,
    test_connection_view, delete_server_view,
    schedule_list_view, add_schedule_view, edit_schedule_view,
    delete_schedule_view, toggle_schedule_view, run_backup_now_view,
    backup_history_view, export_history_csv_view,
    backup_files_view, download_backup_view, restore_backup_view,
    delete_backup_view, delete_history_view, settings_view,
    save_settings_view, add_storage_view, edit_storage_view,
    delete_storage_view, storage_list_view
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # Ścieżki autentykacji
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('password_change/', auth_views.PasswordChangeView.as_view(template_name='registration/password_change_form.html'), name='password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='registration/password_change_done.html'), name='password_change_done'),
    
    path('', login_required(dashboard_view), name='dashboard'),
    
    # Serwery baz danych
    path('servers/add/', login_required(add_server_view), name='add_server'),
    path('servers/', login_required(server_list_view), name='server_list'),
    path('settings/', login_required(settings_view), name='settings'),
    path('settings/save/', login_required(save_settings_view), name='save_settings'),
    path('api/test-connection/', login_required(test_connection_view), name='test_connection'),
    path('api/servers/<int:server_id>/', login_required(delete_server_view), name='delete_server'),
    
    # Harmonogramy backupów
    path('schedules/', login_required(schedule_list_view), name='schedule_list'),
    path('schedules/add/', login_required(add_schedule_view), name='add_schedule'),
    path('schedules/edit/<int:task_id>/', login_required(edit_schedule_view), name='edit_schedule'),
    path('api/schedules/<int:task_id>/', login_required(delete_schedule_view), name='delete_schedule'),
    path('api/schedules/<int:task_id>/toggle/', login_required(toggle_schedule_view), name='toggle_schedule'),
    path('api/schedules/<int:task_id>/run-now/', login_required(run_backup_now_view), name='run_backup_now'),
    
    # Historia backupów
    path('history/', login_required(backup_history_view), name='backup_history'),
    path('history/export/', login_required(export_history_csv_view), name='export_history'),

    # Backupy
    path('backups/', login_required(backup_files_view), name='backup_files'),
    path('backups/download/<int:backup_id>/', login_required(download_backup_view), name='download_backup'),
    path('api/backups/restore/<int:backup_id>/', login_required(restore_backup_view), name='restore_backup'),
    path('api/backups/delete/<int:backup_id>/', login_required(delete_backup_view), name='delete_backup'),
    path('api/history/delete/<int:history_id>/', login_required(delete_history_view), name='delete_history'),

    # Storage configurations
    path('storage/', login_required(storage_list_view), name='storage_list'),
    path('storage/add/', login_required(add_storage_view), name='add_storage'),
    path('storage/edit/<int:storage_id>/', login_required(edit_storage_view), name='edit_storage'),
    path('api/storage/<int:storage_id>/', login_required(delete_storage_view), name='delete_storage'),
]