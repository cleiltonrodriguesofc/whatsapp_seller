"""
WhatsApp Connection Views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import requests
from .whatsapp_models import WhatsAppConnection, WhatsAppGroup
from .whatsapp_forms import WhatsAppConnectionForm

# @login_required  # Removido para facilitar teste
def whatsapp_setup(request):
    """Página principal de configuração do WhatsApp"""
    # Para teste, usar usuário admin ou criar um padrão
    from django.contrib.auth.models import User
    user, created = User.objects.get_or_create(username='testuser', defaults={'email': 'test@test.com'})
    
    try:
        connection = WhatsAppConnection.objects.get(user=user)
    except WhatsAppConnection.DoesNotExist:
        connection = None
    
    if request.method == 'POST':
        form = WhatsAppConnectionForm(request.POST, instance=connection)
        if form.is_valid():
            connection = form.save(commit=False)
            connection.user = user
            connection.save()
            
            # Iniciar processo de conexão
            if connection.status == 'disconnected':
                success = start_whatsapp_connection(connection)
                if success:
                    messages.success(request, 'Processo de conexão iniciado! Escaneie o QR Code com seu WhatsApp.')
                    return redirect('whatsapp_qr', connection_id=connection.id)
                else:
                    messages.error(request, 'Erro ao iniciar conexão. Tente novamente.')
    else:
        form = WhatsAppConnectionForm(instance=connection)
    
    context = {
        'form': form,
        'connection': connection,
        'page_title': 'Configuração WhatsApp'
    }
    return render(request, 'core/whatsapp_setup.html', context)

# @login_required  # Removido para facilitar teste
def whatsapp_qr(request, connection_id):
    """Página para exibir QR Code"""
    from django.contrib.auth.models import User
    user, created = User.objects.get_or_create(username='testuser', defaults={'email': 'test@test.com'})
    connection = get_object_or_404(WhatsAppConnection, id=connection_id, user=user)
    
    context = {
        'connection': connection,
        'page_title': 'Conectar WhatsApp'
    }
    return render(request, 'core/whatsapp_qr.html', context)

# @login_required  # Removido para facilitar teste
def whatsapp_status(request):
    """API para verificar status da conexão"""
    from django.contrib.auth.models import User
    user, created = User.objects.get_or_create(username='testuser', defaults={'email': 'test@test.com'})
    
    try:
        connection = WhatsAppConnection.objects.get(user=user)
        
        # Verificar status no microserviço
        status_data = check_microservice_status(connection)
        
        return JsonResponse({
            'status': connection.status,
            'phone_number': connection.get_formatted_phone(),
            'last_connected': connection.last_connected.isoformat() if connection.last_connected else None,
            'qr_code': connection.qr_code,
            'microservice_status': status_data
        })
    except WhatsAppConnection.DoesNotExist:
        return JsonResponse({
            'status': 'not_configured',
            'message': 'WhatsApp não configurado'
        })

@login_required
def whatsapp_disconnect(request):
    """Desconectar WhatsApp"""
    if request.method == 'POST':
        try:
            connection = WhatsAppConnection.objects.get(user=request.user)
            
            # Desconectar do microserviço
            disconnect_microservice(connection)
            
            # Atualizar status
            connection.status = 'disconnected'
            connection.qr_code = None
            connection.session_id = None
            connection.save()
            
            messages.success(request, 'WhatsApp desconectado com sucesso!')
        except WhatsAppConnection.DoesNotExist:
            messages.error(request, 'Nenhuma conexão encontrada.')
    
    return redirect('whatsapp_setup')

@login_required
def whatsapp_groups(request):
    """Listar grupos WhatsApp"""
    try:
        connection = WhatsAppConnection.objects.get(user=request.user)
        
        if connection.status == 'connected':
            # Sincronizar grupos do microserviço
            sync_groups(connection)
            groups = WhatsAppGroup.objects.filter(connection=connection)
        else:
            groups = []
            messages.warning(request, 'WhatsApp não está conectado.')
    except WhatsAppConnection.DoesNotExist:
        groups = []
        messages.error(request, 'Configure o WhatsApp primeiro.')
    
    context = {
        'groups': groups,
        'page_title': 'Grupos WhatsApp'
    }
    return render(request, 'core/whatsapp_groups.html', context)

@csrf_exempt
@require_http_methods(["POST"])
def whatsapp_webhook_status(request):
    """Webhook para receber atualizações de status do microserviço"""
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        status = data.get('status')
        qr_code = data.get('qr_code')
        
        # Encontrar conexão pelo session_id
        try:
            connection = WhatsAppConnection.objects.get(session_id=session_id)
            connection.status = status
            
            if qr_code:
                connection.qr_code = qr_code
            
            if status == 'connected':
                connection.last_connected = timezone.now()
                connection.qr_code = None  # Limpar QR code quando conectado
            
            connection.save()
            
            return JsonResponse({'success': True})
        except WhatsAppConnection.DoesNotExist:
            return JsonResponse({'error': 'Connection not found'}, status=404)
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# Funções auxiliares

def start_whatsapp_connection(connection):
    """Inicia conexão com microserviço WhatsApp"""
    try:
        from django.conf import settings
        microservice_url = getattr(settings, 'MICROSERVICE_URL', 'http://localhost:3001')
        
        # Verificar se microserviço está rodando
        response = requests.get(f'{microservice_url}/status', timeout=5)
        
        if response.status_code == 200:
            status_data = response.json()
            connection.session_id = str(connection.id)
            connection.status = 'connecting'
            
            # Se há QR code disponível, buscar
            if status_data.get('qr_code'):
                qr_response = requests.get(f'{microservice_url}/qr', timeout=5)
                if qr_response.status_code == 200:
                    qr_data = qr_response.json()
                    connection.qr_code = qr_data.get('qr_code')
            
            connection.save()
            return True
        return False
    except Exception as e:
        print(f"Error starting WhatsApp connection: {e}")
        return False

def check_microservice_status(connection):
    """Verifica status no microserviço"""
    try:
        from django.conf import settings
        microservice_url = getattr(settings, 'MICROSERVICE_URL', 'http://localhost:3001')
        
        # Verificar status geral
        response = requests.get(f'{microservice_url}/api/status', timeout=5)
        if response.status_code == 200:
            status_data = response.json()
            
            # Se há QR code disponível, buscar a imagem
            if status_data.get('success') and status_data.get('data', {}).get('qrAvailable'):
                qr_response = requests.get(f'{microservice_url}/api/qr', timeout=5)
                if qr_response.status_code == 200:
                    qr_data = qr_response.json()
                    if qr_data.get('success'):
                        status_data['qr_image'] = qr_data['data']['qrCode']
            
            return status_data
        return {'status': 'unknown'}
    except Exception as e:
        print(f"Error checking microservice status: {e}")
        return {'status': 'offline'}

def disconnect_microservice(connection):
    """Desconecta do microserviço"""
    try:
        from django.conf import settings
        microservice_url = getattr(settings, 'MICROSERVICE_URL', 'http://localhost:3000')
        
        requests.post(f'{microservice_url}/disconnect/{connection.session_id}', timeout=5)
    except:
        pass  # Ignorar erros de desconexão

def sync_groups(connection):
    """Sincroniza grupos do microserviço"""
    try:
        from django.conf import settings
        microservice_url = getattr(settings, 'MICROSERVICE_URL', 'http://localhost:3000')
        
        response = requests.get(f'{microservice_url}/groups/{connection.session_id}', timeout=10)
        if response.status_code == 200:
            groups_data = response.json().get('groups', [])
            
            for group_data in groups_data:
                WhatsAppGroup.objects.update_or_create(
                    connection=connection,
                    group_id=group_data['id'],
                    defaults={
                        'name': group_data['name'],
                        'participants_count': group_data.get('participants', 0),
                        'is_admin': group_data.get('isAdmin', False)
                    }
                )
    except Exception as e:
        print(f"Error syncing groups: {e}")

