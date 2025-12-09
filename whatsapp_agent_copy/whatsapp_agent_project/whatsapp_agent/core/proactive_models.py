"""
Proactive Lead Generation Models - AI Prospector functionality
"""
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
import json


class LeadOpportunity(models.Model):
    """Represents a potential sales opportunity identified by AI"""
    
    OPPORTUNITY_TYPES = [
        ('product_interest', 'Product Interest'),
        ('price_inquiry', 'Price Inquiry'),
        ('comparison_shopping', 'Comparison Shopping'),
        ('repeat_customer', 'Repeat Customer'),
        ('referral_potential', 'Referral Potential'),
        ('seasonal_opportunity', 'Seasonal Opportunity'),
        ('abandoned_cart', 'Abandoned Cart'),
        ('engagement_drop', 'Engagement Drop'),
    ]
    
    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    STATUS_CHOICES = [
        ('identified', 'Identified'),
        ('pending_action', 'Pending Action'),
        ('action_taken', 'Action Taken'),
        ('converted', 'Converted'),
        ('dismissed', 'Dismissed'),
        ('expired', 'Expired'),
    ]
    
    contact = models.ForeignKey('Contact', on_delete=models.CASCADE, related_name='lead_opportunities')
    opportunity_type = models.CharField(max_length=30, choices=OPPORTUNITY_TYPES)
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='identified')
    
    # AI analysis data
    confidence_score = models.FloatField(help_text="AI confidence in this opportunity (0-1)")
    trigger_data = models.JSONField(default=dict, help_text="Data that triggered this opportunity")
    analysis_summary = models.TextField(help_text="AI-generated summary of the opportunity")
    
    # Recommended actions
    suggested_action = models.TextField(help_text="AI-suggested action to take")
    suggested_message = models.TextField(blank=True, help_text="AI-suggested message to send")
    optimal_timing = models.DateTimeField(help_text="Best time to take action")
    
    # Products related to this opportunity
    related_products = models.ManyToManyField('Product', blank=True)
    estimated_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Tracking
    identified_at = models.DateTimeField(auto_now_add=True)
    action_taken_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(help_text="When this opportunity expires")
    
    # Results
    conversion_achieved = models.BooleanField(default=False)
    actual_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    feedback_score = models.IntegerField(null=True, blank=True, help_text="1-5 rating of opportunity quality")
    
    class Meta:
        ordering = ['-priority', '-confidence_score', '-identified_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['contact', 'status']),
            models.Index(fields=['optimal_timing']),
        ]
    
    def __str__(self):
        return f"{self.get_opportunity_type_display()} - {self.contact} ({self.priority})"
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def time_until_optimal(self):
        """Returns timedelta until optimal timing"""
        return self.optimal_timing - timezone.now()
    
    def mark_action_taken(self, actual_message=None):
        """Mark that action was taken on this opportunity"""
        self.status = 'action_taken'
        self.action_taken_at = timezone.now()
        if actual_message:
            self.trigger_data['actual_message_sent'] = actual_message
        self.save()


class ProactiveAction(models.Model):
    """Tracks proactive actions taken by the AI"""
    
    ACTION_TYPES = [
        ('follow_up_message', 'Follow-up Message'),
        ('product_recommendation', 'Product Recommendation'),
        ('price_alert', 'Price Alert'),
        ('seasonal_promotion', 'Seasonal Promotion'),
        ('engagement_recovery', 'Engagement Recovery'),
        ('cross_sell', 'Cross-sell'),
        ('upsell', 'Upsell'),
        ('referral_request', 'Referral Request'),
    ]
    
    opportunity = models.ForeignKey(LeadOpportunity, on_delete=models.CASCADE, related_name='actions')
    action_type = models.CharField(max_length=30, choices=ACTION_TYPES)
    
    # Message details
    message_sent = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    
    # Results tracking
    message_delivered = models.BooleanField(default=False)
    message_read = models.BooleanField(default=False)
    response_received = models.BooleanField(default=False)
    response_time = models.DurationField(null=True, blank=True)
    
    # Engagement metrics
    engagement_score = models.FloatField(null=True, blank=True, help_text="0-1 score of engagement quality")
    conversion_achieved = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-sent_at']
    
    def __str__(self):
        return f"{self.get_action_type_display()} - {self.opportunity.contact}"


class CustomerBehaviorPattern(models.Model):
    """Tracks customer behavior patterns for proactive analysis"""
    
    PATTERN_TYPES = [
        ('browsing_pattern', 'Browsing Pattern'),
        ('purchase_timing', 'Purchase Timing'),
        ('price_sensitivity', 'Price Sensitivity'),
        ('communication_preference', 'Communication Preference'),
        ('product_affinity', 'Product Affinity'),
        ('seasonal_behavior', 'Seasonal Behavior'),
        ('engagement_cycle', 'Engagement Cycle'),
    ]
    
    contact = models.ForeignKey('Contact', on_delete=models.CASCADE, related_name='behavior_patterns')
    pattern_type = models.CharField(max_length=30, choices=PATTERN_TYPES)
    
    # Pattern data
    pattern_data = models.JSONField(default=dict)
    confidence_level = models.FloatField(help_text="Confidence in this pattern (0-1)")
    sample_size = models.IntegerField(help_text="Number of data points used")
    
    # Timing information
    first_observed = models.DateTimeField()
    last_updated = models.DateTimeField(auto_now=True)
    next_predicted_action = models.DateTimeField(null=True, blank=True)
    
    # Validation
    prediction_accuracy = models.FloatField(null=True, blank=True, help_text="Accuracy of predictions based on this pattern")
    times_validated = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['contact', 'pattern_type']
        ordering = ['-confidence_level', '-last_updated']
    
    def __str__(self):
        return f"{self.contact} - {self.get_pattern_type_display()}"


class ProspectingRule(models.Model):
    """Configurable rules for proactive lead generation"""
    
    TRIGGER_TYPES = [
        ('time_based', 'Time-based'),
        ('behavior_based', 'Behavior-based'),
        ('event_based', 'Event-based'),
        ('pattern_based', 'Pattern-based'),
        ('external_trigger', 'External Trigger'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    trigger_type = models.CharField(max_length=20, choices=TRIGGER_TYPES)
    
    # Rule configuration
    trigger_conditions = models.JSONField(default=dict, help_text="Conditions that trigger this rule")
    action_template = models.TextField(help_text="Template for the action to take")
    message_template = models.TextField(help_text="Template for the message to send")
    
    # Targeting
    target_customer_segments = models.JSONField(default=list, help_text="Customer segments this rule applies to")
    product_categories = models.ManyToManyField('Product', blank=True)
    
    # Timing and frequency
    min_interval_hours = models.IntegerField(default=24, help_text="Minimum hours between applications")
    max_applications_per_customer = models.IntegerField(default=3, help_text="Max times to apply per customer")
    optimal_hours = models.JSONField(default=list, help_text="Optimal hours of day to apply (0-23)")
    
    # Performance tracking
    times_triggered = models.IntegerField(default=0)
    success_rate = models.FloatField(default=0.0, help_text="Success rate (0-1)")
    avg_response_time = models.DurationField(null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-success_rate', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_trigger_type_display()})"
    
    def can_apply_to_contact(self, contact):
        """Check if this rule can be applied to a specific contact"""
        # Check recent applications
        recent_actions = ProactiveAction.objects.filter(
            opportunity__contact=contact,
            sent_at__gte=timezone.now() - timezone.timedelta(hours=self.min_interval_hours)
        ).count()
        
        if recent_actions > 0:
            return False
        
        # Check max applications
        total_actions = ProactiveAction.objects.filter(
            opportunity__contact=contact
        ).count()
        
        return total_actions < self.max_applications_per_customer


class LeadScore(models.Model):
    """Dynamic lead scoring for contacts"""
    
    contact = models.OneToOneField('Contact', on_delete=models.CASCADE, related_name='lead_score')
    
    # Score components
    engagement_score = models.FloatField(default=0.0, help_text="Based on message frequency and quality")
    interest_score = models.FloatField(default=0.0, help_text="Based on product inquiries and browsing")
    purchase_intent_score = models.FloatField(default=0.0, help_text="Based on buying signals")
    timing_score = models.FloatField(default=0.0, help_text="Based on optimal timing patterns")
    
    # Composite scores
    overall_score = models.FloatField(default=0.0, help_text="Weighted combination of all scores")
    conversion_probability = models.FloatField(default=0.0, help_text="Predicted probability of conversion")
    
    # Metadata
    last_calculated = models.DateTimeField(auto_now=True)
    calculation_version = models.CharField(max_length=10, default='1.0')
    factors_considered = models.JSONField(default=list, help_text="List of factors used in calculation")
    
    # Trends
    score_trend = models.CharField(max_length=20, default='stable', 
                                 choices=[('increasing', 'Increasing'), ('decreasing', 'Decreasing'), ('stable', 'Stable')])
    trend_strength = models.FloatField(default=0.0, help_text="Strength of the trend (0-1)")
    
    class Meta:
        ordering = ['-overall_score']
    
    def __str__(self):
        return f"{self.contact} - Score: {self.overall_score:.2f}"
    
    def update_score(self, engagement=None, interest=None, purchase_intent=None, timing=None):
        """Update individual score components and recalculate overall score"""
        if engagement is not None:
            self.engagement_score = engagement
        if interest is not None:
            self.interest_score = interest
        if purchase_intent is not None:
            self.purchase_intent_score = purchase_intent
        if timing is not None:
            self.timing_score = timing
        
        # Calculate weighted overall score
        weights = {
            'engagement': 0.25,
            'interest': 0.30,
            'purchase_intent': 0.35,
            'timing': 0.10
        }
        
        self.overall_score = (
            self.engagement_score * weights['engagement'] +
            self.interest_score * weights['interest'] +
            self.purchase_intent_score * weights['purchase_intent'] +
            self.timing_score * weights['timing']
        )
        
        # Update conversion probability (simplified model)
        self.conversion_probability = min(1.0, self.overall_score * 1.2)
        
        self.save()


class ProspectingCampaign(models.Model):
    """Organized campaigns for proactive lead generation"""
    
    CAMPAIGN_TYPES = [
        ('seasonal', 'Seasonal Campaign'),
        ('product_launch', 'Product Launch'),
        ('re_engagement', 'Re-engagement'),
        ('cross_sell', 'Cross-sell'),
        ('win_back', 'Win-back'),
        ('referral', 'Referral'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    campaign_type = models.CharField(max_length=20, choices=CAMPAIGN_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Targeting
    target_segments = models.JSONField(default=list, help_text="Customer segments to target")
    min_lead_score = models.FloatField(default=0.0, help_text="Minimum lead score to include")
    max_contacts = models.IntegerField(null=True, blank=True, help_text="Maximum contacts to include")
    
    # Timing
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    optimal_send_hours = models.JSONField(default=list, help_text="Preferred hours to send messages")
    
    # Content
    message_templates = models.JSONField(default=list, help_text="List of message templates")
    products_to_promote = models.ManyToManyField('Product', blank=True)
    
    # Performance tracking
    contacts_targeted = models.IntegerField(default=0)
    messages_sent = models.IntegerField(default=0)
    responses_received = models.IntegerField(default=0)
    conversions_achieved = models.IntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_campaign_type_display()})"
    
    @property
    def response_rate(self):
        """Calculate response rate percentage"""
        if self.messages_sent == 0:
            return 0
        return (self.responses_received / self.messages_sent) * 100
    
    @property
    def conversion_rate(self):
        """Calculate conversion rate percentage"""
        if self.contacts_targeted == 0:
            return 0
        return (self.conversions_achieved / self.contacts_targeted) * 100
    
    @property
    def roi(self):
        """Calculate return on investment"""
        # This would need to factor in campaign costs
        return float(self.total_revenue)  # Simplified for now

