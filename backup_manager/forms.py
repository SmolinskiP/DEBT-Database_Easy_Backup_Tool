from django import forms
from .models import DatabaseServer

class DatabaseServerForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    ssh_password = forms.CharField(widget=forms.PasswordInput, required=False)
    
    class Meta:
        model = DatabaseServer
        fields = [
            'name', 'connection_type', 'hostname', 'port', 
            'username', 'password', 'ssh_hostname', 'ssh_port', 
            'ssh_username', 'ssh_password', 'ssh_key_file'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['connection_type'].widget.attrs.update({'class': 'form-control', 'id': 'connection_type'})
        
        # Pola SSH oznaczamy klasą CSS dla łatwiejszego zarządzania widocznością
        ssh_fields = ['ssh_hostname', 'ssh_port', 'ssh_username', 'ssh_password', 'ssh_key_file']
        for field in ssh_fields:
            self.fields[field].widget.attrs.update({'class': 'ssh-field form-control'})