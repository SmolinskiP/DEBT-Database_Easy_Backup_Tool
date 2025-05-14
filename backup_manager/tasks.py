# backup_manager/tasks.py
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
from .storage import StorageService
import logging
import traceback

def file_log(message):
    """Log message to a file in logs directory"""
    try:
        log_dir = os.path.join(settings.BASE_DIR, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'debug.log')

        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_file, 'a') as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        try:
            error_file = "/tmp/debt_backup_error.log"
            with open(error_file, 'a') as f:
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"[{timestamp}] ERROR LOGGING: {str(e)}, Original message: {message}\n")
        except:
            pass


@shared_task
def run_scheduled_backups():
    file_log("Checking for scheduled backups...")
    now = timezone.now()
    
    due_tasks = BackupTask.objects.filter(
        enabled=True,
        next_run__lte=now
    )
    
    file_log(f"Found {due_tasks.count()} tasks due for execution")
    
    for task in due_tasks:
        file_log(f"Scheduling task: {task.name} (ID: {task.id})")
        execute_backup_task.delay(task.id)

@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def execute_backup_task(self, task_id):
    """
    Execute backup for a specific schedule task
    """
    file_log(f"Starting backup for task_id: {task_id}")
    
    try:
        task = BackupTask.objects.get(id=task_id)
        server = task.server
        file_log(f"Task found: {task.name}, server: {server.name}")
        
        # Log storage details
        if task.storage_config:
            file_log(f"Using storage config: {task.storage_config.name}")
            file_log(f"Config type: {task.storage_config.storage_type}")
            file_log(f"Config hostname: {task.storage_config.hostname}")
            file_log(f"Config username: {task.storage_config.username}")
            file_log(f"Config password present: {'Yes' if task.storage_config.password else 'No'}")
            file_log(f"Config path: {task.storage_config.path}")
        
        file_log(f"Task storage type: {task.storage_type}")
        if task.storage_type != 'local':
            file_log(f"Task remote hostname: {task.remote_hostname}")
            file_log(f"Task remote port: {task.remote_port}")
            file_log(f"Task remote username: {task.remote_username}")
            file_log(f"Task remote password present: {'Yes' if task.remote_password else 'No'}")
            file_log(f"Task remote path: {task.remote_path}")

        # Check if there's already a pending backup for this task
        existing_pending = BackupHistory.objects.filter(
            task=task,
            status='pending'
        ).exists()
        
        # If there's already a pending backup, abort
        if existing_pending:
            file_log(f"Skipping task {task_id} - already has a pending backup")
            return
        
        # Check if we've run this task recently (within last 30 seconds)
        recent_backup = BackupHistory.objects.filter(
            task=task,
            started_at__gte=timezone.now() - datetime.timedelta(seconds=30)
        ).exists()
        
        if recent_backup:
            file_log(f"Skipping task {task_id} - recently executed (within last 30 seconds)")
            return

        # Make sure storage_config values are synced to task fields
        if task.storage_config:
            file_log("Syncing storage_config values to task fields")
            # This is critical - make sure remote settings are properly set from storage_config
            task.storage_type = task.storage_config.storage_type
            task.remote_hostname = task.storage_config.hostname
            task.remote_port = task.storage_config.port
            task.remote_username = task.storage_config.username
            # Only set password if it's not already set in task
            if task.storage_config.password and not task.remote_password:
                task.remote_password = task.storage_config.password
            task.remote_path = task.storage_config.path or task.remote_path
            task.save()
            
            # Log the values after syncing
            file_log(f"After sync - Task storage type: {task.storage_type}")
            file_log(f"After sync - Task remote hostname: {task.remote_hostname}")
            file_log(f"After sync - Task remote port: {task.remote_port}")
            file_log(f"After sync - Task remote username: {task.remote_username}")
            file_log(f"After sync - Task remote password present: {'Yes' if task.remote_password else 'No'}")
            file_log(f"After sync - Task remote path: {task.remote_path}")

        history = BackupHistory.objects.create(
            server=server,
            task=task,
            status='pending'
        )
        file_log(f"Created history entry: {history.id}")
        
        try:
            # Execute backup
            file_log("Creating backup service...")
            backup_service = BackupService(server.id)
            file_log("Executing backup...")
            result = backup_service.execute_backup(task)
            file_log(f"Backup result success: {result.get('success', False)}")
            file_log(f"Backup result message: {result.get('message', '')}")
            file_log(f"Backup result path: {result.get('path', '')}")
            
            if result['success']:
                # Store backup to selected storage
                file_log(f"Backup successful, uploading to {task.storage_type} storage...")
                storage_result = StorageService.store_backup(result['path'], task)
                file_log(f"Storage result success: {storage_result.get('success', False)}")
                file_log(f"Storage result message: {storage_result.get('message', '')}")
                
                if storage_result.get('success', False):
                    # Update history with success
                    file_log("Storage successful, updating history...")
                    history.completed_at = timezone.now()
                    history.status = 'success'
                    history.file_path = storage_result.get('path', result['path'])
                    history.file_size = os.path.getsize(result['path'])
                    history.description = storage_result.get('message', '')
                    history.save()
                    file_log("History updated with success")
                else:
                    # Storage error
                    file_log(f"Storage failed: {storage_result.get('message', 'Unknown error')}")
                    history.completed_at = timezone.now()
                    history.status = 'error'
                    history.error_message = storage_result.get('message', 'Unknown storage error')
                    history.save()
                    file_log("History updated with storage error")
            else:
                # Backup error
                file_log(f"Backup failed: {result.get('message', 'Unknown error')}")
                history.completed_at = timezone.now()
                history.status = 'error'
                history.error_message = result.get('message', 'Unknown backup error')
                history.save()
                file_log("History updated with backup error")
            
            # Update task
            file_log("Updating task execution info...")
            task.last_run = timezone.now()
            task._calculate_next_run()
            task.save()
            file_log(f"Task updated, next run: {task.next_run}")

            # Clean up old backups
            file_log(f"Cleaning up old backups, retain count: {task.retain_count}")
            _cleanup_old_backups(server.id, task.retain_count)
            
            # Send notifications if needed
            if task.email_notification and task.email_address:
                file_log(f"Sending email notification to {task.email_address}")
                _send_backup_notification(task, history, result)
                
        except Exception as e:
            error_msg = f"BACKUP ERROR: {str(e)}"
            stack_trace = traceback.format_exc()
            file_log(error_msg)
            file_log(stack_trace)
            
            history.status = 'error'
            history.error_message = f"{error_msg}\n{stack_trace}"
            history.completed_at = timezone.now()
            history.save()
            file_log("History updated with execution error")
            
    except Exception as e:
        error_msg = f"MAIN TASK ERROR: {str(e)}"
        stack_trace = traceback.format_exc()
        file_log(error_msg)
        file_log(stack_trace)
        
        # Retry in case of database lock or similar
        file_log(f"Retrying task in 30 seconds, attempt {self.request.retries + 1}")
        self.retry(exc=e, countdown=30)

def _cleanup_old_backups(server_id, retain_count):
    """
    Remove old backups exceeding the retain count
    """
    file_log(f"Running cleanup for server {server_id}, retain count: {retain_count}")
    
    if retain_count <= 0:
        file_log("Retain count is 0 or negative, skipping cleanup")
        return 
        
    # Get successful backups for this server, ordered by completion time (newest first)
    history_entries = BackupHistory.objects.filter(
        server_id=server_id,
        status='success'
    ).order_by('-completed_at')
    
    file_log(f"Found {history_entries.count()} successful backups for this server")
    
    # If we have more backups than the retain count
    if history_entries.count() > retain_count:
        file_log(f"Need to remove {history_entries.count() - retain_count} oldest backups")
        # For each entry that exceeds our retain count
        for entry in history_entries[retain_count:]:
            try:
                file_log(f"Processing entry ID: {entry.id}, date: {entry.completed_at}")
                # If the file exists, delete it
                if entry.file_path and os.path.exists(entry.file_path):
                    file_log(f"Deleting file: {entry.file_path}")
                    os.remove(entry.file_path)
                    file_log("File deleted successfully")
                else:
                    file_log(f"File not found or path is empty: {entry.file_path}")
                
                # Also delete the database entry to fully clean up
                file_log(f"Deleting history entry from database: {entry.id}")
                entry.delete()
                file_log("Entry deleted successfully")
                
            except Exception as e:
                file_log(f"Error while deleting old backup: {str(e)}")
                file_log(traceback.format_exc())

def _send_backup_notification(task, history, result):
    """
    Send email notification about backup result
    """
    file_log(f"Preparing email notification for task: {task.name}")
    
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
    
    try:
        file_log(f"Sending email from {settings.DEFAULT_FROM_EMAIL} to {task.email_address}")
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[task.email_address],
            fail_silently=True
        )
        file_log("Email sent successfully")
    except Exception as e:
        file_log(f"Error sending email: {str(e)}")

@shared_task
def restore_backup_task(backup_id, history_id):
    """
    Restore database from backup
    """
    file_log(f"Starting restore of backup ID: {backup_id}, history ID: {history_id}")
    
    try:
        backup = BackupHistory.objects.get(id=backup_id)
        history = BackupHistory.objects.get(id=history_id)
        server = backup.server
        
        file_log(f"Found backup for server: {server.name}")
        file_log(f"Backup file: {backup.file_path}")
        
        if not backup.file_path or not os.path.exists(backup.file_path):
            error_msg = "Backup file does not exist"
            file_log(f"ERROR: {error_msg}")
            raise FileNotFoundError(error_msg)
        
        file_log(f"Using connection type: {server.connection_type}")
        
        if server.connection_type == 'direct':
            file_log("Performing direct restore")
            result = _restore_direct(server, backup.file_path)
        elif server.connection_type == 'ssh':
            file_log("Performing SSH tunnel restore")
            result = _restore_ssh_tunnel(server, backup.file_path)
        else:
            error_msg = f"Unsupported connection type: {server.connection_type}"
            file_log(f"ERROR: {error_msg}")
            raise ValueError(error_msg)
        
        history.completed_at = timezone.now()
        history.status = 'success' if result['success'] else 'error'
        
        if result['success']:
            file_log("Restore completed successfully")
            history.description += f" - completed successfully"
        else:
            file_log(f"Restore failed: {result.get('message', 'Unknown error')}")
            history.error_message = result.get('message', 'Unknown error')
        
        history.save()
        file_log(f"History updated with status: {history.status}")
        
    except Exception as e:
        file_log(f"ERROR in restore_backup_task: {str(e)}")
        file_log(traceback.format_exc())
        
        try:
            history = BackupHistory.objects.get(id=history_id)
            history.status = 'error'
            history.error_message = str(e)
            history.completed_at = timezone.now()
            history.save()
            file_log("History updated with error status")
        except Exception as history_error:
            file_log(f"Could not update history: {str(history_error)}")

def _restore_direct(server, backup_file):
    """Restore database directly via TCP/IP"""
    file_log(f"Starting direct restore for server: {server.name}")
    file_log(f"Using backup file: {backup_file}")
    
    try:
        # Check if MySQL client is installed
        try:
            file_log("Checking if mysql client is installed")
            subprocess.run(['which', 'mysql'], check=True, capture_output=True)
            file_log("MySQL client found")
        except subprocess.CalledProcessError:
            error_msg = 'Error: mysql is not installed. Install MySQL client on the server.'
            file_log(f"ERROR: {error_msg}")
            return {
                'success': False,
                'message': error_msg
            }
        
        # Build command for restore
        cmd = [
            'mysql',
            f'--host={server.hostname}',
            f'--port={server.port}',
            f'--user={server.username}',
            f'--password={server.password}',
        ]
        
        if server.database_name:
            cmd.append(server.database_name)
            file_log(f"Restoring specific database: {server.database_name}")
        else:
            file_log("Restoring all databases")
        
        file_log(f"Running MySQL restore command: {' '.join(cmd)}")
        
        with open(backup_file, 'rb') as f:
            result = subprocess.run(
                cmd,
                stdin=f,
                capture_output=True,
                text=True
            )
        
        if result.returncode == 0:
            file_log("Restore command completed successfully")
            return {
                'success': True,
                'message': 'Backup restored successfully'
            }
        else:
            error_msg = f'Error during restore: {result.stderr}'
            file_log(f"ERROR: {error_msg}")
            return {
                'success': False,
                'message': error_msg
            }
    except Exception as e:
        error_msg = f'Restore error: {str(e)}'
        file_log(f"ERROR: {error_msg}")
        file_log(traceback.format_exc())
        return {
            'success': False,
            'message': error_msg
        }

def _restore_ssh_tunnel(server, backup_file):
    """Restore database through SSH tunnel"""
    file_log(f"Starting SSH tunnel restore for server: {server.name}")
    file_log(f"Using backup file: {backup_file}")
    
    try:
        # Validate SSH connection info
        if not all([server.ssh_hostname, server.ssh_port, server.ssh_username]):
            error_msg = 'Missing SSH data: hostname, port or username'
            file_log(f"ERROR: {error_msg}")
            return {
                'success': False,
                'message': error_msg
            }
        
        if not server.ssh_password and not server.ssh_key_file:
            error_msg = 'No SSH authentication method (password or key)'
            file_log(f"ERROR: {error_msg}")
            return {
                'success': False,
                'message': error_msg
            }
            
        # Check if MySQL client is installed
        try:
            file_log("Checking if mysql client is installed")
            subprocess.run(['which', 'mysql'], check=True, capture_output=True)
            file_log("MySQL client found")
        except subprocess.CalledProcessError:
            error_msg = 'Error: mysql is not installed. Install MySQL client on the server.'
            file_log(f"ERROR: {error_msg}")
            return {
                'success': False,
                'message': error_msg
            }
        
        # Setup SSH tunnel configuration
        file_log(f"Setting up SSH tunnel to {server.ssh_hostname}:{server.ssh_port}")
        file_log(f"SSH username: {server.ssh_username}")
        file_log(f"SSH authentication: {'Password' if server.ssh_password else 'Key'}")
        
        ssh_config = {
            'ssh_address_or_host': (server.ssh_hostname, int(server.ssh_port)),
            'ssh_username': server.ssh_username,
            'remote_bind_address': (server.hostname, int(server.port))
        }
        
        if server.ssh_password:
            ssh_config['ssh_password'] = server.ssh_password
        elif server.ssh_key_file and server.ssh_key_file.path:
            ssh_config['ssh_pkey'] = server.ssh_key_file.path
            file_log(f"Using SSH key file: {server.ssh_key_file.path}")
            
        file_log("Opening SSH tunnel")
        with sshtunnel.SSHTunnelForwarder(**ssh_config) as tunnel:
            file_log(f"SSH tunnel established, local port: {tunnel.local_bind_port}")
            
            cmd = [
                'mysql',
                '--host=127.0.0.1',
                f'--port={tunnel.local_bind_port}',
                f'--user={server.username}',
                f'--password={server.password}',
            ]
            
            if server.database_name:
                cmd.append(server.database_name)
                file_log(f"Restoring specific database: {server.database_name}")
            else:
                file_log("Restoring all databases")
            
            file_log(f"Running MySQL restore command through tunnel: {' '.join(cmd)}")
            
            with open(backup_file, 'rb') as f:
                result = subprocess.run(
                    cmd,
                    stdin=f,
                    capture_output=True,
                    text=True
                )
            
            if result.returncode == 0:
                file_log("Restore command completed successfully")
                return {
                    'success': True,
                    'message': 'Backup successfully restored through SSH tunnel'
                }
            else:
                error_msg = f'Error during restore: {result.stderr}'
                file_log(f"ERROR: {error_msg}")
                return {
                    'success': False,
                    'message': error_msg
                }
                
    except Exception as e:
        error_msg = f'SSH tunnel error: {str(e)}'
        file_log(f"ERROR: {error_msg}")
        file_log(traceback.format_exc())
        return {
            'success': False,
            'message': error_msg
        }