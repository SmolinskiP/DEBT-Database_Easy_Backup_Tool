# backup_manager/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.urls import reverse
from django.conf import settings
from .models import DatabaseServer, BackupTask, BackupHistory
from .forms import DatabaseServerForm, BackupTaskForm
from .services import DatabaseConnectionService, BackupService
from .tasks import execute_backup_task, restore_backup_task
import json
import csv
from datetime import datetime
import os

def dashboard_view(request):
    """Główna strona - dashboard"""
    servers = DatabaseServer.objects.all().order_by('-created_at')
    
    # Pobierz ostatnie backupy
    recent_backups = BackupHistory.objects.all().order_by('-started_at')[:5]
    
    # Pobierz statystyki
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
    """Lista harmonogramów backupów"""
    tasks = BackupTask.objects.all().order_by('-created_at')
    
    context = {
        'tasks': tasks,
    }
    return render(request, 'schedule_list.html', context)

def add_schedule_view(request):
    """Dodawanie nowego harmonogramu backupu"""
    form = BackupTaskForm()
    
    if request.method == 'POST':
        form = BackupTaskForm(request.POST)
        if form.is_valid():
            task = form.save()
            messages.success(request, f"Harmonogram '{task.name}' został utworzony.")
            return redirect('schedule_list')
        else:
            messages.error(request, "Popraw błędy w formularzu.")
    
    context = {
        'form': form,
    }
    return render(request, 'add_schedule.html', context)

def edit_schedule_view(request, task_id):
    """Edycja harmonogramu backupu"""
    task = get_object_or_404(BackupTask, id=task_id)
    form = BackupTaskForm(instance=task)
    
    if request.method == 'POST':
        form = BackupTaskForm(request.POST, instance=task)
        if form.is_valid():
            task = form.save()
            messages.success(request, f"Harmonogram '{task.name}' został zaktualizowany.")
            return redirect('schedule_list')
        else:
            messages.error(request, "Popraw błędy w formularzu.")
    
    context = {
        'form': form,
        'task': task,
    }
    return render(request, 'edit_schedule.html', context)

@csrf_exempt
def delete_schedule_view(request, task_id):
    """API endpoint do usuwania harmonogramu"""
    if request.method == 'DELETE':
        try:
            task = BackupTask.objects.get(id=task_id)
            task_name = task.name
            task.delete()
            return JsonResponse({
                'success': True, 
                'message': f"Harmonogram '{task_name}' został usunięty."
            })
        except BackupTask.DoesNotExist:
            return JsonResponse({
                'success': False, 
                'message': 'Harmonogram nie istnieje.'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'success': False, 
                'message': f'Błąd: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False, 
        'message': 'Nieprawidłowa metoda HTTP.'
    }, status=405)

@csrf_exempt
def toggle_schedule_view(request, task_id):
    """API endpoint do włączania/wyłączania harmonogramu"""
    if request.method == 'POST':
        try:
            task = BackupTask.objects.get(id=task_id)
            task.enabled = not task.enabled
            task.save()
            
            status = "włączony" if task.enabled else "wyłączony"
            return JsonResponse({
                'success': True, 
                'enabled': task.enabled,
                'message': f"Harmonogram '{task.name}' został {status}."
            })
        except BackupTask.DoesNotExist:
            return JsonResponse({
                'success': False, 
                'message': 'Harmonogram nie istnieje.'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'success': False, 
                'message': f'Błąd: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False, 
        'message': 'Nieprawidłowa metoda HTTP.'
    }, status=405)

@csrf_exempt
def run_backup_now_view(request, task_id):
    """API endpoint do ręcznego uruchomienia backupu z harmonogramu"""
    if request.method == 'POST':
        try:
            task = BackupTask.objects.get(id=task_id)
            
            # Uruchom zadanie Celery do wykonania backupu
            execute_backup_task.delay(task.id)
            
            return JsonResponse({
                'success': True,
                'message': f"Backup dla '{task.name}' został uruchomiony. Sprawdź historię backupów za chwilę."
            })
        except BackupTask.DoesNotExist:
            return JsonResponse({
                'success': False, 
                'message': 'Harmonogram nie istnieje.'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'success': False, 
                'message': f'Błąd: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False, 
        'message': 'Nieprawidłowa metoda HTTP.'
    }, status=405)

# Widoki dla historii backupów
def backup_history_view(request):
    """Widok historii backupów"""
    history = BackupHistory.objects.all().order_by('-started_at')
    
    context = {
        'history': history,
    }
    return render(request, 'backup_history.html', context)

def export_history_csv_view(request):
    """Eksport historii backupów do CSV"""
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
    """Widok listy plików backupu"""
    history = BackupHistory.objects.filter(status='success').order_by('-started_at')
    
    context = {
        'history': history,
    }
    return render(request, 'backup_files.html', context)

def download_backup_view(request, backup_id):
    """Pobieranie pliku backupu"""
    backup = get_object_or_404(BackupHistory, id=backup_id, status='success')
    
    if not backup.file_path or not os.path.exists(backup.file_path):
        raise Http404("Plik backupu nie istnieje")
    
    # Otwórz plik i zwróć jako odpowiedź
    file_path = backup.file_path
    filename = os.path.basename(file_path)
    
    response = FileResponse(open(file_path, 'rb'))
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@csrf_exempt
def restore_backup_view(request, backup_id):
    """Przywracanie backupu"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Nieprawidłowa metoda HTTP'}, status=405)
    
    backup = get_object_or_404(BackupHistory, id=backup_id, status='success')
    
    if not backup.file_path or not os.path.exists(backup.file_path):
        return JsonResponse({'success': False, 'message': 'Plik backupu nie istnieje'}, status=404)
    
    try:
        filename = os.path.basename(backup.file_path)
        # Utwórz wpis w historii o rozpoczęciu przywracania
        restore_history = BackupHistory.objects.create(
            server=backup.server,
            status='pending',
            description=f"Przywracanie z backupu {filename}"  # Użyj nowego pola
        )
        
        # Uruchom zadanie przywracania w tle
        restore_backup_task.delay(backup_id, restore_history.id)
        
        return JsonResponse({
            'success': True,
            'message': 'Przywracanie rozpoczęte. Sprawdź historię backupów, aby zobaczyć status.'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Błąd: {str(e)}'}, status=500)
    """Przywracanie backupu"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Nieprawidłowa metoda HTTP'}, status=405)
    
    backup = get_object_or_404(BackupHistory, id=backup_id, status='success')
    
    if not backup.file_path or not os.path.exists(backup.file_path):
        return JsonResponse({'success': False, 'message': 'Plik backupu nie istnieje'}, status=404)
    
    try:
        # Utwórz wpis w historii o rozpoczęciu przywracania
        restore_history = BackupHistory.objects.create(
            server=backup.server,
            status='pending',
            error_message=f"Przywracanie z backupu {os.path.basename(backup.file_path)}"
        )
        
        # Uruchom zadanie przywracania w tle
        restore_backup_task.delay(backup_id, restore_history.id)
        
        return JsonResponse({
            'success': True,
            'message': 'Przywracanie rozpoczęte. Sprawdź historię backupów, aby zobaczyć status.'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Błąd: {str(e)}'}, status=500)

@csrf_exempt
def delete_backup_view(request, backup_id):
    """API endpoint do usuwania backupu"""
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'message': 'Nieprawidłowa metoda HTTP'}, status=405)
    
    try:
        backup = BackupHistory.objects.get(id=backup_id)
        
        # Usuń plik jeśli istnieje
        if backup.file_path and os.path.exists(backup.file_path):
            try:
                os.remove(backup.file_path)
            except OSError as e:
                return JsonResponse({
                    'success': False, 
                    'message': f'Nie można usunąć pliku: {str(e)}'
                }, status=500)
        
        # Usuń wpis z bazy
        backup_name = backup.get_filename() if backup.file_path else f"#{backup.id}"
        backup.delete()
        
        return JsonResponse({
            'success': True, 
            'message': f'Backup {backup_name} został usunięty.'
        })
    except BackupHistory.DoesNotExist:
        return JsonResponse({
            'success': False, 
            'message': 'Backup nie istnieje.'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'message': f'Błąd: {str(e)}'
        }, status=500)

@csrf_exempt
def delete_history_view(request, history_id):
    """API endpoint do usuwania wpisu historii (z opcjonalnym usunięciem pliku)"""
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'message': 'Nieprawidłowa metoda HTTP'}, status=405)
    
    try:
        history = BackupHistory.objects.get(id=history_id)
        
        # Sprawdź czy istnieje plik i usuń go jeśli tak
        if history.file_path and os.path.exists(history.file_path):
            try:
                os.remove(history.file_path)
            except OSError as e:
                # Loguj błąd, ale kontynuuj usuwanie wpisu
                print(f"Błąd usuwania pliku: {str(e)}")
        
        history_id = history.id
        history.delete()
        
        return JsonResponse({
            'success': True, 
            'message': f'Wpis historii #{history_id} został usunięty wraz z powiązanym plikiem.'
        })
    except BackupHistory.DoesNotExist:
        return JsonResponse({
            'success': False, 
            'message': 'Wpis historii nie istnieje.'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'message': f'Błąd: {str(e)}'
        }, status=500)
