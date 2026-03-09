# weather_app/tasks.py
from apscheduler.schedulers.background import BackgroundScheduler
from django.conf import settings
import logging

from .views import fetch_and_store_weather

logger = logging.getLogger(__name__)

scheduler = None


def start_scheduler():
    """啟動後台調度器"""
    global scheduler

    if scheduler is not None and scheduler.running:
        logger.info('⚠️ 調度器已在運行')
        return

    scheduler = BackgroundScheduler()

    # ✅ 添加定時任務：每天 7:00 AM 執行一次
    scheduler.add_job(
        func=fetch_and_store_weather,
        trigger='cron',
        hour=7,
        minute=0,
        second=0,
        id='fetch_weather_job',
        name='Fetch and store weather data',
        replace_existing=True,  # ✅ 重要：替換已存在的任務
        max_instances=1  # ✅ 重要：同時只運行一個實例
    )

    scheduler.start()
    logger.info('✅ 定時調度器已啟動')
