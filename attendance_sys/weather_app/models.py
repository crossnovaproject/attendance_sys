# weather_app/models.py

from django.db import models
from django.utils import timezone


class SchoolSchedule(models.Model):
    """
    學校課表模型 - 只用來存儲課表數據
    """
    DAYS_OF_WEEK = [
        (0, '星期一'),
        (1, '星期二'),
        (2, '星期三'),
        (3, '星期四'),
        (4, '星期五'),
        (5, '星期六'),
        (6, '星期日'),
    ]

    day_of_week = models.IntegerField(
        choices=DAYS_OF_WEEK,
        unique=True,
        help_text="星期幾 (0=星期一, 6=星期日)"
    )
    has_class = models.BooleanField(
        default=True,
        help_text="該天是否有課"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "學校課表"
        verbose_name_plural = "學校課表"

    def __str__(self):
        # get_day_of_week_display() 由 Django 自動生成
        return f"{self.get_day_of_week_display()} - {'有課' if self.has_class else '無課'}"

    @classmethod
    def has_class_today(cls):
        """
        檢查今天是否有課
        """
        from datetime import datetime
        today_weekday = datetime.now().weekday()  # 0=星期一, 6=星期日

        try:
            schedule = cls.objects.get(day_of_week=today_weekday)
            return schedule.has_class
        except cls.DoesNotExist:
            # 如果沒有設置，默認有課
            return True

class WeatherData(models.Model):

    general_situation = models.CharField(max_length=255, blank=True, default='')  # 添加 default=''
    temperature = models.FloatField(null=True, blank=True)
    humidity = models.FloatField(null=True, blank=True)
    wind_speed = models.FloatField(null=True, blank=True)
    # ✅ 加上 null=True
    wind_direction = models.CharField(max_length=50, blank=True, null=True, default='')
    pressure = models.FloatField(null=True, blank=True)
    rainfall = models.FloatField(null=True, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)

    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['-recorded_at']),
        ]

    def __str__(self):
        return f"天氣數據 - {self.recorded_at.strftime('%Y-%m-%d %H:%M:%S')}"

class WarningAccessLog(models.Model):
    """天氣警告讀取記錄"""

    warning_count = models.IntegerField(
        verbose_name='警告數量'
    )

    warning_types = models.CharField(
        verbose_name='警告類型列表',
        max_length=500,
        help_text='逗號分隔的警告類型'
    )

    raw_response = models.JSONField(
        verbose_name='原始 API 響應',
        blank=True,
        null=True
    )

    ip_address = models.GenericIPAddressField(
        verbose_name='訪問 IP',
        blank=True,
        null=True
    )

    user_agent = models.CharField(
        verbose_name='用戶代理',
        max_length=500,
        blank=True,
        null=True
    )

    accessed_at = models.DateTimeField(
        verbose_name='訪問時間',
        auto_now_add=True
    )

    class Meta:
        verbose_name = '警告讀取記錄'
        verbose_name_plural = '警告讀取記錄'
        ordering = ['-accessed_at']

    def __str__(self):
        return f"讀取記錄 - {self.accessed_at.strftime('%Y-%m-%d %H:%M')} ({self.warning_count} 個警告)"
