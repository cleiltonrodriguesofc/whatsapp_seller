"""
Hyper-Personalization Models - Advanced customer segmentation and personalization
"""
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
import json
from decimal import Decimal


class CustomerSegment(models.Model):
    """Dynamic customer segments based on behavior and characteristics"""
    
    SEGMENT_TYPES = [
        ('behavioral', 'Behavioral'),
        ('demographic', 'Demographic'),
        ('psychographic', 'Psychographic'),
        ('transactional', 'Transactional'),
        ('engagement', 'Engagement'),
        ('lifecycle', 'Lifecycle'),
        ('value_based', 'Value-based'),
        ('predictive', 'Predictive'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    segment_type = models.CharField(max_length=20, choices=SEGMENT_TYPES)
    
    # Segmentation criteria
    criteria = models.JSONField(default=dict, help_text="Criteria for segment membership")
    rules = models.JSONField(default=list, help_text="List of rules that define this segment")
    
    # Segment characteristics
    size = models.IntegerField(default=0, help_text="Number of contacts in this segment")
    avg_engagement_score = models.FloatField(default=0.0)
    avg_purchase_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    conversion_rate = models.FloatField(default=0.0)
    
    # Personalization settings
    preferred_communication_style = models.CharField(max_length=50, default='friendly')
    optimal_message_frequency = models.CharField(max_length=20, default='medium')
    best_contact_hours = models.JSONField(default=list, help_text="Preferred hours for contact")
    
    # Performance tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_analyzed = models.DateTimeField(null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    auto_update = models.BooleanField(default=True, help_text="Automatically update segment membership")
    
    class Meta:
        ordering = ['-size', 'name']
        indexes = [
            models.Index(fields=['segment_type', 'is_active']),
            models.Index(fields=['size']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.size} contacts)"
    
    def update_segment_stats(self):
        """Update segment statistics based on current members"""
        # Get segment members through ContactSegmentMembership
        memberships = ContactSegmentMembership.objects.filter(segment=self)
        members = [membership.contact for membership in memberships]
        self.size = len(members)
        
        if self.size > 0:
            # Calculate average engagement
            total_engagement = sum(
                getattr(contact, 'lead_score', None) and contact.lead_score.engagement_score or 0
                for contact in members
            )
            self.avg_engagement_score = total_engagement / self.size
            
            # Calculate conversion rate (simplified)
            # This would need to be connected to actual sales data
            self.conversion_rate = 0.15  # Placeholder
        
        self.last_analyzed = timezone.now()
        self.save()


class PersonalizationProfile(models.Model):
    """Individual personalization profile for each contact"""
    
    COMMUNICATION_STYLES = [
        ('formal', 'Formal'),
        ('friendly', 'Friendly'),
        ('casual', 'Casual'),
        ('professional', 'Professional'),
        ('enthusiastic', 'Enthusiastic'),
        ('consultative', 'Consultative'),
    ]
    
    PERSONALITY_TYPES = [
        ('analytical', 'Analytical'),
        ('driver', 'Driver'),
        ('expressive', 'Expressive'),
        ('amiable', 'Amiable'),
    ]
    
    contact = models.OneToOneField('Contact', on_delete=models.CASCADE, related_name='personalization_profile')
    
    # Communication preferences
    preferred_style = models.CharField(max_length=20, choices=COMMUNICATION_STYLES, default='friendly')
    personality_type = models.CharField(max_length=20, choices=PERSONALITY_TYPES, null=True, blank=True)
    response_speed_preference = models.CharField(max_length=20, default='normal')  # fast, normal, slow
    
    # Content preferences
    prefers_detailed_info = models.BooleanField(default=False)
    prefers_visual_content = models.BooleanField(default=False)
    prefers_price_focus = models.BooleanField(default=False)
    prefers_feature_focus = models.BooleanField(default=True)
    
    # Behavioral insights
    decision_making_speed = models.CharField(max_length=20, default='medium')  # fast, medium, slow
    price_sensitivity = models.CharField(max_length=20, default='medium')  # low, medium, high
    brand_loyalty = models.CharField(max_length=20, default='medium')  # low, medium, high
    
    # Timing preferences
    optimal_contact_hours = models.JSONField(default=list)
    optimal_days_of_week = models.JSONField(default=list)
    timezone_preference = models.CharField(max_length=50, default='America/Sao_Paulo')
    
    # Product preferences
    favorite_categories = models.JSONField(default=list)
    avoided_categories = models.JSONField(default=list)
    price_range_preference = models.JSONField(default=dict)  # min/max for different categories
    
    # Engagement patterns
    avg_session_duration = models.DurationField(null=True, blank=True)
    preferred_message_length = models.CharField(max_length=20, default='medium')  # short, medium, long
    emoji_usage_preference = models.CharField(max_length=20, default='moderate')  # none, minimal, moderate, frequent
    
    # Predictive attributes
    predicted_lifetime_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    churn_risk_score = models.FloatField(default=0.0, help_text="0-1 score indicating churn risk")
    next_purchase_probability = models.FloatField(default=0.0)
    recommended_approach = models.TextField(blank=True)
    
    # Metadata
    confidence_score = models.FloatField(default=0.0, help_text="Confidence in personalization data")
    last_updated = models.DateTimeField(auto_now=True)
    data_points_count = models.IntegerField(default=0, help_text="Number of interactions used for profiling")
    
    class Meta:
        ordering = ['-confidence_score']
    
    def __str__(self):
        return f"Profile for {self.contact.name or self.contact.phone_number}"
    
    def update_confidence_score(self):
        """Update confidence score based on available data"""
        # Simple confidence calculation based on data completeness
        total_fields = 15  # Approximate number of key fields
        filled_fields = 0
        
        if self.preferred_style != 'friendly':  # Default value
            filled_fields += 1
        if self.personality_type:
            filled_fields += 1
        if self.optimal_contact_hours:
            filled_fields += 1
        if self.favorite_categories:
            filled_fields += 1
        if self.data_points_count > 10:
            filled_fields += 2
        if self.data_points_count > 50:
            filled_fields += 3
        
        self.confidence_score = min(1.0, filled_fields / total_fields)
        self.save()


class MicroSegment(models.Model):
    """Ultra-specific micro-segments for hyper-personalization"""
    
    name = models.CharField(max_length=150)
    description = models.TextField()
    parent_segment = models.ForeignKey(CustomerSegment, on_delete=models.CASCADE, related_name='micro_segments')
    
    # Micro-segment criteria (very specific)
    specific_criteria = models.JSONField(default=dict)
    behavioral_patterns = models.JSONField(default=dict)
    
    # Personalization strategy
    messaging_strategy = models.TextField()
    product_focus = models.JSONField(default=list)
    communication_frequency = models.CharField(max_length=20, default='weekly')
    
    # Performance
    size = models.IntegerField(default=0)
    performance_score = models.FloatField(default=0.0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-performance_score', '-size']
    
    def __str__(self):
        return f"{self.name} (Micro-segment of {self.parent_segment.name})"


class PersonalizedContent(models.Model):
    """Personalized content templates and variations"""
    
    CONTENT_TYPES = [
        ('greeting', 'Greeting'),
        ('product_intro', 'Product Introduction'),
        ('follow_up', 'Follow-up'),
        ('offer', 'Special Offer'),
        ('educational', 'Educational Content'),
        ('social_proof', 'Social Proof'),
        ('urgency', 'Urgency/Scarcity'),
        ('closing', 'Closing/CTA'),
    ]
    
    name = models.CharField(max_length=100)
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPES)
    
    # Target criteria
    target_segments = models.ManyToManyField(CustomerSegment, blank=True)
    target_personality_types = models.JSONField(default=list)
    target_communication_styles = models.JSONField(default=list)
    
    # Content variations
    formal_version = models.TextField(blank=True)
    friendly_version = models.TextField(blank=True)
    casual_version = models.TextField(blank=True)
    professional_version = models.TextField(blank=True)
    enthusiastic_version = models.TextField(blank=True)
    consultative_version = models.TextField(blank=True)
    
    # Conditional content
    price_sensitive_version = models.TextField(blank=True)
    feature_focused_version = models.TextField(blank=True)
    quick_decision_version = models.TextField(blank=True)
    detailed_info_version = models.TextField(blank=True)
    
    # Performance tracking
    usage_count = models.IntegerField(default=0)
    success_rate = models.FloatField(default=0.0)
    avg_response_time = models.DurationField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-success_rate', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_content_type_display()})"
    
    def get_personalized_content(self, profile: PersonalizationProfile) -> str:
        """Get the most appropriate content version for a profile"""
        style = profile.preferred_style
        
        # Map style to content version
        content_map = {
            'formal': self.formal_version,
            'friendly': self.friendly_version,
            'casual': self.casual_version,
            'professional': self.professional_version,
            'enthusiastic': self.enthusiastic_version,
            'consultative': self.consultative_version,
        }
        
        content = content_map.get(style, self.friendly_version)
        
        # Apply conditional modifications
        if profile.prefers_price_focus and self.price_sensitive_version:
            content = self.price_sensitive_version
        elif profile.prefers_feature_focus and self.feature_focused_version:
            content = self.feature_focused_version
        elif profile.prefers_detailed_info and self.detailed_info_version:
            content = self.detailed_info_version
        elif profile.decision_making_speed == 'fast' and self.quick_decision_version:
            content = self.quick_decision_version
        
        return content or self.friendly_version  # Fallback


class PredictiveInsight(models.Model):
    """AI-generated predictive insights about customers"""
    
    INSIGHT_TYPES = [
        ('next_purchase', 'Next Purchase Prediction'),
        ('churn_risk', 'Churn Risk Assessment'),
        ('upsell_opportunity', 'Upsell Opportunity'),
        ('cross_sell_opportunity', 'Cross-sell Opportunity'),
        ('optimal_timing', 'Optimal Contact Timing'),
        ('price_sensitivity', 'Price Sensitivity Analysis'),
        ('product_affinity', 'Product Affinity Prediction'),
        ('lifetime_value', 'Lifetime Value Prediction'),
    ]
    
    contact = models.ForeignKey('Contact', on_delete=models.CASCADE, related_name='predictive_insights')
    insight_type = models.CharField(max_length=30, choices=INSIGHT_TYPES)
    
    # Prediction details
    prediction = models.TextField(help_text="Human-readable prediction")
    confidence_score = models.FloatField(help_text="Confidence in prediction (0-1)")
    predicted_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    predicted_date = models.DateTimeField(null=True, blank=True)
    
    # Supporting data
    factors = models.JSONField(default=list, help_text="Factors that led to this prediction")
    data_sources = models.JSONField(default=list, help_text="Data sources used")
    model_version = models.CharField(max_length=20, default='1.0')
    
    # Actionable recommendations
    recommended_actions = models.JSONField(default=list)
    suggested_messaging = models.TextField(blank=True)
    optimal_approach = models.TextField(blank=True)
    
    # Validation
    actual_outcome = models.TextField(blank=True, help_text="What actually happened")
    accuracy_score = models.FloatField(null=True, blank=True, help_text="How accurate was the prediction")
    
    # Metadata
    generated_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(help_text="When this insight becomes stale")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-confidence_score', '-generated_at']
        indexes = [
            models.Index(fields=['contact', 'insight_type']),
            models.Index(fields=['predicted_date']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.get_insight_type_display()} for {self.contact}"
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def validate_prediction(self, actual_outcome: str, accuracy: float):
        """Validate the prediction with actual outcome"""
        self.actual_outcome = actual_outcome
        self.accuracy_score = accuracy
        self.save()


class PersonalizationRule(models.Model):
    """Rules for dynamic personalization"""
    
    RULE_TYPES = [
        ('content_selection', 'Content Selection'),
        ('timing_optimization', 'Timing Optimization'),
        ('frequency_control', 'Frequency Control'),
        ('channel_preference', 'Channel Preference'),
        ('product_recommendation', 'Product Recommendation'),
        ('pricing_strategy', 'Pricing Strategy'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    rule_type = models.CharField(max_length=30, choices=RULE_TYPES)
    
    # Rule conditions
    conditions = models.JSONField(default=dict, help_text="Conditions that trigger this rule")
    target_criteria = models.JSONField(default=dict, help_text="Customer criteria for this rule")
    
    # Rule actions
    actions = models.JSONField(default=dict, help_text="Actions to take when rule is triggered")
    personalization_adjustments = models.JSONField(default=dict)
    
    # Priority and execution
    priority = models.IntegerField(default=100, help_text="Higher numbers = higher priority")
    is_active = models.BooleanField(default=True)
    
    # Performance tracking
    times_triggered = models.IntegerField(default=0)
    success_rate = models.FloatField(default=0.0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-priority', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_rule_type_display()})"


class PersonalizationExperiment(models.Model):
    """A/B testing for personalization strategies"""
    
    EXPERIMENT_TYPES = [
        ('content_variation', 'Content Variation'),
        ('timing_test', 'Timing Test'),
        ('frequency_test', 'Frequency Test'),
        ('personalization_level', 'Personalization Level'),
        ('segment_strategy', 'Segment Strategy'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('running', 'Running'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    experiment_type = models.CharField(max_length=30, choices=EXPERIMENT_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Experiment setup
    control_group_criteria = models.JSONField(default=dict)
    test_group_criteria = models.JSONField(default=dict)
    control_strategy = models.JSONField(default=dict)
    test_strategy = models.JSONField(default=dict)
    
    # Targeting
    target_segments = models.ManyToManyField(CustomerSegment, blank=True)
    sample_size = models.IntegerField(help_text="Number of contacts per group")
    
    # Timeline
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    
    # Results
    control_group_performance = models.JSONField(default=dict)
    test_group_performance = models.JSONField(default=dict)
    statistical_significance = models.FloatField(null=True, blank=True)
    winner = models.CharField(max_length=20, blank=True)  # 'control', 'test', or 'inconclusive'
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_experiment_type_display()})"
    
    @property
    def is_active(self):
        now = timezone.now()
        return self.status == 'running' and self.start_date <= now <= self.end_date


# Junction table for contact-segment relationships
class ContactSegmentMembership(models.Model):
    """Many-to-many relationship between contacts and segments with metadata"""
    
    contact = models.ForeignKey('Contact', on_delete=models.CASCADE)
    segment = models.ForeignKey(CustomerSegment, on_delete=models.CASCADE)
    
    # Membership details
    membership_score = models.FloatField(default=1.0, help_text="How well contact fits this segment")
    joined_at = models.DateTimeField(auto_now_add=True)
    last_validated = models.DateTimeField(auto_now=True)
    
    # Automatic vs manual assignment
    is_automatic = models.BooleanField(default=True)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        unique_together = ['contact', 'segment']
        ordering = ['-membership_score']
    
    def __str__(self):
        return f"{self.contact} in {self.segment.name}"

