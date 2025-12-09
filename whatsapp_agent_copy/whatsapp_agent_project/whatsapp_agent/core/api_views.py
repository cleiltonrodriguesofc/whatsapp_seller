"""
API Views for WhatsApp Microservice Integration
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
import json
import logging
from .models import Contact, Conversation, Message, AIConfig
from .services.hybrid_ai_service import hybrid_ai_service
from .services.whatsapp_command_service import whatsapp_command_service
from .services.proactive_service import proactive_ai_service
from .services.personalization_service import personalization_engine

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class WebhookView(View):
    """Webhook para receber mensagens do microserviço Node.js"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            message_type = data.get('type')
            
            if message_type == 'message':
                return self.handle_message(data)
            elif message_type == 'status':
                return self.handle_status(data)
            else:
                return JsonResponse({'error': 'Unknown message type'}, status=400)
                
        except Exception as e:
            logger.error(f"Webhook error: {str(e)}")
            return JsonResponse({'error': 'Internal server error'}, status=500)
    
    def handle_message(self, data):
        """Processa mensagem recebida"""
        try:
            phone_number = data.get('from')
            message_content = data.get('body', '')
            message_id = data.get('id')
            
            # Buscar ou criar contato
            contact, created = Contact.objects.get_or_create(
                phone_number=phone_number,
                defaults={'name': data.get('name', f'Contato {phone_number}')}
            )
            
            # Buscar ou criar conversa
            conversation, created = Conversation.objects.get_or_create(
                contact=contact
            )
            
            # Criar mensagem
            message = Message.objects.create(
                conversation=conversation,
                content=message_content,
                message_type='received',
                whatsapp_id=message_id
            )
            
            # Verificar se é comando (mensagem para próprio número)
            if phone_number == data.get('to'):  # Mensagem para si mesmo
                command_response = whatsapp_command_service.process_incoming_message(message)
                if command_response:
                    return JsonResponse({
                        'response': command_response.preview_content,
                        'command_id': command_response.id,
                        'requires_confirmation': True
                    })
            
            # Processar com IA contextual
            ai_response = hybrid_ai_service.get_contextual_response(
                message_content, contact, conversation
            )
            
            # Atualizar perfil de personalização
            personalization_engine.update_contact_profile(contact, message)
            
            # Verificar oportunidades proativas
            proactive_ai_service.analyze_message_for_opportunities(message)
            
            return JsonResponse({
                'response': ai_response,
                'contact_id': contact.id,
                'conversation_id': conversation.id
            })
            
        except Exception as e:
            logger.error(f"Message handling error: {str(e)}")
            return JsonResponse({'error': 'Failed to process message'}, status=500)
    
    def handle_status(self, data):
        """Processa status de mensagem"""
        try:
            message_id = data.get('id')
            status = data.get('status')
            
            # Atualizar status da mensagem se existir
            try:
                message = Message.objects.get(whatsapp_id=message_id)
                message.status = status
                message.save()
            except Message.DoesNotExist:
                pass
            
            return JsonResponse({'status': 'ok'})
            
        except Exception as e:
            logger.error(f"Status handling error: {str(e)}")
            return JsonResponse({'error': 'Failed to process status'}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def confirm_command(request):
    """Confirma execução de comando"""
    try:
        data = json.loads(request.body)
        command_id = data.get('command_id')
        action = data.get('action')  # 'confirm', 'edit', 'cancel'
        edited_content = data.get('edited_content', '')
        
        response = whatsapp_command_service.handle_command_response(
            command_id, action, edited_content
        )
        
        return JsonResponse(response)
        
    except Exception as e:
        logger.error(f"Command confirmation error: {str(e)}")
        return JsonResponse({'error': 'Failed to confirm command'}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
def get_ai_config(request):
    """Retorna configuração atual da IA"""
    try:
        config = AIConfig.objects.filter(is_active=True).first()
        if config:
            return JsonResponse({
                'persona_prompt': config.persona_prompt,
                'api_key_configured': bool(config.api_key),
                'is_active': config.is_active
            })
        else:
            return JsonResponse({
                'persona_prompt': 'Você é um assistente de vendas especializado.',
                'api_key_configured': False,
                'is_active': False
            })
            
    except Exception as e:
        logger.error(f"AI config error: {str(e)}")
        return JsonResponse({'error': 'Failed to get AI config'}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
def get_proactive_opportunities(request):
    """Retorna oportunidades proativas detectadas"""
    try:
        opportunities = proactive_ai_service.get_pending_opportunities()
        
        return JsonResponse({
            'opportunities': [
                {
                    'id': opp.id,
                    'contact_name': opp.contact.name,
                    'contact_phone': opp.contact.phone_number,
                    'opportunity_type': opp.opportunity_type,
                    'confidence_score': opp.confidence_score,
                    'recommended_action': opp.recommended_action,
                    'priority': opp.priority,
                    'created_at': opp.created_at.isoformat()
                }
                for opp in opportunities[:10]  # Últimas 10
            ]
        })
        
    except Exception as e:
        logger.error(f"Proactive opportunities error: {str(e)}")
        return JsonResponse({'error': 'Failed to get opportunities'}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def execute_proactive_action(request):
    """Executa ação proativa"""
    try:
        data = json.loads(request.body)
        opportunity_id = data.get('opportunity_id')
        
        result = proactive_ai_service.execute_opportunity_action(opportunity_id)
        
        return JsonResponse(result)
        
    except Exception as e:
        logger.error(f"Proactive action error: {str(e)}")
        return JsonResponse({'error': 'Failed to execute action'}, status=500)

@csrf_exempt
@require_http_methods(["GET"])
def health_check(request):
    """Health check para monitoramento"""
    try:
        # Verificar componentes principais
        ai_status = hybrid_ai_service.get_ai_status()
        db_status = Contact.objects.count() >= 0  # Teste simples do DB
        
        return JsonResponse({
            'status': 'healthy',
            'ai_local_available': ai_status.get('local_available', False),
            'ai_api_available': ai_status.get('api_available', False),
            'database_connected': db_status,
            'version': '2.0.0'
        })
        
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e)
        }, status=500)

