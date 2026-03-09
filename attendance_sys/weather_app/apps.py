# weather_app/apps.py
from django.apps import AppConfig


class WeatherAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'weather_app'

    def ready(self):
        """應用啟動時執行"""
        from .views import start_scheduler
        try:
            start_scheduler()
            print("✅ 7:00定時調度器已啟動")
        except Exception as e:
            print(f"❌ 啟動調度器失敗: {e}")
