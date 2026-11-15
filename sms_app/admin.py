from django.contrib import admin

from .models import SMSMessage


@admin.register(SMSMessage)
class SMSMessageAdmin(admin.ModelAdmin):
    list_display = ("created_at", "masked_recipient", "outcome", "provider_status")
    list_filter = ("outcome", "provider_status")
    readonly_fields = [f.name for f in SMSMessage._meta.fields]
