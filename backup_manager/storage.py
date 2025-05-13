# backup_manager/storage.py - nowy plik

import os
import ftplib
import paramiko
from django.conf import settings

class StorageService:
    """Service for storing backups in different locations"""
    
    @staticmethod
    def store_backup(backup_file_path, task):
        """Store backup file according to task configuration"""
        if task.storage_type == 'local':
            # Local storage is default, file is already in the right place
            return {
                'success': True,
                'message': 'File stored in local storage',
                'path': backup_file_path
            }
        elif task.storage_type == 'ftp':
            return StorageService._store_ftp(backup_file_path, task)
        elif task.storage_type == 'sftp':
            return StorageService._store_sftp(backup_file_path, task)
        else:
            return {
                'success': False,
                'message': f'Unsupported storage type: {task.storage_type}'
            }
    
    @staticmethod
    def _store_ftp(backup_file_path, task):
        """Upload file to FTP server"""
        try:
            # Validate task configuration
            if not all([task.remote_hostname, task.remote_username, task.remote_password]):
                return {
                    'success': False,
                    'message': 'Missing FTP configuration: hostname, username or password'
                }
            
            # Connect to FTP server
            ftp = ftplib.FTP()
            ftp.connect(
                host=task.remote_hostname, 
                port=task.remote_port or 21
            )
            ftp.login(
                user=task.remote_username, 
                passwd=task.remote_password
            )
            
            # Navigate to directory if specified
            if task.remote_path:
                try:
                    ftp.cwd(task.remote_path)
                except ftplib.error_perm:
                    # Try to create directory if it doesn't exist
                    dirs = task.remote_path.split('/')
                    for d in dirs:
                        if d:
                            try:
                                ftp.cwd(d)
                            except ftplib.error_perm:
                                ftp.mkd(d)
                                ftp.cwd(d)
            
            # Upload file
            filename = os.path.basename(backup_file_path)
            with open(backup_file_path, 'rb') as file:
                ftp.storbinary(f'STOR {filename}', file)
            
            ftp.quit()
            
            return {
                'success': True,
                'message': f'File uploaded to FTP server {task.remote_hostname}',
                'path': backup_file_path  # Return the local path for reference
            }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'FTP error: {str(e)}'
            }
    
    @staticmethod
    def _store_sftp(backup_file_path, task):
        """Upload file to SFTP server"""
        try:
            # Validate task configuration
            if not all([task.remote_hostname, task.remote_username]):
                return {
                    'success': False,
                    'message': 'Missing SFTP configuration: hostname or username'
                }
            
            if not task.remote_password and not task.remote_key_file:
                return {
                    'success': False,
                    'message': 'No SFTP authentication method provided (password or key file)'
                }
            
            # Create SSH client
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect to server
            connect_params = {
                'hostname': task.remote_hostname,
                'port': task.remote_port or 22,
                'username': task.remote_username,
            }
            
            if task.remote_password:
                connect_params['password'] = task.remote_password
            elif task.remote_key_file and task.remote_key_file.path:
                connect_params['key_filename'] = task.remote_key_file.path
            
            ssh_client.connect(**connect_params)
            
            # Open SFTP session
            sftp = ssh_client.open_sftp()
            
            # Create directory if needed
            if task.remote_path:
                try:
                    sftp.stat(task.remote_path)
                except FileNotFoundError:
                    # Path doesn't exist, try to create it
                    current_path = ''
                    for d in task.remote_path.split('/'):
                        if d:
                            current_path += f'/{d}'
                            try:
                                sftp.stat(current_path)
                            except FileNotFoundError:
                                sftp.mkdir(current_path)
            
            # Upload file
            filename = os.path.basename(backup_file_path)
            remote_file_path = f"{task.remote_path}/{filename}" if task.remote_path else filename
            sftp.put(backup_file_path, remote_file_path)
            
            # Close connections
            sftp.close()
            ssh_client.close()
            
            return {
                'success': True,
                'message': f'File uploaded to SFTP server {task.remote_hostname}',
                'path': backup_file_path  # Return the local path for reference
            }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'SFTP error: {str(e)}'
            }