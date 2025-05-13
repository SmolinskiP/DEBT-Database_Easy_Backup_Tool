# db_backup_tool/urls.py
from django.contrib import admin
from django.urls import path
from backup_manager.views import (
    dashboard_view, add_server_view, server_list_view,
    test_connection_view, delete_server_view
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', dashboard_view, name='dashboard'),
    path('servers/add/', add_server_view, name='add_server'),
    path('servers/', server_list_view, name='server_list'),
    path('api/test-connection/', test_connection_view, name='test_connection'),
    path('api/servers/<int:server_id>/', delete_server_view, name='delete_server'),
]