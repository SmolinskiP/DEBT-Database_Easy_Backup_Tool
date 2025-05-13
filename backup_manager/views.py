# backup_manager/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import DatabaseServer
from .forms import DatabaseServerForm
from .services import DatabaseConnectionService
import json
from django.utils import timezone

def dashboard_view(request):
    """Main page - dashboard"""
    servers = DatabaseServer.objects.all().order_by('-created_at')
    
    context = {
        'servers': servers,
        'servers_count': servers.count(),
        'scheduled_count': 0,  # Placeholder
        'successful_backups': 0,  # Placeholder
        'failed_backups': 0,  # Placeholder
        'recent_backups': []  # Placeholder
    }
    return render(request, 'dashboard.html', context)

def add_server_view(request):
    """Add server view"""
    form = DatabaseServerForm()
    
    if request.method == 'POST':
        form = DatabaseServerForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Database server has been added successfully.")
            return redirect('dashboard')
    
    context = {
        'form': form,
    }
    return render(request, 'add_server.html', context)

def server_list_view(request):
    """Server list view"""
    servers = DatabaseServer.objects.all().order_by('-created_at')
    
    context = {
        'servers': servers,
    }
    return render(request, 'server_list.html', context)

@csrf_exempt
def test_connection_view(request):
    """API view for testing database connection"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # If we have a server ID, test connection to existing server
            if 'server_id' in data:
                server_id = data['server_id']
                result = DatabaseConnectionService.test_connection(server_id=server_id)
                
                # Update server status
                try:
                    server = DatabaseServer.objects.get(id=server_id)
                    server.last_status = result['success']
                    server.last_status_check = timezone.now()
                    server.last_status_message = result['message']
                    server.save()
                except DatabaseServer.DoesNotExist:
                    pass
                
                return JsonResponse(result)
            
            # Otherwise test connection with form data
            connection_data = {
                'connection_type': data.get('connection_type'),
                'hostname': data.get('hostname'),
                'port': data.get('port'),
                'username': data.get('username'),
                'password': data.get('password'),
                'ssh_hostname': data.get('ssh_hostname'),
                'ssh_port': data.get('ssh_port'),
                'ssh_username': data.get('ssh_username'),
                'ssh_password': data.get('ssh_password'),
            }
            result = DatabaseConnectionService.test_connection(connection_data=connection_data)
            return JsonResponse(result)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error processing request: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid HTTP method. Use POST.'
    })

@csrf_exempt
def delete_server_view(request, server_id):
    """API view for deleting a server"""
    if request.method == 'DELETE':
        try:
            server = DatabaseServer.objects.get(id=server_id)
            server.delete()
            return JsonResponse({'success': True, 'message': 'Server deleted successfully'})
        except DatabaseServer.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Server does not exist'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'message': 'Invalid HTTP method'}, status=405)