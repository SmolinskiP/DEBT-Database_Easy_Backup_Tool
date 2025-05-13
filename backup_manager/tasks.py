# tasks.py
import os
import datetime
import subprocess
import sshtunnel
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from .models import BackupTask, BackupHistory, DatabaseServer
from .services import BackupService

@shared_task
def run_scheduled_backups():
    """Główne zadanie do sprawdzania i uruchamiania zaplanowanych backupów"""
    now = timezone.now()
    
    # Znajdź wszystkie zadania, które powinny być uruchomione
    due_tasks = BackupTask.objects.filter(
        enabled=True,
        next_run__lte=now
    )
    
    for task in due_tasks:
        execute_backup_task.delay(task.id)

@shared_task
def execute_backup_task(task_id):
    """Wykonuje pojedyncze zadanie backupu"""
    try:
        task = BackupTask.objects.get(id=task_id)
        server = task.server
        
        # Utwórz wpis w historii
        history = BackupHistory.objects.create(
            server=server,
            task=task,
            status='pending'
        )
        
        try:
            # Wykonaj backup
            backup_service = BackupService(server.id)
            result = backup_service.execute_backup()
            
            # Aktualizuj historię
            history.completed_at = timezone.now()
            history.status = 'success' if result['success'] else 'error'
            
            if result['success']:
                history.file_path = result['path']
                history.file_size = os.path.getsize(result['path'])
            else:
                history.error_message = result['message']
            
            history.save()
            
            # Aktualizuj ostatnie uruchomienie zadania
            task.last_run = timezone.now()
            task._calculate_next_run()  # Oblicz następne uruchomienie
            task.save()
            
            # Usuń stare backupy jeśli przekroczono limit
            _cleanup_old_backups(server.id, task.retain_count)
            
            # Wyślij powiadomienie email jeśli włączone
            if task.email_notification and task.email_address:
                _send_backup_notification(task, history, result)
                
        except Exception as e:
            # Ważne - dodaj print aby zobaczyć błąd w logach
            import traceback
            print(f"BACKUP ERROR: {str(e)}")
            print(traceback.format_exc())
            
            # Obsługa błędów
            history.status = 'error'
            history.error_message = str(e)
            history.completed_at = timezone.now()
            history.save()
            
    except Exception as e:
        # Logowanie błędu głównego
        import traceback
        print(f"MAIN TASK ERROR: {str(e)}")
        print(traceback.format_exc())

def _cleanup_old_backups(server_id, retain_count):
    """Usuwa stare backupy, zachowując tylko określoną liczbę"""
    if retain_count <= 0:
        return  # Zachowaj wszystkie
        
    # Pobierz historię backupów dla tego serwera
    history_entries = BackupHistory.objects.filter(
        server_id=server_id,
        status='success'
    ).order_by('-completed_at')
    
    # Jeśli mamy więcej niż limit, usuń nadmiarowe
    if history_entries.count() > retain_count:
        for entry in history_entries[retain_count:]:
            try:
                # Usuń plik backupu
                if entry.file_path and os.path.exists(entry.file_path):
                    os.remove(entry.file_path)
                # Nie usuwaj wpisu w historii
            except Exception as e:
                print(f"Błąd podczas usuwania starego backupu: {str(e)}")

def _send_backup_notification(task, history, result):
    """Wysyła powiadomienie email o wyniku backupu"""
    subject = f"Backup {task.server.name}: {'Sukces' if result['success'] else 'Błąd'}"
    
    if result['success']:
        message = (
            f"Backup serwera {task.server.name} zakończony powodzeniem.\n\n"
            f"Czas rozpoczęcia: {history.started_at}\n"
            f"Czas zakończenia: {history.completed_at}\n"
            f"Rozmiar pliku: {history.file_size / (1024*1024):.2f} MB\n"
            f"Ścieżka: {history.file_path}"
        )
    else:
        message = (
            f"Backup serwera {task.server.name} zakończony niepowodzeniem.\n\n"
            f"Czas rozpoczęcia: {history.started_at}\n"
            f"Czas zakończenia: {history.completed_at}\n"
            f"Błąd: {history.error_message}"
        )
    
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[task.email_address],
        fail_silently=True
    )

@shared_task
def restore_backup_task(backup_id, history_id):
    """Przywraca backup z pliku"""
    try:
        backup = BackupHistory.objects.get(id=backup_id)
        history = BackupHistory.objects.get(id=history_id)
        server = backup.server
        
        if not backup.file_path or not os.path.exists(backup.file_path):
            raise FileNotFoundError("Plik backupu nie istnieje")
        
        # Logika przywracania
        if server.connection_type == 'direct':
            result = _restore_direct(server, backup.file_path)
        elif server.connection_type == 'ssh':
            result = _restore_ssh_tunnel(server, backup.file_path)
        else:
            raise ValueError(f"Nieobsługiwany typ połączenia: {server.connection_type}")
        
        # Zaktualizuj historię
        history.completed_at = timezone.now()
        history.status = 'success' if result['success'] else 'error'
        
        if result['success']:
            # Dodaj dodatkowy opis przy sukcesie
            history.description += f" - zakończone powodzeniem"
        else:
            # Zapisz komunikat błędu
            history.error_message = result['message']
        
        history.save()
        
    except Exception as e:
        try:
            history = BackupHistory.objects.get(id=history_id)
            history.status = 'error'
            history.error_message = str(e)
            history.completed_at = timezone.now()
            history.save()
        except:
            pass
        
        # Logowanie błędu
        import traceback
        print(f"RESTORE ERROR: {str(e)}")
        print(traceback.format_exc())

def _restore_direct(server, backup_file):
    """Przywraca backup przez bezpośrednie połączenie"""
    try:
        # Sprawdź czy mysql jest zainstalowany
        try:
            subprocess.run(['which', 'mysql'], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            return {
                'success': False,
                'message': 'Błąd: mysql nie jest zainstalowany. Zainstaluj klienta MySQL na serwerze.'
            }
        
        # Wykonaj przywracanie
        cmd = [
            'mysql',
            f'--host={server.hostname}',
            f'--port={server.port}',
            f'--user={server.username}',
            f'--password={server.password}',
        ]
        
        # Dodaj nazwę bazy, jeśli określona
        if server.database_name:
            cmd.append(server.database_name)
        
        # Odtwórz z pliku
        with open(backup_file, 'rb') as f:
            result = subprocess.run(
                cmd,
                stdin=f,
                capture_output=True,
                text=True
            )
        
        if result.returncode == 0:
            return {
                'success': True,
                'message': 'Backup przywrócony pomyślnie'
            }
        else:
            return {
                'success': False,
                'message': f'Błąd podczas przywracania: {result.stderr}'
            }
    except Exception as e:
        return {
            'success': False,
            'message': f'Błąd: {str(e)}'
        }

def _restore_ssh_tunnel(server, backup_file):
    """Przywraca backup przez tunel SSH"""
    try:
        # Sprawdź dane SSH
        if not all([server.ssh_hostname, server.ssh_port, server.ssh_username]):
            return {
                'success': False,
                'message': 'Brakujące dane SSH: hostname, port lub username'
            }
        
        # Sprawdź czy posiadamy hasło lub klucz SSH
        if not server.ssh_password and not server.ssh_key_file:
            return {
                'success': False,
                'message': 'Brak metody uwierzytelniania SSH (hasło lub klucz)'
            }
            
        # Sprawdź czy mysql jest zainstalowany
        try:
            subprocess.run(['which', 'mysql'], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            return {
                'success': False,
                'message': 'Błąd: mysql nie jest zainstalowany. Zainstaluj klienta MySQL na serwerze.'
            }
        
        # Tworzenie tunelu SSH
        ssh_config = {
            'ssh_address_or_host': (server.ssh_hostname, int(server.ssh_port)),
            'ssh_username': server.ssh_username,
            'remote_bind_address': (server.hostname, int(server.port))
        }
        
        # Dodawanie metody uwierzytelniania
        if server.ssh_password:
            ssh_config['ssh_password'] = server.ssh_password
        elif server.ssh_key_file and server.ssh_key_file.path:
            ssh_config['ssh_pkey'] = server.ssh_key_file.path
            
        # Utwórz tunel SSH
        with sshtunnel.SSHTunnelForwarder(**ssh_config) as tunnel:
            # Wykonaj przywracanie przez tunel
            cmd = [
                'mysql',
                '--host=127.0.0.1',
                f'--port={tunnel.local_bind_port}',
                f'--user={server.username}',
                f'--password={server.password}',
            ]
            
            # Dodaj nazwę bazy, jeśli określona
            if server.database_name:
                cmd.append(server.database_name)
            
            # Odtwórz z pliku
            with open(backup_file, 'rb') as f:
                result = subprocess.run(
                    cmd,
                    stdin=f,
                    capture_output=True,
                    text=True
                )
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': 'Backup przywrócony pomyślnie przez tunel SSH'
                }
            else:
                return {
                    'success': False,
                    'message': f'Błąd podczas przywracania: {result.stderr}'
                }
                
    except Exception as e:
        return {
            'success': False,
            'message': f'Błąd tunelu SSH: {str(e)}'
        }
