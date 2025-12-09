"""
urls.py for core app
"""
from django.urls import path
from . import views, whatsapp_connect_views

app_name = 'core'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Products
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.product_add, name='product_add'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),
    
    # Contacts
    path('contacts/', views.contact_list, name='contact_list'),
    path('contacts/add/', views.contact_add, name='contact_add'),
    path('contacts/<int:pk>/edit/', views.contact_edit, name='contact_edit'),
    path('contacts/<int:pk>/delete/', views.contact_delete, name='contact_delete'),
    
    # Groups
    path('groups/', views.group_list, name='group_list'),
    path('groups/add/', views.group_add, name='group_add'),
    path('groups/<int:pk>/edit/', views.group_edit, name='group_edit'),
    path('groups/<int:pk>/delete/', views.group_delete, name='group_delete'),
    
    # Conversations
    path('conversations/', views.conversation_list, name='conversation_list'),
    path('conversations/<int:pk>/', views.conversation_detail, name='conversation_detail'),
    path('conversations/<int:pk>/close/', views.conversation_close, name='conversation_close'),
    
    # Sales
    path('sales/', views.sale_list, name='sale_list'),
    path('sales/<int:pk>/', views.sale_detail, name='sale_detail'),
    path('sales/<int:pk>/update-status/', views.sale_update_status, name='sale_update_status'),
    
    # Status Updates
    path('status-updates/', views.status_update_list, name='status_update_list'),
    path('status-updates/add/', views.status_update_add, name='status_update_add'),
    path('status-updates/<int:pk>/edit/', views.status_update_edit, name='status_update_edit'),
    path('status-updates/<int:pk>/delete/', views.status_update_delete, name='status_update_delete'),
    
    # Bulk Message
    path('bulk-message/', views.bulk_message, name='bulk_message'),
    
    # WhatsApp Config
    path("config/", views.whatsapp_config, name="whatsapp_config"),
    
    # AI Config (New)
    path("ai-config/", views.ai_config, name="ai_config"),
    
    # Webhook
    path('webhook/', views.webhook, name='webhook'),
    
    # WhatsApp Connection URLs (Old)
    path('whatsapp/setup/', views.whatsapp_setup, name='whatsapp_setup'),
    path('whatsapp/qr/<uuid:connection_id>/', views.whatsapp_qr, name='whatsapp_qr'),
    path('whatsapp/status/', views.whatsapp_status, name='whatsapp_status'),
    path('whatsapp/disconnect/', views.whatsapp_disconnect, name='whatsapp_disconnect'),
    path('whatsapp/groups/', views.whatsapp_groups, name='whatsapp_groups'),
    
    # WhatsApp Connection URLs (New - Direct QR Code)
    path('whatsapp/connect/', whatsapp_connect_views.whatsapp_connect, name='whatsapp_connect'),
    path('whatsapp/api/status/', whatsapp_connect_views.whatsapp_api_status, name='whatsapp_api_status'),
    path('whatsapp/api/restart/', whatsapp_connect_views.whatsapp_api_restart, name='whatsapp_api_restart'),
    path('whatsapp/api/send-message/', whatsapp_connect_views.whatsapp_api_send_message, name='whatsapp_api_send_message'),
    
    # API Endpoints
    path('api/products/', views.api_products, name='api_products'),
    path('api/conversations/', views.api_conversations, name='api_conversations'),
    path("ai-test/", views.ai_test, name="ai_test"),
]

# Import WhatsApp Web views
from . import whatsapp_web_views

# Add WhatsApp Web URLs to existing urlpatterns
urlpatterns += [
    # WhatsApp Web Interface
    path('whatsapp/web/', whatsapp_web_views.whatsapp_web_interface, name='whatsapp_web'),
    path('api/whatsapp/conversations/', whatsapp_web_views.whatsapp_web_conversations, name='whatsapp_web_conversations'),
    path('api/whatsapp/conversations/<str:chat_id>/messages/', whatsapp_web_views.whatsapp_web_chat_messages, name='whatsapp_web_chat_messages'),
    path('api/whatsapp/contacts/', whatsapp_web_views.whatsapp_web_contacts, name='whatsapp_web_contacts'),
    path('api/whatsapp/send-message/', whatsapp_web_views.whatsapp_web_send_message, name='whatsapp_web_send_message'),
    path('api/whatsapp/status/', whatsapp_web_views.whatsapp_web_connection_status, name='whatsapp_web_status'),
]


# Import AI processing views
from .whatsapp_ai_views import (
    ProcessMessageView, whatsapp_status, whatsapp_conversations,
    whatsapp_chat_messages, whatsapp_send_message, whatsapp_contacts
)

# Add AI processing URLs
urlpatterns += [
    # AI message processing
    path('api/whatsapp/process-message/', ProcessMessageView.as_view(), name='process_message'),
    
    # WhatsApp Web API endpoints
    path('api/whatsapp/status/', whatsapp_status, name='api_whatsapp_status'),
    path('api/whatsapp/conversations/', whatsapp_conversations, name='api_whatsapp_conversations'),
    path('api/whatsapp/conversations/<str:chat_id>/messages/', whatsapp_chat_messages, name='api_whatsapp_chat_messages'),
    path('api/whatsapp/send-message/', whatsapp_send_message, name='api_whatsapp_send_message'),
    path('api/whatsapp/contacts/', whatsapp_contacts, name='api_whatsapp_contacts'),
]

