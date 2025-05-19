import os
import paramiko
import mysql.connector
from mysql.connector import Error as MySQLError
import psycopg2
from psycopg2 import Error as PostgreSQLError
import subprocess
import datetime
import sshtunnel
from django.conf import settings
from .models import DatabaseServer
import socket

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

class BackupService:
    """Service for performing database backups"""
    
    def __init__(self, server_id):
        self.server = DatabaseServer.objects.get(id=server_id)
        self.timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        self.backup_dir = settings.BACKUP_DIR
        
    def execute_backup(self, task=None):
        """Executes backup depending on connection type"""
        direct_log(f"SERVICES: Schedule name - {task}")
        
        # Handling both old and new connection types
        if self.server.connection_type in ['direct', 'direct_mysql']:
            return self._direct_mysql_backup(task)
        elif self.server.connection_type in ['ssh', 'ssh_mysql']:
            return self._ssh_tunnel_mysql_backup(task)
        elif self.server.connection_type == 'direct_postgresql':
            return self._direct_postgresql_backup(task)
        elif self.server.connection_type == 'ssh_postgresql':
            return self._ssh_tunnel_postgresql_backup(task)
        else:
            raise ValueError(f"Unsupported connection type: {self.server.connection_type}")
    
    def _direct_mysql_backup(self, task=None):
        """Performs direct MySQL database backup through TCP/IP"""
        try:
            # Test connection to database
            conn_params = {
                'host': self.server.hostname,
                'port': self.server.port,
                'user': self.server.username,
                'password': self.server.password,
            }
            
            # Add database to connection parameters if specified
            if self.server.database_name:
                conn_params['database'] = self.server.database_name
                
            conn = mysql.connector.connect(**conn_params)
            conn.close()
            
            # Backup filename with new format: DATETIME_SERVERNAME_SCHEDULENAME.sql
            schedule_name = f"_{task.name}" if task else ""
            backup_filename = f"{self.timestamp}_{self.server.name}{schedule_name}.sql"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            # Execute mysqldump
            cmd = [
                'mysqldump',
                f'--host={self.server.hostname}',
                f'--port={self.server.port}',
                f'--user={self.server.username}',
                f'--password={self.server.password}',
            ]
            
            # Add option to select database or all databases
            if self.server.database_name:
                cmd.append(self.server.database_name)
            else:
                cmd.append('--all-databases')
            
            # Path to output file
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
    
    def _ssh_tunnel_mysql_backup(self, task=None):
        """Performs MySQL backup through SSH tunnel"""
        try:
            # Check SSH data
            if not all([self.server.ssh_hostname, self.server.ssh_port, self.server.ssh_username]):
                return {
                    'success': False,
                    'message': 'Missing SSH data: hostname, port or username'
                }
            
            # Check if we have password or SSH key
            if not self.server.ssh_password and not self.server.ssh_key_file:
                return {
                    'success': False,
                    'message': 'No SSH authentication method (password or key)'
                }
            
            # Backup filename with new format: DATETIME_SERVERNAME_SCHEDULENAME.sql
            schedule_name = f"_{task.name}" if task else ""
            backup_filename = f"{self.timestamp}_{self.server.name}{schedule_name}.sql"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            # Creating SSH tunnel
            ssh_config = {
                'ssh_address_or_host': (self.server.ssh_hostname, int(self.server.ssh_port)),
                'ssh_username': self.server.ssh_username,
                'remote_bind_address': (self.server.hostname, int(self.server.port))
            }
            
            # Adding authentication method
            if self.server.ssh_password:
                ssh_config['ssh_password'] = self.server.ssh_password
            elif self.server.ssh_key_file and self.server.ssh_key_file.path:
                ssh_config['ssh_pkey'] = self.server.ssh_key_file.path
                
            # Create SSH tunnel
            with sshtunnel.SSHTunnelForwarder(**ssh_config) as tunnel:
                # Execute backup through tunnel - mysqldump connects to local port
                cmd = [
                    'mysqldump',
                    '--host=127.0.0.1',
                    f'--port={tunnel.local_bind_port}',
                    f'--user={self.server.username}',
                    f'--password={self.server.password}',
                ]
                
                # Add option to select database or all databases
                if self.server.database_name:
                    cmd.append(self.server.database_name)
                else:
                    cmd.append('--all-databases')
                
                # Add useful options for large databases
                cmd.extend([
                    '--single-transaction',    # Consistent backup without table locks
                    '--quick',                 # Less memory usage for large tables
                    '--compress',              # Data compression between client and server
                    '--routines',              # Include procedures and functions
                    '--triggers',              # Include triggers
                    '--events'                 # Include events
                ])
                
                # Path to output file
                cmd.append(f'--result-file={backup_path}')
                
                # Run mysqldump
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
    
    def _direct_postgresql_backup(self, task=None):
        """Performs direct PostgreSQL database backup through TCP/IP"""
        try:
            # Test connection to database
            conn_params = {
                'host': self.server.hostname,
                'port': self.server.port,
                'user': self.server.username,
                'password': self.server.password,
            }
            
            # Add database to connection parameters if specified
            if self.server.database_name:
                conn_params['dbname'] = self.server.database_name
            else:
                # For PostgreSQL, we need a specific database to connect to
                conn_params['dbname'] = 'postgres'  # Connect to default database
                
            conn = psycopg2.connect(**conn_params)
            conn.close()
            
            # Backup filename
            schedule_name = f"_{task.name}" if task else ""
            backup_filename = f"{self.timestamp}_{self.server.name}{schedule_name}.sql"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            # Set environment variables for pg_dump
            env = os.environ.copy()
            # Add PGPASSWORD env variable for password
            env['PGPASSWORD'] = self.server.password
            
            # Build pg_dump command
            cmd = [
                'pg_dump',
                '-h', self.server.hostname,
                '-p', str(self.server.port),
                '-U', self.server.username,
                '-F', 'p',  # Custom format (compressed)
                '-b',       # Include large objects
                '-v',       # Verbose mode
                '-f', backup_path
            ]
            
            # Add database name
            if self.server.database_name:
                cmd.append(self.server.database_name)
            else:
                # For all databases, we need to use pg_dumpall instead
                cmd = [
                    'pg_dumpall',
                    '-h', self.server.hostname,
                    '-p', str(self.server.port),
                    '-U', self.server.username,
                    '-f', backup_path
                ]
            
            # Execute pg_dump
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'path': backup_path,
                    'message': 'PostgreSQL backup completed successfully'
                }
            else:
                return {
                    'success': False,
                    'message': f'PostgreSQL backup error: {result.stderr}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'PostgreSQL connection error: {str(e)}'
            }
    
    def _ssh_tunnel_postgresql_backup(self, task=None):
        """Performs PostgreSQL backup through SSH tunnel"""
        try:
            # Check SSH data
            if not all([self.server.ssh_hostname, self.server.ssh_port, self.server.ssh_username]):
                return {
                    'success': False,
                    'message': 'Missing SSH data: hostname, port or username'
                }
            
            # Check if we have password or SSH key
            if not self.server.ssh_password and not self.server.ssh_key_file:
                return {
                    'success': False,
                    'message': 'No SSH authentication method (password or key)'
                }
            
            # Backup filename
            schedule_name = f"_{task.name}" if task else ""
            backup_filename = f"{self.timestamp}_{self.server.name}{schedule_name}.sql"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            # Creating SSH tunnel
            ssh_config = {
                'ssh_address_or_host': (self.server.ssh_hostname, int(self.server.ssh_port)),
                'ssh_username': self.server.ssh_username,
                'remote_bind_address': (self.server.hostname, int(self.server.port))
            }
            
            # Adding authentication method
            if self.server.ssh_password:
                ssh_config['ssh_password'] = self.server.ssh_password
            elif self.server.ssh_key_file and self.server.ssh_key_file.path:
                ssh_config['ssh_pkey'] = self.server.ssh_key_file.path
                
            # Set environment variables for pg_dump
            env = os.environ.copy()
            # Add PGPASSWORD env variable for password
            env['PGPASSWORD'] = self.server.password
                
            # Create SSH tunnel
            with sshtunnel.SSHTunnelForwarder(**ssh_config) as tunnel:
                # Build pg_dump command through tunnel
                cmd = [
                    'pg_dump',
                    '-h', '127.0.0.1',
                    '-p', str(tunnel.local_bind_port),
                    '-U', self.server.username,
                    '-F', 'p',  # Custom format (compressed)
                    '-b',       # Include large objects
                    '-v',       # Verbose mode
                    '-f', backup_path
                ]
                
                # Add database name
                if self.server.database_name:
                    cmd.append(self.server.database_name)
                else:
                    # For all databases, we need to use pg_dumpall instead
                    cmd = [
                        'pg_dumpall',
                        '-h', '127.0.0.1',
                        '-p', str(tunnel.local_bind_port),
                        '-U', self.server.username,
                        '-f', backup_path
                    ]
                
                # Execute pg_dump through tunnel
                result = subprocess.run(cmd, env=env, capture_output=True, text=True)
                
                if result.returncode == 0:
                    return {
                        'success': True,
                        'path': backup_path,
                        'message': 'PostgreSQL backup completed successfully through SSH tunnel'
                    }
                else:
                    return {
                        'success': False,
                        'message': f'PostgreSQL backup error: {result.stderr}'
                    }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'SSH tunnel error for PostgreSQL: {str(e)}'
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
                database_name = server.database_name
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
            database_name = connection_data.get('database_name')
            ssh_hostname = connection_data.get('ssh_hostname')
            ssh_port = connection_data.get('ssh_port')
            ssh_username = connection_data.get('ssh_username')
            ssh_password = connection_data.get('ssh_password')
        else:
            return {
                'success': False,
                'message': 'No connection data provided'
            }
        
        # Handling both old and new connection types
        # Test connection based on type
        if connection_type in ['direct', 'direct_mysql']:
            return DatabaseConnectionService._test_direct_mysql_connection(
                hostname, port, username, password, database_name
            )
        elif connection_type in ['ssh', 'ssh_mysql']:
            return DatabaseConnectionService._test_ssh_mysql_connection(
                hostname, port, username, password, database_name,
                ssh_hostname, ssh_port, ssh_username, ssh_password
            )
        elif connection_type == 'direct_postgresql':
            return DatabaseConnectionService._test_direct_postgresql_connection(
                hostname, port, username, password, database_name
            )
        elif connection_type == 'ssh_postgresql':
            return DatabaseConnectionService._test_ssh_postgresql_connection(
                hostname, port, username, password, database_name,
                ssh_hostname, ssh_port, ssh_username, ssh_password
            )
        else:
            return {
                'success': False,
                'message': f'Unsupported connection type: {connection_type}'
            }

    @staticmethod
    def _test_direct_mysql_connection(hostname, port, username, password, database_name=None):
        """Tests direct TCP/IP connection to MySQL database"""
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
            conn_params = {
                'host': hostname,
                'port': int(port),
                'user': username,
                'password': password,
                'connection_timeout': 10
            }
            
            if database_name:
                conn_params['database'] = database_name
                
            conn = mysql.connector.connect(**conn_params)
            
            # Check MySQL server version
            cursor = conn.cursor()
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            return {
                'success': True,
                'message': f'MySQL connection established successfully. Server version: {version}'
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
    def _test_direct_postgresql_connection(hostname, port, username, password, database_name=None):
        """Tests direct TCP/IP connection to PostgreSQL database"""
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
            conn_params = {
                'host': hostname,
                'port': int(port),
                'user': username,
                'password': password,
                'connect_timeout': 10
            }
            
            # For PostgreSQL, we need a specific database to connect to
            if database_name:
                conn_params['dbname'] = database_name
            else:
                conn_params['dbname'] = 'postgres'  # Connect to default database
                
            conn = psycopg2.connect(**conn_params)
            
            # Check PostgreSQL server version
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            return {
                'success': True,
                'message': f'PostgreSQL connection established successfully. Server info: {version}'
            }
            
        except PostgreSQLError as e:
            return {
                'success': False,
                'message': f'PostgreSQL Error: {str(e)}'
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
    def _test_ssh_mysql_connection(db_hostname, db_port, db_username, db_password, 
                            db_name, ssh_hostname, ssh_port, ssh_username, ssh_password):
        """Tests MySQL database connection through SSH tunnel"""
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
                conn_params = {
                    'host': '127.0.0.1',
                    'port': tunnel.local_bind_port,
                    'user': db_username,
                    'password': db_password,
                    'connection_timeout': 10
                }
                
                if db_name:
                    conn_params['database'] = db_name
                
                conn = mysql.connector.connect(**conn_params)
                
                # Check MySQL server version
                cursor = conn.cursor()
                cursor.execute("SELECT VERSION()")
                version = cursor.fetchone()[0]
                cursor.close()
                conn.close()
                
                return {
                    'success': True,
                    'message': f'MySQL connection through SSH established successfully. Server version: {version}'
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
    
    @staticmethod
    def _test_ssh_postgresql_connection(db_hostname, db_port, db_username, db_password, 
                                db_name, ssh_hostname, ssh_port, ssh_username, ssh_password):
        """Tests PostgreSQL database connection through SSH tunnel"""
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
                conn_params = {
                    'host': '127.0.0.1',
                    'port': tunnel.local_bind_port,
                    'user': db_username,
                    'password': db_password,
                    'connect_timeout': 10
                }
                
                # For PostgreSQL, we need a specific database to connect to
                if db_name:
                    conn_params['dbname'] = db_name
                else:
                    conn_params['dbname'] = 'postgres'  # Connect to default database
                
                conn = psycopg2.connect(**conn_params)
                
                # Check PostgreSQL server version
                cursor = conn.cursor()
                cursor.execute("SELECT version();")
                version = cursor.fetchone()[0]
                cursor.close()
                conn.close()
                
                return {
                    'success': True,
                    'message': f'PostgreSQL connection through SSH established successfully. Server info: {version}'
                }
                
        except PostgreSQLError as e:
            return {
                'success': False,
                'message': f'PostgreSQL Error: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Unexpected error: {str(e)}'
            }