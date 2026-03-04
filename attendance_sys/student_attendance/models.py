from django.db import models
from datetime import datetime
from django.utils import timezone
from datetime import timezone as dt_timezone
from django.utils import timezone
from django.contrib.auth.models import User
import random
import string
import json


class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, related_name='teacher_profile')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    teacher_id = models.CharField(max_length=20, unique=True, editable=False)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def generate_teacher_id(self):
        """Generate a unique teacher ID with format: TCH-YYYY-XXXX"""
        year = timezone.now().strftime('%Y')
        last_teacher = Teacher.objects.filter(
            teacher_id__startswith=f'TCH-{year}-'
        ).order_by('teacher_id').last()

        if last_teacher:
            last_sequence = int(last_teacher.teacher_id.split('-')[-1])
            new_sequence = last_sequence + 1
        else:
            new_sequence = 1

        return f'TCH-{year}-{new_sequence:04d}'

    def save(self, *args, **kwargs):
        if not self.teacher_id:
            self.teacher_id = self.generate_teacher_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.teacher_id} - {self.first_name} {self.last_name}'

    class Meta:
        db_table = 'teacher'
        verbose_name_plural = 'Teachers'
        ordering = ['-created_at']

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, related_name='student_profile')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    student_id = models.CharField(max_length=20, unique=True, editable=False)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def generate_student_id(self):
        """Generate a unique student ID with format: STU-YYYY-XXXX"""
        year = timezone.now().strftime('%Y')
        last_student = Student.objects.filter(
            student_id__startswith=f'STU-{year}-'
        ).order_by('student_id').last()

        if last_student:
            last_sequence = int(last_student.student_id.split('-')[-1])
            new_sequence = last_sequence + 1
        else:
            new_sequence = 1

        return f'STU-{year}-{new_sequence:04d}'

    def save(self, *args, **kwargs):
        if not self.student_id:
            self.student_id = self.generate_student_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.student_id} - {self.first_name} {self.last_name}'

    class Meta:
        db_table = 'student'
        verbose_name_plural = 'Students'
        ordering = ['-created_at']


class Course(models.Model):
    course_id = models.CharField(max_length=20, primary_key=True)
    course_name = models.CharField(max_length=100)
    course_description = models.TextField()
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='courses', null=True, blank=True)
    total_sessions = models.IntegerField(default=0, help_text="Total number of sessions for this course")

    # Many-to-many relationship with students
    enrolled_students = models.ManyToManyField(
        'Student',
        related_name='enrolled_courses',
        blank=True,
        help_text="Students enrolled in this course"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.course_id} - {self.course_name}'

    def enrolled_count(self):
        """Return the number of enrolled students"""
        return self.enrolled_students.count()

    enrolled_count.short_description = 'Enrolled Students'

    class Meta:
        db_table = 'course'
        verbose_name_plural = 'Courses'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['course_id']),
            models.Index(fields=['course_name']),
        ]

class CourseSession(models.Model):
    """
    Represents a specific session of a course (e.g., Session 1 of 50)
    """
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='sessions')
    session_number = models.IntegerField(help_text="Session number (e.g., 1, 2, 3...)")
    session_code = models.CharField(max_length=50, unique=True, editable=False)
    session_date = models.DateField(default=timezone.now)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    topic = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'course_session'
        verbose_name_plural = 'Course Sessions'
        ordering = ['course', 'session_number']
        unique_together = ['course', 'session_number']
        indexes = [
            models.Index(fields=['course', 'session_number']),
            models.Index(fields=['session_code']),
            models.Index(fields=['session_date']),
        ]

    def generate_session_code(self):
        """
        Generate session code: COURSE_ID + SESSION_NUMBER (formatted to 4 digits)
        Example: CS101-0001, CS101-0002, etc.
        """
        return f"{self.course.course_id}-{self.session_number:04d}"

    def save(self, *args, **kwargs):
        if not self.session_code:
            self.session_code = self.generate_session_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.session_code} - {self.session_date}"

    @property
    def start_time_hkt(self):
        """Get start time in Hong Kong time"""
        if not self.start_time or not self.session_date:
            return None

        try:
            # Combine date with UTC time
            naive_dt = datetime.combine(self.session_date, self.start_time)
            utc_dt = timezone.make_aware(naive_dt, dt_timezone.utc)
            hk_dt = timezone.localtime(utc_dt)
            return hk_dt.time()
        except:
            return self.start_time

    @property
    def end_time_hkt(self):
        """Get end time in Hong Kong time"""
        if not self.end_time or not self.session_date:
            return None

        try:
            # Combine date with UTC time
            naive_dt = datetime.combine(self.session_date, self.end_time)
            utc_dt = timezone.make_aware(naive_dt, dt_timezone.utc)
            hk_dt = timezone.localtime(utc_dt)
            return hk_dt.time()
        except:
            return self.end_time

    @property
    def start_time_hkt_str(self):
        """Get formatted start time string"""
        hk_time = self.start_time_hkt
        return hk_time.strftime('%H:%M') if hk_time else None

    @property
    def end_time_hkt_str(self):
        """Get formatted end time string"""
        hk_time = self.end_time_hkt
        return hk_time.strftime('%H:%M') if hk_time else None

class AttendanceCode(models.Model):
    """
    Generates unique attendance codes for each session (with random component)
    """
    session = models.OneToOneField(CourseSession, on_delete=models.CASCADE, related_name='attendance_code')
    code = models.CharField(max_length=20, unique=True)
    qr_code_data = models.TextField(help_text="Data to be encoded in QR code", blank=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'attendance_code'
        verbose_name_plural = 'Attendance Codes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['expires_at']),
        ]

    def generate_attendance_code(self):
        """
        Generate attendance code: COURSE_ID + SESSION_NUMBER + RANDOM_STRING
        Example: CS101-0001-A7B9, CS101-0002-X3K8, etc.
        """
        # Generate a random 4-character alphanumeric code
        random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"{self.session.course.course_id}-{self.session.session_number:04d}-{random_part}"

    def generate_qr_data(self):
        """
        Generate data to be encoded in QR code
        """
        return {
            'code': self.code,
            'session': self.session.session_code,
            'course': self.session.course.course_id,
            'course_name': self.session.course.course_name,
            'expires': self.expires_at.isoformat(),
            'type': 'attendance'
        }

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_attendance_code()
        if not self.qr_code_data:
            self.qr_code_data = json.dumps(self.generate_qr_data())
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - Expires: {self.expires_at.strftime('%Y-%m-%d %H:%M')}"


class Attendance(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, db_index=True)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, db_index=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    MONDAY = 'MON'
    TUESDAY = 'TUE'
    WEDNESDAY = 'WED'
    THURSDAY = 'THU'
    FRIDAY = 'FRI'
    SATURDAY = 'SAT'
    SUNDAY = 'SUN'

    DAY_CHOICES = [
        (MONDAY, 'Monday'),
        (TUESDAY, 'Tuesday'),
        (WEDNESDAY, 'Wednesday'),
        (THURSDAY, 'Thursday'),
        (FRIDAY, 'Friday'),
        (SATURDAY, 'Saturday'),
        (SUNDAY, 'Sunday'),
    ]

    effective_day = models.CharField(max_length=3, choices=DAY_CHOICES,
                                     default=MONDAY, db_index=True)

    def __str__(self):
        return f'{self.student} - {self.course} - {self.get_effective_day_display()}'

    class Meta:
        db_table = 'attendance'
        verbose_name_plural = 'Attendances'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['student', 'course']),
            models.Index(fields=['teacher', 'course']),
            models.Index(fields=['effective_day']),
        ]


class AttendanceLog(models.Model):
    """
    Records student attendance for specific sessions
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_logs')
    session = models.ForeignKey(CourseSession, on_delete=models.CASCADE, related_name='attendance_logs')
    attendance_code = models.ForeignKey(AttendanceCode, on_delete=models.SET_NULL, null=True, blank=True)

    PRESENT = 'PRESENT'
    ABSENT = 'ABSENT'
    LATE = 'LATE'
    EXCUSED = 'EXCUSED'

    STATUS_CHOICES = [
        (PRESENT, 'Present'),
        (ABSENT, 'Absent'),
        (LATE, 'Late'),
        (EXCUSED, 'Excused'),
    ]

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PRESENT, db_index=True)
    check_in_time = models.DateTimeField(default=timezone.now, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_info = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attendance_log'
        verbose_name_plural = 'Attendance Logs'
        ordering = ['-check_in_time']
        unique_together = ['student', 'session']
        indexes = [
            models.Index(fields=['student', 'session']),
            models.Index(fields=['status', 'check_in_time']),
            models.Index(fields=['session', 'status']),
        ]

    def __str__(self):
        return f"{self.student} - {self.session} - {self.status}"

    @property
    def lateness_minutes(self):
        """Calculate how late the student was (in minutes)"""
        if not self.session or not self.session.start_time or not self.check_in_time:
            return 0

        try:
            # Get session start in UTC
            session_start_naive = datetime.combine(self.session.session_date, self.session.start_time)
            session_start_utc = timezone.make_aware(session_start_naive, dt_timezone.utc)

            # Check-in time is already timezone-aware UTC
            time_diff = self.check_in_time - session_start_utc
            minutes = time_diff.total_seconds() / 60

            # Only count positive lateness (can't be early)
            return round(max(0, minutes), 1)
        except Exception as e:
            print(f"Error calculating lateness: {e}")
            return 0