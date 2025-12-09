from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
import json
import logging
from datetime import datetime
from .models import Contact, Conversation, Message
from .services.enhanced_ai_service import EnhancedAIService

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class ProcessMessageView(View):
    """
    Process incoming WhatsApp messages and generate AI responses
    """
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            
            # extract message data
            whatsapp_id = data.get('whatsapp_id')
            contact_name = data.get('contact_name')
            message_body = data.get('message_body')
            message_type = data.get('message_type', 'chat')
            timestamp = data.get('timestamp')
            is_group = data.get('is_group', False)
            chat_name = data.get('chat_name')
            
            logger.info(f"Processing message from {whatsapp_id}: {message_body}")
            
            # skip if no message body or if it's a group (for now)
            if not message_body or is_group:
                return JsonResponse({
                    'should_respond': False,
                    'reason': 'No message body or group message'
                })
            
            # get or create contact
            contact, created = Contact.objects.get_or_create(
                whatsapp_id=whatsapp_id,
                defaults={
                    'name': contact_name,
                    'phone': whatsapp_id.split('@')[0] if '@' in whatsapp_id else whatsapp_id,
                    'is_active': True
                }
            )
            
            # update contact name if it changed
            if contact.name != contact_name and contact_name:
                contact.name = contact_name
                contact.save()
            
            # get or create conversation
            conversation, created = Conversation.objects.get_or_create(
                contact=contact,
                defaults={
                    'status': 'active',
                    'last_message_at': datetime.now()
                }
            )
            
            # create message record
            message = Message.objects.create(
                conversation=conversation,
                content=message_body,
                message_type='received',
                whatsapp_message_id=data.get('message_id', ''),
                timestamp=datetime.fromtimestamp(timestamp) if timestamp else datetime.now()
            )
            
            # check if contact allows AI interaction
            if not contact.ai_enabled:
                logger.info(f"AI disabled for contact {contact.name}")
                return JsonResponse({
                    'should_respond': False,
                    'reason': 'AI disabled for this contact'
                })
            
            # check if we should respond (basic rules)
            should_respond = self.should_respond_to_message(contact, message_body)
            
            if not should_respond:
                return JsonResponse({
                    'should_respond': False,
                    'reason': 'Message does not require response'
                })
            
            # generate AI response
            try:
                ai_service = EnhancedAIService()
                
                # get conversation context
                recent_messages = Message.objects.filter(
                    conversation=conversation
                ).order_by('-created_at')[:10]
                
                context = []
                for msg in reversed(recent_messages):
                    context.append({
                        'role': 'user' if msg.message_type == 'received' else 'assistant',
                        'content': msg.content,
                        'timestamp': msg.timestamp.isoformat() if msg.timestamp else msg.created_at.isoformat()
                    })
                
                # generate response
                ai_response = ai_service.generate_contextual_response(
                    message_body,
                    contact,
                    context
                )
                
                if ai_response:
                    # save AI response as message
                    Message.objects.create(
                        conversation=conversation,
                        content=ai_response,
                        message_type='sent',
                        is_ai_generated=True
                    )
                    
                    # update conversation
                    conversation.last_message_at = datetime.now()
                    conversation.save()
                    
                    logger.info(f"Generated AI response for {contact.name}: {ai_response[:100]}...")
                    
                    return JsonResponse({
                        'should_respond': True,
                        'ai_response': ai_response,
                        'contact_id': contact.id,
                        'conversation_id': conversation.id
                    })
                else:
                    return JsonResponse({
                        'should_respond': False,
                        'reason': 'Could not generate AI response'
                    })
                    
            except Exception as ai_error:
                logger.error(f"Error generating AI response: {ai_error}")
                return JsonResponse({
                    'should_respond': False,
                    'reason': f'AI service error: {str(ai_error)}'
                })
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return JsonResponse({
                'error': str(e),
                'should_respond': False
            }, status=500)
    
    def should_respond_to_message(self, contact, message_body):
        """
        Determine if we should respond to this message
        """
        # skip empty messages
        if not message_body or len(message_body.strip()) < 2:
            return False
        
        # skip if message looks like automated/system message
        automated_indicators = [
            'delivered', 'read', 'typing', 'recording',
            'location shared', 'contact shared'
        ]
        
        if any(indicator in message_body.lower() for indicator in automated_indicators):
            return False
        
        # check if contact is in business hours (if configured)
        current_hour = datetime.now().hour
        if current_hour < 7 or current_hour > 23:  # outside 7 AM - 11 PM
            return False
        
        # always respond to questions
        question_indicators = ['?', 'como', 'quando', 'onde', 'por que', 'qual', 'quem']
        if any(indicator in message_body.lower() for indicator in question_indicators):
            return True
        
        # respond to greetings
        greeting_indicators = ['oi', 'olá', 'bom dia', 'boa tarde', 'boa noite', 'hello', 'hi']
        if any(indicator in message_body.lower() for indicator in greeting_indicators):
            return True
        
        # respond to product inquiries
        product_indicators = ['preço', 'valor', 'custo', 'comprar', 'produto', 'serviço']
        if any(indicator in message_body.lower() for indicator in product_indicators):
            return True
        
        # respond to support requests
        support_indicators = ['ajuda', 'suporte', 'problema', 'dúvida', 'help', 'support']
        if any(indicator in message_body.lower() for indicator in support_indicators):
            return True
        
        # default: respond to messages longer than 10 characters
        return len(message_body.strip()) > 10


@csrf_exempt
@require_http_methods(["GET"])
def whatsapp_status(request):
    """
    Get WhatsApp connection status from microservice
    """
    try:
        import requests
        from django.conf import settings
        
        microservice_url = getattr(settings, 'MICROSERVICE_URL', 'http://localhost:3001')
        response = requests.get(f"{microservice_url}/api/status", timeout=5)
        
        if response.status_code == 200:
            return JsonResponse(response.json())
        else:
            return JsonResponse({
                'connected': False,
                'status': 'error',
                'error': 'Microservice not responding'
            })
            
    except Exception as e:
        return JsonResponse({
            'connected': False,
            'status': 'error',
            'error': str(e)
        })


@csrf_exempt
@require_http_methods(["GET"])
def whatsapp_conversations(request):
    """
    Get conversations from microservice
    """
    try:
        import requests
        from django.conf import settings
        
        microservice_url = getattr(settings, 'MICROSERVICE_URL', 'http://localhost:3001')
        response = requests.get(f"{microservice_url}/api/conversations", timeout=10)
        
        if response.status_code == 200:
            return JsonResponse(response.json())
        else:
            return JsonResponse({
                'conversations': [],
                'total': 0,
                'error': 'Microservice not responding'
            })
            
    except Exception as e:
        return JsonResponse({
            'conversations': [],
            'total': 0,
            'error': str(e)
        })


@csrf_exempt
@require_http_methods(["GET"])
def whatsapp_chat_messages(request, chat_id):
    """
    Get messages for specific chat from microservice
    """
    try:
        import requests
        from django.conf import settings
        
        microservice_url = getattr(settings, 'MICROSERVICE_URL', 'http://localhost:3001')
        response = requests.get(f"{microservice_url}/api/conversations/{chat_id}/messages", timeout=10)
        
        if response.status_code == 200:
            return JsonResponse(response.json())
        else:
            return JsonResponse({
                'messages': [],
                'total': 0,
                'error': 'Microservice not responding'
            })
            
    except Exception as e:
        return JsonResponse({
            'messages': [],
            'total': 0,
            'error': str(e)
        })


@csrf_exempt
@require_http_methods(["POST"])
def whatsapp_send_message(request):
    """
    Send message via microservice
    """
    try:
        import requests
        from django.conf import settings
        
        data = json.loads(request.body)
        chat_id = data.get('chat_id')
        message = data.get('message')
        
        if not chat_id or not message:
            return JsonResponse({
                'success': False,
                'error': 'chat_id and message are required'
            }, status=400)
        
        microservice_url = getattr(settings, 'MICROSERVICE_URL', 'http://localhost:3001')
        response = requests.post(
            f"{microservice_url}/api/send-message",
            json={'chat_id': chat_id, 'message': message},
            timeout=15
        )
        
        if response.status_code == 200:
            return JsonResponse(response.json())
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to send message'
            }, status=500)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def whatsapp_contacts(request):
    """
    Get contacts from microservice
    """
    try:
        import requests
        from django.conf import settings
        
        microservice_url = getattr(settings, 'MICROSERVICE_URL', 'http://localhost:3001')
        response = requests.get(f"{microservice_url}/api/contacts", timeout=10)
        
        if response.status_code == 200:
            return JsonResponse(response.json())
        else:
            return JsonResponse({
                'contacts': [],
                'total': 0,
                'error': 'Microservice not responding'
            })
            
    except Exception as e:
        return JsonResponse({
            'contacts': [],
            'total': 0,
            'error': str(e)
        })

