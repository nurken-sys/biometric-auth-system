from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('set-language/<str:lang>/', views.set_language, name='set_language'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('logout/', views.logout_view, name='logout'),
    
    # Әкімшілікпен байланыс
    path('recovery/', views.recovery_view, name='recovery'),
    path('api/recovery-status/<int:req_id>/', views.check_recovery_status, name='check_recovery_status'),

    # API
    path('api/challenge/', views.api_challenge, name='api_challenge'),
    path('api/register-phrases/', views.api_register_phrases, name='api_register_phrases'),
    path('preview-asr/', views.preview_asr, name='preview_asr'),
    path('api/verify-audio/', views.verify_audio, name='verify_audio'),
]