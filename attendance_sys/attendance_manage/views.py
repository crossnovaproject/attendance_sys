from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime, timedelta
from student_attendance.models import (
    Student, Teacher, Course, CourseSession,
    AttendanceCode, Attendance, AttendanceLog
)


# Admin check decorator
def admin_required(view_func):
    decorated_view_func = user_passes_test(
        lambda user: user.is_active and user.is_staff,
        login_url='admin:login'
    )(view_func)
    return decorated_view_func


@admin_required
def dashboard(request):
    """Admin dashboard with statistics and quick links"""
    # Get overall statistics
    total_students = Student.objects.count()
    total_teachers = Teacher.objects.count()
    total_courses = Course.objects.count()
    total_sessions = CourseSession.objects.count()
    total_attendance = AttendanceLog.objects.count()

    # Recent attendance records
    recent_attendance = AttendanceLog.objects.select_related(
        'student', 'session__course'
    ).order_by('-check_in_time')[:20]

    # Upcoming sessions
    upcoming_sessions = CourseSession.objects.filter(
        session_date__gte=timezone.now().date()
    ).select_related('course').order_by('session_date', 'start_time')[:10]

    # Attendance statistics by status
    status_stats = {
        'PRESENT': AttendanceLog.objects.filter(status='PRESENT').count(),
        'LATE': AttendanceLog.objects.filter(status='LATE').count(),
        'ABSENT': AttendanceLog.objects.filter(status='ABSENT').count(),
        'EXCUSED': AttendanceLog.objects.filter(status='EXCUSED').count(),
    }

    context = {
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_courses': total_courses,
        'total_sessions': total_sessions,
        'total_attendance': total_attendance,
        'recent_attendance': recent_attendance,
        'upcoming_sessions': upcoming_sessions,
        'status_stats': status_stats,
    }
    return render(request, 'attendance_manage/dashboard.html', context)


@admin_required
def attendance_list(request):
    """List all attendance records with filters"""
    # Get filter parameters
    student_id = request.GET.get('student_id')
    course_id = request.GET.get('course')
    session_id = request.GET.get('session')
    status = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    # Base queryset
    attendance_records = AttendanceLog.objects.select_related(
        'student', 'session__course', 'attendance_code'
    ).order_by('-check_in_time')

    # Apply filters
    if student_id:
        attendance_records = attendance_records.filter(student__student_id__icontains=student_id)
    if course_id:
        attendance_records = attendance_records.filter(session__course__course_id=course_id)
    if session_id:
        attendance_records = attendance_records.filter(session__id=session_id)
    if status:
        attendance_records = attendance_records.filter(status=status)
    if date_from:
        attendance_records = attendance_records.filter(check_in_time__date__gte=date_from)
    if date_to:
        attendance_records = attendance_records.filter(check_in_time__date__lte=date_to)

    # Pagination
    paginator = Paginator(attendance_records, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get filter dropdown data
    courses = Course.objects.all()
    sessions = CourseSession.objects.all()

    context = {
        'page_obj': page_obj,
        'courses': courses,
        'sessions': sessions,
        'status_choices': AttendanceLog.STATUS_CHOICES,
        'filters': {
            'student_id': student_id,
            'course': course_id,
            'session': session_id,
            'status': status,
            'date_from': date_from,
            'date_to': date_to,
        }
    }
    return render(request, 'attendance_manage/attendance_list.html', context)


@admin_required
def attendance_edit(request, attendance_id):
    """Edit a specific attendance record"""
    attendance = get_object_or_404(AttendanceLog, id=attendance_id)

    if request.method == 'POST':
        # Update attendance fields
        attendance.status = request.POST.get('status')
        attendance.notes = request.POST.get('notes')

        # Parse check_in_time if provided
        check_in_date = request.POST.get('check_in_date')
        check_in_time = request.POST.get('check_in_time')
        if check_in_date and check_in_time:
            naive_dt = datetime.strptime(f"{check_in_date} {check_in_time}", "%Y-%m-%d %H:%M")
            attendance.check_in_time = timezone.make_aware(naive_dt)

        attendance.save()
        messages.success(request, f'Attendance record for {attendance.student} updated successfully.')
        return redirect('attendance_manage:attendance_list')

    context = {
        'attendance': attendance,
        'status_choices': AttendanceLog.STATUS_CHOICES,
    }
    return render(request, 'attendance_manage/attendance_edit.html', context)


@admin_required
def attendance_delete(request, attendance_id):
    """Delete an attendance record"""
    attendance = get_object_or_404(AttendanceLog, id=attendance_id)

    if request.method == 'POST':
        student_name = str(attendance.student)
        attendance.delete()
        messages.success(request, f'Attendance record for {student_name} deleted successfully.')
        return redirect('attendance_manage:attendance_list')

    context = {
        'attendance': attendance,
    }
    return render(request, 'attendance_manage/attendance_confirm_delete.html', context)


@admin_required
def session_list(request):
    """List all course sessions"""
    sessions = CourseSession.objects.select_related(
        'course'
    ).prefetch_related(
        'attendance_logs'
    ).order_by('-session_date', '-start_time')

    # Add attendance count to each session
    for session in sessions:
        session.attendance_count = session.attendance_logs.count()

    context = {
        'sessions': sessions,
    }
    return render(request, 'attendance_manage/session_list.html', context)


@admin_required
def session_edit(request, session_id):
    """Edit a course session"""
    session = get_object_or_404(CourseSession, id=session_id)

    if request.method == 'POST':
        # Update session fields
        session.session_date = request.POST.get('session_date')

        # Parse times
        start_time = request.POST.get('start_time')
        if start_time:
            session.start_time = datetime.strptime(start_time, '%H:%M').time()

        end_time = request.POST.get('end_time')
        if end_time:
            session.end_time = datetime.strptime(end_time, '%H:%M').time()

        session.topic = request.POST.get('topic')
        session.is_active = request.POST.get('is_active') == 'on'
        session.save()

        messages.success(request, f'Session {session.session_code} updated successfully.')
        return redirect('attendance_manage:session_list')

    context = {
        'session': session,
    }
    return render(request, 'attendance_manage/session_edit.html', context)


@admin_required
def session_create(request):
    """Create a new course session"""
    if request.method == 'POST':
        course_id = request.POST.get('course')
        course = get_object_or_404(Course, course_id=course_id)

        session_number = request.POST.get('session_number')

        # Check if session already exists
        if CourseSession.objects.filter(course=course, session_number=session_number).exists():
            messages.error(request, f'Session {session_number} already exists for this course.')
            return redirect('attendance_manage:session_create')

        # Create new session
        session = CourseSession.objects.create(
            course=course,
            session_number=session_number,
            session_date=request.POST.get('session_date'),
            start_time=datetime.strptime(request.POST.get('start_time'), '%H:%M').time() if request.POST.get(
                'start_time') else None,
            end_time=datetime.strptime(request.POST.get('end_time'), '%H:%M').time() if request.POST.get(
                'end_time') else None,
            topic=request.POST.get('topic', ''),
            is_active=request.POST.get('is_active') == 'on'
        )

        messages.success(request, f'Session {session.session_code} created successfully.')
        return redirect('attendance_manage:session_list')

    courses = Course.objects.all()
    context = {
        'courses': courses,
    }
    return render(request, 'attendance_manage/session_create.html', context)


@admin_required
def session_delete(request, session_id):
    """Delete a course session"""
    session = get_object_or_404(CourseSession, id=session_id)

    if request.method == 'POST':
        session_code = session.session_code
        session.delete()
        messages.success(request, f'Session {session_code} deleted successfully.')
        return redirect('attendance_manage:session_list')

    context = {
        'session': session,
    }
    return render(request, 'attendance_manage/session_confirm_delete.html', context)


@admin_required
def bulk_attendance_update(request):
    """Bulk update attendance records"""
    if request.method == 'POST':
        session_id = request.POST.get('session')
        status = request.POST.get('status')
        student_ids = request.POST.getlist('students')

        session = get_object_or_404(CourseSession, id=session_id)

        updated_count = 0
        for student_id in student_ids:
            student = get_object_or_404(Student, id=student_id)

            # Update or create attendance record
            attendance, created = AttendanceLog.objects.update_or_create(
                student=student,
                session=session,
                defaults={
                    'status': status,
                    'check_in_time': timezone.now(),
                    'notes': f'Bulk updated by admin on {timezone.now().strftime("%Y-%m-%d %H:%M")}'
                }
            )
            updated_count += 1

        messages.success(request, f'{updated_count} attendance records updated to {status}.')
        return redirect('attendance_manage:attendance_list')

    # GET request - show bulk update form
    sessions = CourseSession.objects.filter(is_active=True).select_related('course')
    students = Student.objects.all().order_by('first_name', 'last_name')

    context = {
        'sessions': sessions,
        'students': students,
        'status_choices': AttendanceLog.STATUS_CHOICES,
    }
    return render(request, 'attendance_manage/bulk_attendance_update.html', context)