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
    now = timezone.now()
    
    due_tasks = BackupTask.objects.filter(
        enabled=True,
        next_run__lte=now
    )
    
    for task in due_tasks:
        execute_backup_task.delay(task.id)

@shared_task
def execute_backup_task(task_id):
    try:
        task = BackupTask.objects.get(id=task_id)
        server = task.server

        history = BackupHistory.objects.create(
            server=server,
            task=task,
            status='pending'
        )
        
        try:
            backup_service = BackupService(server.id)
            result = backup_service.execute_backup()
            
            history.completed_at = timezone.now()
            history.status = 'success' if result['success'] else 'error'
            
            if result['success']:
                history.file_path = result['path']
                history.file_size = os.path.getsize(result['path'])
            else:
                history.error_message = result['message']
            
            history.save()
            
            task.last_run = timezone.now()
            task._calculate_next_run()
            task.save()

            _cleanup_old_backups(server.id, task.retain_count)
            
            if task.email_notification and task.email_address:
                _send_backup_notification(task, history, result)
                
        except Exception as e:
            import traceback
            print(f"BACKUP ERROR: {str(e)}")
            print(traceback.format_exc())
            
            history.status = 'error'
            history.error_message = str(e)
            history.completed_at = timezone.now()
            history.save()
            
    except Exception as e:
        import traceback
        print(f"MAIN TASK ERROR: {str(e)}")
        print(traceback.format_exc())

def _cleanup_old_backups(server_id, retain_count):
    if retain_count <= 0:
        return 
        
    history_entries = BackupHistory.objects.filter(
        server_id=server_id,
        status='success'
    ).order_by('-completed_at')
    
    if history_entries.count() > retain_count:
        for entry in history_entries[retain_count:]:
            try:
                if entry.file_path and os.path.exists(entry.file_path):
                    os.remove(entry.file_path)
            except Exception as e:
                print(f"Error while deleting old backup: {str(e)}")

def _send_backup_notification(task, history, result):
    subject = f"Backup {task.server.name}: {'Success' if result['success'] else 'Error'}"
    
    if result['success']:
        message = (
            f"Backup of server {task.server.name} completed successfully.\n\n"
            f"Start time: {history.started_at}\n"
            f"End time: {history.completed_at}\n"
            f"File size: {history.file_size / (1024*1024):.2f} MB\n"
            f"Path: {history.file_path}"
        )
    else:
        message = (
            f"Backup of server {task.server.name} failed.\n\n"
            f"Start time: {history.started_at}\n"
            f"End time: {history.completed_at}\n"
            f"Error: {history.error_message}"
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
    try:
        backup = BackupHistory.objects.get(id=backup_id)
        history = BackupHistory.objects.get(id=history_id)
        server = backup.server
        
        if not backup.file_path or not os.path.exists(backup.file_path):
            raise FileNotFoundError("Backup file does not exist")
        
        if server.connection_type == 'direct':
            result = _restore_direct(server, backup.file_path)
        elif server.connection_type == 'ssh':
            result = _restore_ssh_tunnel(server, backup.file_path)
        else:
            raise ValueError(f"Unsupported connection type: {server.connection_type}")
        
        history.completed_at = timezone.now()
        history.status = 'success' if result['success'] else 'error'
        
        if result['success']:
            history.description += f" - completed successfully"
        else:
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
        
        import traceback
        print(f"RESTORE ERROR: {str(e)}")
        print(traceback.format_exc())

def _restore_direct(server, backup_file):
    try:
        try:
            subprocess.run(['which', 'mysql'], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            return {
                'success': False,
                'message': 'Error: mysql is not installed. Install MySQL client on the server.'
            }
        
        cmd = [
            'mysql',
            f'--host={server.hostname}',
            f'--port={server.port}',
            f'--user={server.username}',
            f'--password={server.password}',
        ]
        
        if server.database_name:
            cmd.append(server.database_name)
        
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
                'message': 'Backup restored successfully'
            }
        else:
            return {
                'success': False,
                'message': f'Error during restore: {result.stderr}'
            }
    except Exception as e:
        return {
            'success': False,
            'message': f'Error: {str(e)}'
        }

def _restore_ssh_tunnel(server, backup_file):
    try:
        if not all([server.ssh_hostname, server.ssh_port, server.ssh_username]):
            return {
                'success': False,
                'message': 'Missing SSH data: hostname, port or username'
            }
        
        if not server.ssh_password and not server.ssh_key_file:
            return {
                'success': False,
                'message': 'No SSH authentication method (password or key)'
            }
            
        try:
            subprocess.run(['which', 'mysql'], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            return {
                'success': False,
                'message': 'Error: mysql is not installed. Install MySQL client on the server.'
            }
        
        ssh_config = {
            'ssh_address_or_host': (server.ssh_hostname, int(server.ssh_port)),
            'ssh_username': server.ssh_username,
            'remote_bind_address': (server.hostname, int(server.port))
        }
        
        if server.ssh_password:
            ssh_config['ssh_password'] = server.ssh_password
        elif server.ssh_key_file and server.ssh_key_file.path:
            ssh_config['ssh_pkey'] = server.ssh_key_file.path
            
        with sshtunnel.SSHTunnelForwarder(**ssh_config) as tunnel:
            cmd = [
                'mysql',
                '--host=127.0.0.1',
                f'--port={tunnel.local_bind_port}',
                f'--user={server.username}',
                f'--password={server.password}',
            ]
            
            if server.database_name:
                cmd.append(server.database_name)
            
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
                    'message': 'Backup successfully restored through SSH tunnel'
                }
            else:
                return {
                    'success': False,
                    'message': f'Error during restore: {result.stderr}'
                }
                
    except Exception as e:
        return {
            'success': False,
            'message': f'SSH tunnel error: {str(e)}'
        }