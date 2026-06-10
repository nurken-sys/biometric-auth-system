from django.contrib import admin
from .models import User, Phrase, RecoveryRequest

admin.site.register(User)
admin.site.register(Phrase)

@admin.register(RecoveryRequest)
class RecoveryRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'reason', 'status', 'suggested_username', 'admin_response_username', 'created_at')
    list_filter = ('status', 'reason')
    
    readonly_fields = ('face_photo', 'reason', 'description', 'suggested_username', 'created_at')
    list_editable = ('status', 'admin_response_username')

    
    def save_model(self, request, obj, form, change):
        if change and obj.status == 'approved_reset' and obj.admin_response_username:
            try:
                user_to_delete = User.objects.get(username=obj.admin_response_username)
                user_to_delete.delete()
            except User.DoesNotExist:
                pass 

        super().save_model(request, obj, form, change)