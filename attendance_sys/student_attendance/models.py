from django.db import models
from django.db.models.functions import datetime
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
    def local_start_datetime(self):
        """Get the session start time converted to local timezone"""
        if not self.start_time or not self.session_date:
            return None

        # Create a naive datetime from date and time
        naive_dt = datetime.combine(self.session_date, self.start_time)

        # IMPORTANT: The time in database is stored as UTC
        # So we make it aware in UTC first
        utc_dt = timezone.make_aware(naive_dt, timezone.utc)

        # Then convert to local timezone (Hong Kong)
        return timezone.localtime(utc_dt)

    @property
    def local_start_time(self):
        """Get start time in local timezone (for display)"""
        local_dt = self.local_start_datetime
        if local_dt:
            return local_dt.time()
        return None

    @property
    def local_start_datetime_str(self):
        """Get formatted local start datetime for display"""
        local_dt = self.local_start_datetime
        if local_dt:
            return local_dt.strftime('%Y-%m-%d %H:%M:%S')
        return None

    @property
    def utc_start_datetime(self):
        """Get the session start time as UTC datetime (for calculations)"""
        if not self.start_time or not self.session_date:
            return None

        naive_dt = datetime.combine(self.session_date, self.start_time)
        return timezone.make_aware(naive_dt, timezone.utc)


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
        unique_together = ['student', 'session']  # One attendance per student per session
        indexes = [
            models.Index(fields=['student', 'session']),
            models.Index(fields=['status', 'check_in_time']),
            models.Index(fields=['session', 'status']),
        ]

    def __str__(self):
        return f"{self.student} - {self.session} - {self.status}"