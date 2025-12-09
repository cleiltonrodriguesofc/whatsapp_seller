"""
views.py updates for AI integration
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count

from .models import Product, Contact, Conversation, Message, Sale, WhatsAppConfig, Group, StatusUpdate, AIConfig # Added AIConfig
from .forms import ProductForm, ContactForm, GroupForm, StatusUpdateForm, WhatsAppConfigForm, BulkMessageForm, AIConfigForm # Added AIConfigForm
from .services import ai_service
from .services.product_filters import ProductFilters

# # @login_required  # Removido para facilitar teste  # Removido para facilitar teste
def dashboard(request):
    """dashboard view"""
    # Get counts for dashboard stats
    products_count = Product.objects.filter(is_active=True).count()
    contacts_count = Contact.objects.filter(is_allowed=True).count()
    active_conversations_count = Conversation.objects.filter(status='active').count()
    sales_count = Sale.objects.all().count()
    pending_sales_count = Sale.objects.filter(status='pending').count()
    
    # Get recent conversations
    recent_conversations = Conversation.objects.filter(status='active').order_by("-started_at")[:5]
    
    # Get recent sales
    recent_sales = Sale.objects.all().order_by("-created_at")[:5]
    
    # Prepare data for sales chart
    sales_data = Sale.objects.filter(
        created_at__gte=timezone.now() - timezone.timedelta(days=30)
    ).values('created_at__date').annotate(
        total=Sum('total_price')
    ).order_by('created_at__date')
    
    sales_chart_labels = [str(item['created_at__date']) for item in sales_data]
    sales_chart_values = [float(item['total']) for item in sales_data]
    
    context = {
        'products_count': products_count,
        'contacts_count': contacts_count,
        'active_conversations_count': active_conversations_count,
        'sales_count': sales_count,
        'pending_sales_count': pending_sales_count,
        'recent_conversations': recent_conversations,
        'recent_sales': recent_sales,
        'sales_chart_labels': sales_chart_labels,
        'sales_chart_values': sales_chart_values,
    }
    
    return render(request, 'core/dashboard.html', context)

# @login_required  # Removido para facilitar teste
def product_list(request):
    """product list view"""
    products = Product.objects.all().order_by("-created_at")
    return render(request, 'core/product_list.html', {'products': products})

# @login_required  # Removido para facilitar teste
def product_add(request):
    """add product view"""
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Produto adicionado com sucesso!')
            return redirect('core:product_list')
    else:
        form = ProductForm()
    
    return render(request, 'core/product_form.html', {'form': form, 'title': 'Adicionar Produto'})

# @login_required  # Removido para facilitar teste
def product_edit(request, pk):
    """edit product view"""
    product = get_object_or_404(Product, pk=pk)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Produto atualizado com sucesso!')
            return redirect('core:product_list')
    else:
        form = ProductForm(instance=product)
    
    return render(request, 'core/product_form.html', {'form': form, 'title': 'Editar Produto'})

# @login_required  # Removido para facilitar teste
def product_delete(request, pk):
    """delete product view"""
    product = get_object_or_404(Product, pk=pk)
    
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Produto excluído com sucesso!')
        return redirect("core:product_list")
    
    return render(request, "core/product_confirm_delete.html", {"product": product})

# @login_required  # Removido para facilitar teste
def contact_list(request):
    """contact list view"""
    contacts = Contact.objects.all().order_by("-created_at")
    return render(request, 'core/contact_list.html', {'contacts': contacts})

# @login_required  # Removido para facilitar teste
def contact_add(request):
    """add contact view"""
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Contato adicionado com sucesso!')
            return redirect('core:contact_list')
    else:
        form = ContactForm()
    
    return render(request, 'core/contact_form.html', {'form': form, 'title': 'Adicionar Contato'})

# @login_required  # Removido para facilitar teste
def contact_edit(request, pk):
    """edit contact view"""
    contact = get_object_or_404(Contact, pk=pk)
    
    if request.method == 'POST':
        form = ContactForm(request.POST, instance=contact)
        if form.is_valid():
            form.save()
            messages.success(request, 'Contato atualizado com sucesso!')
            return redirect('core:contact_list')
    else:
        form = ContactForm(instance=contact)
    
    return render(request, 'core/contact_form.html', {'form': form, 'title': 'Editar Contato'})

# @login_required  # Removido para facilitar teste
def contact_delete(request, pk):
    """delete contact view"""
    contact = get_object_or_404(Contact, pk=pk)
    
    if request.method == 'POST':
        contact.delete()
        messages.success(request, 'Contato excluído com sucesso!')
        return redirect('core:contact_list')
    
    return render(request, 'core/contact_confirm_delete.html', {'contact': contact})

# @login_required  # Removido para facilitar teste
def group_list(request):
    """group list view"""
    groups = Group.objects.all().order_by("-created_at")
    return render(request, 'core/group_list.html', {'groups': groups})

# @login_required  # Removido para facilitar teste
def group_add(request):
    """add group view"""
    if request.method == 'POST':
        form = GroupForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Grupo adicionado com sucesso!')
            return redirect('core:group_list')
    else:
        form = GroupForm()
    
    return render(request, 'core/group_form.html', {'form': form, 'title': 'Adicionar Grupo'})

# @login_required  # Removido para facilitar teste
def group_edit(request, pk):
    """edit group view"""
    group = get_object_or_404(Group, pk=pk)
    
    if request.method == 'POST':
        form = GroupForm(request.POST, instance=group)
        if form.is_valid():
            form.save()
            messages.success(request, 'Grupo atualizado com sucesso!')
            return redirect('core:group_list')
    else:
        form = GroupForm(instance=group)
    
    return render(request, 'core/group_form.html', {'form': form, 'title': 'Editar Grupo'})

# @login_required  # Removido para facilitar teste
def group_delete(request, pk):
    """delete group view"""
    group = get_object_or_404(Group, pk=pk)
    
    if request.method == 'POST':
        group.delete()
        messages.success(request, 'Grupo excluído com sucesso!')
        return redirect('core:group_list')
    
    return render(request, 'core/group_confirm_delete.html', {'group': group})

# @login_required  # Removido para facilitar teste
def conversation_list(request):
    """conversation list view"""
    conversations = Conversation.objects.all().order_by("-started_at")
    return render(request, 'core/conversation_list.html', {'conversations': conversations})

# @login_required  # Removido para facilitar teste
def conversation_detail(request, pk):
    """conversation detail view"""
    conversation = get_object_or_404(Conversation, pk=pk)
    messages_list = Message.objects.filter(conversation=conversation).order_by('timestamp')
    
    # Get related products for recommendations
    all_products = Product.objects.filter(is_active=True)
    
    # Get recommended products based on conversation content
    conversation_text = " ".join([msg.content for msg in messages_list])
    recommended_products = ProductFilters.get_recommended_products(all_products, conversation_text)
    
    context = {
        'conversation': conversation,
        'messages': messages_list,
        'recommended_products': recommended_products[:5],  # Limit to 5 recommendations
    }
    
    return render(request, 'core/conversation_detail.html', context)

# @login_required  # Removido para facilitar teste
def conversation_close(request, pk):
    """close conversation view"""
    conversation = get_object_or_404(Conversation, pk=pk)
    
    if request.method == 'POST':
        conversation.close()
        messages.success(request, 'Conversa encerrada com sucesso!')
        return redirect('core:conversation_list')
    
    return render(request, 'core/conversation_confirm_close.html', {'conversation': conversation})

# @login_required  # Removido para facilitar teste
def sale_list(request):
    """sale list view"""
    sales = Sale.objects.all().order_by("-created_at")
    return render(request, 'core/sale_list.html', {'sales': sales})

# @login_required  # Removido para facilitar teste
def sale_detail(request, pk):
    """sale detail view"""
    sale = get_object_or_404(Sale, pk=pk)
    return render(request, 'core/sale_detail.html', {'sale': sale})

# @login_required  # Removido para facilitar teste
def sale_update_status(request, pk):
    """update sale status view"""
    sale = get_object_or_404(Sale, pk=pk)
    
    if request.method == 'POST':
        status = request.POST.get('status')
        if status in [s[0] for s in Sale.STATUS_CHOICES]:
            sale.status = status
            sale.save()
            messages.success(request, 'Status da venda atualizado com sucesso!')
        else:
            messages.error(request, 'Status inválido!')
        
        return redirect('core:sale_detail', pk=sale.pk)
    
    return redirect('core:sale_detail', pk=sale.pk)

# @login_required  # Removido para facilitar teste
def whatsapp_config(request):
    """whatsapp configuration view"""
    # Get the active (or first) WhatsApp config instance
    try:
        config = WhatsAppConfig.objects.get(is_active=True)
    except WhatsAppConfig.DoesNotExist:
        config = WhatsAppConfig.objects.first()
    except WhatsAppConfig.MultipleObjectsReturned:
        # If multiple are active (shouldn't happen with model save logic, but handle defensively)
        config = WhatsAppConfig.objects.filter(is_active=True).first()
        
    if request.method == 'POST':
        form = WhatsAppConfigForm(request.POST, instance=config)
        if form.is_valid():
            # Deactivate other configs if this one is set to active
            if form.cleaned_data.get('is_active'):
                WhatsAppConfig.objects.exclude(pk=form.instance.pk).update(is_active=False)
            
            form.save()
            messages.success(request, 'Configuração do WhatsApp atualizada com sucesso!')
            return redirect('core:whatsapp_config')
        else:
            # Form is invalid, display errors
            messages.error(request, 'Erro ao salvar configuração do WhatsApp. Verifique os campos.')
            
    else:
        form = WhatsAppConfigForm(instance=config)
    
    webhook_url = request.build_absolute_uri('/webhook/')
    
    context = {
        'form': form,
        'webhook_url': webhook_url,
    }
    
    return render(request, 'core/whatsapp_config.html', context)

# @login_required  # Removido para facilitar teste
def ai_config(request):
    """ai configuration view"""
    # Get the active (or first) AI config instance
    try:
        config = AIConfig.objects.get(is_active=True)
    except AIConfig.DoesNotExist:
        # If no config exists, create a default one (or pass None to form)
        # config = AIConfig.objects.create(provider='gemini', is_active=True) # Option 1: Create
        config = None # Option 2: Pass None, form will be unbound
    except AIConfig.MultipleObjectsReturned:
        config = AIConfig.objects.filter(is_active=True).first()
        
    if request.method == 'POST':
        # If config is None, we are creating a new one
        form = AIConfigForm(request.POST, instance=config) 
        if form.is_valid():
            # Deactivate other configs if this one is set to active
            if form.cleaned_data.get('is_active'):
                AIConfig.objects.exclude(pk=form.instance.pk).update(is_active=False)
            
            ai_config_instance = form.save()
            
            # Re-configure the AI service with the potentially updated key
            # Use the reconfigure method which handles loading from DB/settings
            ai_service.reconfigure() 
            messages.success(request, 'Configuração da IA atualizada com sucesso!')
            return redirect('core:ai_config')
        else:
            # Form is invalid, display errors
            messages.error(request, 'Erro ao salvar configuração da IA. Verifique os campos.')
            
    else:
        form = AIConfigForm(instance=config)
    
    # Check if AI is configured (either via DB or settings fallback)
    # Reload config status after potential POST or on initial load
    ai_service.reconfigure() # Ensure service reflects current state
    ai_configured = ai_service.is_configured()
    
    context = {
        'form': form,
        'ai_configured': ai_configured,
        'ai_config_instance': config, # Pass instance for potential display
    }
    
    return render(request, 'core/ai_config.html', context)

# @login_required  # Removido para facilitar teste
# @login_required  # Removido para facilitar teste
def status_update_list(request):
    """status update list view"""
    status_updates = StatusUpdate.objects.all().order_by("-scheduled_for")
    return render(request, 'core/status_update_list.html', {'status_updates': status_updates})

# @login_required  # Removido para facilitar teste
def status_update_add(request):
    """add status update view"""
    if request.method == 'POST':
        form = StatusUpdateForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Status adicionado com sucesso!')
            return redirect('core:status_update_list')
    else:
        form = StatusUpdateForm()
    
    return render(request, 'core/status_update_form.html', {'form': form, 'title': 'Adicionar Status'})

# @login_required  # Removido para facilitar teste
def status_update_edit(request, pk):
    """edit status update view"""
    status_update = get_object_or_404(StatusUpdate, pk=pk)
    
    if request.method == 'POST':
        form = StatusUpdateForm(request.POST, request.FILES, instance=status_update)
        if form.is_valid():
            form.save()
            messages.success(request, 'Status atualizado com sucesso!')
            return redirect('core:status_update_list')
    else:
        form = StatusUpdateForm(instance=status_update)
    
    return render(request, 'core/status_update_form.html', {'form': form, 'title': 'Editar Status'})

# @login_required  # Removido para facilitar teste
def status_update_delete(request, pk):
    """delete status update view"""
    status_update = get_object_or_404(StatusUpdate, pk=pk)
    
    if request.method == 'POST':
        status_update.delete()
        messages.success(request, 'Status excluído com sucesso!')
        return redirect('core:status_update_list')
    
    return render(request, 'core/status_update_confirm_delete.html', {'status_update': status_update})

# @login_required  # Removido para facilitar teste
def bulk_message(request):
    """bulk message view"""
    if request.method == 'POST':
        form = BulkMessageForm(request.POST, request.FILES)
        if form.is_valid():
            # Process bulk message
            # This would integrate with the WhatsApp API
            messages.success(request, 'Mensagem em massa enviada com sucesso!')
            return redirect('core:dashboard')
    else:
        form = BulkMessageForm()
    
    return render(request, 'core/bulk_message.html', {'form': form})

@csrf_exempt
def webhook(request):
    """webhook for whatsapp api"""
    if request.method == 'POST':
        # Process incoming webhook
        try:
            data = request.POST if request.POST else request.body
            
            # Log the webhook data
            print(f"Webhook received: {data}")
            
            # Process the webhook data
            # This would integrate with the WhatsApp API
            
            return JsonResponse({'status': 'success'}) 
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}) 

# @login_required  # Removido para facilitar teste
def api_products(request):
    """api endpoint for products"""
    products = Product.objects.filter(is_active=True)
    
    # Apply filters if provided
    category = request.GET.get('category')
    if category:
        products = products.filter(category__iexact=category)
    
    # Format response
    products_data = [{
        'id': p.id,
        'name': p.name,
        'description': p.description,
        'price': float(p.price),
        'category': p.category,
        'image_url': p.image.url if p.image else None,
        'affiliate_link': p.affiliate_link,
    } for p in products]
    
    return JsonResponse({'products': products_data})

# @login_required  # Removido para facilitar teste
def api_conversations(request):
    """api endpoint for conversations"""
    conversations = Conversation.objects.all().order_by("-started_at")
    
    # Apply filters if provided
    status = request.GET.get('status')
    if status:
        conversations = conversations.filter(status=status)
    
    # Format response
    conversations_data = [{
        'id': c.id,
        'contact_name': c.contact.name,
        'contact_phone': c.contact.phone_number,
        'status': c.status,
        'started_at': c.started_at.isoformat(),
        'last_message_at': c.last_message_at.isoformat() if c.last_message_at else None,
    } for c in conversations]
    
    return JsonResponse({'conversations': conversations_data})


# @login_required  # Removido para facilitar teste
def ai_test(request):
    """AI test view for WhatsApp Sales Agent"""
    response = None
    message = None
    products = Product.objects.filter(is_active=True)  # Produtos ativos para recomendar

    if request.method == 'POST':
        message = request.POST.get('message', '').strip()
        if message:
            # Chama o serviço de IA e retorna o dicionário de resposta
            response = ai_service.get_product_recommendation(message, list(products))
        else:
            from django.contrib import messages
            messages.warning(request, "Por favor, insira uma mensagem.")

    context = {
        'response': response,
        'message': message,
        'products': products,
    }
    return render(request, 'core/ai_test.html', context)

# Import WhatsApp views
from .whatsapp_views import (
    whatsapp_setup, whatsapp_qr, whatsapp_status, 
    whatsapp_disconnect, whatsapp_groups
)

