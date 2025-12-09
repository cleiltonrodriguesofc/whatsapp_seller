"""
WhatsApp Command System Models - AI configuration and control via WhatsApp messages
"""
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
import json
from datetime import timedelta


class CommandPattern(models.Model):
    """Patterns for detecting commands in WhatsApp messages"""
    
    COMMAND_TYPES = [
        ('ai_config', 'AI Configuration'),
        ('group_action', 'Group Action'),
        ('status_action', 'Status Action'),
        ('contact_action', 'Contact Action'),
        ('analytics', 'Analytics Request'),
        ('content_creation', 'Content Creation'),
        ('scheduling', 'Scheduling'),
        ('persona_change', 'Persona Change'),
        ('system_control', 'System Control'),
    ]
    
    name = models.CharField(max_length=100)
    command_type = models.CharField(max_length=20, choices=COMMAND_TYPES)
    
    # Pattern matching
    keywords = models.JSONField(default=list, help_text="Keywords that indicate this command")
    patterns = models.JSONField(default=list, help_text="Regex patterns for command detection")
    context_indicators = models.JSONField(default=list, help_text="Context clues for command identification")
    
    # Command structure
    required_parameters = models.JSONField(default=list, help_text="Required parameters for this command")
    optional_parameters = models.JSONField(default=list, help_text="Optional parameters")
    parameter_extraction_rules = models.JSONField(default=dict, help_text="Rules for extracting parameters")
    
    # Confidence scoring
    confidence_threshold = models.FloatField(default=0.7, help_text="Minimum confidence to trigger")
    priority = models.IntegerField(default=100, help_text="Priority when multiple patterns match")
    
    # Safety and validation
    requires_confirmation = models.BooleanField(default=True)
    requires_preview = models.BooleanField(default=True)
    risk_level = models.CharField(max_length=10, choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High')
    ], default='medium')
    
    # Performance tracking
    usage_count = models.IntegerField(default=0)
    success_rate = models.FloatField(default=0.0)
    false_positive_rate = models.FloatField(default=0.0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-priority', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_command_type_display()})"


class WhatsAppCommand(models.Model):
    """Detected and processed WhatsApp commands"""
    
    STATUS_CHOICES = [
        ('detected', 'Detected'),
        ('confirmed', 'Confirmed'),
        ('preview_sent', 'Preview Sent'),
        ('executing', 'Executing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Source information
    contact = models.ForeignKey('Contact', on_delete=models.CASCADE, related_name='whatsapp_commands')
    original_message = models.TextField(help_text="Original WhatsApp message")
    message_timestamp = models.DateTimeField()
    
    # Command detection
    detected_pattern = models.ForeignKey(CommandPattern, on_delete=models.SET_NULL, null=True, blank=True)
    command_type = models.CharField(max_length=20, choices=CommandPattern.COMMAND_TYPES)
    confidence_score = models.FloatField(help_text="Confidence in command detection")
    
    # Command details
    command_intent = models.TextField(help_text="Interpreted command intent")
    extracted_parameters = models.JSONField(default=dict, help_text="Extracted command parameters")
    target_entity = models.CharField(max_length=200, blank=True, help_text="Target (group, contact, etc.)")
    
    # Content and preview
    generated_content = models.TextField(blank=True, help_text="AI-generated content for the command")
    preview_message = models.TextField(blank=True, help_text="Preview sent to user")
    user_modifications = models.TextField(blank=True, help_text="User modifications to generated content")
    final_content = models.TextField(blank=True, help_text="Final content after user edits")
    
    # Execution
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='detected')
    execution_scheduled_at = models.DateTimeField(null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    execution_result = models.JSONField(default=dict, help_text="Result of command execution")
    
    # Safety and compliance
    risk_assessment = models.JSONField(default=dict, help_text="Risk assessment for this command")
    safety_checks_passed = models.BooleanField(default=False)
    requires_manual_approval = models.BooleanField(default=False)
    
    # User interaction
    confirmation_sent_at = models.DateTimeField(null=True, blank=True)
    user_confirmed_at = models.DateTimeField(null=True, blank=True)
    user_response = models.TextField(blank=True, help_text="User's response to confirmation")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['contact', 'status']),
            models.Index(fields=['command_type', 'status']),
            models.Index(fields=['execution_scheduled_at']),
        ]
    
    def __str__(self):
        return f"{self.get_command_type_display()} from {self.contact} - {self.status}"
    
    @property
    def is_pending_confirmation(self):
        return self.status in ['detected', 'preview_sent']
    
    @property
    def is_ready_for_execution(self):
        return self.status == 'confirmed' and self.safety_checks_passed
    
    def mark_as_confirmed(self, user_response: str = ""):
        """Mark command as confirmed by user"""
        self.status = 'confirmed'
        self.user_confirmed_at = timezone.now()
        self.user_response = user_response
        self.save()
    
    def schedule_execution(self, delay_seconds: int = 0):
        """Schedule command for execution"""
        self.execution_scheduled_at = timezone.now() + timedelta(seconds=delay_seconds)
        self.save()


class AIConfigurationChange(models.Model):
    """Track AI configuration changes made via WhatsApp"""
    
    CHANGE_TYPES = [
        ('persona_update', 'Persona Update'),
        ('style_change', 'Communication Style Change'),
        ('behavior_modification', 'Behavior Modification'),
        ('response_pattern', 'Response Pattern Change'),
        ('automation_setting', 'Automation Setting'),
        ('safety_setting', 'Safety Setting'),
        ('integration_config', 'Integration Configuration'),
    ]
    
    command = models.ForeignKey(WhatsAppCommand, on_delete=models.CASCADE, related_name='config_changes')
    change_type = models.CharField(max_length=30, choices=CHANGE_TYPES)
    
    # Change details
    setting_name = models.CharField(max_length=100)
    old_value = models.JSONField(null=True, blank=True, help_text="Previous value")
    new_value = models.JSONField(help_text="New value")
    change_description = models.TextField()
    
    # Scope
    applies_to_contact = models.ForeignKey('Contact', on_delete=models.CASCADE, null=True, blank=True)
    applies_globally = models.BooleanField(default=False)
    
    # Validation and rollback
    is_validated = models.BooleanField(default=False)
    validation_errors = models.JSONField(default=list)
    can_rollback = models.BooleanField(default=True)
    rollback_data = models.JSONField(default=dict)
    
    # Metadata
    applied_at = models.DateTimeField(auto_now_add=True)
    applied_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-applied_at']
    
    def __str__(self):
        return f"{self.get_change_type_display()}: {self.setting_name}"
    
    def rollback(self):
        """Rollback this configuration change"""
        if not self.can_rollback:
            raise ValueError("This change cannot be rolled back")
        
        # Implementation would depend on the specific setting
        # This is a placeholder for the rollback logic
        pass


class CommandExecution(models.Model):
    """Track execution of WhatsApp commands"""
    
    EXECUTION_TYPES = [
        ('group_post', 'Group Post'),
        ('status_update', 'Status Update'),
        ('direct_message', 'Direct Message'),
        ('ai_config', 'AI Configuration'),
        ('analytics_report', 'Analytics Report'),
        ('content_generation', 'Content Generation'),
        ('system_action', 'System Action'),
    ]
    
    command = models.OneToOneField(WhatsAppCommand, on_delete=models.CASCADE, related_name='execution')
    execution_type = models.CharField(max_length=20, choices=EXECUTION_TYPES)
    
    # Execution details
    target_identifier = models.CharField(max_length=200, help_text="Group ID, contact ID, etc.")
    content_sent = models.TextField(help_text="Actual content that was sent")
    media_files = models.JSONField(default=list, help_text="List of media files sent")
    
    # Timing and safety
    executed_at = models.DateTimeField()
    execution_duration = models.DurationField(null=True, blank=True)
    safety_delay_applied = models.DurationField(null=True, blank=True)
    
    # Results
    success = models.BooleanField(default=False)
    response_received = models.TextField(blank=True, help_text="Response from WhatsApp API")
    error_message = models.TextField(blank=True)
    
    # Impact tracking
    message_delivered = models.BooleanField(default=False)
    message_read = models.BooleanField(default=False)
    responses_generated = models.IntegerField(default=0, help_text="Number of responses this generated")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-executed_at']
    
    def __str__(self):
        return f"{self.get_execution_type_display()} - {'Success' if self.success else 'Failed'}"


class CommandTemplate(models.Model):
    """Templates for common WhatsApp commands"""
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    command_type = models.CharField(max_length=20, choices=CommandPattern.COMMAND_TYPES)
    
    # Template structure
    template_text = models.TextField(help_text="Template with placeholders")
    required_placeholders = models.JSONField(default=list)
    optional_placeholders = models.JSONField(default=list)
    
    # Generation rules
    content_generation_rules = models.JSONField(default=dict)
    personalization_rules = models.JSONField(default=dict)
    safety_rules = models.JSONField(default=dict)
    
    # Usage and performance
    usage_count = models.IntegerField(default=0)
    success_rate = models.FloatField(default=0.0)
    user_satisfaction_score = models.FloatField(default=0.0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-usage_count', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_command_type_display()})"
    
    def generate_content(self, parameters: dict) -> str:
        """Generate content using this template and provided parameters"""
        content = self.template_text
        
        # Replace placeholders
        for placeholder, value in parameters.items():
            content = content.replace(f"{{{placeholder}}}", str(value))
        
        return content


class SafetyRule(models.Model):
    """Safety rules for WhatsApp command execution"""
    
    RULE_TYPES = [
        ('frequency_limit', 'Frequency Limit'),
        ('content_filter', 'Content Filter'),
        ('timing_restriction', 'Timing Restriction'),
        ('target_validation', 'Target Validation'),
        ('risk_assessment', 'Risk Assessment'),
        ('approval_required', 'Approval Required'),
    ]
    
    name = models.CharField(max_length=100)
    rule_type = models.CharField(max_length=20, choices=RULE_TYPES)
    description = models.TextField()
    
    # Rule configuration
    rule_parameters = models.JSONField(default=dict)
    applies_to_commands = models.JSONField(default=list, help_text="Command types this rule applies to")
    
    # Enforcement
    is_blocking = models.BooleanField(default=True, help_text="Whether this rule blocks execution")
    warning_message = models.TextField(blank=True)
    
    # Performance
    times_triggered = models.IntegerField(default=0)
    times_blocked = models.IntegerField(default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=100)
    
    class Meta:
        ordering = ['-priority', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_rule_type_display()})"
    
    def evaluate(self, command: WhatsAppCommand) -> dict:
        """Evaluate this rule against a command"""
        result = {
            'passed': True,
            'warning': '',
            'blocking': False,
            'details': {}
        }
        
        # Implementation would depend on rule type
        # This is a placeholder for rule evaluation logic
        
        if not result['passed']:
            self.times_triggered += 1
            if self.is_blocking:
                self.times_blocked += 1
                result['blocking'] = True
            self.save()
        
        return result


class CommandAnalytics(models.Model):
    """Analytics for WhatsApp command usage"""
    
    date = models.DateField()
    
    # Command statistics
    total_commands_detected = models.IntegerField(default=0)
    total_commands_executed = models.IntegerField(default=0)
    total_commands_failed = models.IntegerField(default=0)
    total_commands_cancelled = models.IntegerField(default=0)
    
    # Command type breakdown
    command_type_stats = models.JSONField(default=dict)
    
    # Performance metrics
    avg_detection_confidence = models.FloatField(default=0.0)
    avg_execution_time = models.DurationField(null=True, blank=True)
    success_rate = models.FloatField(default=0.0)
    
    # User interaction
    avg_confirmation_time = models.DurationField(null=True, blank=True)
    user_modification_rate = models.FloatField(default=0.0)
    
    # Safety metrics
    safety_violations = models.IntegerField(default=0)
    blocked_commands = models.IntegerField(default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['date']
        ordering = ['-date']
    
    def __str__(self):
        return f"Command Analytics for {self.date}"


class UserPreference(models.Model):
    """User preferences for WhatsApp command system"""
    
    contact = models.OneToOneField('Contact', on_delete=models.CASCADE, related_name='command_preferences')
    
    # Command detection preferences
    auto_detect_commands = models.BooleanField(default=True)
    require_keyword_prefix = models.BooleanField(default=False)
    keyword_prefix = models.CharField(max_length=20, default='#IA')
    confidence_threshold = models.FloatField(default=0.7)
    
    # Confirmation preferences
    always_require_confirmation = models.BooleanField(default=True)
    auto_confirm_low_risk = models.BooleanField(default=False)
    preview_timeout_minutes = models.IntegerField(default=5)
    
    # Execution preferences
    preferred_execution_delay = models.IntegerField(default=30, help_text="Seconds")
    max_daily_commands = models.IntegerField(default=50)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    
    # Notification preferences
    notify_on_detection = models.BooleanField(default=True)
    notify_on_execution = models.BooleanField(default=True)
    notify_on_errors = models.BooleanField(default=True)
    
    # Safety preferences
    enable_safety_checks = models.BooleanField(default=True)
    paranoid_mode = models.BooleanField(default=False, help_text="Extra safety checks")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['contact__name']
    
    def __str__(self):
        return f"Preferences for {self.contact}"

