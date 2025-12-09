"""
WhatsApp Connection Forms
"""
from django import forms
from .whatsapp_models import WhatsAppConnection
import re

class WhatsAppConnectionForm(forms.ModelForm):
    """Formulário para configurar conexão WhatsApp"""
    
    phone_number = forms.CharField(
        label='Número do WhatsApp',
        max_length=20,
        help_text='Digite seu número no formato: +5511999999999',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+5511999999999',
            'pattern': r'\+[1-9]\d{1,14}',
            'title': 'Formato: +5511999999999'
        })
    )
    
    max_messages_per_hour = forms.IntegerField(
        label='Limite de mensagens por hora',
        min_value=1,
        max_value=500,
        initial=100,
        help_text='Recomendado: 100 mensagens/hora para evitar bloqueios',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '1',
            'max': '500'
        })
    )
    
    min_interval_seconds = forms.IntegerField(
        label='Intervalo mínimo entre mensagens (segundos)',
        min_value=1,
        max_value=60,
        initial=2,
        help_text='Recomendado: 2-5 segundos para parecer natural',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '1',
            'max': '60'
        })
    )
    
    class Meta:
        model = WhatsAppConnection
        fields = ['phone_number', 'max_messages_per_hour', 'min_interval_seconds']
    
    def clean_phone_number(self):
        """Validar e formatar número de telefone"""
        phone = self.cleaned_data.get('phone_number', '').strip()
        
        # Remover espaços e caracteres especiais, exceto +
        phone = re.sub(r'[^\d+]', '', phone)
        
        # Verificar se começa com +
        if not phone.startswith('+'):
            raise forms.ValidationError('O número deve começar com + seguido do código do país.')
        
        # Verificar formato básico
        if not re.match(r'^\+[1-9]\d{1,14}$', phone):
            raise forms.ValidationError('Formato inválido. Use: +5511999999999')
        
        # Verificar se é um número brasileiro válido
        if phone.startswith('+55'):
            # Número brasileiro deve ter 13 dígitos (+55 + 11 dígitos)
            if len(phone) != 14:
                raise forms.ValidationError('Número brasileiro deve ter 11 dígitos após +55.')
        
        return phone
    
    def clean_max_messages_per_hour(self):
        """Validar limite de mensagens"""
        limit = self.cleaned_data.get('max_messages_per_hour')
        
        if limit and limit > 200:
            # Aviso para limites altos
            pass  # Permitir, mas com aviso no template
        
        return limit
    
    def clean(self):
        """Validação geral do formulário"""
        cleaned_data = super().clean()
        
        max_messages = cleaned_data.get('max_messages_per_hour', 0)
        min_interval = cleaned_data.get('min_interval_seconds', 0)
        
        # Calcular se os limites são compatíveis
        if max_messages and min_interval:
            max_possible_per_hour = 3600 / min_interval  # 3600 segundos em 1 hora
            
            if max_messages > max_possible_per_hour:
                raise forms.ValidationError(
                    f'Com intervalo de {min_interval}s, o máximo possível é '
                    f'{int(max_possible_per_hour)} mensagens/hora.'
                )
        
        return cleaned_data

