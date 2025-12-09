from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import requests
import json

def whatsapp_connect(request):
    """
    Página principal de conexão WhatsApp com QR Code direto
    """
    return render(request, 'core/whatsapp_connect.html')

def whatsapp_api_status(request):
    """
    API endpoint para verificar status da conexão WhatsApp
    """
    try:
        # fazer requisição para o microserviço
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

@csrf_exempt
def whatsapp_api_restart(request):
    """
    API endpoint para reiniciar a conexão WhatsApp
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        # fazer requisição para o microserviço
        microservice_url = getattr(settings, 'MICROSERVICE_URL', 'http://localhost:3001')
        response = requests.post(f'{microservice_url}/api/restart', timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return JsonResponse(data)
        else:
            return JsonResponse({
                'success': False,
                'error': f'Microservice returned status {response.status_code}'
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

@csrf_exempt
def whatsapp_api_send_message(request):
    """
    API endpoint para enviar mensagem via WhatsApp
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        # obter dados do request
        data = json.loads(request.body)
        phone = data.get('phone')
        message = data.get('message')
        
        if not phone or not message:
            return JsonResponse({
                'success': False,
                'error': 'Phone and message are required'
            })
        
        # fazer requisição para o microserviço
        microservice_url = getattr(settings, 'MICROSERVICE_URL', 'http://localhost:3001')
        response = requests.post(
            f'{microservice_url}/api/send-message',
            json={'phone': phone, 'message': message},
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

