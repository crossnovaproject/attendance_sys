# weather_app/admin.py
from django.contrib import admin
from .models import WeatherData, WarningAccessLog, SchoolSchedule


@admin.register(SchoolSchedule)
class SchoolScheduleAdmin(admin.ModelAdmin):
    """學校課表管理"""
    list_display = ('get_day_display', 'has_class', 'updated_at')
    list_editable = ('has_class',)
    list_filter = ('has_class',)
    readonly_fields = ('updated_at',)

    def get_day_display(self, obj):
        return obj.get_day_of_week_display()

    get_day_display.short_description = '星期'


@admin.register(WeatherData)
class WeatherDataAdmin(admin.ModelAdmin):
    """天氣數據管理"""
    list_display = ('recorded_at', 'temperature', 'humidity', 'wind_speed', 'pressure', 'rainfall')
    list_filter = ('recorded_at', 'created_at')
    search_fields = ('general_situation',)
    # ✅ 修正：包含 updated_at
    readonly_fields = ('created_at', 'updated_at', 'raw_data')
    date_hierarchy = 'recorded_at'
    ordering = ('-recorded_at',)

    fieldsets = (
        ('基本信息', {
            'fields': ('general_situation', 'recorded_at')
        }),
        ('氣象數據', {
            'fields': ('temperature', 'humidity', 'wind_speed', 'wind_direction', 'pressure', 'rainfall'),
            'description': '從香港天文台 API 獲取的實時數據'
        }),
        ('原始數據', {
            'fields': ('raw_data',),
            'classes': ('collapse',)
        }),
        ('時間戳', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(WarningAccessLog)
class WarningAccessLogAdmin(admin.ModelAdmin):
    """天氣警告讀取記錄管理"""
    # ✅ 修正：使用 accessed_at（Model 中的字段名）
    list_display = ('accessed_at', 'warning_count', 'warning_types', 'ip_address')
    search_fields = ('warning_types', 'ip_address', 'user_agent')
    list_filter = ('accessed_at', 'warning_count')
    # ✅ 修正：readonly_fields 中使用 accessed_at
    readonly_fields = ('accessed_at', 'raw_response', 'ip_address', 'user_agent')
    # ✅ 修正：date_hierarchy 使用 accessed_at
    date_hierarchy = 'accessed_at'
    list_per_page = 50

    fieldsets = (
        ('訪問信息', {
            'fields': ('accessed_at', 'ip_address', 'user_agent')
        }),
        ('警告統計', {
            'fields': ('warning_count', 'warning_types')
        }),
        ('原始響應', {
            'fields': ('raw_response',),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        """禁止手動添加記錄"""
        return False

    def has_delete_permission(self, request, obj=None):
        """禁止刪除記錄"""
        return False
