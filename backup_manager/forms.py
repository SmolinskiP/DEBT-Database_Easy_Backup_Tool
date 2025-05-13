from django import forms
from .models import BackupTask, DatabaseServer
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

class BackupTaskForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['server'].queryset = DatabaseServer.objects.all().order_by('name')
        self.fields['server'].empty_label = "-- Wybierz serwer --"
        
        # Inicjalizacja pól
        self.fields['time'].initial = datetime.time(1, 0)  # 01:00 AM
        self.fields['retain_count'].initial = 10
        
        # Dodaj klasy CSS
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})
    
    class Meta:
        model = BackupTask
        fields = [
            'name', 'server', 'frequency', 'time', 'day_of_week', 
            'day_of_month', 'enabled', 'retain_count',
            'email_notification', 'email_address'
        ]
        widgets = {
            'time': forms.TimeInput(attrs={'type': 'time'}),
            'day_of_month': forms.NumberInput(attrs={'min': 1, 'max': 31}),
            'enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_notification': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
