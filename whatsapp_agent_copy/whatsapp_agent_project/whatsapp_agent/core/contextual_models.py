"""
Extended models for AI Contextual and Dynamic functionality.
"""
from django.db import models
from django.utils import timezone
from .models import Contact, Conversation, Message


class ConversationContext(models.Model):
    """Model to store real-time conversation analysis and context"""
    
    SENTIMENT_CHOICES = (
        ('very_positive', 'Very Positive'),
        ('positive', 'Positive'),
        ('neutral', 'Neutral'),
        ('negative', 'Negative'),
        ('very_negative', 'Very Negative'),
        ('frustrated', 'Frustrated'),
        ('excited', 'Excited'),
        ('confused', 'Confused'),
    )
    
    TECHNICAL_LEVEL_CHOICES = (
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('expert', 'Expert'),
    )
    
    SALES_FUNNEL_CHOICES = (
        ('awareness', 'Awareness'),
        ('interest', 'Interest'),
        ('consideration', 'Consideration'),
        ('intent', 'Intent'),
        ('evaluation', 'Evaluation'),
        ('purchase', 'Purchase'),
        ('retention', 'Retention'),
    )
    
    conversation = models.OneToOneField(Conversation, on_delete=models.CASCADE, related_name='context')
    
    # sentiment analysis
    current_sentiment = models.CharField(max_length=20, choices=SENTIMENT_CHOICES, default='neutral')
    sentiment_confidence = models.FloatField(default=0.0)  # 0.0 to 1.0
    sentiment_history = models.JSONField(default=list)  # stores last 10 sentiment analyses
    
    # technical level detection
    technical_level = models.CharField(max_length=20, choices=TECHNICAL_LEVEL_CHOICES, default='beginner')
    technical_confidence = models.FloatField(default=0.0)
    technical_indicators = models.JSONField(default=dict)  # stores technical terms used, complexity scores
    
    # sales funnel stage
    funnel_stage = models.CharField(max_length=20, choices=SALES_FUNNEL_CHOICES, default='awareness')
    funnel_confidence = models.FloatField(default=0.0)
    
    # conversation patterns
    message_count = models.PositiveIntegerField(default=0)
    avg_response_time = models.FloatField(default=0.0)  # in seconds
    conversation_topics = models.JSONField(default=list)  # main topics discussed
    
    # persona adaptation triggers
    needs_persona_adaptation = models.BooleanField(default=False)
    last_adaptation_trigger = models.CharField(max_length=100, blank=True)
    
    # timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Context for {self.conversation}"
    
    def update_sentiment(self, sentiment, confidence, analysis_data):
        """Update sentiment with historical tracking"""
        self.current_sentiment = sentiment
        self.sentiment_confidence = confidence
        
        # add to history (keep last 10)
        sentiment_entry = {
            'sentiment': sentiment,
            'confidence': confidence,
            'timestamp': timezone.now().isoformat(),
            'data': analysis_data
        }
        
        if not self.sentiment_history:
            self.sentiment_history = []
        
        self.sentiment_history.append(sentiment_entry)
        if len(self.sentiment_history) > 10:
            self.sentiment_history = self.sentiment_history[-10:]
        
        self.save()
    
    def update_technical_level(self, level, confidence, indicators):
        """Update technical level assessment"""
        self.technical_level = level
        self.technical_confidence = confidence
        self.technical_indicators = indicators
        self.save()
    
    def should_adapt_persona(self):
        """Determine if persona should be adapted based on context changes"""
        # check for significant sentiment changes
        if len(self.sentiment_history) >= 2:
            current = self.sentiment_history[-1]
            previous = self.sentiment_history[-2]
            
            sentiment_change = abs(
                self._sentiment_to_score(current['sentiment']) - 
                self._sentiment_to_score(previous['sentiment'])
            )
            
            if sentiment_change >= 2:  # significant change
                return True, f"sentiment_change_{current['sentiment']}"
        
        # check for technical level confidence threshold
        if self.technical_confidence > 0.8 and self.technical_level != 'beginner':
            return True, f"technical_level_{self.technical_level}"
        
        # check for funnel stage progression
        if self.funnel_confidence > 0.7:
            return True, f"funnel_stage_{self.funnel_stage}"
        
        return False, None
    
    def _sentiment_to_score(self, sentiment):
        """Convert sentiment to numeric score for comparison"""
        sentiment_scores = {
            'very_negative': -2,
            'negative': -1,
            'frustrated': -1,
            'confused': -0.5,
            'neutral': 0,
            'positive': 1,
            'excited': 1.5,
            'very_positive': 2,
        }
        return sentiment_scores.get(sentiment, 0)


class PersonaAdaptation(models.Model):
    """Model to track persona adaptations applied to conversations"""
    
    ADAPTATION_TYPE_CHOICES = (
        ('sentiment_based', 'Sentiment Based'),
        ('technical_level', 'Technical Level'),
        ('funnel_stage', 'Sales Funnel Stage'),
        ('conversation_pattern', 'Conversation Pattern'),
        ('manual_override', 'Manual Override'),
    )
    
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='persona_adaptations')
    adaptation_type = models.CharField(max_length=30, choices=ADAPTATION_TYPE_CHOICES)
    
    # original and adapted personas
    original_persona = models.TextField()
    adapted_persona = models.TextField()
    
    # adaptation details
    trigger_reason = models.CharField(max_length=200)
    adaptation_data = models.JSONField(default=dict)  # stores context data that triggered adaptation
    
    # effectiveness tracking
    is_active = models.BooleanField(default=True)
    effectiveness_score = models.FloatField(null=True, blank=True)  # measured by user engagement
    
    # timestamps
    applied_at = models.DateTimeField(auto_now_add=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Adaptation for {self.conversation} - {self.adaptation_type}"
    
    def deactivate(self):
        """Deactivate this adaptation"""
        self.is_active = False
        self.deactivated_at = timezone.now()
        self.save()


class MessageAnalysis(models.Model):
    """Model to store detailed analysis of individual messages"""
    
    message = models.OneToOneField(Message, on_delete=models.CASCADE, related_name='analysis')
    
    # sentiment analysis
    sentiment = models.CharField(max_length=20)
    sentiment_confidence = models.FloatField()
    sentiment_keywords = models.JSONField(default=list)
    
    # technical analysis
    technical_terms = models.JSONField(default=list)
    complexity_score = models.FloatField(default=0.0)
    
    # intent analysis
    detected_intent = models.CharField(max_length=100, blank=True)
    intent_confidence = models.FloatField(default=0.0)
    
    # topic analysis
    main_topics = models.JSONField(default=list)
    
    # urgency and priority
    urgency_level = models.CharField(
        max_length=10,
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('urgent', 'Urgent')],
        default='medium'
    )
    
    # analysis metadata
    analysis_version = models.CharField(max_length=10, default='1.0')
    processing_time = models.FloatField(default=0.0)  # in seconds
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Analysis for message {self.message.id}"


class PersonaTemplate(models.Model):
    """Model to store predefined persona templates for different contexts"""
    
    CONTEXT_TYPE_CHOICES = (
        ('sentiment', 'Sentiment Based'),
        ('technical', 'Technical Level'),
        ('funnel', 'Sales Funnel'),
        ('industry', 'Industry Specific'),
        ('time_of_day', 'Time of Day'),
        ('urgency', 'Urgency Level'),
    )
    
    name = models.CharField(max_length=100)
    context_type = models.CharField(max_length=20, choices=CONTEXT_TYPE_CHOICES)
    context_value = models.CharField(max_length=50)  # e.g., 'frustrated', 'expert', 'purchase'
    
    persona_prompt = models.TextField()
    tone_adjustments = models.JSONField(default=dict)  # specific tone modifications
    
    # usage tracking
    usage_count = models.PositiveIntegerField(default=0)
    effectiveness_rating = models.FloatField(default=0.0)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.context_type}: {self.context_value})"
    
    class Meta:
        unique_together = ['context_type', 'context_value']


class AdaptationRule(models.Model):
    """Model to define rules for automatic persona adaptation"""
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    
    # trigger conditions
    trigger_conditions = models.JSONField(default=dict)  # complex conditions in JSON format
    
    # adaptation actions
    target_persona_template = models.ForeignKey(PersonaTemplate, on_delete=models.CASCADE)
    priority = models.PositiveIntegerField(default=1)  # higher number = higher priority
    
    # effectiveness and usage
    is_active = models.BooleanField(default=True)
    usage_count = models.PositiveIntegerField(default=0)
    success_rate = models.FloatField(default=0.0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    def evaluate_conditions(self, context):
        """Evaluate if this rule's conditions are met for given context"""
        # this would contain logic to evaluate complex conditions
        # for now, simplified implementation
        return False
    
    class Meta:
        ordering = ['-priority', 'name']

