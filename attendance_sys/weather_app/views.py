# weather_app/views.py
import requests
import logging
from datetime import datetime, timedelta, time
from django.http import JsonResponse
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import WeatherData, WarningAccessLog
from apscheduler.schedulers.background import BackgroundScheduler
from django.utils import timezone
from django.db.models import Count
from django.db.models import Max

logger = logging.getLogger(__name__)

# 全局調度器實例
scheduler = None


class WeatherHistoryView(APIView):
    """查詢天氣歷史記錄"""

    def get(self, request):
        """
        查詢指定日期的天氣數據
        ?date=2024-03-04 或 ?days=7 (最近 7 天)
        """
        try:
            date_str = request.query_params.get('date')
            days = request.query_params.get('days', 7)

            if date_str:
                # 查詢特定日期
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                records = WeatherData.objects.filter(
                    recorded_at__date=target_date
                ).order_by('-recorded_at')
            else:
                # 查詢最近 N 天
                start_date = timezone.now() - timedelta(days=int(days))
                records = WeatherData.objects.filter(
                    recorded_at__gte=start_date
                ).order_by('-recorded_at')

            data = [{
                'date': r.recorded_at.strftime('%Y-%m-%d %H:%M:%S'),
                'temperature': r.temperature,
                'humidity': r.humidity,
                'windSpeed': r.wind_speed,
                'windDirection': r.wind_direction,
                'pressure': r.pressure,
                'rainfall': r.rainfall,
            } for r in records]

            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f'查詢歷史數據失敗: {str(e)}')
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


def delete_duplicate_records():
    """
    ✅ 新增：清理重複的天氣記錄
    只保留每天最新的一條記錄
    """
    try:
        logger.info('[清理任務] 開始清理重複記錄...')

        # 獲取所有記錄，按日期和 ID 分組

        # 找出有重複的日期
        duplicate_dates = WeatherData.objects.extra(
            select={'date': 'DATE(recorded_at)'}
        ).values('date').annotate(
            count=Count('id')
        ).filter(count__gt=1)

        total_deleted = 0

        for item in duplicate_dates:
            date = item['date']
            # 獲取該日期的所有記錄，保留最新的
            records = WeatherData.objects.filter(
                recorded_at__date=date
            ).order_by('-recorded_at')

            if records.count() > 1:
                # 保留第一條（最新的），刪除其他
                records_to_delete = records[1:]
                deleted_count = records_to_delete.delete()[0]
                total_deleted += deleted_count
                logger.info(f'  - {date}: 刪除 {deleted_count} 條重複記錄')

        logger.info(f'[清理任務] ✅ 完成 - 共刪除 {total_deleted} 條重複記錄')
        return total_deleted

    except Exception as e:
        logger.error(f'[清理任務] ❌ 清理重複記錄失敗: {str(e)}')
        return 0


def fetch_and_store_weather():
    """
    ✅ 修改版本：定時任務 - 每天 7:00 AM 獲取並存儲天氣數據
    使用 update_or_create() 避免重複記錄
    """
    try:
        logger.info(f'[定時任務] 開始獲取天氣數據 - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

        base_url = "https://data.weather.gov.hk/weatherAPI/opendata/weather.php"

        # 獲取 rhrread 數據
        rhrread_resp = requests.get(
            base_url,
            params={'dataType': 'rhrread', 'lang': 'tc'},
            timeout=10
        )
        rhrread_resp.raise_for_status()
        rhrread_data = rhrread_resp.json()

        # 獲取 flw 數據
        flw_resp = requests.get(
            base_url,
            params={'dataType': 'flw', 'lang': 'tc'},
            timeout=10
        )
        flw_resp.raise_for_status()
        flw_data = flw_resp.json()

        # 解析數據
        parsed = WeatherDataView.parse_weather_data(rhrread_data, flw_data)

        # ✅ 使用 update_or_create() 而不是 create()
        now = timezone.now()
        today = now.date()

        weather_record, created = WeatherData.objects.update_or_create(
            # 查詢條件：同一天的記錄
            recorded_at__date=today,
            # 默認值（創建新記錄時使用）
            defaults={
                'general_situation': parsed.get('generalSituation', ''),
                'temperature': parsed.get('temperature'),
                'humidity': parsed.get('humidity'),
                'wind_speed': parsed.get('windSpeed'),
                'wind_direction': parsed.get('windDirection', ''),
                'pressure': parsed.get('pressure'),
                'rainfall': parsed.get('rainfall'),
                'raw_data': rhrread_data,
                'recorded_at': now,
            }
        )

        if created:
            logger.info(f'[定時任務] ✅ 新建天氣數據記錄 - ID: {weather_record.id}, 溫度: {parsed.get("temperature")}°C')
        else:
            logger.info(f'[定時任務] ✅ 更新天氣數據記錄 - ID: {weather_record.id}, 溫度: {parsed.get("temperature")}°C')

    except requests.exceptions.RequestException as e:
        logger.error(f'[定時任務] ❌ API 請求失敗: {str(e)}')
    except Exception as e:
        logger.error(f'[定時任務] ❌ 獲取天氣數據失敗: {str(e)}')


def fetch_and_store_warnings():
    """
    ✅ 新增：定時任務 - 每天 7:00 AM 獲取並存儲天氣警告數據
    使用 update_or_create() 避免重複記錄
    """
    try:
        logger.info(f'[定時任務] 開始獲取天氣警告 - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

        url = "https://data.weather.gov.hk/weatherAPI/opendata/weather.php"
        params = {
            'dataType': 'warnsum',
            'lang': 'tc'
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # 獲取警告列表
        warnings = data.get('warning', [])
        school_status = get_school_status(warnings)

        # ✅ 使用 update_or_create() 保存警告數據
        now = timezone.now()
        today = now.date()

        warning_types_list = [w.get('type', '') for w in warnings]
        warning_types_str = ', '.join(warning_types_list) if warning_types_list else '無警告'

        warning_record, created = WarningAccessLog.objects.update_or_create(
            # 查詢條件：同一天的記錄
            accessed_at__date=today,
            # 默認值（創建新記錄時使用）
            defaults={
                'warning_count': len(warnings),
                'warning_types': warning_types_str,
                'raw_response': data,
                'ip_address': '127.0.0.1',  # 定時任務使用本地 IP
                'user_agent': 'ScheduledTask',
                'accessed_at': now,
            }
        )

        if created:
            logger.info(f'[定時任務] ✅ 新建天氣警告記錄 - ID: {warning_record.id}, 警告數: {len(warnings)}')
        else:
            logger.info(f'[定時任務] ✅ 更新天氣警告記錄 - ID: {warning_record.id}, 警告數: {len(warnings)}')

    except requests.exceptions.RequestException as e:
        logger.error(f'[定時任務] ❌ 警告 API 請求失敗: {str(e)}')
    except Exception as e:
        logger.error(f'[定時任務] ❌ 獲取天氣警告失敗: {str(e)}')


def start_scheduler():
    """
    ✅ 修改版本：啟動定時任務調度器
    添加 max_instances=1 確保同時只運行一個任務
    """
    global scheduler

    if scheduler is not None and scheduler.running:
        logger.info('⚠️ 調度器已在運行中')
        return

    scheduler = BackgroundScheduler()

    # ✅ 每天 7:00 AM 執行一次 - 獲取天氣數據
    scheduler.add_job(
        fetch_and_store_weather,
        'cron',
        hour=7,
        minute=0,
        second=0,
        id='daily_weather_job',
        name='Daily Weather Fetcher',
        replace_existing=True,  # ✅ 替換已存在的任務
        max_instances=1  # ✅ 同時只運行一個實例
    )

    # ✅ 新增：每天 7:00 AM 執行一次 - 獲取天氣警告
    scheduler.add_job(
        fetch_and_store_warnings,
        'cron',
        hour=7,
        minute=0,
        second=5,  # 延遲 5 秒，確保天氣數據先執行
        id='daily_warning_job',
        name='Daily Warning Fetcher',
        replace_existing=True,
        max_instances=1
    )

    # ✅ 新增：每天 23:59 清理一次重複記錄
    scheduler.add_job(
        delete_duplicate_records,
        'cron',
        hour=23,
        minute=59,
        second=0,
        id='cleanup_duplicates_job',
        name='Cleanup Duplicate Records',
        replace_existing=True,
        max_instances=1
    )

    scheduler.start()
    logger.info('✅ 定時調度器已啟動')
    logger.info('   - 每天 07:00:00 執行：獲取天氣數據')
    logger.info('   - 每天 07:00:05 執行：獲取天氣警告')
    logger.info('   - 每天 23:59:00 執行：清理重複記錄')


class WeatherDataView(APIView):
    """天氣數據 API"""

    def get(self, request):
        """
        ✅ 修改版本：獲取最新天氣數據
        優先返回今天的緩存數據，只在沒有時才即時獲取
        """
        try:
            # 優先返回今天的記錄
            today = timezone.now().date()
            today_data = WeatherData.objects.filter(
                recorded_at__date=today
            ).order_by('-recorded_at').first()

            if today_data:
                logger.info('✅ 返回今天的天氣數據（來自數據庫緩存）')
                return Response({
                    'temperature': today_data.temperature,
                    'humidity': today_data.humidity,
                    'windSpeed': today_data.wind_speed,
                    'windDirection': today_data.wind_direction,
                    'pressure': today_data.pressure,
                    'rainfall': today_data.rainfall,
                    'generalSituation': today_data.general_situation,
                    'recordedAt': today_data.recorded_at.isoformat(),
                    'source': 'database_cache'
                }, status=status.HTTP_200_OK)

            # 如果沒有今天的記錄，即時獲取並保存
            logger.info('📡 數據庫無今天記錄，即時獲取天氣數據...')
            base_url = "https://data.weather.gov.hk/weatherAPI/opendata/weather.php"

            # 獲取 rhrread 數據
            rhrread_resp = requests.get(
                base_url,
                params={'dataType': 'rhrread', 'lang': 'tc'},
                timeout=10
            )
            rhrread_resp.raise_for_status()
            rhrread_data = rhrread_resp.json()

            # 獲取 flw 數據
            flw_resp = requests.get(
                base_url,
                params={'dataType': 'flw', 'lang': 'tc'},
                timeout=10
            )
            flw_resp.raise_for_status()
            flw_data = flw_resp.json()

            # 解析數據
            parsed = self.parse_weather_data(rhrread_data, flw_data)
            logger.info(f'📊 解析成功 - 溫度: {parsed.get("temperature")}°C, 濕度: {parsed.get("humidity")}%')

            # ✅ 關鍵：保存到數據庫
            now = timezone.now()
            today_date = now.date()

            try:
                # 使用 update_or_create 避免重複
                weather_record, created = WeatherData.objects.update_or_create(
                    recorded_at__date=today_date,
                    defaults={
                        'general_situation': parsed.get('generalSituation', ''),
                        'temperature': parsed.get('temperature'),
                        'humidity': parsed.get('humidity'),
                        'wind_speed': parsed.get('windSpeed'),
                        'wind_direction': parsed.get('windDirection', ''),
                        'pressure': parsed.get('pressure'),
                        'rainfall': parsed.get('rainfall'),
                        'raw_data': rhrread_data,
                        'recorded_at': now,
                    }
                )

                if created:
                    logger.info(f'✅ 新建天氣數據 - ID: {weather_record.id}, 時間: {now}')
                else:
                    logger.info(f'✅ 更新天氣數據 - ID: {weather_record.id}, 時間: {now}')

            except Exception as save_error:
                logger.error(f'❌ 保存到數據庫失敗: {str(save_error)}', exc_info=True)
                # 即使保存失敗也返回數據
                pass

            # 返回數據
            parsed['recordedAt'] = now.isoformat()
            parsed['source'] = 'api_real_time'
            logger.info(f'✅ 返回實時 API 數據')
            return Response(parsed, status=status.HTTP_200_OK)

        except requests.exceptions.RequestException as e:
            logger.error(f'❌ 天氣 API 請求失敗: {str(e)}', exc_info=True)
            return Response(
                {'error': f'無法獲取天氣數據: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f'❌ 天氣數據處理失敗: {str(e)}', exc_info=True)
            return Response(
                {'error': '數據處理失敗'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @staticmethod
    def parse_weather_data(rhrread, flw):
        """解析天文台 API 數據"""
        result = {
            'generalSituation': flw.get('generalSituation', ''),
            'forecastDesc': flw.get('forecastDesc', ''),
            'temperature': None,
            'humidity': None,
            'windSpeed': None,
            'windDirection': '',
            'pressure': None,
            'rainfall': None,
            'updateTime': rhrread.get('updateTime', ''),
        }

        # 溫度
        temp_list = rhrread.get('temperature', {}).get('data', [])
        for temp_data in temp_list:
            if temp_data.get('place') == '香港天文台':
                result['temperature'] = temp_data.get('value')
                break
        if result['temperature'] is None and temp_list:
            result['temperature'] = temp_list[0].get('value')

        # 濕度
        humidity_list = rhrread.get('humidity', {}).get('data', [])
        if humidity_list:
            result['humidity'] = humidity_list[0].get('value')

        # 風速
        wind_speed_list = rhrread.get('wind', {}).get('data', [])
        if wind_speed_list:
            result['windSpeed'] = wind_speed_list[0].get('speed')
            result['windDirection'] = wind_speed_list[0].get('direction')

        # 氣壓
        pressure_list = rhrread.get('pressure', {}).get('data', [])
        if pressure_list:
            result['pressure'] = pressure_list[0].get('value')

        # 降雨量
        rainfall_list = rhrread.get('rainfall', {}).get('data', [])
        if rainfall_list:
            max_vals = [r.get('max', 0) for r in rainfall_list]
            result['rainfall'] = max(max_vals) if max_vals else 0

        return result


def index(request):
    """顯示天氣數據的 HTML 頁面"""
    return render(request, 'weather_app/index.html')


def get_client_ip(request):
    """獲取客戶端 IP 地址"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_school_status(warnings):
    """
    根據警告類型判斷是否要上課
    返回: {'status': '要上課/不用上課', 'color': '顏色代碼', 'icon': '圖標', 'message': '信息'}
    """
    if not warnings:
        return {
            'status': '要上課',
            'color': '#28a745',
            'icon': '✅',
            'message': '沒有天氣警告'
        }

    # 定義不用上課的警告類型
    no_school_warnings = ['8號風球', '9號風球', '10號風球', '黑色暴雨警告']

    warning_types = [w.get('type', '') for w in warnings]

    for warning_type in warning_types:
        if any(no_school in warning_type for no_school in no_school_warnings):
            return {
                'status': '不用上課',
                'color': '#dc3545',
                'icon': '🚫',
                'message': f'因為 {warning_type}'
            }

    return {
        'status': '要上課',
        'color': '#28a745',
        'icon': '✅',
        'message': '天氣警告不影響上課'
    }


class WeatherWarningView(APIView):
    """天氣警告 API - 優先返回緩存數據，只在沒有時才即時獲取"""

    def get(self, request):
        """
        ✅ 修改版本：獲取天氣警告數據
        優先返回今天的緩存數據，只在沒有時才即時獲取
        """
        try:
            # 優先返回今天的記錄
            today = timezone.now().date()
            today_warning = WarningAccessLog.objects.filter(
                accessed_at__date=today
            ).order_by('-accessed_at').first()

            if today_warning:
                logger.info('✅ 返回今天的天氣警告（來自數據庫緩存）')

                # 從保存的原始響應中提取數據
                raw_data = today_warning.raw_response
                warnings = raw_data.get('warning', [])
                school_status = get_school_status(warnings)

                return Response({
                    'warning': warnings,
                    'schoolStatus': school_status,
                    'recordedAt': today_warning.accessed_at.isoformat(),
                    'source': 'database_cache'
                }, status=status.HTTP_200_OK)

            # 如果沒有今天的記錄，即時獲取並保存
            logger.info('📡 數據庫無今天警告記錄，即時獲取天氣警告...')

            url = "https://data.weather.gov.hk/weatherAPI/opendata/weather.php"
            params = {
                'dataType': 'warnsum',
                'lang': request.query_params.get('lang', 'tc')
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            # 獲取學校狀態
            warnings = data.get('warning', [])
            school_status = get_school_status(warnings)

            # 添加學校狀態到響應
            data['schoolStatus'] = school_status

            # ✅ 關鍵：保存到數據庫
            now = timezone.now()
            today_date = now.date()

            try:
                warning_types_list = [w.get('type', '') for w in warnings]
                warning_types_str = ', '.join(warning_types_list) if warning_types_list else '無警告'

                ip_address = get_client_ip(request)
                user_agent = request.META.get('HTTP_USER_AGENT', '')

                # 使用 update_or_create 避免重複
                warning_record, created = WarningAccessLog.objects.update_or_create(
                    accessed_at__date=today_date,
                    defaults={
                        'warning_count': len(warnings),
                        'warning_types': warning_types_str,
                        'raw_response': data,
                        'ip_address': ip_address,
                        'user_agent': user_agent,
                        'accessed_at': now,
                    }
                )

                if created:
                    logger.info(f'✅ 新建天氣警告數據 - ID: {warning_record.id}, 警告數: {len(warnings)}')
                else:
                    logger.info(f'✅ 更新天氣警告數據 - ID: {warning_record.id}, 警告數: {len(warnings)}')

            except Exception as save_error:
                logger.error(f'❌ 保存警告到數據庫失敗: {str(save_error)}', exc_info=True)
                # 即使保存失敗也返回數據
                pass

            # 返回數據
            data['recordedAt'] = now.isoformat()
            data['source'] = 'api_real_time'
            logger.info(f'✅ 返回實時 API 警告數據')
            return Response(data, status=status.HTTP_200_OK)

        except requests.exceptions.RequestException as e:
            logger.error(f'❌ 警告 API 請求失敗: {str(e)}')
            return Response(
                {'error': f'無法獲取警告數據: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f'❌ 警告數據處理失敗: {str(e)}')
            return Response(
                {'error': '數據處理失敗'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )