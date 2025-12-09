"""
admin configuration for core app.
"""
from django.contrib import admin
from .models import (
    Product, Contact, Group, Conversation, 
    Message, Sale, WhatsAppConfig, StatusUpdate
)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """admin interface for product model"""
    list_display = ('name', 'price', 'category', 'is_active')
    list_filter = ('is_active', 'category')
    search_fields = ('name', 'description')


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    """admin interface for contact model"""
    list_display = ('phone_number', 'name', 'is_allowed', 'created_at')
    list_filter = ('is_allowed',)
    search_fields = ('phone_number', 'name')


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    """admin interface for group model"""
    list_display = ('name', 'group_id', 'is_allowed')
    list_filter = ('is_allowed',)
    search_fields = ('name', 'group_id')


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """admin interface for conversation model"""
    list_display = ('contact', 'status', 'started_at', 'closed_at')
    list_filter = ('status',)
    search_fields = ('contact__phone_number', 'contact__name')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """admin interface for message model"""
    list_display = ('conversation', 'message_type', 'timestamp')
    list_filter = ('message_type', 'timestamp')
    search_fields = ('content', 'conversation__contact__phone_number')


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    """admin interface for sale model"""
    list_display = ('product', 'conversation', 'quantity', 'total_price', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('product__name', 'conversation__contact__phone_number')


@admin.register(WhatsAppConfig)
class WhatsAppConfigAdmin(admin.ModelAdmin):
    """admin interface for whatsapp configuration model"""
    list_display = ('provider', 'phone_number', 'is_active')
    list_filter = ('provider', 'is_active')


@admin.register(StatusUpdate)
class StatusUpdateAdmin(admin.ModelAdmin):
    """admin interface for status update model"""
    list_display = ('title', 'scheduled_for', 'was_sent')
    list_filter = ('was_sent', 'scheduled_for')
    search_fields = ('title', 'content')


# import contextual admin configurations
from .contextual_admin import *

