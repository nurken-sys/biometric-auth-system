from django.contrib import admin
from django.urls import path, include
from django.conf import settings # <-- Обязательно добавь этот импорт
from django.conf.urls.static import static # <-- И этот

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')), # Это как раз подключает твой первый файл
]

# <-- ДОБАВЬ ЭТИ СТРОЧКИ В САМЫЙ НИЗ -->
# Они говорят Django, как правильно открывать картинки из папки uploads
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)