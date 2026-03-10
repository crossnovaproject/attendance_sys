# weather_app/urls.py
from django.urls import path
from .views import WeatherDataView, WeatherWarningView, index
from django.urls import path
from .views import WeatherDataView, WeatherHistoryView, WeatherWarningView

app_name = 'weather_app'

urlpatterns = [
    path('', index, name='index'),
    path('api/weather/', WeatherDataView.as_view(), name='weather-data'),
    path('api/weather/history/', WeatherHistoryView.as_view(), name='weather-history'),
    path('api/warning/', WeatherWarningView.as_view(), name='weather-warning'),
]
