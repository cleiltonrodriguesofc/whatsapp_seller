from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import requests
import json

def whatsapp_web_interface(request):
    """
    main whatsapp web interface - displays conversations like whatsapp web
    """
    return render(request, 'core/whatsapp_web.html')

def whatsapp_web_conversations(request):
    """
    api endpoint to get all conversations from whatsapp
    """
    try:
        microservice_url = getattr(settings, 'MICROSERVICE_URL', 'http://localhost:3001')
        response = requests.get(f'{microservice_url}/api/conversations', timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return JsonResponse(data)
        else:
            return JsonResponse({
                'error': f'Microservice returned status {response.status_code}',
                'conversations': [],
                'total': 0
            })
            
    except requests.exceptions.RequestException as e:
        return JsonResponse({
            'error': f'Failed to connect to microservice: {str(e)}',
            'conversations': [],
            'total': 0
        })
    except Exception as e:
        return JsonResponse({
            'error': f'Unexpected error: {str(e)}',
            'conversations': [],
            'total': 0
        })

def whatsapp_web_chat_messages(request, chat_id):
    """
    api endpoint to get messages from specific chat
    """
    try:
        microservice_url = getattr(settings, 'MICROSERVICE_URL', 'http://localhost:3001')
        limit = request.GET.get('limit', 50)
        response = requests.get(
            f'{microservice_url}/api/conversations/{chat_id}/messages?limit={limit}', 
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return JsonResponse(data)
        else:
            return JsonResponse({
                'error': f'Microservice returned status {response.status_code}',
                'messages': [],
                'total': 0
            })
            
    except requests.exceptions.RequestException as e:
        return JsonResponse({
            'error': f'Failed to connect to microservice: {str(e)}',
            'messages': [],
            'total': 0
        })
    except Exception as e:
        return JsonResponse({
            'error': f'Unexpected error: {str(e)}',
            'messages': [],
            'total': 0
        })

def whatsapp_web_contacts(request):
    """
    api endpoint to get all contacts from whatsapp
    """
    try:
        microservice_url = getattr(settings, 'MICROSERVICE_URL', 'http://localhost:3001')
        response = requests.get(f'{microservice_url}/api/contacts', timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return JsonResponse(data)
        else:
            return JsonResponse({
                'error': f'Microservice returned status {response.status_code}',
                'contacts': [],
                'total': 0
            })
            
    except requests.exceptions.RequestException as e:
        return JsonResponse({
            'error': f'Failed to connect to microservice: {str(e)}',
            'contacts': [],
            'total': 0
        })
    except Exception as e:
        return JsonResponse({
            'error': f'Unexpected error: {str(e)}',
            'contacts': [],
            'total': 0
        })

@csrf_exempt
def whatsapp_web_send_message(request):
    """
    api endpoint to send message through whatsapp
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        chat_id = data.get('chat_id')
        phone = data.get('phone')
        message = data.get('message')
        
        if not message:
            return JsonResponse({
                'success': False,
                'error': 'Message is required'
            })
        
        if not chat_id and not phone:
            return JsonResponse({
                'success': False,
                'error': 'Either chat_id or phone is required'
            })
        
        # send request to microservice
        microservice_url = getattr(settings, 'MICROSERVICE_URL', 'http://localhost:3001')
        payload = {
            'message': message
        }
        
        if chat_id:
            payload['chatId'] = chat_id
        if phone:
            payload['phone'] = phone
            
        response = requests.post(
            f'{microservice_url}/api/send-message',
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return JsonResponse(data)
        else:
            return JsonResponse({
                'success': False,
                'error': f'Microservice returned status {response.status_code}'
            })
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        })
    except requests.exceptions.RequestException as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to connect to microservice: {str(e)}'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Unexpected error: {str(e)}'
        })

def whatsapp_web_connection_status(request):
    """
    api endpoint to check whatsapp connection status
    """
    try:
        microservice_url = getattr(settings, 'MICROSERVICE_URL', 'http://localhost:3001')
        response = requests.get(f'{microservice_url}/api/status', timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            return JsonResponse(data)
        else:
            return JsonResponse({
                'status': 'error',
                'connected': False,
                'error': f'Microservice returned status {response.status_code}'
            })
            
    except requests.exceptions.RequestException as e:
        return JsonResponse({
            'status': 'error',
            'connected': False,
            'error': f'Failed to connect to microservice: {str(e)}'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'connected': False,
            'error': f'Unexpected error: {str(e)}'
        })

