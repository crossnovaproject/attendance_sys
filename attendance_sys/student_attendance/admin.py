from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.contrib.admin import helpers
from django.utils.timesince import timesince
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import path
from django.template.response import TemplateResponse
from django.contrib.admin import AdminSite
from django.shortcuts import render
from .models import (
    Student, Teacher, Course, CourseSession,
    AttendanceCode, Attendance, AttendanceLog
)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['student_id', 'full_name', 'email', 'created_at', 'attendance_count']
    list_display_links = ['student_id', 'full_name']
    search_fields = ['student_id', 'first_name', 'last_name', 'email']
    list_filter = ['created_at', 'updated_at']
    readonly_fields = ['student_id', 'created_at', 'updated_at']
    ordering = ['-created_at']

    fieldsets = (
        ('Personal Information', {
            'fields': ('user', 'first_name', 'last_name', 'email')
        }),
        ('System Information', {
            'fields': ('student_id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    full_name.short_description = 'Full Name'

    def attendance_count(self, obj):
        count = obj.attendance_logs.count()
        url = reverse('admin:student_attendance_attendancelog_changelist') + f'?student__id__exact={obj.id}'
        return format_html('<a href="{}">{} attendance records</a>', url, count)

    attendance_count.short_description = 'Attendance'

    def delete_model(self, request, obj):
        """Delete the student and optionally the associated user"""
        user = obj.user
        obj.delete()
        if user and not hasattr(user, 'teacher_profile'):
            user.delete()
            self.message_user(request, f"Student and associated user '{user.username}' deleted successfully.")
        else:
            self.message_user(request, "Student deleted successfully. User account preserved.")

    def delete_queryset(self, request, queryset):
        """Handle bulk delete"""
        for obj in queryset:
            user = obj.user
            obj.delete()
            if user and not hasattr(user, 'teacher_profile'):
                user.delete()
        self.message_user(request, f"{queryset.count()} students and their associated users deleted successfully.")


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ['teacher_id', 'full_name', 'email', 'courses_count', 'created_at']
    list_display_links = ['teacher_id', 'full_name']
    search_fields = ['teacher_id', 'first_name', 'last_name', 'email']
    list_filter = ['created_at', 'updated_at']
    readonly_fields = ['teacher_id', 'created_at', 'updated_at']

    fieldsets = (
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'email')
        }),
        ('System Information', {
            'fields': ('teacher_id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    full_name.short_description = 'Full Name'

    def courses_count(self, obj):
        return obj.courses.count()

    courses_count.short_description = 'Courses'

    def delete_model(self, request, obj):
        """Delete the teacher and optionally the associated user"""
        user = obj.user
        obj.delete()
        if user and not hasattr(user, 'student_profile'):
            # If user has no student profile, delete the user too
            user.delete()
            self.message_user(request, f"Teacher and associated user '{user.username}' deleted successfully.")
        else:
            self.message_user(request, "Teacher deleted successfully. User account preserved.")

    def delete_queryset(self, request, queryset):
        """Handle bulk delete"""
        for obj in queryset:
            user = obj.user
            obj.delete()
            if user and not hasattr(user, 'student_profile'):
                user.delete()
        self.message_user(request, f"{queryset.count()} teachers and their associated users deleted successfully.")


class CourseSessionInline(admin.TabularInline):
    model = CourseSession
    extra = 1
    fields = ['session_number', 'session_date', 'start_time', 'end_time', 'topic', 'is_active']
    show_change_link = True

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['course_id', 'course_name', 'teacher', 'total_sessions', 'enrolled_count',
                    'sessions_count', 'attendance_count', 'created_at']
    list_display_links = ['course_id', 'course_name']
    search_fields = ['course_id', 'course_name', 'course_description']
    list_filter = ['teacher', 'created_at', 'updated_at']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [CourseSessionInline]

    # Add filter_horizontal for better many-to-many UI
    filter_horizontal = ['enrolled_students']

    fieldsets = (
        ('Course Information', {
            'fields': ('course_id', 'course_name', 'course_description', 'teacher', 'total_sessions')
        }),
        ('Student Enrollment', {
            'fields': ('enrolled_students',),
            'description': 'Select students who are enrolled in this course. Only these students can mark attendance.',
            'classes': ('wide',)
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def sessions_count(self, obj):
        count = obj.sessions.count()
        url = reverse('admin:student_attendance_coursesession_changelist') + f'?course__id__exact={obj.pk}'
        return format_html('<a href="{}">{} sessions</a>', url, count)

    sessions_count.short_description = 'Sessions'

    def attendance_count(self, obj):
        count = AttendanceLog.objects.filter(session__course=obj).count()
        return count

    attendance_count.short_description = 'Total Attendances'

    def enrolled_count(self, obj):
        """Return the number of enrolled students"""
        count = obj.enrolled_students.count()
        url = reverse('admin:student_attendance_student_changelist') + f'?enrolled_courses__id__exact={obj.pk}'
        return format_html('<a href="{}">{} students</a>', url, count)

    enrolled_count.short_description = 'Enrolled Students'

    # Optional: Add action to bulk enroll students
    actions = ['bulk_enroll_students']

    def bulk_enroll_students(self, request, queryset):
        """Action to bulk enroll students to selected courses"""
        if 'apply' in request.POST:
            # Get the selected student IDs from the form
            student_ids = request.POST.getlist('_selected_action_students')
            students = Student.objects.filter(pk__in=student_ids)

            for course in queryset:
                course.enrolled_students.add(*students)

            self.message_user(request,
                              f"Successfully enrolled {students.count()} students to {queryset.count()} courses")
            return None

        # Get all students for selection
        all_students = Student.objects.all().order_by('first_name', 'last_name')

        context = {
            'title': 'Bulk Enroll Students',
            'queryset': queryset,
            'all_students': all_students,
            'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
            'opts': self.model._meta,
        }
        return render(request, 'admin/bulk_enroll_students.html', context)

    bulk_enroll_students.short_description = "Enroll selected students to selected courses"

@admin.register(CourseSession)
class CourseSessionAdmin(admin.ModelAdmin):
    list_display = ['session_code', 'course', 'session_number', 'session_date', 'is_active', 'attendance_count']
    list_display_links = ['session_code']
    search_fields = ['session_code', 'course__course_name', 'topic']
    list_filter = ['is_active', 'session_date', 'course']
    readonly_fields = ['session_code', 'created_at', 'updated_at']
    raw_id_fields = ['course']

    fieldsets = (
        ('Session Information', {
            'fields': ('course', 'session_number', 'session_code', 'session_date', 'start_time', 'end_time', 'topic',
                       'is_active')
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def attendance_count(self, obj):
        count = obj.attendance_logs.count()
        url = reverse('admin:student_attendance_attendancelog_changelist') + f'?session__id__exact={obj.id}'
        return format_html('<a href="{}">{} attendances</a>', url, count)

    attendance_count.short_description = 'Attendances'


@admin.register(AttendanceCode)
class AttendanceCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'session', 'expires_at', 'is_used', 'time_remaining', 'created_at']
    list_display_links = ['code']
    search_fields = ['code', 'session__session_code']
    list_filter = ['is_used', 'expires_at', 'created_at']
    readonly_fields = ['code', 'qr_code_data', 'created_at']
    raw_id_fields = ['session']
    actions = ['mark_as_used', 'mark_as_unused']

    fieldsets = (
        ('Code Information', {
            'fields': ('session', 'code', 'expires_at', 'is_used')
        }),
        ('QR Code Data', {
            'fields': ('qr_code_data',),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def time_remaining(self, obj):
        if obj.expires_at > timezone.now():
            remaining = obj.expires_at - timezone.now()
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60
            if remaining.days > 0:
                return format_html('<span style="color: green;">{} days, {} hours</span>', remaining.days, hours)
            else:
                return format_html('<span style="color: green;">{} hours, {} minutes</span>', hours, minutes)
        else:
            return format_html('<span style="color: red;">Expired</span>')

    time_remaining.short_description = 'Time Remaining'

    def mark_as_used(self, request, queryset):
        queryset.update(is_used=True)

    mark_as_used.short_description = "Mark selected codes as used"

    def mark_as_unused(self, request, queryset):
        queryset.update(is_used=False)

    mark_as_unused.short_description = "Mark selected codes as unused"


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'teacher', 'effective_day', 'created_at']
    list_filter = ['effective_day', 'created_at', 'course', 'teacher']
    search_fields = ['student__first_name', 'student__last_name', 'course__course_name']
    raw_id_fields = ['student', 'teacher', 'course']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Attendance Information', {
            'fields': ('student', 'teacher', 'course', 'effective_day')
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AttendanceLog)
class AttendanceLogAdmin(admin.ModelAdmin):
    list_display = ['student', 'session', 'status', 'check_in_time', 'time_ago', 'device_info_short']
    list_display_links = ['student', 'session']
    list_filter = ['status', 'check_in_time', 'session__course']
    search_fields = ['student__first_name', 'student__last_name', 'student__student_id', 'session__session_code']
    readonly_fields = ['created_at', 'updated_at', 'ip_address', 'device_info']
    raw_id_fields = ['student', 'session', 'attendance_code']
    date_hierarchy = 'check_in_time'
    actions = ['mark_as_present', 'mark_as_absent', 'mark_as_late', 'mark_as_excused']

    fieldsets = (
        ('Attendance Information', {
            'fields': ('student', 'session', 'attendance_code', 'status', 'check_in_time')
        }),
        ('Additional Information', {
            'fields': ('ip_address', 'device_info', 'notes'),
            'classes': ('wide',)
        }),
        ('System Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def device_info_short(self, obj):
        if obj.device_info:
            return obj.device_info[:50] + '...' if len(obj.device_info) > 50 else obj.device_info
        return '-'

    device_info_short.short_description = 'Device'

    def time_ago(self, obj):

        return timesince(obj.check_in_time, timezone.now()) + ' ago'

    time_ago.short_description = 'Time Ago'

    def mark_as_present(self, request, queryset):
        queryset.update(status='PRESENT')

    mark_as_present.short_description = "Mark selected as Present"

    def mark_as_absent(self, request, queryset):
        queryset.update(status='ABSENT')

    mark_as_absent.short_description = "Mark selected as Absent"

    def mark_as_late(self, request, queryset):
        queryset.update(status='LATE')

    mark_as_late.short_description = "Mark selected as Late"

    def mark_as_excused(self, request, queryset):
        queryset.update(status='EXCUSED')

    mark_as_excused.short_description = "Mark selected as Excused"


# Customize Admin Site
admin.site.site_header = 'Attendance System Administration'
admin.site.site_title = 'Attendance System Admin'
admin.site.index_title = 'Welcome to Attendance System Administration'

class AttendanceAdminSite(AdminSite):
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('attendance-summary/', self.admin_view(self.attendance_summary), name='attendance-summary'),
            path('export-data/', self.admin_view(self.export_data), name='export-data'),
        ]
        return custom_urls + urls

    def attendance_summary(self, request):
        """Custom admin view for attendance summary"""
        context = dict(
            self.each_context(request),
            title='Attendance Summary',
            # Add your summary data here
            total_students=Student.objects.count(),
            total_teachers=Teacher.objects.count(),
            total_courses=Course.objects.count(),
            total_attendances=AttendanceLog.objects.count(),
            today_attendances=AttendanceLog.objects.filter(check_in_time__date=timezone.now().date()).count(),
        )
        return TemplateResponse(request, 'admin/attendance_summary.html', context)

    def export_data(self, request):
        """Custom admin view for data export"""
        if request.method == 'POST':
            # Handle data export logic here
            messages.success(request, 'Data exported successfully!')
            return HttpResponseRedirect(request.path_info)

        context = dict(
            self.each_context(request),
            title='Export Data',
        )
        return TemplateResponse(request, 'admin/export_data.html', context)

# Uncomment the following line to use custom admin site
# admin_site = AttendanceAdminSite(name='myadmin')