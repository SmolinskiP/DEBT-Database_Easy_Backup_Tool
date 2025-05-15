from django import forms
from .models import BackupTask, DatabaseServer, StorageConfig, AppSettings
import datetime

class DatabaseServerForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    ssh_password = forms.CharField(widget=forms.PasswordInput, required=False)
    
    class Meta:
        model = DatabaseServer
        fields = [
            'name', 'connection_type', 'hostname', 'port', 
            'username', 'password', 'database_name',
            'ssh_hostname', 'ssh_port', 
            'ssh_username', 'ssh_password', 'ssh_key_file'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['connection_type'].widget.attrs.update({'class': 'form-control', 'id': 'connection_type'})
        
        # Mark SSH fields with a CSS class for easier visibility management
        ssh_fields = ['ssh_hostname', 'ssh_port', 'ssh_username', 'ssh_password', 'ssh_key_file']
        for field in ssh_fields:
            self.fields[field].widget.attrs.update({'class': 'ssh-field form-control'})
            
        # Set initial port value based on connection type
        if not self.instance.pk:  # Only for new servers
            self.fields['port'].initial = 3306  # Default to MySQL port
        
        # Add help text for database_name
        self.fields['database_name'].help_text = "Specific database to backup. For PostgreSQL, leave empty for all databases (requires superuser privileges)."

class BackupTaskForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['server'].queryset = DatabaseServer.objects.all().order_by('name')
        self.fields['server'].empty_label = "-- Select server --"
        
        # Dodaj pole dla storage_config
        self.fields['storage_config'].queryset = StorageConfig.objects.all().order_by('-is_default', 'name')
        self.fields['storage_config'].empty_label = "-- Custom storage --"
        
        # Ustaw domyślną wartość dla storage_config
        if not self.instance.pk:  # Tylko dla nowych rekordów
            try:
                self.fields['storage_config'].initial = StorageConfig.objects.filter(is_default=True).first().id
            except:
                pass
        
        # Inicjalizacja pól
        self.fields['time'].initial = datetime.time(1, 0)  # 01:00 AM
        self.fields['retain_count'].initial = int(AppSettings.get('default_retention', 10))
        
        # Dodaj klasy CSS
        for field_name, field in self.fields.items():
            if field_name not in ['enabled', 'email_notification']:
                field.widget.attrs.update({'class': 'form-control'})
    
    class Meta:
        model = BackupTask
        fields = [
            'name', 'server', 'frequency', 'time', 'day_of_week', 
            'day_of_month', 'enabled', 'retain_count',
            'email_notification', 'email_address',
            'storage_config', 'storage_type', 'remote_hostname', 
            'remote_port', 'remote_username', 'remote_password', 
            'remote_path', 'remote_key_file'
        ]
        widgets = {
            'time': forms.TimeInput(attrs={'type': 'time'}),
            'day_of_month': forms.NumberInput(attrs={'min': 1, 'max': 31}),
            'enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_notification': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'remote_password': forms.PasswordInput(),
        }

class StorageConfigForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=False)
    
    class Meta:
        model = StorageConfig
        fields = [
            'name', 'storage_type', 'is_default',
            'hostname', 'port', 'username', 'password',
            'path', 'key_file',
            'gdrive_folder_id', 'gdrive_credentials_file'
        ]
        widgets = {
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'is_default':
                field.widget.attrs.update({'class': 'form-control'})
                
        # Dodaj atrybuty dla pól Google Drive
        if 'gdrive_folder_id' in self.fields:
            self.fields['gdrive_folder_id'].widget.attrs.update({
                'placeholder': 'np. 1A2B3C4D5E6F7G8H9I', 
                'class': 'form-control'
            })