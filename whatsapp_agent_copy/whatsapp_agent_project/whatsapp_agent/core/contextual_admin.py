"""
Admin configuration for contextual AI models
"""
from django.contrib import admin
from .contextual_models import (
    ConversationContext, PersonaAdaptation, MessageAnalysis, 
    PersonaTemplate, AdaptationRule
)


@admin.register(ConversationContext)
class ConversationContextAdmin(admin.ModelAdmin):
    list_display = ['conversation', 'current_sentiment', 'technical_level', 'funnel_stage', 'message_count', 'updated_at']
    list_filter = ['current_sentiment', 'technical_level', 'funnel_stage', 'needs_persona_adaptation']
    search_fields = ['conversation__contact__name', 'conversation__contact__phone_number']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Conversation', {
            'fields': ('conversation',)
        }),
        ('Sentiment Analysis', {
            'fields': ('current_sentiment', 'sentiment_confidence', 'sentiment_history')
        }),
        ('Technical Analysis', {
            'fields': ('technical_level', 'technical_confidence', 'technical_indicators')
        }),
        ('Sales Funnel', {
            'fields': ('funnel_stage', 'funnel_confidence')
        }),
        ('Conversation Stats', {
            'fields': ('message_count', 'avg_response_time', 'conversation_topics')
        }),
        ('Adaptation', {
            'fields': ('needs_persona_adaptation', 'last_adaptation_trigger')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        })
    )


@admin.register(PersonaAdaptation)
class PersonaAdaptationAdmin(admin.ModelAdmin):
    list_display = ['conversation', 'adaptation_type', 'trigger_reason', 'is_active', 'applied_at']
    list_filter = ['adaptation_type', 'is_active', 'applied_at']
    search_fields = ['conversation__contact__name', 'trigger_reason']
    readonly_fields = ['applied_at', 'deactivated_at']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('conversation', 'adaptation_type', 'trigger_reason')
        }),
        ('Persona Details', {
            'fields': ('original_persona', 'adapted_persona')
        }),
        ('Adaptation Data', {
            'fields': ('adaptation_data',)
        }),
        ('Status', {
            'fields': ('is_active', 'effectiveness_score')
        }),
        ('Timestamps', {
            'fields': ('applied_at', 'deactivated_at')
        })
    )


@admin.register(MessageAnalysis)
class MessageAnalysisAdmin(admin.ModelAdmin):
    list_display = ['message', 'sentiment', 'sentiment_confidence', 'detected_intent', 'urgency_level', 'created_at']
    list_filter = ['sentiment', 'detected_intent', 'urgency_level', 'created_at']
    search_fields = ['message__content', 'detected_intent']
    readonly_fields = ['created_at', 'processing_time']
    
    fieldsets = (
        ('Message', {
            'fields': ('message',)
        }),
        ('Sentiment Analysis', {
            'fields': ('sentiment', 'sentiment_confidence', 'sentiment_keywords')
        }),
        ('Technical Analysis', {
            'fields': ('technical_terms', 'complexity_score')
        }),
        ('Intent & Topics', {
            'fields': ('detected_intent', 'intent_confidence', 'main_topics')
        }),
        ('Priority', {
            'fields': ('urgency_level',)
        }),
        ('Metadata', {
            'fields': ('analysis_version', 'processing_time', 'created_at')
        })
    )


@admin.register(PersonaTemplate)
class PersonaTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'context_type', 'context_value', 'usage_count', 'effectiveness_rating', 'is_active']
    list_filter = ['context_type', 'is_active', 'created_at']
    search_fields = ['name', 'context_value']
    readonly_fields = ['usage_count', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'context_type', 'context_value')
        }),
        ('Persona Configuration', {
            'fields': ('persona_prompt', 'tone_adjustments')
        }),
        ('Usage Statistics', {
            'fields': ('usage_count', 'effectiveness_rating')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        })
    )


@admin.register(AdaptationRule)
class AdaptationRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'target_persona_template', 'priority', 'usage_count', 'success_rate', 'is_active']
    list_filter = ['is_active', 'priority', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['usage_count', 'success_rate', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'description', 'priority')
        }),
        ('Rule Configuration', {
            'fields': ('trigger_conditions', 'target_persona_template')
        }),
        ('Performance', {
            'fields': ('usage_count', 'success_rate')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        })
    )

