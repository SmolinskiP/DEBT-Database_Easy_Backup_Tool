# backup_manager/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.urls import reverse
from django.conf import settings
from .models import DatabaseServer, BackupTask, BackupHistory, StorageConfig, AppSettings
from .forms import DatabaseServerForm, BackupTaskForm, StorageConfigForm
from .services import DatabaseConnectionService, BackupService
from .tasks import execute_backup_task, restore_backup_task
import json
import csv
from datetime import datetime
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import os

def dashboard_view(request):
    """Main page - dashboard"""
    servers = DatabaseServer.objects.all().order_by('-created_at')
    
    # Get recent backups
    recent_backups = BackupHistory.objects.all().order_by('-started_at')[:5]
    
    # Get statistics
    scheduled_count = BackupTask.objects.filter(enabled=True).count()
    successful_backups = BackupHistory.objects.filter(status='success').count()
    failed_backups = BackupHistory.objects.filter(status='error').count()
    
    context = {
        'servers': servers,
        'servers_count': servers.count(),
        'scheduled_count': scheduled_count,
        'successful_backups': successful_backups,
        'failed_backups': failed_backups,
        'recent_backups': recent_backups
    }
    return render(request, 'dashboard.html', context)

def add_server_view(request):
    """Add server view"""
    form = DatabaseServerForm()
    
    if request.method == 'POST':
        form = DatabaseServerForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Database server has been added successfully.")
            return redirect('dashboard')
    
    context = {
        'form': form,
    }
    return render(request, 'add_server.html', context)

def server_list_view(request):
    """Server list view"""
    servers = DatabaseServer.objects.all().order_by('-created_at')
    
    context = {
        'servers': servers,
    }
    return render(request, 'server_list.html', context)

@csrf_exempt
def test_connection_view(request):
    """API view for testing database connection"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # If we have a server ID, test connection to existing server
            if 'server_id' in data:
                server_id = data['server_id']
                result = DatabaseConnectionService.test_connection(server_id=server_id)
                
                # Update server status
                try:
                    server = DatabaseServer.objects.get(id=server_id)
                    server.last_status = result['success']
                    server.last_status_check = timezone.now()
                    server.last_status_message = result['message']
                    server.save()
                except DatabaseServer.DoesNotExist:
                    pass
                
                return JsonResponse(result)
            
            # Otherwise test connection with form data
            connection_data = {
                'connection_type': data.get('connection_type'),
                'hostname': data.get('hostname'),
                'port': data.get('port'),
                'username': data.get('username'),
                'password': data.get('password'),
                'ssh_hostname': data.get('ssh_hostname'),
                'ssh_port': data.get('ssh_port'),
                'ssh_username': data.get('ssh_username'),
                'ssh_password': data.get('ssh_password'),
            }
            result = DatabaseConnectionService.test_connection(connection_data=connection_data)
            return JsonResponse(result)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error processing request: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid HTTP method. Use POST.'
    })

@csrf_exempt
def delete_server_view(request, server_id):
    """API view for deleting a server"""
    if request.method == 'DELETE':
        try:
            server = DatabaseServer.objects.get(id=server_id)
            server.delete()
            return JsonResponse({'success': True, 'message': 'Server deleted successfully'})
        except DatabaseServer.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Server does not exist'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'message': 'Invalid HTTP method'}, status=405)

def schedule_list_view(request):
    """Backup schedules list"""
    tasks = BackupTask.objects.all().order_by('-created_at')
    
    context = {
        'tasks': tasks,
    }
    return render(request, 'schedule_list.html', context)

def add_schedule_view(request):
    """Adding a new backup schedule"""
    form = BackupTaskForm()
    
    if request.method == 'POST':
        form = BackupTaskForm(request.POST)
        if form.is_valid():
            task = form.save()
            messages.success(request, f"Schedule '{task.name}' has been created.")
            return redirect('schedule_list')
        else:
            messages.error(request, "Please correct the form errors.")
    
    context = {
        'form': form,
    }
    return render(request, 'add_schedule.html', context)

def edit_schedule_view(request, task_id):
    """Editing backup schedule"""
    task = get_object_or_404(BackupTask, id=task_id)
    form = BackupTaskForm(instance=task)
    
    if request.method == 'POST':
        form = BackupTaskForm(request.POST, instance=task)
        if form.is_valid():
            task = form.save()
            messages.success(request, f"Schedule '{task.name}' has been updated.")
            return redirect('schedule_list')
        else:
            messages.error(request, "Please correct the form errors.")
    
    context = {
        'form': form,
        'task': task,
    }
    return render(request, 'edit_schedule.html', context)

@csrf_exempt
def delete_schedule_view(request, task_id):
    """API endpoint for deleting a schedule"""
    if request.method == 'DELETE':
        try:
            task = BackupTask.objects.get(id=task_id)
            task_name = task.name
            task.delete()
            return JsonResponse({
                'success': True, 
                'message': f"Schedule '{task_name}' has been deleted."
            })
        except BackupTask.DoesNotExist:
            return JsonResponse({
                'success': False, 
                'message': 'Schedule does not exist.'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'success': False, 
                'message': f'Error: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False, 
        'message': 'Invalid HTTP method.'
    }, status=405)

@csrf_exempt
def toggle_schedule_view(request, task_id):
    """API endpoint for enabling/disabling a schedule"""
    if request.method == 'POST':
        try:
            task = BackupTask.objects.get(id=task_id)
            task.enabled = not task.enabled
            task.save()
            
            status = "enabled" if task.enabled else "disabled"
            return JsonResponse({
                'success': True, 
                'enabled': task.enabled,
                'message': f"Schedule '{task.name}' has been {status}."
            })
        except BackupTask.DoesNotExist:
            return JsonResponse({
                'success': False, 
                'message': 'Schedule does not exist.'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'success': False, 
                'message': f'Error: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False, 
        'message': 'Invalid HTTP method.'
    }, status=405)

@csrf_exempt
def run_backup_now_view(request, task_id):
    """API endpoint for manually running a backup from a schedule"""
    if request.method == 'POST':
        try:
            task = BackupTask.objects.get(id=task_id)
            
            # Run Celery task to perform backup
            execute_backup_task.delay(task.id)
            
            return JsonResponse({
                'success': True,
                'message': f"Backup for '{task.name}' has been initiated. Check backup history shortly."
            })
        except BackupTask.DoesNotExist:
            return JsonResponse({
                'success': False, 
                'message': 'Schedule does not exist.'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'success': False, 
                'message': f'Error: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False, 
        'message': 'Invalid HTTP method.'
    }, status=405)

# Backup history views
def backup_history_view(request):
    """Backup history view"""
    history = BackupHistory.objects.all().order_by('-started_at')
    
    context = {
        'history': history,
    }
    return render(request, 'backup_history.html', context)

def export_history_csv_view(request):
    """Export backup history to CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="backup_history.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Server', 'Task', 'Started', 'Completed', 'Status', 'File Size (MB)', 'Error'])
    
    history = BackupHistory.objects.all().order_by('-started_at')
    for entry in history:
        file_size = f"{entry.file_size / (1024*1024):.2f}" if entry.file_size else "N/A"
        task_name = entry.task.name if entry.task else "Manual"
        
        writer.writerow([
            entry.server.name,
            task_name,
            entry.started_at.strftime('%Y-%m-%d %H:%M:%S'),
            entry.completed_at.strftime('%Y-%m-%d %H:%M:%S') if entry.completed_at else "N/A",
            entry.get_status_display(),
            file_size,
            entry.error_message
        ])
    
    return response

def backup_files_view(request):
    """Backup files list view"""
    history = BackupHistory.objects.filter(status='success').order_by('-started_at')
    
    context = {
        'history': history,
    }
    return render(request, 'backup_files.html', context)

def download_backup_view(request, backup_id):
    """Downloading a backup file"""
    backup = get_object_or_404(BackupHistory, id=backup_id, status='success')
    
    if not backup.file_path or not os.path.exists(backup.file_path):
        raise Http404("Backup file does not exist")
    
    # Open file and return as response
    file_path = backup.file_path
    filename = os.path.basename(file_path)
    
    response = FileResponse(open(file_path, 'rb'))
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@csrf_exempt
def restore_backup_view(request, backup_id):
    """Restoring a backup"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid HTTP method'}, status=405)
    
    backup = get_object_or_404(BackupHistory, id=backup_id, status='success')
    
    if not backup.file_path or not os.path.exists(backup.file_path):
        return JsonResponse({'success': False, 'message': 'Backup file does not exist'}, status=404)
    
    try:
        filename = os.path.basename(backup.file_path)
        # Create history entry for restore operation
        restore_history = BackupHistory.objects.create(
            server=backup.server,
            status='pending',
            description=f"Restoring from backup {filename}"  # Use new field
        )
        
        # Launch restore task in background
        restore_backup_task.delay(backup_id, restore_history.id)
        
        return JsonResponse({
            'success': True,
            'message': 'Restore initiated. Check backup history to see status.'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'}, status=500)
    """Restoring a backup"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid HTTP method'}, status=405)
    
    backup = get_object_or_404(BackupHistory, id=backup_id, status='success')
    
    if not backup.file_path or not os.path.exists(backup.file_path):
        return JsonResponse({'success': False, 'message': 'Backup file does not exist'}, status=404)
    
    try:
        # Create history entry for restore operation
        restore_history = BackupHistory.objects.create(
            server=backup.server,
            status='pending',
            error_message=f"Restoring from backup {os.path.basename(backup.file_path)}"
        )
        
        # Launch restore task in background
        restore_backup_task.delay(backup_id, restore_history.id)
        
        return JsonResponse({
            'success': True,
            'message': 'Restore initiated. Check backup history to see status.'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'}, status=500)

@csrf_exempt
def delete_backup_view(request, backup_id):
    """API endpoint for deleting a backup"""
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'message': 'Invalid HTTP method'}, status=405)
    
    try:
        backup = BackupHistory.objects.get(id=backup_id)
        
        # Delete file if exists
        if backup.file_path and os.path.exists(backup.file_path):
            try:
                os.remove(backup.file_path)
            except OSError as e:
                return JsonResponse({
                    'success': False, 
                    'message': f'Cannot delete file: {str(e)}'
                }, status=500)
        
        # Delete database entry
        backup_name = backup.get_filename() if backup.file_path else f"#{backup.id}"
        backup.delete()
        
        return JsonResponse({
            'success': True, 
            'message': f'Backup {backup_name} has been deleted.'
        })
    except BackupHistory.DoesNotExist:
        return JsonResponse({
            'success': False, 
            'message': 'Backup does not exist.'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'message': f'Error: {str(e)}'
        }, status=500)

@csrf_exempt
def delete_history_view(request, history_id):
    """API endpoint for deleting a history entry (with optional file deletion)"""
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'message': 'Invalid HTTP method'}, status=405)
    
    try:
        history = BackupHistory.objects.get(id=history_id)
        
        # Check if file exists and delete it if so
        if history.file_path and os.path.exists(history.file_path):
            try:
                os.remove(history.file_path)
            except OSError as e:
                # Log error but continue deleting entry
                print(f"Error deleting file: {str(e)}")
        
        history_id = history.id
        history.delete()
        
        return JsonResponse({
            'success': True, 
            'message': f'History entry #{history_id} has been deleted along with associated file.'
        })
    except BackupHistory.DoesNotExist:
        return JsonResponse({
            'success': False, 
            'message': 'History entry does not exist.'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'message': f'Error: {str(e)}'
        }, status=500)


def storage_list_view(request):
    """Storage configurations list"""
    storage_configs = StorageConfig.objects.all().order_by('-is_default', 'name')
    
    context = {
        'storage_configs': storage_configs,
    }
    return render(request, 'storage_list.html', context)

def add_storage_view(request):
    """Add new storage configuration"""
    form = StorageConfigForm()
    
    if request.method == 'POST':
        form = StorageConfigForm(request.POST, request.FILES)
        if form.is_valid():
            storage = form.save()
            messages.success(request, f"Storage configuration '{storage.name}' has been added.")
            return redirect('storage_list')
        else:
            messages.error(request, "Please correct the form errors.")
    
    context = {
        'form': form,
    }
    return render(request, 'add_storage.html', context)

def edit_storage_view(request, storage_id):
    """Edit storage configuration"""
    storage = get_object_or_404(StorageConfig, id=storage_id)
    form = StorageConfigForm(instance=storage)
    
    if request.method == 'POST':
        form = StorageConfigForm(request.POST, request.FILES, instance=storage)
        if form.is_valid():
            storage = form.save()
            messages.success(request, f"Storage configuration '{storage.name}' has been updated.")
            return redirect('storage_list')
        else:
            messages.error(request, "Please correct the form errors.")
    
    context = {
        'form': form,
        'storage': storage,
    }
    return render(request, 'edit_storage.html', context)

@csrf_exempt
def delete_storage_view(request, storage_id):
    """API endpoint for deleting a storage configuration"""
    if request.method == 'DELETE':
        try:
            storage = StorageConfig.objects.get(id=storage_id)
            name = storage.name
            
            # Check if it's being used by any backup tasks
            tasks_using = BackupTask.objects.filter(
                models.Q(remote_hostname=storage.hostname) & 
                models.Q(remote_username=storage.username)
            ).count()
            
            if tasks_using > 0:
                return JsonResponse({
                    'success': False,
                    'message': f"Cannot delete '{name}' - it's being used by {tasks_using} backup tasks."
                }, status=400)
                
            storage.delete()
            return JsonResponse({
                'success': True,
                'message': f"Storage configuration '{name}' has been deleted."
            })
        except StorageConfig.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Storage configuration does not exist.'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid HTTP method.'
    }, status=405)

def gdrive_auth_start(request):
    """Placeholder for Google Drive auth start"""
    messages.info(request, "Using service account authentication. No user auth needed.")
    return redirect('storage_list')

def gdrive_auth_callback(request):
    """Placeholder for Google Drive auth callback"""
    return redirect('storage_list')
    """Handle Google Drive OAuth callback"""
    state = request.session.get('gdrive_auth_state')
    
    if not state:
        messages.error(request, "Authentication state mismatch. Please try again.")
        return redirect('storage_list')
    
    flow = Flow.from_client_secrets_file(
        'client_secret.json',
        scopes=['https://www.googleapis.com/auth/drive.file'],
        state=state,
        redirect_uri=request.build_absolute_uri(reverse('gdrive_auth_callback'))
    )
    
    flow.fetch_token(authorization_response=request.build_absolute_uri())
    credentials = flow.credentials
    
    # Save credentials to file
    credentials_path = os.path.join(settings.MEDIA_ROOT, 'gdrive_creds', f"user_{request.user.id}.json")
    os.makedirs(os.path.dirname(credentials_path), exist_ok=True)
    
    with open(credentials_path, 'w') as f:
        f.write(credentials.to_json())
    
    messages.success(request, "Google Drive authentication successful. You can now use Google Drive for backups.")
    return redirect('storage_list')