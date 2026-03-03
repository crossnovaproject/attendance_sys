from django.urls import path
from . import views

app_name = 'attendance_manage'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Attendance CRUD
    path('attendance/', views.attendance_list, name='attendance_list'),
    path('attendance/edit/<int:attendance_id>/', views.attendance_edit, name='attendance_edit'),
    path('attendance/delete/<int:attendance_id>/', views.attendance_delete, name='attendance_delete'),
    path('attendance/bulk-update/', views.bulk_attendance_update, name='bulk_attendance_update'),

    # Session CRUD
    path('sessions/', views.session_list, name='session_list'),
    path('sessions/create/', views.session_create, name='session_create'),
    path('sessions/edit/<int:session_id>/', views.session_edit, name='session_edit'),
    path('sessions/delete/<int:session_id>/', views.session_delete, name='session_delete'),
]