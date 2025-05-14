# backup_manager/storage.py

import os
import ftplib
import paramiko
from django.conf import settings
import logging
import datetime  # dodany import dla timestampów

# Bezpośredni zapis do pliku - niezależny od konfiguracji Django
def direct_log(message):
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

class StorageService:
    """Service for storing backups in different locations"""
    
    @staticmethod
    def store_backup(backup_file_path, task):
        """Store backup file according to task configuration"""
        direct_log(f"StorageService.store_backup called for file: {backup_file_path}")
        direct_log(f"Task: {task.name}, storage type: {task.storage_type}")

        if task.storage_config:
            direct_log(f"Using storage config: {task.storage_config.name}")
        else:
            direct_log(f"Using direct storage settings")
            
        if task.storage_type != 'local':
            direct_log(f"Remote settings: {task.remote_hostname}:{task.remote_port} (user: {task.remote_username})")
            direct_log(f"Remote path: {task.remote_path}")
            direct_log(f"Remote password set: {'Yes' if task.remote_password else 'No'}")

        if task.storage_type == 'local':
            # Local storage is default, file is already in the right place
            direct_log("Using local storage, file is already in place")
            return {
                'success': True,
                'message': 'File stored in local storage',
                'path': backup_file_path
            }
        elif task.storage_type == 'ftp':
            return StorageService._store_ftp(backup_file_path, task)
        elif task.storage_type == 'sftp':
            return StorageService._store_sftp(backup_file_path, task)
        elif task.storage_type == 'gdrive':
            return StorageService._store_gdrive(backup_file_path, task)
        else:
            error_msg = f'Unsupported storage type: {task.storage_type}'
            direct_log(f"ERROR: {error_msg}")
            return {
                'success': False,
                'message': error_msg
            }
    
    @staticmethod
    def _store_ftp(backup_file_path, task):
        """Upload file to FTP server"""
        try:
            direct_log(f"Starting FTP upload for file: {backup_file_path}")
            
            # Validate task configuration
            missing_fields = []
            if not task.remote_hostname:
                missing_fields.append('hostname')
            if not task.remote_username:
                missing_fields.append('username')
            if not task.remote_password:
                missing_fields.append('password')
                
            if missing_fields:
                error_msg = f"Missing FTP configuration: {', '.join(missing_fields)}"
                direct_log(f"ERROR: {error_msg}")
                return {
                    'success': False,
                    'message': error_msg
                }
            
            # Connect to FTP server
            direct_log(f"Connecting to FTP server: {task.remote_hostname}:{task.remote_port or 21}")
            ftp = ftplib.FTP()
            try:
                ftp.connect(
                    host=task.remote_hostname, 
                    port=task.remote_port or 21,
                    timeout=30  # Dodajemy timeout
                )
                direct_log("Connection established")
            except Exception as e:
                error_msg = f"Failed to connect to FTP server: {str(e)}"
                direct_log(f"ERROR: {error_msg}")
                return {
                    'success': False,
                    'message': error_msg
                }
            
            # Login to FTP server
            direct_log(f"Logging in with user: {task.remote_username}")
            try:
                ftp.login(
                    user=task.remote_username, 
                    passwd=task.remote_password
                )
                direct_log("FTP login successful")
            except ftplib.error_perm as e:
                error_msg = f"FTP login failed: {str(e)}"
                direct_log(f"ERROR: {error_msg}")
                return {
                    'success': False,
                    'message': error_msg
                }
            
            # Navigate to directory if specified
            if task.remote_path:
                try:
                    direct_log(f"Changing to directory: {task.remote_path}")
                    ftp.cwd(task.remote_path)
                    direct_log("Directory changed successfully")
                except ftplib.error_perm as e:
                    direct_log(f"Directory does not exist: {task.remote_path}, error: {str(e)}")
                    direct_log("Attempting to create directories...")
                    
                    # Try to create directory if it doesn't exist
                    dirs = task.remote_path.split('/')
                    current_dir = ""
                    
                    for d in dirs:
                        if d:
                            try:
                                direct_log(f"Trying to change to subdirectory: {d}")
                                ftp.cwd(d)
                                current_dir += f"/{d}"
                                direct_log(f"Changed to existing subdirectory: {d}")
                            except ftplib.error_perm as dir_error:
                                try:
                                    direct_log(f"Creating subdirectory: {d}")
                                    ftp.mkd(d)
                                    ftp.cwd(d)
                                    current_dir += f"/{d}"
                                    direct_log(f"Created and changed to subdirectory: {d}")
                                except ftplib.error_perm as mkdir_error:
                                    error_msg = f"Failed to create directory {d}: {str(mkdir_error)}"
                                    direct_log(f"ERROR: {error_msg}")
                                    return {
                                        'success': False,
                                        'message': error_msg
                                    }
            
            # List current directory to verify
            try:
                file_list = ftp.nlst()
                direct_log(f"Current directory contents: {', '.join(file_list) if file_list else 'empty'}")
            except:
                direct_log("Could not list directory contents")
            
            # Upload file
            filename = os.path.basename(backup_file_path)
            direct_log(f"Uploading file: {filename}")
            
            try:
                with open(backup_file_path, 'rb') as file:
                    direct_log("File opened, starting upload...")
                    ftp.storbinary(f'STOR {filename}', file)
                direct_log("File uploaded successfully")
            except Exception as e:
                error_msg = f"File upload failed: {str(e)}"
                direct_log(f"ERROR: {error_msg}")
                return {
                    'success': False,
                    'message': error_msg
                }
            
            # Verify file was uploaded
            try:
                file_list = ftp.nlst()
                if filename in file_list:
                    direct_log(f"Verified file {filename} exists in directory")
                else:
                    direct_log(f"WARNING: File {filename} not found in directory after upload")
            except:
                direct_log("Could not verify file upload")
                
            ftp.quit()
            direct_log("FTP connection closed")
            
            storage_path = f"FTP: {task.remote_hostname}" + (f"/{task.remote_path}" if task.remote_path else "")
            
            return {
                'success': True,
                'message': f'File uploaded to FTP server {task.remote_hostname}' + 
                           (f' in {task.remote_path}' if task.remote_path else ''),
                'path': backup_file_path,  # Return the local path for reference
                'storage_path': storage_path  # Add the remote path for reference
            }
        
        except Exception as e:
            import traceback
            error_message = f'FTP error: {str(e)}'
            stack_trace = traceback.format_exc()
            direct_log(f"ERROR: {error_message}")
            direct_log(f"TRACEBACK: {stack_trace}")
            return {
                'success': False,
                'message': error_message
            }
    
    @staticmethod
    def _store_sftp(backup_file_path, task):
        """Upload file to SFTP server"""
        try:
            direct_log(f"Starting SFTP upload for file: {backup_file_path}")
            
            # Validate task configuration
            missing_fields = []
            if not task.remote_hostname:
                missing_fields.append('hostname')
            if not task.remote_username:
                missing_fields.append('username')
            if not (task.remote_password or task.remote_key_file):
                missing_fields.append('password or key file')
                
            if missing_fields:
                error_msg = f"Missing SFTP configuration: {', '.join(missing_fields)}"
                direct_log(f"ERROR: {error_msg}")
                return {
                    'success': False,
                    'message': error_msg
                }
            
            # Create SSH client
            direct_log("Creating SSH client")
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect to server
            connect_params = {
                'hostname': task.remote_hostname,
                'port': task.remote_port or 22,
                'username': task.remote_username,
                'timeout': 30  # Add timeout
            }
            
            if task.remote_password:
                connect_params['password'] = task.remote_password
                direct_log("Using password authentication")
            elif task.remote_key_file and task.remote_key_file.path:
                connect_params['key_filename'] = task.remote_key_file.path
                direct_log(f"Using key file authentication: {task.remote_key_file.path}")
            
            direct_log(f"Connecting to SFTP server: {task.remote_hostname}:{task.remote_port or 22}")
            try:
                ssh_client.connect(**connect_params)
                direct_log("SSH connection established")
            except Exception as e:
                error_msg = f"SSH connection failed: {str(e)}"
                direct_log(f"ERROR: {error_msg}")
                return {
                    'success': False,
                    'message': error_msg
                }
            
            # Open SFTP session
            direct_log("Opening SFTP session")
            sftp = ssh_client.open_sftp()
            
            # Create directory if needed
            if task.remote_path:
                try:
                    direct_log(f"Checking if path exists: {task.remote_path}")
                    sftp.stat(task.remote_path)
                    direct_log("Path exists")
                except FileNotFoundError:
                    direct_log(f"Path does not exist: {task.remote_path}")
                    direct_log("Creating directories...")
                    
                    # Path doesn't exist, try to create it
                    current_path = ''
                    for d in task.remote_path.split('/'):
                        if d:
                            current_path += f'/{d}'
                            try:
                                direct_log(f"Checking if directory exists: {current_path}")
                                sftp.stat(current_path)
                                direct_log(f"Directory exists: {current_path}")
                            except FileNotFoundError:
                                try:
                                    direct_log(f"Creating directory: {current_path}")
                                    sftp.mkdir(current_path)
                                    direct_log(f"Created directory: {current_path}")
                                except Exception as dir_error:
                                    error_msg = f"Failed to create directory {current_path}: {str(dir_error)}"
                                    direct_log(f"ERROR: {error_msg}")
                                    sftp.close()
                                    ssh_client.close()
                                    return {
                                        'success': False,
                                        'message': error_msg
                                    }
            
            # Upload file
            filename = os.path.basename(backup_file_path)
            remote_file_path = f"{task.remote_path}/{filename}" if task.remote_path else filename
            direct_log(f"Uploading file to: {remote_file_path}")
            
            try:
                sftp.put(backup_file_path, remote_file_path)
                direct_log("File uploaded successfully")
            except Exception as e:
                error_msg = f"File upload failed: {str(e)}"
                direct_log(f"ERROR: {error_msg}")
                sftp.close()
                ssh_client.close()
                return {
                    'success': False,
                    'message': error_msg
                }
            
            # Verify file was uploaded
            try:
                direct_log(f"Verifying file: {remote_file_path}")
                sftp.stat(remote_file_path)
                direct_log("File verified on remote server")
            except Exception as e:
                direct_log(f"WARNING: Could not verify file: {str(e)}")
            
            # Close connections
            direct_log("Closing SFTP session")
            sftp.close()
            direct_log("Closing SSH connection")
            ssh_client.close()
            
            storage_path = f"SFTP: {task.remote_hostname}" + (f"/{task.remote_path}" if task.remote_path else "")
            
            return {
                'success': True,
                'message': f'File uploaded to SFTP server {task.remote_hostname}' + 
                           (f' in {task.remote_path}' if task.remote_path else ''),
                'path': backup_file_path,  # Return the local path for reference
                'storage_path': storage_path  # Add the remote path for reference
            }
        
        except Exception as e:
            import traceback
            error_message = f'SFTP error: {str(e)}'
            stack_trace = traceback.format_exc()
            direct_log(f"ERROR: {error_message}")
            direct_log(f"TRACEBACK: {stack_trace}")
            return {
                'success': False,
                'message': error_message
            }

    @staticmethod
    def _store_gdrive(backup_file_path, task):
        """Upload file to Google Drive"""
        try:
            direct_log(f"Starting Google Drive upload for file: {backup_file_path}")
            
            if not task.storage_config or not task.storage_config.gdrive_credentials_file:
                error_msg = "Missing Google Drive credentials file"
                direct_log(f"ERROR: {error_msg}")
                return {
                    'success': False,
                    'message': error_msg
                }
                
            filename = os.path.basename(backup_file_path)
            
            # Initialize Google Drive API client
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
            from google.oauth2 import service_account
            
            creds_path = task.storage_config.gdrive_credentials_file.path
            direct_log(f"Using credentials file: {creds_path}")
            
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    creds_path, scopes=['https://www.googleapis.com/auth/drive']
                )
                drive_service = build('drive', 'v3', credentials=credentials)
                direct_log("Google Drive API client initialized")
            except Exception as e:
                error_msg = f"Failed to initialize Google Drive client: {str(e)}"
                direct_log(f"ERROR: {error_msg}")
                return {
                    'success': False,
                    'message': error_msg
                }
                
            # Prepare file metadata and media
            file_metadata = {
                'name': filename,
                'mimeType': 'application/octet-stream'
            }
            
            # Add to folder if folder ID provided
            if task.storage_config.gdrive_folder_id:
                direct_log(f"Using folder ID: {task.storage_config.gdrive_folder_id}")
                file_metadata['parents'] = [task.storage_config.gdrive_folder_id]
                
            media = MediaFileUpload(
                backup_file_path,
                mimetype='application/octet-stream',
                resumable=True
            )
            
            # Upload file
            direct_log("Starting file upload to Google Drive")
            file = drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,webViewLink'
            ).execute()
            
            direct_log(f"File uploaded successfully, ID: {file.get('id')}")
            
            return {
                'success': True,
                'message': f'File uploaded to Google Drive with ID: {file.get("id")}',
                'path': backup_file_path,
                'storage_path': f"GDrive: {file.get('name')} ({file.get('webViewLink')})"
            }
                
        except Exception as e:
            import traceback
            error_message = f'Google Drive error: {str(e)}'
            stack_trace = traceback.format_exc()
            direct_log(f"ERROR: {error_message}")
            direct_log(f"TRACEBACK: {stack_trace}")
            return {
                'success': False,
                'message': error_message
            }

    @staticmethod
    def get_storage_info(task):
        """Get human-readable storage information for a task"""
        if task.storage_config:
            config = task.storage_config
            if config.storage_type == 'local':
                return "Local storage"
            elif config.storage_type == 'ftp':
                return f"FTP: {config.hostname}" + (f"/{config.path}" if config.path else "")
            elif config.storage_type == 'sftp':
                return f"SFTP: {config.hostname}" + (f"/{config.path}" if config.path else "")
            elif config.storage_type == 'gdrive':  # Dodaj tę obsługę
                folder_id = config.gdrive_folder_id if config.gdrive_folder_id else "root"
                return f"Google Drive: {folder_id}"
        else:
            if task.storage_type == 'local':
                return "Local storage"
            elif task.storage_type == 'ftp':
                return f"FTP: {task.remote_hostname}" + (f"/{task.remote_path}" if task.remote_path else "")
            elif task.storage_type == 'sftp':
                return f"SFTP: {task.remote_hostname}" + (f"/{task.remote_path}" if task.remote_path else "")
            elif task.storage_type == 'gdrive':  # Dodaj tę obsługę
                folder_id = task.gdrive_folder_id if hasattr(task, 'gdrive_folder_id') and task.gdrive_folder_id else "root"
                return f"Google Drive: {folder_id}"
                    
        return "Unknown storage"