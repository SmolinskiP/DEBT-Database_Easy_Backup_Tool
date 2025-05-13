import os
import paramiko
import mysql.connector
from mysql.connector import Error as MySQLError
import subprocess
import datetime
import sshtunnel
from django.conf import settings
from .models import DatabaseServer
import socket

class BackupService:
    """Service for performing database backups"""
    
    def __init__(self, server_id):
        self.server = DatabaseServer.objects.get(id=server_id)
        self.timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        self.backup_dir = settings.BACKUP_DIR
        
    def execute_backup(self):
        """Executes backup depending on connection type"""
        if self.server.connection_type == 'direct':
            return self._direct_backup()
        elif self.server.connection_type == 'ssh':
            return self._ssh_tunnel_backup()
        else:
            raise ValueError(f"Unsupported connection type: {self.server.connection_type}")
    
    def _direct_backup(self):
        """Performs direct database backup through TCP/IP"""
        try:
            # Test connection to database
            conn_params = {
                'host': self.server.hostname,
                'port': self.server.port,
                'user': self.server.username,
                'password': self.server.password,
            }
            
            # Dodaj bazę danych do parametrów połączenia, jeśli określona
            if self.server.database_name:
                conn_params['database'] = self.server.database_name
                
            conn = mysql.connector.connect(**conn_params)
            conn.close()
            
            # Backup filename
            backup_filename = f"{self.server.name}_{self.timestamp}.sql"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            # Execute mysqldump
            cmd = [
                'mysqldump',
                f'--host={self.server.hostname}',
                f'--port={self.server.port}',
                f'--user={self.server.username}',
                f'--password={self.server.password}',
            ]
            
            # Dodaj opcję wyboru bazy lub wszystkich baz
            if self.server.database_name:
                cmd.append(self.server.database_name)
            else:
                cmd.append('--all-databases')
            
            # Ścieżka do pliku wyjściowego
            cmd.append(f'--result-file={backup_path}')
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'path': backup_path,
                    'message': 'Backup completed successfully'
                }
            else:
                return {
                    'success': False,
                    'message': f'Backup execution error: {result.stderr}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Connection error: {str(e)}'
            }
    
    def _ssh_tunnel_backup(self):
        """Performs backup through SSH tunnel"""
        try:
            # Sprawdź dane SSH
            if not all([self.server.ssh_hostname, self.server.ssh_port, self.server.ssh_username]):
                return {
                    'success': False,
                    'message': 'Brakujące dane SSH: hostname, port lub username'
                }
            
            # Sprawdź czy posiadamy hasło lub klucz SSH
            if not self.server.ssh_password and not self.server.ssh_key_file:
                return {
                    'success': False,
                    'message': 'Brak metody uwierzytelniania SSH (hasło lub klucz)'
                }
            
            # Nazwa pliku backupu
            backup_filename = f"{self.server.name}_{self.timestamp}.sql"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            # Tworzenie tunelu SSH
            ssh_config = {
                'ssh_address_or_host': (self.server.ssh_hostname, int(self.server.ssh_port)),
                'ssh_username': self.server.ssh_username,
                'remote_bind_address': (self.server.hostname, int(self.server.port))
            }
            
            # Dodawanie metody uwierzytelniania
            if self.server.ssh_password:
                ssh_config['ssh_password'] = self.server.ssh_password
            elif self.server.ssh_key_file and self.server.ssh_key_file.path:
                ssh_config['ssh_pkey'] = self.server.ssh_key_file.path
                
            # Utwórz tunel SSH
            with sshtunnel.SSHTunnelForwarder(**ssh_config) as tunnel:
                # Wykonaj backup przez tunel - mysqldump łączy się z lokalnym portem
                cmd = [
                    'mysqldump',
                    '--host=127.0.0.1',
                    f'--port={tunnel.local_bind_port}',
                    f'--user={self.server.username}',
                    f'--password={self.server.password}',
                ]
                
                # Dodaj opcję wyboru bazy lub wszystkich baz
                if self.server.database_name:
                    cmd.append(self.server.database_name)
                else:
                    cmd.append('--all-databases')
                
                # Dodaj przydatne opcje dla dużych baz
                cmd.extend([
                    '--single-transaction',    # Spójny backup bez blokowania tabel
                    '--quick',                 # Mniejsze użycie pamięci dla dużych tabel
                    '--compress',              # Kompresja danych między klientem a serwerem
                    '--routines',              # Uwzględnij procedury i funkcje
                    '--triggers',              # Uwzględnij triggery
                    '--events'                 # Uwzględnij wydarzenia
                ])
                
                # Ścieżka do pliku wyjściowego
                cmd.append(f'--result-file={backup_path}')
                
                # Uruchom mysqldump
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    return {
                        'success': True,
                        'path': backup_path,
                        'message': 'Backup completed successfully through SSH tunnel'
                    }
                else:
                    return {
                        'success': False,
                        'message': f'Backup execution error: {result.stderr}'
                    }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'SSH tunnel error: {str(e)}'
            }

class DatabaseConnectionService:
    """Service for testing and managing database connections"""
    
    @staticmethod
    def test_connection(server_id=None, connection_data=None):
        """
        Tests connection to a database.
        Can take an existing server ID or connection data as a dictionary.
        """
        if server_id:
            try:
                server = DatabaseServer.objects.get(id=server_id)
                connection_type = server.connection_type
                hostname = server.hostname
                port = server.port
                username = server.username
                password = server.password
                ssh_hostname = server.ssh_hostname
                ssh_port = server.ssh_port
                ssh_username = server.ssh_username
                ssh_password = server.ssh_password
            except DatabaseServer.DoesNotExist:
                return {
                    'success': False,
                    'message': 'Database server does not exist'
                }
        elif connection_data:
            connection_type = connection_data.get('connection_type')
            hostname = connection_data.get('hostname')
            port = connection_data.get('port')
            username = connection_data.get('username')
            password = connection_data.get('password')
            ssh_hostname = connection_data.get('ssh_hostname')
            ssh_port = connection_data.get('ssh_port')
            ssh_username = connection_data.get('ssh_username')
            ssh_password = connection_data.get('ssh_password')
        else:
            return {
                'success': False,
                'message': 'No connection data provided'
            }
        
        # Test connection based on type
        if connection_type == 'direct':
            return DatabaseConnectionService._test_direct_connection(
                hostname, port, username, password
            )
        elif connection_type == 'ssh':
            return DatabaseConnectionService._test_ssh_connection(
                hostname, port, username, password,
                ssh_hostname, ssh_port, ssh_username, ssh_password
            )
        else:
            return {
                'success': False,
                'message': f'Unsupported connection type: {connection_type}'
            }
    
    @staticmethod
    def _test_direct_connection(hostname, port, username, password):
        """Tests direct TCP/IP connection to database"""
        try:
            # First check if port is open
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((hostname, int(port)))
            sock.close()
            
            if result != 0:
                return {
                    'success': False,
                    'message': f'Port {port} is closed on server {hostname}'
                }
            
            # Try to connect to database
            conn = mysql.connector.connect(
                host=hostname,
                port=int(port),
                user=username,
                password=password,
                connection_timeout=10
            )
            
            # Check MySQL server version
            cursor = conn.cursor()
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            return {
                'success': True,
                'message': f'Connection established successfully. Server version: {version}'
            }
            
        except MySQLError as e:
            return {
                'success': False,
                'message': f'MySQL Error: {str(e)}'
            }
        except socket.error as e:
            return {
                'success': False,
                'message': f'Connection error: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Unexpected error: {str(e)}'
            }
    
    @staticmethod
    def _test_ssh_connection(db_hostname, db_port, db_username, db_password, 
                            ssh_hostname, ssh_port, ssh_username, ssh_password):
        """Tests database connection through SSH tunnel"""
        try:
            # Check if we can connect to SSH server
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            try:
                ssh_client.connect(
                    hostname=ssh_hostname,
                    port=int(ssh_port),
                    username=ssh_username,
                    password=ssh_password,
                    timeout=10
                )
                ssh_client.close()
            except Exception as e:
                return {
                    'success': False,
                    'message': f'SSH connection error: {str(e)}'
                }
            
            # Try to open SSH tunnel and connect to database
            with sshtunnel.SSHTunnelForwarder(
                (ssh_hostname, int(ssh_port)),
                ssh_username=ssh_username,
                ssh_password=ssh_password,
                remote_bind_address=(db_hostname, int(db_port))
            ) as tunnel:
                conn = mysql.connector.connect(
                    host='127.0.0.1',
                    port=tunnel.local_bind_port,
                    user=db_username,
                    password=db_password,
                    connection_timeout=10
                )
                
                # Check MySQL server version
                cursor = conn.cursor()
                cursor.execute("SELECT VERSION()")
                version = cursor.fetchone()[0]
                cursor.close()
                conn.close()
                
                return {
                    'success': True,
                    'message': f'Connection through SSH established successfully. Server version: {version}'
                }
                
        except MySQLError as e:
            return {
                'success': False,
                'message': f'MySQL Error: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Unexpected error: {str(e)}'
            }