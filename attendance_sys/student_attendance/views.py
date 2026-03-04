from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.middleware.csrf import get_token
from datetime import datetime, timezone as dt_timezone
from django.db.models import Count, Q, Avg, F
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime, timedelta
import json
from .models import (
    Student, Teacher, Course, CourseSession,
    AttendanceCode, Attendance, AttendanceLog
)

# Authentication Views
@csrf_protect
@ensure_csrf_cookie
def login_view(request):
    """Handle user login for both teachers and students"""

    get_token(request)

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user_type = request.POST.get('user_type')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            # Check if user is teacher or student
            try:
                if user_type == 'teacher' and hasattr(user, 'teacher_profile'):
                    messages.success(request, f'Welcome back, {user.teacher_profile.first_name}!')
                    return redirect('student_attendance:teacher_dashboard')
                elif user_type == 'student' and hasattr(user, 'student_profile'):
                    messages.success(request, f'Welcome back, {user.student_profile.first_name}!')
                    return redirect('student_attendance:student_dashboard')
                else:
                    messages.error(request, 'Invalid user type or profile not found.')
                    logout(request)
            except:
                messages.error(request, 'User profile not found.')
                logout(request)
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'student_attendance/auth/login.html')


def logout_view(request):
    """Handle user logout - accepts both POST and GET"""
    if request.method == 'POST' or request.method == 'GET':
        logout(request)
        messages.success(request, 'You have been logged out successfully.')
        return redirect('student_attendance:home')
    return redirect('student_attendance:home')

def register_view(request):
    """Handle user registration for both teachers and students"""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        user_type = request.POST.get('user_type')

        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return redirect('student_attendance:register')

        # Check if username exists (including soft-deleted or orphaned users)
        if User.objects.filter(username=username).exists():
            # Check if the user has an associated profile
            user = User.objects.get(username=username)
            if hasattr(user, 'teacher_profile') or hasattr(user, 'student_profile'):
                messages.error(request, 'Username already exists and is associated with an active profile.')
            else:
                messages.error(request,
                               'Username already exists. Please contact administrator or choose a different username.')
            return redirect('student_attendance:register')

        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
            if hasattr(user, 'teacher_profile') or hasattr(user, 'student_profile'):
                messages.error(request, 'Email already exists and is associated with an active profile.')
            else:
                messages.error(request, 'Email already exists. Please use a different email.')
            return redirect('student_attendance:register')

        if Teacher.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered as a teacher.')
            return redirect('student_attendance:register')

        if Student.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered as a student.')
            return redirect('student_attendance:register')

        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        # Create profile based on user type
        try:
            if user_type == 'teacher':
                teacher = Teacher.objects.create(
                    user=user,
                    first_name=first_name,
                    last_name=last_name,
                    email=email
                )
                messages.success(request,
                                 f'Teacher account created successfully! Your Teacher ID: {teacher.teacher_id}')
            elif user_type == 'student':
                student = Student.objects.create(
                    user=user,
                    first_name=first_name,
                    last_name=last_name,
                    email=email
                )
                messages.success(request,
                                 f'Student account created successfully! Your Student ID: {student.student_id}')
            else:
                messages.error(request, 'Invalid user type.')
                user.delete()
                return redirect('student_attendance:register')
        except Exception as e:
            # If profile creation fails, delete the user
            user.delete()
            messages.error(request, f'Error creating profile: {str(e)}')
            return redirect('student_attendance:register')

        return redirect('student_attendance:login')

    return render(request, 'student_attendance/auth/register.html')


def home(request):
    """Home page"""
    return render(request, 'student_attendance/home.html')

@login_required(login_url='student_attendance:login')
def teacher_dashboard(request):
    try:
        teacher = request.user.teacher_profile
    except:
        messages.error(request, 'Only for registered teacher.')
        return redirect('student_attendance:login')

    courses = Course.objects.filter(teacher=teacher).annotate(
        total_students_count=Count('enrolled_students', distinct=True),
        total_sessions_count=Count('sessions', distinct=True)
    )
    #Active session
    recent_sessions = CourseSession.objects.filter(
        course__teacher=teacher,
        is_active=True,
        attendance_code__isnull=False
    ).select_related('course', 'attendance_code').order_by('-created_at')[:10]

    today = timezone.now().date()
    today_attendances = AttendanceLog.objects.filter(
        session__course__teacher=teacher,
        check_in_time__date=today
    )

    total_present = today_attendances.filter(status='PRESENT').count()
    total_late = today_attendances.filter(status='LATE').count()
    total_excused = today_attendances.filter(status='EXCUSED').count()

    today_sessions = CourseSession.objects.filter(
        course__teacher=teacher,
        session_date=today
    ).select_related('course').prefetch_related('attendance_logs')

    # Calculate total statistics
    total_courses = courses.count()
    total_students = Student.objects.filter(
        attendance_logs__session__course__teacher=teacher
    ).distinct().count()
    total_sessions = CourseSession.objects.filter(
        course__teacher=teacher
    ).count()
    total_attendance = AttendanceLog.objects.filter(
        session__course__teacher=teacher
    ).count()

    context = {
        'teacher': teacher,
        'courses': courses,
        'recent_sessions': recent_sessions,
        'today_sessions': today_sessions,
        'total_present': total_present,
        'total_late': total_late,
        'total_excused': total_excused,
        'today': today,
        'total_courses': total_courses,
        'total_students': total_students,
        'total_sessions': total_sessions,
        'total_attendance': total_attendance,
        'now': timezone.now(),
    }
    return render(request, 'student_attendance/teacher/dashboard.html', context)


@login_required(login_url='student_attendance:login')
def generate_attendance_code(request):
    try:
        teacher = request.user.teacher_profile
    except:
        messages.error(request, 'Only for registered teacher.')
        return redirect('student_attendance:login')

    if request.method == 'POST':
        course_id = request.POST.get('course_id')
        session_number = request.POST.get('session_number')
        duration_minutes = int(request.POST.get('duration', 60))

        # Get session date and time from form
        session_date = request.POST.get('session_date')
        session_start_time = request.POST.get('session_start_time')

        try:
            # Get the course
            course = get_object_or_404(Course, course_id=course_id, teacher=teacher)

            # VALIDATION: Check if session number exceeds course total sessions
            if int(session_number) > course.total_sessions:
                messages.error(
                    request,
                    f'Invalid session number. This course only has {course.total_sessions} sessions. '
                    f'Please choose a session number between 1 and {course.total_sessions}.'
                )
                return redirect('student_attendance:generate_attendance_code')

            # VALIDATION: Check if session number is less than 1
            if int(session_number) < 1:
                messages.error(
                    request,
                    'Session number must be at least 1.'
                )
                return redirect('student_attendance:generate_attendance_code')

            # Get current time with timezone
            now = timezone.now()

            # Initialize variables
            session_start_hk = None
            session_date_obj = now.date()
            session_time_obj = now.time()

            # Determine session date and time with proper timezone handling
            if session_date and session_start_time:
                # Parse the provided date and time (these are in Hong Kong time)
                session_date_obj = datetime.strptime(session_date, '%Y-%m-%d').date()
                session_time_obj = datetime.strptime(session_start_time, '%H:%M').time()

                # IMPORTANT: Create a datetime in Hong Kong time
                hk_tz = timezone.get_current_timezone()  # Asia/Hong_Kong
                hk_datetime = timezone.make_aware(
                    datetime.combine(session_date_obj, session_time_obj),
                    hk_tz
                )

                # Convert to UTC for storage
                utc_datetime = hk_datetime.astimezone(dt_timezone.utc)

                # Extract UTC date and time for storage
                session_date_obj = utc_datetime.date()
                session_time_obj = utc_datetime.time()

                # Keep the Hong Kong version for display
                session_start_hk = hk_datetime

            # Check if session exists
            session, created = CourseSession.objects.get_or_create(
                course=course,
                session_number=session_number,
                defaults={
                    'session_date': session_date_obj,  # Stored as UTC date
                    'start_time': session_time_obj,  # Stored as UTC time
                    'is_active': True
                }
            )

            # If session exists but dates are different, update them
            if not created:
                session.session_date = session_date_obj
                session.start_time = session_time_obj
                # Don't save yet - we'll save after setting end_time

            # ============ Calculate and set end_time ============
            if session_start_hk:
                # Calculate end time in Hong Kong using the duration
                end_time_hk = session_start_hk + timedelta(minutes=duration_minutes)

                # Convert to UTC for storage
                end_time_utc = end_time_hk.astimezone(dt_timezone.utc)

                # Set the end_time field
                session.end_time = end_time_utc.time()

                # Debug output (will appear in console)
                print(f"\n=== SESSION TIME DEBUG ===")
                print(f"Session ID: {session.id}")
                print(f"Start HKT: {session_start_hk.strftime('%H:%M')}")
                print(f"End HKT: {end_time_hk.strftime('%H:%M')}")
                print(f"Start UTC stored: {session_time_obj.strftime('%H:%M')}")
                print(f"End UTC stored: {end_time_utc.strftime('%H:%M')}")
                print(f"==========================\n")
            elif session.start_time and session.session_date:
                # Fallback: calculate from stored UTC start time
                stored_start_utc = timezone.make_aware(
                    datetime.combine(session.session_date, session.start_time),
                    dt_timezone.utc
                )
                end_time_utc = stored_start_utc + timedelta(minutes=duration_minutes)
                session.end_time = end_time_utc.time()

            # Save the session with both start_time and end_time
            session.save()
            # ============ END NEW CODE ============

            # If session already existed but was created manually, ensure it doesn't exceed total
            if not created and session.session_number > course.total_sessions:
                messages.error(
                    request,
                    f'Session {session_number} exists but exceeds the course total of {course.total_sessions}. '
                    f'Please update the course total sessions or contact administrator.'
                )
                return redirect('student_attendance:generate_attendance_code')

            # Check if there's already an active code for this session
            existing_code = AttendanceCode.objects.filter(
                session=session,
                expires_at__gt=now,
            ).first()

            if existing_code:
                # Format expiration time in local timezone
                local_expiry = timezone.localtime(existing_code.expires_at)
                expiry_formatted = local_expiry.strftime('%Y-%m-%d %H:%M:%S')

                messages.warning(
                    request,
                    f'An active code already exists for this session: {existing_code.code} '
                    f'(expires at {expiry_formatted})'
                )
            else:
                # Calculate expiration time
                if session_start_hk:
                    # Use Hong Kong time for calculation
                    expires_at_hk = session_start_hk + timedelta(minutes=duration_minutes)

                    # Convert to UTC for storage
                    expires_at_utc = expires_at_hk.astimezone(dt_timezone.utc)

                    # For display, use the Hong Kong time
                    expires_local = expires_at_hk
                    session_start_local = session_start_hk
                else:
                    # Fallback to current time
                    expires_at_utc = now + timedelta(minutes=duration_minutes)
                    expires_local = timezone.localtime(expires_at_utc)

                    # Get session start for display
                    stored_utc = timezone.make_aware(
                        datetime.combine(session.session_date, session.start_time),
                        dt_timezone.utc
                    )
                    session_start_local = timezone.localtime(stored_utc)

                # Create new attendance code (store in UTC)
                attendance_code = AttendanceCode.objects.create(
                    session=session,
                    expires_at=expires_at_utc
                )

                # Format times for display
                created_local = timezone.localtime(attendance_code.created_at)

                # Get end time in HKT for display in the success message
                end_time_hkt_display = session.end_time_hkt_str if session.end_time else 'Not set'

                messages.success(
                    request,
                    f'✅ Attendance code generated successfully! Code: {attendance_code.code}'
                )

                # Store additional info in session for the template
                request.session['last_generated_code'] = {
                    'code': attendance_code.code,
                    'course_id': course.course_id,
                    'course_name': course.course_name,
                    'session_number': session.session_number,
                    'session_date': session_start_local.strftime('%Y-%m-%d'),
                    'session_start_time': session_start_local.strftime('%H:%M'),
                    'session_end_time': end_time_hkt_display,  # Add end time to display
                    'session_start': session_start_local.isoformat(),
                    'created_at': created_local.isoformat(),
                    'expires_at': expires_local.isoformat(),
                    'expires_timestamp': int(expires_at_utc.timestamp() * 1000),
                    'duration': duration_minutes,
                    'note': f'Session: {session_start_local.strftime("%Y-%m-%d %H:%M")} - {end_time_hkt_display} HKT. '
                            f'Code valid until {expires_local.strftime("%Y-%m-%d %H:%M")} (Hong Kong Time)'
                }

        except Course.DoesNotExist:
            messages.error(request, 'Course not found or you do not have permission')
        except ValueError as e:
            messages.error(request, f'Invalid input: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error generating code: {str(e)}')
            import traceback
            traceback.print_exc()

        return redirect('student_attendance:generate_attendance_code')

    # GET request - show form
    courses = Course.objects.filter(teacher=teacher).prefetch_related('sessions')

    # Create a serializable structure for JavaScript with pre-formatted HKT times
    course_sessions_data = {}
    for course in courses:
        sessions_list = []
        for session in course.sessions.all():
            sessions_list.append({
                'number': session.session_number,
                'date': session.session_date.strftime('%Y-%m-%d'),
                'start_time_hkt': session.start_time_hkt_str or '',
                'end_time_hkt': session.end_time_hkt_str or '',
                'has_start_time': session.start_time is not None,
                'has_end_time': session.end_time is not None,
                'is_active': session.is_active
            })
        course_sessions_data[course.course_id] = sessions_list

    # Get last generated code from session if exists
    last_code = request.session.get('last_generated_code')

    # Prepare course data with max sessions for JavaScript validation
    course_data = []
    for course in courses:
        course_data.append({
            'id': course.course_id,
            'name': course.course_name,
            'total_sessions': course.total_sessions
        })

    # Get tomorrow's date for default session date (in Hong Kong time)
    tomorrow_hk = timezone.localtime(timezone.now() + timedelta(days=1)).date()

    context = {
        'courses': courses,
        'course_sessions_json': json.dumps(course_sessions_data),  # Add this for JavaScript
        'course_data_json': json.dumps(course_data),
        'last_code': last_code,
        'now': timezone.now(),
        'tomorrow': tomorrow_hk,
        'teacher': teacher,
    }

    # Clear the session data after passing to template
    if 'last_generated_code' in request.session:
        del request.session['last_generated_code']

    return render(request, 'student_attendance/teacher/generate_code.html', context)

@login_required(login_url='student_attendance:login')
def session_attendance_count_api(request, session_id):
    """API endpoint to get real-time attendance count for a session"""
    try:
        teacher = request.user.teacher_profile
        session = get_object_or_404(CourseSession, id=session_id, course__teacher=teacher)

        # Count attendance logs for this session
        attendance_count = AttendanceLog.objects.filter(session=session).count()

        # Calculate percentage (you can adjust this based on total students)
        total_students = Student.objects.filter(
            attendance_logs__session__course=session.course
        ).distinct().count()

        if total_students > 0:
            percentage = round((attendance_count / total_students) * 100, 1)
        else:
            percentage = 0

        return JsonResponse({
            'success': True,
            'count': attendance_count,
            'percentage': percentage,
            'total_students': total_students,
            'session_id': session_id
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@login_required(login_url='student_attendance:login')
def active_sessions(request):
    """View all active sessions with real-time attendance stats"""
    try:
        teacher = request.user.teacher_profile
    except:
        messages.error(request, 'Teacher profile not found.')
        return redirect('student_attendance:login')

    # Get current time for comparison
    now = timezone.now()

    # Get active sessions with valid attendance codes
    active_sessions = CourseSession.objects.filter(
        course__teacher=teacher,
        is_active=True,
        attendance_code__isnull=False,
        attendance_code__expires_at__gt=now
    ).select_related('course', 'attendance_code').order_by('-attendance_code__created_at')

    # Add attendance statistics to each session
    for session in active_sessions:
        # Get all attendance logs for this session
        logs = AttendanceLog.objects.filter(session=session)

        # Basic counts
        session.attendance_count = logs.count()
        session.present_count = logs.filter(status='PRESENT').count()
        session.late_count = logs.filter(status='LATE').count()
        session.absent_count = logs.filter(status='ABSENT').count()

        # Calculate lateness statistics
        late_logs = logs.filter(status='LATE')
        late_minutes = []

        if late_logs.exists() and session.start_time:
            session_start = timezone.make_aware(
                datetime.combine(session.session_date, session.start_time)
            )

            for log in late_logs:
                lateness = (log.check_in_time - session_start).total_seconds() / 60
                late_minutes.append(round(lateness, 1))

            if late_minutes:
                session.avg_lateness = round(sum(late_minutes) / len(late_minutes), 1)
                session.min_lateness = min(late_minutes)
                session.max_lateness = max(late_minutes)
            else:
                session.avg_lateness = 0
                session.min_lateness = 0
                session.max_lateness = 0
        else:
            session.avg_lateness = 0
            session.min_lateness = 0
            session.max_lateness = 0

        # Calculate percentage (based on total students in course)
        total_students = Student.objects.filter(
            attendance_logs__session__course=session.course
        ).distinct().count()

        if total_students > 0:
            session.attendance_percentage = round((session.attendance_count / total_students) * 100, 1)
        else:
            session.attendance_percentage = 0

    context = {
        'active_sessions': active_sessions,
        'now': now,
    }
    return render(request, 'student_attendance/teacher/active_sessions.html', context)


@login_required(login_url='student_attendance:login')
def student_dashboard(request):
    """Student dashboard showing their courses and attendance"""
    try:
        student = request.user.student_profile
    except:
        messages.error(request, 'Student profile not found. Please register as a student.')
        return redirect('student_attendance:login')

    # Get all courses the student is enrolled in
    enrolled_courses = student.enrolled_courses.all()

    # Current time
    now = timezone.now()
    today = now.date()

    # ============ AUTO-MARK ABSENT FOR SESSIONS THAT HAVE ENDED ============
    # Get all sessions for enrolled courses
    all_sessions = CourseSession.objects.filter(
        course__in=enrolled_courses
    ).select_related('course')

    auto_marked_count = 0

    for session in all_sessions:
        # Skip if student already has attendance
        if AttendanceLog.objects.filter(student=student, session=session).exists():
            continue

        # Determine if session has ended
        session_ended = False
        end_time_reason = ""

        if session.session_date < today:
            # Session date is in the past
            session_ended = True
            end_time_reason = f"Session date {session.session_date} is in the past"

        elif session.session_date == today:
            # Session is today - check if end time has passed
            if session.end_time:
                # Has explicit end time
                session_end_naive = datetime.combine(session.session_date, session.end_time)
                session_end_utc = timezone.make_aware(session_end_naive, dt_timezone.utc)

                if now > session_end_utc:
                    session_ended = True
                    end_time_reason = f"Session ended at {session.end_time}"
            elif session.start_time:
                # Has start time but no end time - assume 2 hours duration
                session_start_naive = datetime.combine(session.session_date, session.start_time)
                session_start_utc = timezone.make_aware(session_start_naive, dt_timezone.utc)
                estimated_end = session_start_utc + timedelta(hours=2)

                if now > estimated_end:
                    session_ended = True
                    end_time_reason = f"Estimated end time (2 hours after start) has passed"

        if session_ended:
            # Auto-mark as absent
            AttendanceLog.objects.create(
                student=student,
                session=session,
                attendance_code=None,
                status='ABSENT',
                check_in_time=timezone.make_aware(
                    datetime.combine(session.session_date, datetime.min.time())
                ),
                notes=f'Auto-marked ABSENT: {end_time_reason}. No attendance recorded.'
            )
            auto_marked_count += 1

    if auto_marked_count > 0:
        messages.info(request, f'{auto_marked_count} past sessions were automatically marked as absent.')

    upcoming_sessions = []
    past_sessions = []

    for session in all_sessions:
        session_datetime = None
        if session.start_time and session.session_date:
            session_datetime = timezone.make_aware(
                datetime.combine(session.session_date, session.start_time)
            )

        session_info = {
            'session': session,
            'course_name': session.course.course_name,
            'course_id': session.course.course_id,
            'session_number': session.session_number,
            'date': session.session_date,
            'start_time': session.start_time,
            'end_time': session.end_time,
            'topic': session.topic,
            'has_passed': session_datetime < now if session_datetime else session.session_date < today,
            'datetime': session_datetime,
        }

        if session_info['has_passed']:
            past_sessions.append(session_info)
        else:
            upcoming_sessions.append(session_info)

    # ============ FUNCTION 2: Simplified Attendance Rate ============
    course_stats = []
    total_buffer_all = 0
    total_used_buffer_all = 0

    for course in enrolled_courses:
        # Get PAST sessions for this course
        course_past_sessions = []
        for session_info in past_sessions:
            if session_info['course_id'] == course.course_id:
                course_past_sessions.append(session_info['session'])

        past_sessions_count = len(course_past_sessions)
        total_sessions_count = course.total_sessions

        # Default values
        present_count = 0
        late_count = 0
        absent_count = 0
        excused_count = 0

        if past_sessions_count > 0:
            # Get student's attendance logs for PAST sessions
            attendance_logs = AttendanceLog.objects.filter(
                student=student,
                session__in=course_past_sessions
            )

            # Count by status
            present_count = attendance_logs.filter(status='PRESENT').count()
            late_count = attendance_logs.filter(status='LATE').count()
            absent_count = attendance_logs.filter(status='ABSENT').count()
            excused_count = attendance_logs.filter(status='EXCUSED').count()

        # Calculate buffer used: late = 0.5, absent/excused = 1
        buffer_used = (late_count * 0.5) + (absent_count * 1.0) + (excused_count * 1.0)
        buffer_total = round(total_sessions_count * 0.2)
        buffer_remaining = buffer_total - buffer_used

        # Sessions left to attend
        sessions_left = total_sessions_count - past_sessions_count

        # FIXED: Determine status based on ACTUAL attendance
        if past_sessions_count == 0:
            status = 'No Sessions Yet'
            status_class = 'secondary'
        elif present_count == 0 and past_sessions_count > 0:
            # Attended zero sessions but there were sessions - definitely AT RISK
            status = 'At Risk'
            status_class = 'danger'
        elif buffer_remaining < 0:
            # Used more buffer than available
            status = 'At Risk'
            status_class = 'danger'
        elif buffer_remaining == 0:
            # Buffer exactly used up
            status = 'Critical'
            status_class = 'danger'
        elif buffer_remaining <= buffer_total * 0.3:  # Less than 30% buffer left
            status = 'Caution'
            status_class = 'warning'
        else:
            status = 'Good'
            status_class = 'success'

        # Calculate attendance rate for display
        attendance_rate = 0
        if past_sessions_count > 0:
            # Simple percentage of sessions attended (present or late counts as attended)
            attended_count = present_count + late_count
            attendance_rate = round((attended_count / past_sessions_count) * 100, 1)

        course_stats.append({
            'course': course,
            'course_id': course.course_id,
            'course_name': course.course_name,
            'total_sessions': total_sessions_count,
            'past_sessions': past_sessions_count,
            'present': present_count,
            'late': late_count,
            'absent': absent_count,
            'excused': excused_count,
            'attendance_rate': attendance_rate,
            'buffer_total': buffer_total,
            'buffer_used': round(buffer_used, 1),
            'buffer_remaining': round(buffer_remaining, 1),
            'sessions_left': sessions_left,
            'status': status,
            'status_class': status_class
        })

        total_buffer_all += buffer_total
        total_used_buffer_all += buffer_used

    context = {
        'student': student,

        # Timetable with course_id
        'upcoming_sessions': upcoming_sessions[:15],
        'past_sessions': past_sessions[:15],
        'has_upcoming': len(upcoming_sessions) > 0,
        'has_past': len(past_sessions) > 0,

        # Simplified attendance stats
        'course_stats': course_stats,
        'total_buffer_all': total_buffer_all,
        'total_used_buffer_all': round(total_used_buffer_all, 1),
        'total_remaining_buffer_all': round(total_buffer_all - total_used_buffer_all, 1),

        # Recent Attendance
        'recent_attendance': AttendanceLog.objects.filter(
            student=student
        ).select_related('session__course').order_by('-check_in_time')[:10],
    }

    return render(request, 'student_attendance/student/dashboard.html', context)

@login_required(login_url='student_attendance:login')
def my_attendance(request):
    """View all attendance records for a student"""
    try:
        student = request.user.student_profile
    except:
        messages.error(request, 'Student profile not found.')
        return redirect('student_attendance:login')

    # Get filter parameters
    course_id = request.GET.get('course')
    month = request.GET.get('month')
    status = request.GET.get('status')

    # Base queryset
    attendance_records = AttendanceLog.objects.filter(
        student=student
    ).select_related('session__course').order_by('-check_in_time')

    # Apply filters
    if course_id:
        attendance_records = attendance_records.filter(session__course__course_id=course_id)

    if month:
        try:
            year, month_num = map(int, month.split('-'))
            attendance_records = attendance_records.filter(
                check_in_time__year=year,
                check_in_time__month=month_num
            )
        except:
            pass

    if status:
        attendance_records = attendance_records.filter(status=status)

    # Pagination
    paginator = Paginator(attendance_records, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get all courses for filter dropdown
    courses = Course.objects.filter(attendance_logs__student=student).distinct()

    # Calculate summary statistics
    total_attendance = attendance_records.count()
    present_count = attendance_records.filter(status='PRESENT').count()
    late_count = attendance_records.filter(status='LATE').count()
    absent_count = attendance_records.filter(status='ABSENT').count()
    excused_count = attendance_records.filter(status='EXCUSED').count()

    context = {
        'student': student,
        'page_obj': page_obj,
        'courses': courses,
        'total_attendance': total_attendance,
        'present_count': present_count,
        'late_count': late_count,
        'absent_count': absent_count,
        'excused_count': excused_count,
        'current_filters': {
            'course': course_id,
            'month': month,
            'status': status,
        }
    }
    return render(request, 'student_attendance/student/my_attendance.html', context)


@csrf_protect
@ensure_csrf_cookie
def mark_attendance(request):
    """Page for students to mark attendance - public access with late checking"""
    # Ensure CSRF token is set for GET requests
    if request.method == 'GET':
        get_token(request)

    if request.method == 'POST':
        attendance_code = request.POST.get('attendance_code')
        student_id = request.POST.get('student_id')

        try:
            # Get student
            student = Student.objects.get(student_id=student_id)

            # Use timezone.now()
            now = timezone.now()

            # Validate attendance code - ONLY check expiration, NOT is_used
            code = AttendanceCode.objects.filter(
                code=attendance_code,
                expires_at__gt=now,
            ).select_related('session__course').first()

            if not code:
                messages.error(request, 'Invalid or expired attendance code')
                return redirect('student_attendance:mark_attendance')

            # Check if student is enrolled in this course
            course = code.session.course
            if not course.enrolled_students.filter(id=student.id).exists():
                messages.error(
                    request,
                    f'You are not enrolled in {course.course_name}. '
                    f'Please contact your teacher to enroll.'
                )
                return redirect('student_attendance:mark_attendance')

            # Check if session has already ended
            session = code.session
            session_ended = False
            end_time_message = ""

            if session.session_date < now.date():
                # Session date is in the past
                session_ended = True
                end_time_message = f"Session date {session.session_date} has passed"
            elif session.session_date == now.date() and session.end_time:
                # Session is today and has end time - check if end time has passed
                session_end_naive = datetime.combine(session.session_date, session.end_time)
                session_end_utc = timezone.make_aware(session_end_naive, dt_timezone.utc)

                if now > session_end_utc:
                    session_ended = True
                    end_time_message = f"Session ended at {session.end_time}"

            if session_ended:
                messages.error(
                    request,
                    f'Cannot mark attendance. {end_time_message}. '
                    f'This session has already ended.'
                )
                return redirect('student_attendance:mark_attendance')

            # Check if already marked for this session
            existing_attendance = AttendanceLog.objects.filter(
                student=student,
                session=code.session
            ).first()

            if existing_attendance:
                messages.warning(
                    request,
                    f'Attendance already marked for this session as {existing_attendance.get_status_display()} '
                    f'at {timezone.localtime(existing_attendance.check_in_time).strftime("%H:%M:%S")}'
                )
                return redirect('student_attendance:mark_attendance')

            # ============ LATE CHECKING LOGIC ============
            attendance_calc = {
                'session_start': None,
                'lateness_minutes': 0,
                'attendance_status': 'PRESENT',
                'status_message': 'attendance recorded',
                'time_diff_minutes': 0,
                'has_start_time': False,
                'is_late': False,
                'is_absent': False,
                'within_time': True
            }

            # If session has a defined start_time, use it for late checking
            if code.session.start_time:
                attendance_calc['has_start_time'] = True

                # Get the session date
                session_date = code.session.session_date

                # Create a naive datetime from the stored UTC date and time
                session_start_naive = datetime.combine(session_date, code.session.start_time)

                # Make it timezone-aware in UTC (since it's stored in UTC)
                session_start_utc = timezone.make_aware(session_start_naive, dt_timezone.utc)

                # Store the UTC version for calculation
                attendance_calc['session_start_utc'] = session_start_utc

                # For display, convert to local time
                attendance_calc['session_start'] = timezone.localtime(session_start_utc)

                # Calculate time difference in minutes using UTC times
                time_diff = now - session_start_utc
                attendance_calc['time_diff_minutes'] = time_diff.total_seconds() / 60
                attendance_calc['lateness_minutes'] = round(attendance_calc['time_diff_minutes'], 1)

                # Debug prints
                print(f"Session start UTC: {session_start_utc}")
                print(f"Session start HKT: {timezone.localtime(session_start_utc)}")
                print(f"Current time UTC: {now}")
                print(f"Current time HKT: {timezone.localtime(now)}")
                print(f"Time difference (minutes): {attendance_calc['time_diff_minutes']}")

                # Determine attendance status based on lateness
                if attendance_calc['time_diff_minutes'] <= 15:
                    attendance_calc['attendance_status'] = 'PRESENT'
                    attendance_calc[
                        'status_message'] = f'on time (checked in {attendance_calc["lateness_minutes"]} min after start)'
                    attendance_calc['within_time'] = True
                    attendance_calc['is_late'] = False
                    attendance_calc['is_absent'] = False
                elif attendance_calc['time_diff_minutes'] <= 30:
                    attendance_calc['attendance_status'] = 'LATE'
                    attendance_calc['status_message'] = f'{attendance_calc["lateness_minutes"]} minutes late'
                    attendance_calc['within_time'] = False
                    attendance_calc['is_late'] = True
                    attendance_calc['is_absent'] = False
                else:
                    attendance_calc['attendance_status'] = 'ABSENT'
                    attendance_calc[
                        'status_message'] = f'{attendance_calc["lateness_minutes"]} minutes late (marked as absent)'
                    attendance_calc['within_time'] = False
                    attendance_calc['is_late'] = False
                    attendance_calc['is_absent'] = True
            else:
                # If no start time defined, default to PRESENT
                attendance_calc['attendance_status'] = 'PRESENT'
                attendance_calc['status_message'] = 'attendance recorded (no session start time set)'
                attendance_calc['lateness_minutes'] = 0
                attendance_calc['time_diff_minutes'] = 0
                attendance_calc['within_time'] = True
                attendance_calc['is_late'] = False
                attendance_calc['is_absent'] = False
                print("No session start time set, defaulting to PRESENT")

            # Create detailed notes with all calculation information
            notes_parts = [
                f"Lateness: {attendance_calc['lateness_minutes']} minutes",
                f"Status: {attendance_calc['attendance_status']}",
                f"Message: {attendance_calc['status_message']}",
                f"Check-in: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC",
            ]

            if attendance_calc.get('session_start_utc'):
                notes_parts.append(
                    f"Session started: {attendance_calc['session_start_utc'].strftime('%Y-%m-%d %H:%M:%S')} UTC")
                notes_parts.append(f"Time difference: {attendance_calc['time_diff_minutes']} minutes")
                notes_parts.append(f"Has start time: Yes")
            else:
                notes_parts.append("Has start time: No")

            notes_parts.append(f"Is late: {attendance_calc['is_late']}")
            notes_parts.append(f"Is absent: {attendance_calc['is_absent']}")
            notes_parts.append(f"Within time: {attendance_calc['within_time']}")

            notes = ". ".join(notes_parts) + "."

            # Create attendance log with calculated status
            attendance_log = AttendanceLog.objects.create(
                student=student,
                session=code.session,
                attendance_code=code,
                status=attendance_calc['attendance_status'],
                check_in_time=now,  # This is already UTC from timezone.now()
                ip_address=request.META.get('REMOTE_ADDR'),
                device_info=request.META.get('HTTP_USER_AGENT', '')[:200],
                notes=notes
            )

            # Format the check-in time
            check_in_local = timezone.localtime(attendance_log.check_in_time)

            # Use status_message for user feedback
            if attendance_calc['attendance_status'] == 'PRESENT':
                messages.success(
                    request,
                    f'✅ Attendance marked successfully! You are {attendance_calc["status_message"]}. '
                    f'{code.session.course.course_name} - Session {code.session.session_number}'
                )
            elif attendance_calc['attendance_status'] == 'LATE':
                messages.warning(
                    request,
                    f'⚠️ You are {attendance_calc["status_message"]}! Your attendance has been recorded as Late.'
                )
            else:  # ABSENT
                messages.error(
                    request,
                    f'❌ You are {attendance_calc["status_message"]}.'
                )

            # Store in session
            request.session['last_attendance'] = {
                'course': code.session.course.course_name,
                'time': check_in_local.strftime('%H:%M:%S'),
                'status': attendance_calc['attendance_status'],
                'lateness': attendance_calc['lateness_minutes']
            }

            # Redirect based on login status
            if request.user.is_authenticated and hasattr(request.user, 'student_profile'):
                return redirect('student_attendance:student_dashboard')
            else:
                return redirect('student_attendance:mark_attendance')

        except Student.DoesNotExist:
            messages.error(request, 'Student ID not found')
        except Exception as e:
            messages.error(request, f'Error marking attendance: {str(e)}')
            print(f"Attendance error: {str(e)}")

        return redirect('student_attendance:mark_attendance')

    return render(request, 'student_attendance/student/mark_attendance.html')

@login_required(login_url='student_attendance:login')
def session_detail(request, session_id):
    """View details of a specific session with lateness statistics"""
    try:
        teacher = request.user.teacher_profile
    except:
        messages.error(request, 'Teacher profile not found.')
        return redirect('student_attendance:login')

    session = get_object_or_404(
        CourseSession,
        id=session_id,
        course__teacher=teacher
    )

    # Get all enrolled students for this course
    enrolled_students = session.course.enrolled_students.all()
    total_enrolled = enrolled_students.count()

    # Get attendance logs for this session
    attendance_logs = AttendanceLog.objects.filter(
        session=session
    ).select_related('student', 'attendance_code').order_by('-check_in_time')

    # Calculate statistics
    total_marked = attendance_logs.count()
    present_count = attendance_logs.filter(status='PRESENT').count()
    late_count = attendance_logs.filter(status='LATE').count()
    absent_count = attendance_logs.filter(status='ABSENT').count()
    excused_count = attendance_logs.filter(status='EXCUSED').count()

    # Calculate absent students (enrolled but not marked)
    marked_student_ids = attendance_logs.values_list('student_id', flat=True)
    absent_students = enrolled_students.exclude(id__in=marked_student_ids)

    # Calculate attendance rate
    attendance_rate = (total_marked / total_enrolled * 100) if total_enrolled > 0 else 0

    # Calculate average lateness among late students (using the property)
    late_logs = attendance_logs.filter(status='LATE')
    if late_logs.exists():
        avg_lateness = sum([log.lateness_minutes for log in late_logs]) / late_logs.count()
        avg_lateness = round(avg_lateness, 1)
    else:
        avg_lateness = 0

    context = {
        'session': session,
        'attendance_logs': attendance_logs,  # These objects have .lateness_minutes property
        'enrolled_students': enrolled_students,
        'absent_students': absent_students,
        'total_enrolled': total_enrolled,
        'total_marked': total_marked,
        'present_count': present_count,
        'late_count': late_count,
        'absent_count': absent_count,
        'excused_count': excused_count,
        'attendance_rate': attendance_rate,
        'avg_lateness': avg_lateness,
        'now': timezone.now(),
    }
    return render(request, 'student_attendance/teacher/session_detail.html', context)

# Dashboard Views (accessible by teachers)
@login_required(login_url='student_attendance:login')
def course_dashboard(request, course_id):
    """Detailed attendance dashboard for a specific course"""
    try:
        teacher = request.user.teacher_profile
    except:
        messages.error(request, 'Teacher profile not found.')
        return redirect('student_attendance:login')

    course = get_object_or_404(Course, course_id=course_id, teacher=teacher)

    # Get all sessions for this course
    sessions = CourseSession.objects.filter(course=course).order_by('session_number')

    # Get all students who attended this course
    students = Student.objects.filter(
        attendance_logs__session__course=course
    ).distinct().annotate(
        total_attended=Count('attendance_logs', filter=Q(attendance_logs__session__course=course), distinct=True),
        present_count=Count('attendance_logs',
                            filter=Q(attendance_logs__session__course=course, attendance_logs__status='PRESENT')),
        late_count=Count('attendance_logs',
                         filter=Q(attendance_logs__session__course=course, attendance_logs__status='LATE')),
        absent_count=Count('attendance_logs',
                           filter=Q(attendance_logs__session__course=course, attendance_logs__status='ABSENT')),
        excused_count=Count('attendance_logs',
                            filter=Q(attendance_logs__session__course=course, attendance_logs__status='EXCUSED'))
    )

    # Calculate attendance percentage for each student
    total_sessions = sessions.count()
    for student in students:
        if total_sessions > 0:
            student.attendance_percentage = round((student.total_attended / total_sessions) * 100, 2)
        else:
            student.attendance_percentage = 0

    # Session-wise attendance matrix
    attendance_matrix = []
    for session in sessions:
        session_data = {
            'session': session,
            'attendances': {}
        }
        for log in AttendanceLog.objects.filter(session=session).select_related('student'):
            session_data['attendances'][log.student.id] = log
        attendance_matrix.append(session_data)

    context = {
        'course': course,
        'sessions': sessions,
        'students': students,
        'attendance_matrix': attendance_matrix,
        'total_sessions': total_sessions,
    }
    return render(request, 'student_attendance/teacher/course_dashboard.html', context)


@login_required(login_url='student_attendance:login')
def teacher_course_attendance(request):
    """Teacher portal to view overall course attendance with late categories"""
    try:
        teacher = request.user.teacher_profile
    except:
        messages.error(request, 'Teacher profile not found.')
        return redirect('student_attendance:login')

    # Get filter parameters
    course_id = request.GET.get('course')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status_filter = request.GET.get('status')
    session_filter = request.GET.get('session')

    # Get all courses for this teacher (for filter dropdown)
    courses = Course.objects.filter(teacher=teacher)

    # Base queryset for attendance logs (only this teacher's courses)
    attendance_logs = AttendanceLog.objects.filter(
        session__course__teacher=teacher
    ).select_related(
        'student',
        'session__course'
    ).order_by('-check_in_time')

    # Apply filters
    if course_id:
        attendance_logs = attendance_logs.filter(session__course__course_id=course_id)

    if date_from:
        attendance_logs = attendance_logs.filter(check_in_time__date__gte=date_from)

    if date_to:
        attendance_logs = attendance_logs.filter(check_in_time__date__lte=date_to)

    if status_filter:
        attendance_logs = attendance_logs.filter(status=status_filter)

    if session_filter:
        attendance_logs = attendance_logs.filter(session__session_number=session_filter)

    # Calculate lateness for each attendance log
    for log in attendance_logs:
        log.lateness_minutes = 0
        log.lateness_category = 'On Time'

        if log.session.start_time and log.check_in_time:
            session_start = timezone.make_aware(
                datetime.combine(log.session.session_date, log.session.start_time)
            )
            time_diff = (log.check_in_time - session_start).total_seconds() / 60
            log.lateness_minutes = round(time_diff, 1)

            # Categorize lateness
            if time_diff <= 15:
                log.lateness_category = 'On Time'
            elif time_diff <= 30:
                log.lateness_category = 'Late Warning'
            else:
                log.lateness_category = 'Absent (Late)'

    # Course-wise summary statistics
    course_summary = []
    for course in courses:
        course_logs = attendance_logs.filter(session__course=course)
        total_logs = course_logs.count()

        if total_logs > 0:
            summary = {
                'course': course,
                'total_attendance': total_logs,
                'present_count': course_logs.filter(status='PRESENT').count(),
                'late_count': course_logs.filter(status='LATE').count(),
                'absent_count': course_logs.filter(status='ABSENT').count(),
                'excused_count': course_logs.filter(status='EXCUSED').count(),

                # Calculate lateness categories
                'on_time_count': 0,
                'late_warning_count': 0,
                'absent_late_count': 0,
            }

            # Calculate lateness categories for this course
            for log in course_logs:
                if log.session.start_time and log.check_in_time:
                    session_start = timezone.make_aware(
                        datetime.combine(log.session.session_date, log.session.start_time)
                    )
                    time_diff = (log.check_in_time - session_start).total_seconds() / 60

                    if time_diff <= 15:
                        summary['on_time_count'] += 1
                    elif time_diff <= 30:
                        summary['late_warning_count'] += 1
                    else:
                        summary['absent_late_count'] += 1

            # Calculate percentages
            summary['present_percentage'] = round((summary['present_count'] / total_logs) * 100, 1)
            summary['late_percentage'] = round((summary['late_count'] / total_logs) * 100, 1)
            summary['absent_percentage'] = round((summary['absent_count'] / total_logs) * 100, 1)

            course_summary.append(summary)

    # Overall statistics
    total_attendance = attendance_logs.count()
    overall_stats = {
        'total_attendance': total_attendance,
        'present_count': attendance_logs.filter(status='PRESENT').count(),
        'late_count': attendance_logs.filter(status='LATE').count(),
        'absent_count': attendance_logs.filter(status='ABSENT').count(),
        'excused_count': attendance_logs.filter(status='EXCUSED').count(),
        'on_time_count': 0,
        'late_warning_count': 0,
        'absent_late_count': 0,
    }

    # Calculate overall lateness categories
    for log in attendance_logs:
        if log.session.start_time and log.check_in_time:
            session_start = timezone.make_aware(
                datetime.combine(log.session.session_date, log.session.start_time)
            )
            time_diff = (log.check_in_time - session_start).total_seconds() / 60

            if time_diff <= 15:
                overall_stats['on_time_count'] += 1
            elif time_diff <= 30:
                overall_stats['late_warning_count'] += 1
            else:
                overall_stats['absent_late_count'] += 1

    # Pagination
    paginator = Paginator(attendance_logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get unique sessions for filter
    sessions = CourseSession.objects.filter(
        course__teacher=teacher
    ).values_list('session_number', flat=True).distinct().order_by('session_number')

    context = {
        'teacher': teacher,
        'courses': courses,
        'page_obj': page_obj,
        'course_summary': course_summary,
        'overall_stats': overall_stats,
        'sessions': sessions,
        'current_filters': {
            'course': course_id,
            'date_from': date_from,
            'date_to': date_to,
            'status': status_filter,
            'session': session_filter,
        },
        'status_choices': AttendanceLog.STATUS_CHOICES,
    }

    return render(request, 'student_attendance/teacher/course_attendance.html', context)


@login_required(login_url='student_attendance:login')
def student_attendance_detail(request, student_id):
    """Detailed attendance view for a specific student"""
    try:
        teacher = request.user.teacher_profile
    except:
        messages.error(request, 'Teacher profile not found.')
        return redirect('student_attendance:login')

    student = get_object_or_404(Student, id=student_id)

    # Get all courses this student has taken with this teacher
    courses = Course.objects.filter(
        teacher=teacher,
        attendance_logs__student=student
    ).distinct()

    # Get all attendance records for this student with this teacher
    attendance_records = AttendanceLog.objects.filter(
        student=student,
        session__course__teacher=teacher
    ).select_related('session__course').order_by('-check_in_time')

    # Calculate statistics
    total_records = attendance_records.count()
    present_count = attendance_records.filter(status='PRESENT').count()
    late_count = attendance_records.filter(status='LATE').count()
    absent_count = attendance_records.filter(status='ABSENT').count()
    excused_count = attendance_records.filter(status='EXCUSED').count()

    # Attendance by course
    course_stats = []
    for course in courses:
        course_records = attendance_records.filter(session__course=course)
        course_total = course_records.count()
        course_present = course_records.filter(status='PRESENT').count()
        course_stats.append({
            'course': course,
            'total': course_total,
            'present': course_present,
            'percentage': round((course_present / course_total * 100), 2) if course_total > 0 else 0
        })

    context = {
        'student': student,
        'attendance_records': attendance_records,
        'total_records': total_records,
        'present_count': present_count,
        'late_count': late_count,
        'absent_count': absent_count,
        'excused_count': excused_count,
        'course_stats': course_stats,
    }
    return render(request, 'student_attendance/dashboard/student_detail.html', context)


@login_required(login_url='student_attendance:login')
def attendance_reports(request):
    """Generate attendance reports"""
    try:
        teacher = request.user.teacher_profile
    except:
        messages.error(request, 'Teacher profile not found.')
        return redirect('student_attendance:login')

    # Get date range from request
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    course_id = request.GET.get('course')

    # Base queryset
    attendance_logs = AttendanceLog.objects.filter(
        session__course__teacher=teacher
    ).select_related('student', 'session__course')

    # Apply filters
    if start_date:
        attendance_logs = attendance_logs.filter(check_in_time__date__gte=start_date)
    if end_date:
        attendance_logs = attendance_logs.filter(check_in_time__date__lte=end_date)
    if course_id:
        attendance_logs = attendance_logs.filter(session__course__course_id=course_id)

    # Group by course
    course_summary = attendance_logs.values(
        'session__course__course_id',
        'session__course__course_name'
    ).annotate(
        total_students=Count('student', distinct=True),
        total_attendance=Count('id'),
        present_count=Count('id', filter=Q(status='PRESENT')),
        late_count=Count('id', filter=Q(status='LATE')),
        absent_count=Count('id', filter=Q(status='ABSENT')),
        excused_count=Count('id', filter=Q(status='EXCUSED'))
    ).order_by('session__course__course_name')

    # Group by day of week
    day_summary = attendance_logs.values('session__session_date__week_day').annotate(
        total=Count('id')
    ).order_by('session__session_date__week_day')

    courses = Course.objects.filter(teacher=teacher)

    context = {
        'course_summary': course_summary,
        'day_summary': day_summary,
        'courses': courses,
        'start_date': start_date,
        'end_date': end_date,
        'selected_course': course_id,
    }
    return render(request, 'student_attendance/dashboard/reports.html', context)


# API Views
def validate_attendance_code(request):
    """API endpoint to validate attendance code"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            code = data.get('code')

            # Use timezone.now() for comparison
            now = timezone.now()

            attendance_code = AttendanceCode.objects.filter(
                code=code,
                expires_at__gt=now,
                is_used=False
            ).select_related('session__course').first()

            if attendance_code:
                # Format times in local timezone
                expires_local = timezone.localtime(attendance_code.expires_at)

                return JsonResponse({
                    'valid': True,
                    'session': {
                        'code': attendance_code.session.session_code,
                        'course_name': attendance_code.session.course.course_name,
                        'course_id': attendance_code.session.course.course_id,
                        'session_number': attendance_code.session.session_number,
                        'expires_at': expires_local.isoformat(),
                        'expires_at_formatted': expires_local.strftime('%Y-%m-%d %H:%M:%S'),
                        'time_remaining': (attendance_code.expires_at - now).seconds // 60
                    }
                })
            else:
                return JsonResponse({
                    'valid': False,
                    'message': 'Invalid or expired code'
                })
        except Exception as e:
            return JsonResponse({
                'valid': False,
                'message': f'Error validating code: {str(e)}'
            }, status=400)

    return JsonResponse({'error': 'Method not allowed'}, status=405)