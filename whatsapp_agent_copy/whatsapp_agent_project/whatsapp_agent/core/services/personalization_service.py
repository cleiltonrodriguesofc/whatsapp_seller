"""
Hyper-Personalization Service - Advanced customer personalization and micro-segmentation
"""
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from django.utils import timezone
from django.db.models import Q, Avg, Count, F
from textblob import TextBlob
import re

from ..models import Contact, Conversation, Message, Product
from ..personalization_models import (
    CustomerSegment, PersonalizationProfile, MicroSegment,
    PersonalizedContent, PredictiveInsight, PersonalizationRule,
    PersonalizationExperiment, ContactSegmentMembership
)


class CustomerAnalyzer:
    """Analyzes customer behavior for personalization"""
    
    def __init__(self):
        self.personality_indicators = {
            'analytical': ['dados', 'estatística', 'comparar', 'análise', 'detalhes', 'especificações'],
            'driver': ['rápido', 'agora', 'resultado', 'eficiente', 'direto', 'objetivo'],
            'expressive': ['emocionante', 'incrível', 'adorei', 'fantástico', 'impressionante'],
            'amiable': ['obrigado', 'por favor', 'desculpa', 'ajuda', 'gentil', 'amigável']
        }
        
        self.communication_style_indicators = {
            'formal': ['senhor', 'senhora', 'vossa', 'cordialmente', 'atenciosamente'],
            'casual': ['oi', 'tchau', 'beleza', 'massa', 'legal', 'show'],
            'professional': ['empresa', 'negócio', 'profissional', 'corporativo', 'comercial'],
            'enthusiastic': ['!', 'ótimo', 'excelente', 'perfeito', 'maravilhoso']
        }
    
    def analyze_customer_profile(self, contact: Contact) -> Dict:
        """Comprehensive customer analysis for personalization"""
        analysis = {
            'communication_style': self._analyze_communication_style(contact),
            'personality_type': self._analyze_personality_type(contact),
            'content_preferences': self._analyze_content_preferences(contact),
            'behavioral_patterns': self._analyze_behavioral_patterns(contact),
            'product_affinities': self._analyze_product_affinities(contact),
            'timing_preferences': self._analyze_timing_preferences(contact),
            'engagement_patterns': self._analyze_engagement_patterns(contact),
            'predictive_attributes': self._generate_predictive_attributes(contact)
        }
        
        return analysis
    
    def _analyze_communication_style(self, contact: Contact) -> Dict:
        """Analyze preferred communication style"""
        messages = Message.objects.filter(
            conversation__contact=contact,
            message_type='received'
        )
        
        style_scores = {style: 0 for style in self.communication_style_indicators.keys()}
        total_messages = messages.count()
        
        if total_messages == 0:
            return {'style': 'friendly', 'confidence': 0.0, 'indicators': {}}
        
        for message in messages:
            content_lower = message.content.lower()
            
            for style, indicators in self.communication_style_indicators.items():
                for indicator in indicators:
                    if indicator in content_lower:
                        style_scores[style] += 1
        
        # Normalize scores
        for style in style_scores:
            style_scores[style] = style_scores[style] / total_messages
        
        # Determine primary style
        primary_style = max(style_scores.keys(), key=lambda k: style_scores[k])
        confidence = style_scores[primary_style]
        
        # If no clear style, default to friendly
        if confidence < 0.1:
            primary_style = 'friendly'
            confidence = 0.5
        
        return {
            'style': primary_style,
            'confidence': confidence,
            'scores': style_scores,
            'total_messages_analyzed': total_messages
        }
    
    def _analyze_personality_type(self, contact: Contact) -> Dict:
        """Analyze personality type based on communication patterns"""
        messages = Message.objects.filter(
            conversation__contact=contact,
            message_type='received'
        )
        
        personality_scores = {ptype: 0 for ptype in self.personality_indicators.keys()}
        total_messages = messages.count()
        
        if total_messages == 0:
            return {'type': None, 'confidence': 0.0, 'scores': personality_scores}
        
        for message in messages:
            content_lower = message.content.lower()
            
            # Analyze message characteristics
            message_length = len(message.content)
            question_count = content_lower.count('?')
            exclamation_count = content_lower.count('!')
            
            # Score based on indicators
            for ptype, indicators in self.personality_indicators.items():
                for indicator in indicators:
                    if indicator in content_lower:
                        personality_scores[ptype] += 1
            
            # Additional scoring based on message characteristics
            if message_length > 100:  # Long messages
                personality_scores['analytical'] += 0.5
            if question_count > 2:  # Many questions
                personality_scores['analytical'] += 0.3
            if exclamation_count > 1:  # Enthusiastic
                personality_scores['expressive'] += 0.3
            if message_length < 20:  # Short, direct messages
                personality_scores['driver'] += 0.2
        
        # Normalize scores
        for ptype in personality_scores:
            personality_scores[ptype] = personality_scores[ptype] / total_messages
        
        # Determine primary type
        primary_type = max(personality_scores.keys(), key=lambda k: personality_scores[k])
        confidence = personality_scores[primary_type]
        
        # Require minimum confidence
        if confidence < 0.2:
            primary_type = None
            confidence = 0.0
        
        return {
            'type': primary_type,
            'confidence': confidence,
            'scores': personality_scores
        }
    
    def _analyze_content_preferences(self, contact: Contact) -> Dict:
        """Analyze content and information preferences"""
        messages = Message.objects.filter(
            conversation__contact=contact,
            message_type='received'
        )
        
        preferences = {
            'prefers_detailed_info': False,
            'prefers_visual_content': False,
            'prefers_price_focus': False,
            'prefers_feature_focus': False,
            'confidence': 0.0
        }
        
        if not messages.exists():
            return preferences
        
        detail_indicators = ['detalhe', 'especificação', 'informação', 'explicar', 'como funciona']
        visual_indicators = ['foto', 'imagem', 'vídeo', 'mostrar', 'ver']
        price_indicators = ['preço', 'valor', 'custo', 'quanto', 'barato', 'caro', 'desconto']
        feature_indicators = ['funcionalidade', 'característica', 'recurso', 'capacidade', 'função']
        
        total_messages = messages.count()
        detail_count = 0
        visual_count = 0
        price_count = 0
        feature_count = 0
        
        for message in messages:
            content_lower = message.content.lower()
            
            if any(indicator in content_lower for indicator in detail_indicators):
                detail_count += 1
            if any(indicator in content_lower for indicator in visual_indicators):
                visual_count += 1
            if any(indicator in content_lower for indicator in price_indicators):
                price_count += 1
            if any(indicator in content_lower for indicator in feature_indicators):
                feature_count += 1
        
        # Calculate preferences
        preferences['prefers_detailed_info'] = (detail_count / total_messages) > 0.3
        preferences['prefers_visual_content'] = (visual_count / total_messages) > 0.2
        preferences['prefers_price_focus'] = (price_count / total_messages) > 0.4
        preferences['prefers_feature_focus'] = (feature_count / total_messages) > 0.3
        
        # Calculate overall confidence
        total_indicators = detail_count + visual_count + price_count + feature_count
        preferences['confidence'] = min(1.0, total_indicators / (total_messages * 0.5))
        
        return preferences
    
    def _analyze_behavioral_patterns(self, contact: Contact) -> Dict:
        """Analyze behavioral patterns and decision-making style"""
        messages = Message.objects.filter(
            conversation__contact=contact,
            message_type='received'
        ).order_by('timestamp')
        
        patterns = {
            'decision_making_speed': 'medium',
            'response_pattern': 'normal',
            'engagement_consistency': 'stable',
            'information_seeking_behavior': 'moderate'
        }
        
        if not messages.exists():
            return patterns
        
        # Analyze response times
        response_times = []
        conversations = Conversation.objects.filter(contact=contact)
        
        for conversation in conversations:
            conv_messages = Message.objects.filter(conversation=conversation).order_by('timestamp')
            
            for i in range(len(conv_messages) - 1):
                current_msg = conv_messages[i]
                next_msg = conv_messages[i + 1]
                
                if (current_msg.message_type == 'sent' and 
                    next_msg.message_type == 'received'):
                    response_time = (next_msg.timestamp - current_msg.timestamp).total_seconds()
                    response_times.append(response_time)
        
        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            
            if avg_response_time < 300:  # 5 minutes
                patterns['decision_making_speed'] = 'fast'
                patterns['response_pattern'] = 'immediate'
            elif avg_response_time < 3600:  # 1 hour
                patterns['decision_making_speed'] = 'medium'
                patterns['response_pattern'] = 'quick'
            else:
                patterns['decision_making_speed'] = 'slow'
                patterns['response_pattern'] = 'delayed'
        
        # Analyze question patterns
        question_count = 0
        total_messages = messages.count()
        
        for message in messages:
            question_count += message.content.count('?')
        
        if total_messages > 0:
            questions_per_message = question_count / total_messages
            
            if questions_per_message > 1.5:
                patterns['information_seeking_behavior'] = 'high'
            elif questions_per_message > 0.5:
                patterns['information_seeking_behavior'] = 'moderate'
            else:
                patterns['information_seeking_behavior'] = 'low'
        
        return patterns
    
    def _analyze_product_affinities(self, contact: Contact) -> Dict:
        """Analyze product category affinities and preferences"""
        messages = Message.objects.filter(
            conversation__contact=contact,
            message_type='received'
        )
        
        affinities = {
            'favorite_categories': [],
            'avoided_categories': [],
            'price_sensitivity_by_category': {},
            'feature_priorities': []
        }
        
        if not messages.exists():
            return affinities
        
        # Get all products for analysis
        products = Product.objects.all()
        category_mentions = {}
        category_contexts = {}
        
        for message in messages:
            content_lower = message.content.lower()
            
            # Check for product mentions
            for product in products:
                if product.name.lower() in content_lower:
                    category = product.category
                    if category not in category_mentions:
                        category_mentions[category] = 0
                        category_contexts[category] = []
                    
                    category_mentions[category] += 1
                    category_contexts[category].append(content_lower)
        
        # Analyze sentiment for each category
        for category, contexts in category_contexts.items():
            positive_indicators = ['gosto', 'amo', 'ótimo', 'excelente', 'perfeito', 'quero']
            negative_indicators = ['não gosto', 'ruim', 'péssimo', 'caro demais', 'não quero']
            
            positive_count = 0
            negative_count = 0
            
            for context in contexts:
                if any(indicator in context for indicator in positive_indicators):
                    positive_count += 1
                if any(indicator in context for indicator in negative_indicators):
                    negative_count += 1
            
            # Classify category preference
            if positive_count > negative_count and positive_count > 0:
                affinities['favorite_categories'].append(category)
            elif negative_count > positive_count and negative_count > 0:
                affinities['avoided_categories'].append(category)
        
        # Sort by mention frequency
        sorted_categories = sorted(category_mentions.items(), key=lambda x: x[1], reverse=True)
        affinities['favorite_categories'] = [cat for cat, _ in sorted_categories[:3]]
        
        return affinities
    
    def _analyze_timing_preferences(self, contact: Contact) -> Dict:
        """Analyze optimal timing for contact"""
        messages = Message.objects.filter(
            conversation__contact=contact,
            message_type='received'
        )
        
        timing_prefs = {
            'optimal_hours': [],
            'optimal_days': [],
            'response_quality_by_hour': {},
            'engagement_patterns': {}
        }
        
        if not messages.exists():
            return timing_prefs
        
        # Analyze by hour
        hour_stats = {}
        day_stats = {}
        
        for message in messages:
            hour = message.timestamp.hour
            day = message.timestamp.strftime('%A')
            
            # Hour analysis
            if hour not in hour_stats:
                hour_stats[hour] = {'count': 0, 'total_length': 0, 'avg_length': 0}
            
            hour_stats[hour]['count'] += 1
            hour_stats[hour]['total_length'] += len(message.content)
            hour_stats[hour]['avg_length'] = hour_stats[hour]['total_length'] / hour_stats[hour]['count']
            
            # Day analysis
            if day not in day_stats:
                day_stats[day] = 0
            day_stats[day] += 1
        
        # Find optimal hours (top 3 by message quality/length)
        sorted_hours = sorted(hour_stats.items(), 
                            key=lambda x: x[1]['avg_length'] * x[1]['count'], 
                            reverse=True)
        timing_prefs['optimal_hours'] = [hour for hour, _ in sorted_hours[:3]]
        
        # Find optimal days (top 3 by frequency)
        sorted_days = sorted(day_stats.items(), key=lambda x: x[1], reverse=True)
        timing_prefs['optimal_days'] = [day for day, _ in sorted_days[:3]]
        
        timing_prefs['response_quality_by_hour'] = {
            str(hour): stats['avg_length'] for hour, stats in hour_stats.items()
        }
        
        return timing_prefs
    
    def _analyze_engagement_patterns(self, contact: Contact) -> Dict:
        """Analyze engagement patterns and preferences"""
        messages = Message.objects.filter(
            conversation__contact=contact,
            message_type='received'
        )
        
        engagement = {
            'avg_message_length': 0,
            'emoji_usage': 'moderate',
            'question_frequency': 0,
            'engagement_trend': 'stable',
            'preferred_conversation_length': 'medium'
        }
        
        if not messages.exists():
            return engagement
        
        # Calculate average message length
        total_length = sum(len(msg.content) for msg in messages)
        engagement['avg_message_length'] = total_length / messages.count()
        
        # Analyze emoji usage
        emoji_pattern = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]')
        emoji_count = 0
        
        for message in messages:
            emoji_count += len(emoji_pattern.findall(message.content))
        
        emoji_per_message = emoji_count / messages.count()
        
        if emoji_per_message > 2:
            engagement['emoji_usage'] = 'frequent'
        elif emoji_per_message > 0.5:
            engagement['emoji_usage'] = 'moderate'
        elif emoji_per_message > 0:
            engagement['emoji_usage'] = 'minimal'
        else:
            engagement['emoji_usage'] = 'none'
        
        # Analyze question frequency
        total_questions = sum(msg.content.count('?') for msg in messages)
        engagement['question_frequency'] = total_questions / messages.count()
        
        # Determine preferred conversation length
        if engagement['avg_message_length'] > 100:
            engagement['preferred_conversation_length'] = 'long'
        elif engagement['avg_message_length'] > 30:
            engagement['preferred_conversation_length'] = 'medium'
        else:
            engagement['preferred_conversation_length'] = 'short'
        
        return engagement
    
    def _generate_predictive_attributes(self, contact: Contact) -> Dict:
        """Generate predictive attributes for the customer"""
        # This would typically use machine learning models
        # For now, we'll use rule-based predictions
        
        messages = Message.objects.filter(conversation__contact=contact)
        total_messages = messages.count()
        
        predictions = {
            'predicted_lifetime_value': 0.0,
            'churn_risk_score': 0.0,
            'next_purchase_probability': 0.0,
            'optimal_approach': 'standard'
        }
        
        if total_messages == 0:
            predictions['churn_risk_score'] = 0.8  # High risk if no engagement
            return predictions
        
        # Simple CLV prediction based on engagement
        recent_messages = messages.filter(
            timestamp__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        engagement_score = min(1.0, recent_messages / 10)  # Normalize to 10 messages/month
        predictions['predicted_lifetime_value'] = engagement_score * 1000  # Simple calculation
        
        # Churn risk based on recent activity
        days_since_last = (timezone.now() - messages.last().timestamp).days if messages.exists() else 365
        
        if days_since_last > 60:
            predictions['churn_risk_score'] = 0.8
        elif days_since_last > 30:
            predictions['churn_risk_score'] = 0.5
        else:
            predictions['churn_risk_score'] = 0.2
        
        # Purchase probability based on engagement and recency
        predictions['next_purchase_probability'] = max(0, engagement_score - (days_since_last / 100))
        
        # Determine optimal approach
        if predictions['churn_risk_score'] > 0.6:
            predictions['optimal_approach'] = 'retention_focused'
        elif predictions['next_purchase_probability'] > 0.7:
            predictions['optimal_approach'] = 'sales_focused'
        elif engagement_score > 0.8:
            predictions['optimal_approach'] = 'relationship_building'
        else:
            predictions['optimal_approach'] = 'standard'
        
        return predictions


class SegmentationEngine:
    """Advanced customer segmentation engine"""
    
    def __init__(self):
        self.analyzer = CustomerAnalyzer()
    
    def create_dynamic_segments(self) -> List[CustomerSegment]:
        """Create dynamic segments based on customer analysis"""
        segments = []
        
        # Analyze all contacts
        contacts = Contact.objects.all()
        
        if not contacts.exists():
            return segments
        
        # Create behavioral segments
        segments.extend(self._create_behavioral_segments(contacts))
        
        # Create engagement segments
        segments.extend(self._create_engagement_segments(contacts))
        
        # Create value-based segments
        segments.extend(self._create_value_segments(contacts))
        
        # Create lifecycle segments
        segments.extend(self._create_lifecycle_segments(contacts))
        
        return segments
    
    def _create_behavioral_segments(self, contacts) -> List[CustomerSegment]:
        """Create segments based on behavior patterns"""
        segments = []
        
        # Analyze communication styles
        style_groups = {}
        
        for contact in contacts:
            analysis = self.analyzer.analyze_customer_profile(contact)
            style = analysis['communication_style']['style']
            
            if style not in style_groups:
                style_groups[style] = []
            style_groups[style].append(contact)
        
        # Create segments for each style group
        for style, group_contacts in style_groups.items():
            if len(group_contacts) >= 3:  # Minimum segment size
                segment, created = CustomerSegment.objects.get_or_create(
                    name=f"{style.title()} Communicators",
                    segment_type='behavioral',
                    defaults={
                        'description': f"Customers who prefer {style} communication style",
                        'preferred_communication_style': style,
                        'size': len(group_contacts)
                    }
                )
                
                if created:
                    segments.append(segment)
                
                # Add contacts to segment
                for contact in group_contacts:
                    ContactSegmentMembership.objects.get_or_create(
                        contact=contact,
                        segment=segment,
                        defaults={'membership_score': 1.0}
                    )
        
        return segments
    
    def _create_engagement_segments(self, contacts) -> List[CustomerSegment]:
        """Create segments based on engagement levels"""
        segments = []
        
        # Calculate engagement scores for all contacts
        engagement_data = []
        
        for contact in contacts:
            recent_messages = Message.objects.filter(
                conversation__contact=contact,
                timestamp__gte=timezone.now() - timedelta(days=30)
            ).count()
            
            engagement_score = min(1.0, recent_messages / 10)
            engagement_data.append((contact, engagement_score))
        
        # Sort by engagement
        engagement_data.sort(key=lambda x: x[1], reverse=True)
        
        # Create segments
        total_contacts = len(engagement_data)
        
        if total_contacts >= 9:  # Need minimum contacts for 3 segments
            # High engagement (top 30%)
            high_end = int(total_contacts * 0.3)
            high_engagement_contacts = [contact for contact, _ in engagement_data[:high_end]]
            
            # Medium engagement (middle 40%)
            medium_start = high_end
            medium_end = int(total_contacts * 0.7)
            medium_engagement_contacts = [contact for contact, _ in engagement_data[medium_start:medium_end]]
            
            # Low engagement (bottom 30%)
            low_engagement_contacts = [contact for contact, _ in engagement_data[medium_end:]]
            
            # Create segments
            segment_configs = [
                ('High Engagement', high_engagement_contacts, 'daily'),
                ('Medium Engagement', medium_engagement_contacts, 'weekly'),
                ('Low Engagement', low_engagement_contacts, 'monthly')
            ]
            
            for name, group_contacts, frequency in segment_configs:
                if group_contacts:
                    segment, created = CustomerSegment.objects.get_or_create(
                        name=name,
                        segment_type='engagement',
                        defaults={
                            'description': f"Customers with {name.lower()} levels",
                            'optimal_message_frequency': frequency,
                            'size': len(group_contacts)
                        }
                    )
                    
                    if created:
                        segments.append(segment)
                    
                    # Add contacts to segment
                    for contact in group_contacts:
                        ContactSegmentMembership.objects.get_or_create(
                            contact=contact,
                            segment=segment,
                            defaults={'membership_score': 1.0}
                        )
        
        return segments
    
    def _create_value_segments(self, contacts) -> List[CustomerSegment]:
        """Create segments based on predicted customer value"""
        segments = []
        
        # This would typically use actual purchase data
        # For now, we'll use engagement as a proxy for value
        
        value_data = []
        
        for contact in contacts:
            analysis = self.analyzer.analyze_customer_profile(contact)
            predicted_value = analysis['predictive_attributes']['predicted_lifetime_value']
            value_data.append((contact, predicted_value))
        
        # Sort by value
        value_data.sort(key=lambda x: x[1], reverse=True)
        
        total_contacts = len(value_data)
        
        if total_contacts >= 6:  # Need minimum contacts
            # High value (top 20%)
            high_end = max(1, int(total_contacts * 0.2))
            high_value_contacts = [contact for contact, _ in value_data[:high_end]]
            
            # Medium value (next 30%)
            medium_start = high_end
            medium_end = int(total_contacts * 0.5)
            medium_value_contacts = [contact for contact, _ in value_data[medium_start:medium_end]]
            
            # Standard value (remaining 50%)
            standard_value_contacts = [contact for contact, _ in value_data[medium_end:]]
            
            segment_configs = [
                ('VIP Customers', high_value_contacts, 'High-touch, premium service'),
                ('Valued Customers', medium_value_contacts, 'Regular engagement, special offers'),
                ('Standard Customers', standard_value_contacts, 'Standard service level')
            ]
            
            for name, group_contacts, description in segment_configs:
                if group_contacts:
                    segment, created = CustomerSegment.objects.get_or_create(
                        name=name,
                        segment_type='value_based',
                        defaults={
                            'description': description,
                            'size': len(group_contacts)
                        }
                    )
                    
                    if created:
                        segments.append(segment)
                    
                    # Add contacts to segment
                    for contact in group_contacts:
                        ContactSegmentMembership.objects.get_or_create(
                            contact=contact,
                            segment=segment,
                            defaults={'membership_score': 1.0}
                        )
        
        return segments
    
    def _create_lifecycle_segments(self, contacts) -> List[CustomerSegment]:
        """Create segments based on customer lifecycle stage"""
        segments = []
        
        lifecycle_groups = {
            'new': [],
            'active': [],
            'at_risk': [],
            'dormant': []
        }
        
        for contact in contacts:
            # Determine lifecycle stage based on activity
            messages = Message.objects.filter(conversation__contact=contact)
            
            if not messages.exists():
                lifecycle_groups['new'].append(contact)
                continue
            
            first_message = messages.first().timestamp
            last_message = messages.last().timestamp
            days_since_first = (timezone.now() - first_message).days
            days_since_last = (timezone.now() - last_message).days
            
            if days_since_first <= 7:
                lifecycle_groups['new'].append(contact)
            elif days_since_last <= 14:
                lifecycle_groups['active'].append(contact)
            elif days_since_last <= 60:
                lifecycle_groups['at_risk'].append(contact)
            else:
                lifecycle_groups['dormant'].append(contact)
        
        # Create segments
        segment_configs = {
            'new': ('New Customers', 'Recently acquired customers (within 7 days)'),
            'active': ('Active Customers', 'Regularly engaged customers'),
            'at_risk': ('At-Risk Customers', 'Customers showing signs of disengagement'),
            'dormant': ('Dormant Customers', 'Inactive customers needing re-engagement')
        }
        
        for stage, group_contacts in lifecycle_groups.items():
            if group_contacts:
                name, description = segment_configs[stage]
                
                segment, created = CustomerSegment.objects.get_or_create(
                    name=name,
                    segment_type='lifecycle',
                    defaults={
                        'description': description,
                        'size': len(group_contacts)
                    }
                )
                
                if created:
                    segments.append(segment)
                
                # Add contacts to segment
                for contact in group_contacts:
                    ContactSegmentMembership.objects.get_or_create(
                        contact=contact,
                        segment=segment,
                        defaults={'membership_score': 1.0}
                    )
        
        return segments


class PersonalizationEngine:
    """Main engine for hyper-personalization"""
    
    def __init__(self):
        self.analyzer = CustomerAnalyzer()
        self.segmentation_engine = SegmentationEngine()
    
    def create_personalization_profile(self, contact: Contact) -> PersonalizationProfile:
        """Create or update personalization profile for a contact"""
        analysis = self.analyzer.analyze_customer_profile(contact)
        
        # Get or create profile
        profile, created = PersonalizationProfile.objects.get_or_create(
            contact=contact,
            defaults={}
        )
        
        # Update profile with analysis results
        comm_style = analysis['communication_style']
        profile.preferred_style = comm_style['style']
        
        personality = analysis['personality_type']
        if personality['type'] and personality['confidence'] > 0.3:
            profile.personality_type = personality['type']
        
        content_prefs = analysis['content_preferences']
        profile.prefers_detailed_info = content_prefs['prefers_detailed_info']
        profile.prefers_visual_content = content_prefs['prefers_visual_content']
        profile.prefers_price_focus = content_prefs['prefers_price_focus']
        profile.prefers_feature_focus = content_prefs['prefers_feature_focus']
        
        behavioral = analysis['behavioral_patterns']
        profile.decision_making_speed = behavioral['decision_making_speed']
        
        timing = analysis['timing_preferences']
        profile.optimal_contact_hours = timing['optimal_hours']
        
        engagement = analysis['engagement_patterns']
        profile.preferred_message_length = engagement['preferred_conversation_length']
        profile.emoji_usage_preference = engagement['emoji_usage']
        
        affinities = analysis['product_affinities']
        profile.favorite_categories = affinities['favorite_categories']
        profile.avoided_categories = affinities['avoided_categories']
        
        predictive = analysis['predictive_attributes']
        profile.predicted_lifetime_value = predictive['predicted_lifetime_value']
        profile.churn_risk_score = predictive['churn_risk_score']
        profile.next_purchase_probability = predictive['next_purchase_probability']
        profile.recommended_approach = predictive['optimal_approach']
        
        # Update metadata
        profile.data_points_count = Message.objects.filter(conversation__contact=contact).count()
        profile.update_confidence_score()
        
        profile.save()
        
        return profile
    
    def get_personalized_message(self, contact: Contact, content_type: str, context: Dict = None) -> str:
        """Generate a personalized message for a contact"""
        # Get or create personalization profile
        try:
            profile = contact.personalization_profile
        except PersonalizationProfile.DoesNotExist:
            profile = self.create_personalization_profile(contact)
        
        # Find appropriate content template
        content_templates = PersonalizedContent.objects.filter(
            content_type=content_type,
            is_active=True
        )
        
        if not content_templates.exists():
            # Fallback to generic message
            return self._generate_generic_message(contact, content_type, context)
        
        # Select best template based on profile
        best_template = self._select_best_template(content_templates, profile)
        
        # Get personalized content
        personalized_content = best_template.get_personalized_content(profile)
        
        # Apply dynamic personalization
        personalized_content = self._apply_dynamic_personalization(
            personalized_content, contact, profile, context
        )
        
        # Update usage statistics
        best_template.usage_count += 1
        best_template.save()
        
        return personalized_content
    
    def _select_best_template(self, templates, profile: PersonalizationProfile) -> PersonalizedContent:
        """Select the best template for a profile"""
        # Score templates based on profile match
        template_scores = []
        
        for template in templates:
            score = 0
            
            # Check personality type match
            if (profile.personality_type and 
                profile.personality_type in template.target_personality_types):
                score += 3
            
            # Check communication style match
            if profile.preferred_style in template.target_communication_styles:
                score += 2
            
            # Check segment membership
            contact_segments = profile.contact.contactsegmentmembership_set.all()
            for membership in contact_segments:
                if membership.segment in template.target_segments.all():
                    score += membership.membership_score
            
            # Prefer templates with higher success rates
            score += template.success_rate * 2
            
            template_scores.append((template, score))
        
        # Return template with highest score
        template_scores.sort(key=lambda x: x[1], reverse=True)
        return template_scores[0][0] if template_scores else templates.first()
    
    def _apply_dynamic_personalization(self, content: str, contact: Contact, 
                                     profile: PersonalizationProfile, context: Dict = None) -> str:
        """Apply dynamic personalization to content"""
        context = context or {}
        
        # Replace placeholders
        name = contact.name or "Cliente"
        content = content.replace("{name}", name)
        content = content.replace("{nome}", name)
        
        # Apply emoji preferences
        if profile.emoji_usage_preference == 'none':
            # Remove emojis
            import re
            emoji_pattern = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]')
            content = emoji_pattern.sub('', content)
        elif profile.emoji_usage_preference == 'frequent':
            # Add more emojis if not present
            if '!' in content and '😊' not in content:
                content = content.replace('!', '! 😊')
        
        # Adjust message length based on preference
        if profile.preferred_message_length == 'short' and len(content) > 100:
            # Truncate to essential information
            sentences = content.split('.')
            content = '. '.join(sentences[:2]) + '.'
        elif profile.preferred_message_length == 'long' and len(content) < 50:
            # Add more detail
            content += " Posso fornecer mais detalhes se você quiser!"
        
        # Apply context-specific personalization
        if context:
            for key, value in context.items():
                placeholder = f"{{{key}}}"
                if placeholder in content:
                    content = content.replace(placeholder, str(value))
        
        return content
    
    def _generate_generic_message(self, contact: Contact, content_type: str, context: Dict = None) -> str:
        """Generate a generic message when no templates are available"""
        name = contact.name or "Cliente"
        
        generic_messages = {
            'greeting': f"Olá {name}! Como posso ajudá-lo hoje?",
            'product_intro': f"Oi {name}! Temos alguns produtos que podem interessar você.",
            'follow_up': f"Olá {name}! Como está? Gostaria de continuar nossa conversa?",
            'offer': f"Oi {name}! Temos uma oferta especial que pode interessar você!",
            'educational': f"Olá {name}! Aqui estão algumas informações úteis para você.",
            'closing': f"Obrigado pelo seu tempo, {name}! Estou aqui se precisar de mais alguma coisa."
        }
        
        return generic_messages.get(content_type, f"Olá {name}!")
    
    def generate_predictive_insights(self, contact: Contact) -> List[PredictiveInsight]:
        """Generate predictive insights for a contact"""
        insights = []
        
        # Get personalization profile
        try:
            profile = contact.personalization_profile
        except PersonalizationProfile.DoesNotExist:
            profile = self.create_personalization_profile(contact)
        
        # Generate different types of insights
        insights.extend(self._predict_next_purchase(contact, profile))
        insights.extend(self._predict_churn_risk(contact, profile))
        insights.extend(self._predict_optimal_timing(contact, profile))
        insights.extend(self._predict_product_affinity(contact, profile))
        
        return insights
    
    def _predict_next_purchase(self, contact: Contact, profile: PersonalizationProfile) -> List[PredictiveInsight]:
        """Predict next purchase timing and value"""
        insights = []
        
        if profile.next_purchase_probability > 0.5:
            # High probability of purchase
            predicted_date = timezone.now() + timedelta(days=7)  # Simple prediction
            
            insight = PredictiveInsight.objects.create(
                contact=contact,
                insight_type='next_purchase',
                prediction=f"Alta probabilidade de compra nos próximos 7 dias",
                confidence_score=profile.next_purchase_probability,
                predicted_date=predicted_date,
                factors=['engagement_level', 'communication_frequency', 'product_interest'],
                recommended_actions=[
                    'Send personalized product recommendations',
                    'Offer limited-time discount',
                    'Provide detailed product information'
                ],
                suggested_messaging=f"Olá {contact.name or 'Cliente'}! Vi que você tem interesse em nossos produtos. Que tal aproveitarmos uma oferta especial?",
                expires_at=timezone.now() + timedelta(days=14)
            )
            
            insights.append(insight)
        
        return insights
    
    def _predict_churn_risk(self, contact: Contact, profile: PersonalizationProfile) -> List[PredictiveInsight]:
        """Predict churn risk and recommend retention actions"""
        insights = []
        
        if profile.churn_risk_score > 0.6:
            insight = PredictiveInsight.objects.create(
                contact=contact,
                insight_type='churn_risk',
                prediction=f"Alto risco de churn (score: {profile.churn_risk_score:.2f})",
                confidence_score=profile.churn_risk_score,
                factors=['low_engagement', 'long_silence', 'declining_activity'],
                recommended_actions=[
                    'Send re-engagement campaign',
                    'Offer special retention discount',
                    'Personal check-in call',
                    'Survey for feedback'
                ],
                suggested_messaging=f"Olá {contact.name or 'Cliente'}! Senti sua falta por aqui. Como posso melhorar sua experiência conosco?",
                expires_at=timezone.now() + timedelta(days=30)
            )
            
            insights.append(insight)
        
        return insights
    
    def _predict_optimal_timing(self, contact: Contact, profile: PersonalizationProfile) -> List[PredictiveInsight]:
        """Predict optimal timing for contact"""
        insights = []
        
        if profile.optimal_contact_hours:
            current_hour = timezone.now().hour
            
            if current_hour in profile.optimal_contact_hours:
                insight = PredictiveInsight.objects.create(
                    contact=contact,
                    insight_type='optimal_timing',
                    prediction=f"Momento ótimo para contato (hora preferida: {current_hour}h)",
                    confidence_score=0.8,
                    factors=['historical_response_patterns', 'engagement_quality'],
                    recommended_actions=[
                        'Send important messages now',
                        'Schedule follow-up for this time',
                        'Initiate sales conversation'
                    ],
                    expires_at=timezone.now() + timedelta(hours=2)
                )
                
                insights.append(insight)
        
        return insights
    
    def _predict_product_affinity(self, contact: Contact, profile: PersonalizationProfile) -> List[PredictiveInsight]:
        """Predict product affinity and cross-sell opportunities"""
        insights = []
        
        if profile.favorite_categories:
            primary_category = profile.favorite_categories[0]
            
            insight = PredictiveInsight.objects.create(
                contact=contact,
                insight_type='product_affinity',
                prediction=f"Alta afinidade com categoria: {primary_category}",
                confidence_score=0.7,
                factors=['purchase_history', 'browsing_behavior', 'inquiry_patterns'],
                recommended_actions=[
                    f'Recommend products in {primary_category}',
                    'Send category-specific offers',
                    'Share educational content about category'
                ],
                suggested_messaging=f"Olá {contact.name or 'Cliente'}! Temos novidades incríveis em {primary_category} que você vai adorar!",
                expires_at=timezone.now() + timedelta(days=7)
            )
            
            insights.append(insight)
        
        return insights
    
    def run_personalization_update(self) -> Dict:
        """Run a complete personalization update for all contacts"""
        start_time = time.time()
        
        # Update all personalization profiles
        contacts = Contact.objects.all()
        updated_profiles = 0
        
        for contact in contacts:
            try:
                self.create_personalization_profile(contact)
                updated_profiles += 1
            except Exception as e:
                print(f"Error updating profile for {contact}: {e}")
        
        # Update segments
        new_segments = self.segmentation_engine.create_dynamic_segments()
        
        # Generate insights for high-value contacts
        insights_generated = 0
        high_value_contacts = Contact.objects.filter(
            personalization_profile__predicted_lifetime_value__gt=500
        )
        
        for contact in high_value_contacts:
            insights = self.generate_predictive_insights(contact)
            insights_generated += len(insights)
        
        # Update segment statistics
        for segment in CustomerSegment.objects.filter(is_active=True):
            segment.update_segment_stats()
        
        summary = {
            'update_duration': time.time() - start_time,
            'profiles_updated': updated_profiles,
            'new_segments_created': len(new_segments),
            'insights_generated': insights_generated,
            'total_segments': CustomerSegment.objects.filter(is_active=True).count(),
            'total_profiles': PersonalizationProfile.objects.count()
        }
        
        return summary


# Global instance
personalization_engine = PersonalizationEngine()

