from django.urls import path
from . import views

app_name = 'student_attendance'

urlpatterns = [
    # Public URLs
    path('', views.home, name='home'),
    path('mark-attendance/', views.mark_attendance, name='mark_attendance'),

    # Authentication URLs
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),

    # Protected Teacher URLs
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/generate-code/', views.generate_attendance_code, name='generate_attendance_code'),
    path('teacher/active-sessions/', views.active_sessions, name='active_sessions'),
    path('teacher/session/<int:session_id>/', views.session_detail, name='session_detail'),
    path('teacher/course-attendance/', views.teacher_course_attendance, name='teacher_course_attendance'),

    # Protected Student URLs
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('student/my-attendance/', views.my_attendance, name='my_attendance'),

    # Dashboard URLs
    path('dashboard/course/<str:course_id>/', views.course_dashboard, name='course_dashboard'),
    path('dashboard/student/<int:student_id>/', views.student_attendance_detail, name='student_attendance_detail'),
    path('dashboard/reports/', views.attendance_reports, name='attendance_reports'),

    # API endpoints
    path('api/validate-code/', views.validate_attendance_code, name='validate_attendance_code'),
    path('api/session-attendance/<int:session_id>/', views.session_attendance_count_api, name='session_attendance_api'),
]