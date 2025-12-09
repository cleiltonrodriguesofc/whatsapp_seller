"""
API URLs for WhatsApp Microservice Integration
"""
from django.urls import path
from . import api_views

urlpatterns = [
    # Webhook para receber mensagens do microserviço
    path('webhook/', api_views.WebhookView.as_view(), name='webhook'),
    
    # Confirmação de comandos
    path('confirm-command/', api_views.confirm_command, name='confirm_command'),
    
    # Configuração da IA
    path('ai-config/', api_views.get_ai_config, name='ai_config'),
    
    # Oportunidades proativas
    path('proactive-opportunities/', api_views.get_proactive_opportunities, name='proactive_opportunities'),
    path('execute-proactive-action/', api_views.execute_proactive_action, name='execute_proactive_action'),
    
    # Health check
    path('health/', api_views.health_check, name='health_check'),
]

