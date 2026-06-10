from django.db import models
from django.utils import timezone

class User(models.Model):
    username = models.CharField(max_length=255, unique=True, verbose_name="Имя пользователя")
    face_path = models.CharField(max_length=500, null=True, blank=True)
    voice_path = models.CharField(max_length=500, null=True, blank=True)
    
    face_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    voice_print = models.TextField(null=True, blank=True)
    face_encoding = models.TextField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.username

class Phrase(models.Model):
    lang = models.CharField(max_length=10, verbose_name="Язык")
    phrase = models.TextField(verbose_name="Текст фразы")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"[{self.lang}] {self.phrase}"
    
class RecoveryRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Жауап күтілуде (Ожидает)'),
        ('approved_name', '✅ Никнейм еске салу (Напомнить)'),
        ('approved_reset', '🔄 Қайта тіркеуге рұқсат (Сброс)'),
        ('rejected', '❌ Отклонено (Қабылданбады)'),
    ]
    REASON_CHOICES = [
        ('forgot_name', 'Забыл уникальный никнейм'),
        ('face_changed', 'Изменилась внешность/голос'),
        ('other', 'Другая причина'),
    ]
    
    face_photo = models.ImageField(upload_to='recovery/')
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    description = models.TextField(blank=True, null=True, help_text="Доп. информация от пользователя")
    
    suggested_username = models.CharField(
        max_length=150, 
        blank=True, 
        null=True, 
        verbose_name="Предполагаемый никнейм (Авто-поиск)"
    )
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    
    admin_response_username = models.CharField(max_length=150, blank=True, null=True, verbose_name="Ответ админа")
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Запрос #{self.id} | {self.get_reason_display()} | Статус: {self.get_status_display()}"