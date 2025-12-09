"""
WhatsApp Connection Models
"""
from django.db import models
from django.contrib.auth.models import User
import uuid

class WhatsAppConnection(models.Model):
    """Modelo para gerenciar conexões WhatsApp"""
    
    STATUS_CHOICES = [
        ('disconnected', 'Desconectado'),
        ('connecting', 'Conectando'),
        ('qr_waiting', 'Aguardando QR Code'),
        ('connected', 'Conectado'),
        ('error', 'Erro'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='whatsapp_connection')
    phone_number = models.CharField(max_length=20, help_text="Número no formato: +5511999999999")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='disconnected')
    qr_code = models.TextField(blank=True, null=True, help_text="QR Code para conexão")
    session_id = models.CharField(max_length=100, blank=True, null=True)
    last_connected = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Configurações de segurança
    is_active = models.BooleanField(default=True)
    max_messages_per_hour = models.IntegerField(default=100, help_text="Limite de mensagens por hora")
    min_interval_seconds = models.IntegerField(default=2, help_text="Intervalo mínimo entre mensagens")
    
    class Meta:
        verbose_name = "Conexão WhatsApp"
        verbose_name_plural = "Conexões WhatsApp"
    
    def __str__(self):
        return f"{self.phone_number} - {self.get_status_display()}"
    
    def get_formatted_phone(self):
        """Retorna número formatado para exibição"""
        if self.phone_number:
            # Remove caracteres especiais e formata
            clean = ''.join(filter(str.isdigit, self.phone_number))
            if len(clean) >= 11:
                return f"+{clean[:2]} ({clean[2:4]}) {clean[4:9]}-{clean[9:]}"
        return self.phone_number

class WhatsAppMessage(models.Model):
    """Modelo para rastrear mensagens enviadas"""
    
    MESSAGE_TYPES = [
        ('text', 'Texto'),
        ('image', 'Imagem'),
        ('document', 'Documento'),
        ('audio', 'Áudio'),
    ]
    
    connection = models.ForeignKey(WhatsAppConnection, on_delete=models.CASCADE, related_name='sent_messages')
    to_number = models.CharField(max_length=20)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    content = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    delivered = models.BooleanField(default=False)
    read = models.BooleanField(default=False)
    whatsapp_message_id = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        verbose_name = "Mensagem WhatsApp"
        verbose_name_plural = "Mensagens WhatsApp"
        ordering = ['-sent_at']
    
    def __str__(self):
        return f"Para {self.to_number} em {self.sent_at.strftime('%d/%m/%Y %H:%M')}"

class WhatsAppGroup(models.Model):
    """Modelo para gerenciar grupos WhatsApp"""
    
    connection = models.ForeignKey(WhatsAppConnection, on_delete=models.CASCADE, related_name='groups')
    group_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    participants_count = models.IntegerField(default=0)
    is_admin = models.BooleanField(default=False)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Grupo WhatsApp"
        verbose_name_plural = "Grupos WhatsApp"
    
    def __str__(self):
        return f"{self.name} ({self.participants_count} membros)"

