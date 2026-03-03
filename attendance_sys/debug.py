from student_attendance.models import CourseSession, AttendanceLog
from django.utils import timezone
from datetime import datetime, timezone as dt_timezone


def debug_session():
    session = CourseSession.objects.last()
    print(f"Session: {session}")
    print(f"Session date: {session.session_date}")
    print(f"Start time (stored): {session.start_time}")

    if session.start_time:
        naive = datetime.combine(session.session_date, session.start_time)
        utc_time = timezone.make_aware(naive, dt_timezone.utc)
        hkt_time = timezone.localtime(utc_time)
        print(f"As UTC: {utc_time}")
        print(f"As HKT: {hkt_time}")

        log = AttendanceLog.objects.filter(session=session).first()
        if log:
            print(f"\nAttendance log:")
            print(f"Check-in UTC: {log.check_in_time}")
            print(f"Check-in HKT: {timezone.localtime(log.check_in_time)}")

            diff = log.check_in_time - utc_time
            print(f"Lateness minutes: {diff.total_seconds() / 60}")


if __name__ == "__main__":
    debug_session()