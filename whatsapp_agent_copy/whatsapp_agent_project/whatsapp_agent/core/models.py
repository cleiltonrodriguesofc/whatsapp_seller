"""
models for the core app.
"""
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class Product(models.Model):
    """model for products that can be sold through whatsapp"""
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    category = models.CharField(max_length=100)
    affiliate_link = models.URLField(max_length=500)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Contact(models.Model):
    """model for whatsapp contacts"""
    phone_number = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    is_allowed = models.BooleanField(default=True)
    persona_prompt = models.TextField(blank=True, null=True, help_text="Define como a IA deve se comportar especificamente com este contato. Se preenchido, sobrescreve a persona geral da IA.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name if self.name else self.phone_number


class Group(models.Model):
    """model for whatsapp groups"""
    group_id = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    is_allowed = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Conversation(models.Model):
    """model for conversations with contacts"""
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('waiting', 'Waiting'),
    )
    
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    started_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Conversation with {self.contact}"
    
    def close(self):
        """close the conversation"""
        self.status = 'closed'
        self.closed_at = timezone.now()
        self.save()


class Message(models.Model):
    """model for messages in a conversation"""
    TYPE_CHOICES = (
        ('received', 'Received'),
        ('sent', 'Sent'),
    )
    
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    message_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    content = models.TextField()
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.message_type} message in {self.conversation}"


class Sale(models.Model):
    """model for tracking sales"""
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Sale of {self.product} to {self.conversation.contact}"


class WhatsAppConfig(models.Model):
    """model for whatsapp api configuration"""
    PROVIDER_CHOICES = (
        ("z-api", "Z-API"),
        ("360dialog", "360dialog"),
        ("twilio", "Twilio"),
        ("gupshup", "Gupshup"),
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default="z-api")
    token = models.CharField(max_length=255, blank=True, null=True) # Made optional
    instance = models.CharField(max_length=255, blank=True, null=True) # Made optional
    phone_number = models.CharField(max_length=20, blank=True, null=True) # Made optional
    webhook_url = models.URLField(max_length=500, blank=True, null=True)
    # gemini_api_key removed, will be in AIConfig model
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)   
    def __str__(self):
        return f"{self.provider} configuration"
    
    class Meta:
        verbose_name = "WhatsApp Configuration"
        verbose_name_plural = "WhatsApp Configurations"


class StatusUpdate(models.Model):
    """model for whatsapp status updates"""
    title = models.CharField(max_length=255)
    content = models.TextField()
    image = models.ImageField(upload_to='status/', null=True, blank=True)
    products = models.ManyToManyField(Product, blank=True)
    scheduled_for = models.DateTimeField()
    was_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title



class AIConfig(models.Model):
    """model for ai provider configuration"""
    PROVIDER_CHOICES = (
        ("gemini", "Google Gemini"),
        # Add other providers here in the future (e.g., openai, groq)
    )
    
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES, default="gemini", unique=True, help_text="Select the AI provider (Only Gemini supported currently)")
    api_key = models.CharField(max_length=255, blank=True, null=True, help_text="API Key for the selected provider")
    persona_prompt = models.TextField(blank=True, null=True, help_text="Define the AI's persona or system prompt (e.g., 'You are a helpful clothing sales assistant specializing in summer wear.')")
    # Add other relevant fields like model name, base url etc. in future
    # model_name = models.CharField(max_length=100, blank=True, null=True, default="gemini-1.5-flash")
    is_active = models.BooleanField(default=True, help_text="Only one AI configuration can be active at a time.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_provider_display()} Configuration"

    def save(self, *args, **kwargs):
        # Ensure only one config is active
        if self.is_active:
            AIConfig.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "AI Configuration"
        verbose_name_plural = "AI Configurations"

class BulkCampaign(models.Model):
    title = models.CharField(max_length=255)
    message = models.TextField()
    send_to_groups = models.ManyToManyField(Group, blank=True)
    send_to_contacts = models.ManyToManyField(Contact, blank=True)
    send_as_status = models.BooleanField(default=False)
    status_update = models.ForeignKey(StatusUpdate, null=True, blank=True, on_delete=models.SET_NULL)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed')],
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Campaign: {self.title} ({self.status})"


# import contextual models
from .contextual_models import (
    ConversationContext, PersonaAdaptation, MessageAnalysis, 
    PersonaTemplate, AdaptationRule
)


# import proactive models
from .proactive_models import (
    LeadOpportunity, ProactiveAction, CustomerBehaviorPattern,
    ProspectingRule, LeadScore, ProspectingCampaign
)


# import personalization models
from .personalization_models import (
    CustomerSegment, PersonalizationProfile, MicroSegment,
    PersonalizedContent, PredictiveInsight, PersonalizationRule,
    PersonalizationExperiment, ContactSegmentMembership
)


# import command models
from .command_models import (
    CommandPattern, WhatsAppCommand, AIConfigurationChange,
    CommandExecution, CommandTemplate, SafetyRule,
    CommandAnalytics, UserPreference
)


# import whatsapp models
from .whatsapp_models import WhatsAppConnection, WhatsAppMessage, WhatsAppGroup

