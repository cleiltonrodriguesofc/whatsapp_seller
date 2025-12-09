"""
Proactive Lead Generation Service - AI Prospector
"""
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from django.utils import timezone
from django.db.models import Q, Avg, Count
from ..models import Contact, Conversation, Message, Product
from ..proactive_models import (
    LeadOpportunity, ProactiveAction, CustomerBehaviorPattern,
    ProspectingRule, LeadScore, ProspectingCampaign
)


class BehaviorAnalyzer:
    """Analyzes customer behavior patterns for proactive opportunities"""
    
    def __init__(self):
        self.pattern_weights = {
            'message_frequency': 0.25,
            'response_time': 0.20,
            'product_inquiries': 0.30,
            'purchase_history': 0.25
        }
    
    def analyze_contact_behavior(self, contact: Contact) -> Dict:
        """Comprehensive behavior analysis for a contact"""
        analysis = {
            'engagement_level': self._calculate_engagement_level(contact),
            'purchase_intent': self._analyze_purchase_intent(contact),
            'communication_patterns': self._analyze_communication_patterns(contact),
            'product_interests': self._analyze_product_interests(contact),
            'timing_patterns': self._analyze_timing_patterns(contact),
            'risk_factors': self._identify_risk_factors(contact)
        }
        
        return analysis
    
    def _calculate_engagement_level(self, contact: Contact) -> Dict:
        """Calculate engagement level based on recent activity"""
        recent_messages = Message.objects.filter(
            conversation__contact=contact,
            timestamp__gte=timezone.now() - timedelta(days=30)
        )
        
        total_messages = recent_messages.count()
        user_messages = recent_messages.filter(message_type='received').count()
        avg_response_time = self._calculate_avg_response_time(contact)
        
        # Calculate engagement score
        if total_messages == 0:
            engagement_score = 0.0
        else:
            frequency_score = min(1.0, total_messages / 50)  # Normalize to 50 messages/month
            interaction_ratio = user_messages / total_messages if total_messages > 0 else 0
            response_score = max(0, 1.0 - (avg_response_time / 3600))  # Penalize slow responses
            
            engagement_score = (frequency_score * 0.4 + interaction_ratio * 0.4 + response_score * 0.2)
        
        return {
            'score': engagement_score,
            'total_messages': total_messages,
            'user_messages': user_messages,
            'avg_response_time_hours': avg_response_time / 3600,
            'trend': self._calculate_engagement_trend(contact)
        }
    
    def _analyze_purchase_intent(self, contact: Contact) -> Dict:
        """Analyze signals indicating purchase intent"""
        recent_messages = Message.objects.filter(
            conversation__contact=contact,
            timestamp__gte=timezone.now() - timedelta(days=14)
        )
        
        intent_signals = {
            'price_inquiries': 0,
            'product_comparisons': 0,
            'availability_checks': 0,
            'purchase_keywords': 0,
            'urgency_indicators': 0
        }
        
        # Keywords that indicate different types of intent
        price_keywords = ['preço', 'valor', 'quanto', 'custa', 'desconto', 'promoção']
        comparison_keywords = ['comparar', 'diferença', 'melhor', 'versus', 'ou']
        availability_keywords = ['disponível', 'estoque', 'quando chega', 'prazo']
        purchase_keywords = ['comprar', 'adquirir', 'quero', 'preciso', 'vou levar']
        urgency_keywords = ['urgente', 'hoje', 'agora', 'rápido', 'imediato']
        
        for message in recent_messages.filter(message_type='received'):
            content_lower = message.content.lower()
            
            if any(keyword in content_lower for keyword in price_keywords):
                intent_signals['price_inquiries'] += 1
            if any(keyword in content_lower for keyword in comparison_keywords):
                intent_signals['product_comparisons'] += 1
            if any(keyword in content_lower for keyword in availability_keywords):
                intent_signals['availability_checks'] += 1
            if any(keyword in content_lower for keyword in purchase_keywords):
                intent_signals['purchase_keywords'] += 1
            if any(keyword in content_lower for keyword in urgency_keywords):
                intent_signals['urgency_indicators'] += 1
        
        # Calculate intent score
        total_signals = sum(intent_signals.values())
        intent_score = min(1.0, total_signals / 10)  # Normalize to max 10 signals
        
        return {
            'score': intent_score,
            'signals': intent_signals,
            'total_signals': total_signals,
            'stage': self._determine_purchase_stage(intent_signals)
        }
    
    def _analyze_communication_patterns(self, contact: Contact) -> Dict:
        """Analyze communication timing and frequency patterns"""
        messages = Message.objects.filter(
            conversation__contact=contact,
            message_type='received'
        ).order_by('timestamp')
        
        if not messages.exists():
            return {'pattern': 'no_data', 'preferred_hours': [], 'frequency': 'unknown'}
        
        # Analyze preferred hours
        hour_counts = {}
        for message in messages:
            hour = message.timestamp.hour
            hour_counts[hour] = hour_counts.get(hour, 0) + 1
        
        preferred_hours = sorted(hour_counts.keys(), key=lambda h: hour_counts[h], reverse=True)[:3]
        
        # Analyze frequency pattern
        if messages.count() < 5:
            frequency = 'low'
        elif messages.count() < 20:
            frequency = 'medium'
        else:
            frequency = 'high'
        
        return {
            'preferred_hours': preferred_hours,
            'frequency': frequency,
            'total_messages': messages.count(),
            'first_contact': messages.first().timestamp,
            'last_contact': messages.last().timestamp
        }
    
    def _analyze_product_interests(self, contact: Contact) -> Dict:
        """Analyze product categories and specific interests"""
        recent_messages = Message.objects.filter(
            conversation__contact=contact,
            message_type='received',
            timestamp__gte=timezone.now() - timedelta(days=60)
        )
        
        product_mentions = {}
        category_interests = {}
        
        # Get all products for keyword matching
        products = Product.objects.all()
        
        for message in recent_messages:
            content_lower = message.content.lower()
            
            # Check for specific product mentions
            for product in products:
                if product.name.lower() in content_lower:
                    product_mentions[product.name] = product_mentions.get(product.name, 0) + 1
                    category = product.category
                    category_interests[category] = category_interests.get(category, 0) + 1
        
        return {
            'product_mentions': product_mentions,
            'category_interests': category_interests,
            'primary_interest': max(category_interests.keys(), key=category_interests.get) if category_interests else None,
            'interest_diversity': len(category_interests)
        }
    
    def _analyze_timing_patterns(self, contact: Contact) -> Dict:
        """Analyze optimal timing for contact"""
        messages = Message.objects.filter(
            conversation__contact=contact,
            message_type='received'
        )
        
        if not messages.exists():
            return {'optimal_hours': [9, 14, 18], 'confidence': 0.0}
        
        # Analyze response patterns by hour
        hour_response_quality = {}
        
        for message in messages:
            hour = message.timestamp.hour
            # Simple quality metric based on message length and keywords
            quality = len(message.content) / 100  # Normalize by length
            
            if hour not in hour_response_quality:
                hour_response_quality[hour] = []
            hour_response_quality[hour].append(quality)
        
        # Calculate average quality per hour
        hour_avg_quality = {
            hour: sum(qualities) / len(qualities)
            for hour, qualities in hour_response_quality.items()
        }
        
        # Get top 3 hours
        optimal_hours = sorted(hour_avg_quality.keys(), 
                             key=lambda h: hour_avg_quality[h], 
                             reverse=True)[:3]
        
        confidence = len(messages) / 50  # Higher confidence with more data
        confidence = min(1.0, confidence)
        
        return {
            'optimal_hours': optimal_hours,
            'confidence': confidence,
            'hour_quality_map': hour_avg_quality
        }
    
    def _identify_risk_factors(self, contact: Contact) -> Dict:
        """Identify factors that might indicate customer churn risk"""
        risk_factors = {
            'declining_engagement': False,
            'long_silence': False,
            'negative_sentiment': False,
            'price_sensitivity': False,
            'competitor_mentions': False
        }
        
        # Check for declining engagement
        recent_engagement = self._calculate_engagement_trend(contact)
        if recent_engagement == 'decreasing':
            risk_factors['declining_engagement'] = True
        
        # Check for long silence
        last_message = Message.objects.filter(
            conversation__contact=contact,
            message_type='received'
        ).order_by('-timestamp').first()
        
        if last_message:
            days_since_last = (timezone.now() - last_message.timestamp).days
            if days_since_last > 30:
                risk_factors['long_silence'] = True
        
        # Check for negative sentiment (simplified)
        recent_messages = Message.objects.filter(
            conversation__contact=contact,
            message_type='received',
            timestamp__gte=timezone.now() - timedelta(days=14)
        )
        
        negative_keywords = ['ruim', 'péssimo', 'problema', 'reclamação', 'insatisfeito', 'caro', 'demais']
        competitor_keywords = ['concorrente', 'outro lugar', 'mais barato', 'encontrei melhor']
        
        for message in recent_messages:
            content_lower = message.content.lower()
            if any(keyword in content_lower for keyword in negative_keywords):
                risk_factors['negative_sentiment'] = True
            if any(keyword in content_lower for keyword in competitor_keywords):
                risk_factors['competitor_mentions'] = True
            if 'caro' in content_lower or 'preço alto' in content_lower:
                risk_factors['price_sensitivity'] = True
        
        return risk_factors
    
    def _calculate_avg_response_time(self, contact: Contact) -> float:
        """Calculate average response time in seconds"""
        conversations = Conversation.objects.filter(contact=contact)
        response_times = []
        
        for conversation in conversations:
            messages = Message.objects.filter(conversation=conversation).order_by('timestamp')
            
            for i in range(len(messages) - 1):
                current_msg = messages[i]
                next_msg = messages[i + 1]
                
                # If current is from agent and next is from user, calculate response time
                if (current_msg.message_type == 'sent' and 
                    next_msg.message_type == 'received'):
                    response_time = (next_msg.timestamp - current_msg.timestamp).total_seconds()
                    response_times.append(response_time)
        
        return sum(response_times) / len(response_times) if response_times else 3600  # Default 1 hour
    
    def _calculate_engagement_trend(self, contact: Contact) -> str:
        """Calculate if engagement is increasing, decreasing, or stable"""
        # Compare last 2 weeks vs previous 2 weeks
        now = timezone.now()
        recent_period = now - timedelta(days=14)
        previous_period = now - timedelta(days=28)
        
        recent_messages = Message.objects.filter(
            conversation__contact=contact,
            message_type='received',
            timestamp__gte=recent_period
        ).count()
        
        previous_messages = Message.objects.filter(
            conversation__contact=contact,
            message_type='received',
            timestamp__gte=previous_period,
            timestamp__lt=recent_period
        ).count()
        
        if recent_messages > previous_messages * 1.2:
            return 'increasing'
        elif recent_messages < previous_messages * 0.8:
            return 'decreasing'
        else:
            return 'stable'
    
    def _determine_purchase_stage(self, intent_signals: Dict) -> str:
        """Determine what stage of purchase process the customer is in"""
        if intent_signals['purchase_keywords'] > 0:
            return 'ready_to_buy'
        elif intent_signals['price_inquiries'] > 0 or intent_signals['availability_checks'] > 0:
            return 'evaluation'
        elif intent_signals['product_comparisons'] > 0:
            return 'consideration'
        else:
            return 'awareness'


class OpportunityDetector:
    """Detects and creates lead opportunities based on behavior analysis"""
    
    def __init__(self):
        self.behavior_analyzer = BehaviorAnalyzer()
        self.opportunity_thresholds = {
            'high_engagement': 0.7,
            'purchase_intent': 0.6,
            'churn_risk': 0.5
        }
    
    def scan_for_opportunities(self, contact: Contact = None) -> List[LeadOpportunity]:
        """Scan for new opportunities across all contacts or specific contact"""
        opportunities = []
        
        if contact:
            contacts = [contact]
        else:
            # Get all contacts for now (simplified)
            contacts = Contact.objects.all()
        
        for contact in contacts:
            contact_opportunities = self._analyze_contact_opportunities(contact)
            opportunities.extend(contact_opportunities)
        
        return opportunities
    
    def _analyze_contact_opportunities(self, contact: Contact) -> List[LeadOpportunity]:
        """Analyze a specific contact for opportunities"""
        opportunities = []
        
        # Get behavior analysis
        behavior = self.behavior_analyzer.analyze_contact_behavior(contact)
        
        # Check for different types of opportunities
        opportunities.extend(self._check_engagement_opportunities(contact, behavior))
        opportunities.extend(self._check_purchase_intent_opportunities(contact, behavior))
        opportunities.extend(self._check_timing_opportunities(contact, behavior))
        opportunities.extend(self._check_risk_mitigation_opportunities(contact, behavior))
        opportunities.extend(self._check_cross_sell_opportunities(contact, behavior))
        
        return opportunities
    
    def _check_engagement_opportunities(self, contact: Contact, behavior: Dict) -> List[LeadOpportunity]:
        """Check for engagement-based opportunities"""
        opportunities = []
        engagement = behavior['engagement_level']
        
        # High engagement opportunity
        if engagement['score'] >= self.opportunity_thresholds['high_engagement']:
            if engagement['trend'] == 'increasing':
                opportunity = self._create_opportunity(
                    contact=contact,
                    opportunity_type='product_interest',
                    priority='high',
                    confidence_score=engagement['score'],
                    analysis_summary=f"High engagement customer with increasing trend. "
                                   f"Score: {engagement['score']:.2f}. "
                                   f"Recent activity: {engagement['total_messages']} messages.",
                    suggested_action="Send personalized product recommendations",
                    trigger_data={'engagement_data': engagement}
                )
                opportunities.append(opportunity)
        
        # Engagement drop opportunity
        elif engagement['trend'] == 'decreasing' and engagement['score'] > 0.3:
            opportunity = self._create_opportunity(
                contact=contact,
                opportunity_type='engagement_drop',
                priority='medium',
                confidence_score=0.7,
                analysis_summary=f"Declining engagement detected. "
                                f"Current score: {engagement['score']:.2f}. "
                                f"Trend: {engagement['trend']}.",
                suggested_action="Send re-engagement message with special offer",
                trigger_data={'engagement_data': engagement}
            )
            opportunities.append(opportunity)
        
        return opportunities
    
    def _check_purchase_intent_opportunities(self, contact: Contact, behavior: Dict) -> List[LeadOpportunity]:
        """Check for purchase intent opportunities"""
        opportunities = []
        intent = behavior['purchase_intent']
        
        if intent['score'] >= self.opportunity_thresholds['purchase_intent']:
            priority = 'urgent' if intent['stage'] == 'ready_to_buy' else 'high'
            
            opportunity = self._create_opportunity(
                contact=contact,
                opportunity_type='price_inquiry' if 'price_inquiries' in intent['signals'] else 'product_interest',
                priority=priority,
                confidence_score=intent['score'],
                analysis_summary=f"Strong purchase intent detected. "
                               f"Stage: {intent['stage']}. "
                               f"Signals: {intent['total_signals']}.",
                suggested_action=self._get_intent_based_action(intent['stage']),
                trigger_data={'intent_data': intent}
            )
            opportunities.append(opportunity)
        
        return opportunities
    
    def _check_timing_opportunities(self, contact: Contact, behavior: Dict) -> List[LeadOpportunity]:
        """Check for timing-based opportunities"""
        opportunities = []
        timing = behavior['timing_patterns']
        
        # If we have good timing data and it's currently optimal time
        if timing['confidence'] > 0.5:
            current_hour = timezone.now().hour
            if current_hour in timing['optimal_hours']:
                opportunity = self._create_opportunity(
                    contact=contact,
                    opportunity_type='seasonal_opportunity',
                    priority='medium',
                    confidence_score=timing['confidence'],
                    analysis_summary=f"Optimal timing window detected. "
                                   f"Customer typically responds well at hour {current_hour}.",
                    suggested_action="Send timely follow-up or product update",
                    trigger_data={'timing_data': timing},
                    optimal_timing=timezone.now()
                )
                opportunities.append(opportunity)
        
        return opportunities
    
    def _check_risk_mitigation_opportunities(self, contact: Contact, behavior: Dict) -> List[LeadOpportunity]:
        """Check for churn risk mitigation opportunities"""
        opportunities = []
        risks = behavior['risk_factors']
        
        # Count active risk factors
        active_risks = sum(1 for risk in risks.values() if risk)
        
        if active_risks >= 2:  # Multiple risk factors
            opportunity = self._create_opportunity(
                contact=contact,
                opportunity_type='engagement_drop',
                priority='high',
                confidence_score=0.8,
                analysis_summary=f"Churn risk detected. Active risk factors: {active_risks}. "
                               f"Risks: {[k for k, v in risks.items() if v]}",
                suggested_action="Send retention offer or personal check-in",
                trigger_data={'risk_data': risks}
            )
            opportunities.append(opportunity)
        
        return opportunities
    
    def _check_cross_sell_opportunities(self, contact: Contact, behavior: Dict) -> List[LeadOpportunity]:
        """Check for cross-selling opportunities"""
        opportunities = []
        interests = behavior['product_interests']
        
        if interests['primary_interest'] and interests['interest_diversity'] >= 2:
            opportunity = self._create_opportunity(
                contact=contact,
                opportunity_type='repeat_customer',
                priority='medium',
                confidence_score=0.6,
                analysis_summary=f"Cross-sell opportunity in {interests['primary_interest']}. "
                               f"Customer shows interest in {interests['interest_diversity']} categories.",
                suggested_action=f"Recommend complementary products in {interests['primary_interest']}",
                trigger_data={'interest_data': interests}
            )
            opportunities.append(opportunity)
        
        return opportunities
    
    def _create_opportunity(self, contact: Contact, opportunity_type: str, priority: str,
                          confidence_score: float, analysis_summary: str, suggested_action: str,
                          trigger_data: Dict, optimal_timing: datetime = None) -> LeadOpportunity:
        """Create a new lead opportunity"""
        
        if optimal_timing is None:
            # Default to next optimal time based on contact's patterns
            behavior = self.behavior_analyzer.analyze_contact_behavior(contact)
            timing = behavior['timing_patterns']
            
            if timing['optimal_hours']:
                next_optimal_hour = min(timing['optimal_hours'])
                now = timezone.now()
                optimal_timing = now.replace(hour=next_optimal_hour, minute=0, second=0, microsecond=0)
                
                # If the time has passed today, schedule for tomorrow
                if optimal_timing <= now:
                    optimal_timing += timedelta(days=1)
            else:
                optimal_timing = timezone.now() + timedelta(hours=2)  # Default 2 hours
        
        # Set expiration (opportunities expire after 7 days by default)
        expires_at = timezone.now() + timedelta(days=7)
        
        # Generate suggested message based on opportunity type
        suggested_message = self._generate_suggested_message(opportunity_type, contact, trigger_data)
        
        opportunity = LeadOpportunity.objects.create(
            contact=contact,
            opportunity_type=opportunity_type,
            priority=priority,
            confidence_score=confidence_score,
            trigger_data=trigger_data,
            analysis_summary=analysis_summary,
            suggested_action=suggested_action,
            suggested_message=suggested_message,
            optimal_timing=optimal_timing,
            expires_at=expires_at
        )
        
        return opportunity
    
    def _get_intent_based_action(self, stage: str) -> str:
        """Get appropriate action based on purchase intent stage"""
        actions = {
            'awareness': "Send educational content about products",
            'consideration': "Provide detailed product comparisons",
            'evaluation': "Share pricing information and availability",
            'ready_to_buy': "Facilitate immediate purchase with direct assistance"
        }
        return actions.get(stage, "Send personalized follow-up")
    
    def _generate_suggested_message(self, opportunity_type: str, contact: Contact, trigger_data: Dict) -> str:
        """Generate a suggested message based on opportunity type and context"""
        
        name = contact.name or "Cliente"
        
        messages = {
            'product_interest': f"Olá {name}! Vi que você tem demonstrado interesse em nossos produtos. "
                              f"Temos algumas novidades que podem te interessar. Gostaria de saber mais?",
            
            'price_inquiry': f"Oi {name}! Notei que você estava perguntando sobre preços. "
                           f"Temos uma promoção especial que pode te interessar. Posso te mostrar?",
            
            'engagement_drop': f"Olá {name}! Senti sua falta por aqui. "
                             f"Preparei uma oferta especial só para você. Que tal darmos uma olhada?",
            
            'repeat_customer': f"Oi {name}! Como cliente especial, queria te mostrar alguns produtos "
                             f"que combinam perfeitamente com suas preferências. Interessado?",
            
            'seasonal_opportunity': f"Olá {name}! É um ótimo momento para aquela conversa que estávamos tendo. "
                                  f"Você tem alguns minutos para conversarmos?",
            
            'referral_potential': f"Oi {name}! Sua experiência conosco tem sido ótima! "
                                f"Conhece alguém que também poderia se beneficiar de nossos produtos?"
        }
        
        return messages.get(opportunity_type, f"Olá {name}! Como posso ajudá-lo hoje?")


class ProactiveAIService:
    """Main service for proactive lead generation and AI prospecting"""
    
    def __init__(self):
        self.opportunity_detector = OpportunityDetector()
        self.behavior_analyzer = BehaviorAnalyzer()
    
    def run_proactive_scan(self) -> Dict:
        """Run a complete proactive scan for opportunities"""
        start_time = time.time()
        
        # Detect new opportunities
        opportunities = self.opportunity_detector.scan_for_opportunities()
        
        # Update lead scores
        self.update_all_lead_scores()
        
        # Process pending opportunities
        processed_actions = self.process_pending_opportunities()
        
        # Generate summary
        summary = {
            'scan_duration': time.time() - start_time,
            'new_opportunities': len(opportunities),
            'actions_processed': len(processed_actions),
            'opportunities_by_type': self._group_opportunities_by_type(opportunities),
            'high_priority_count': len([o for o in opportunities if o.priority == 'high']),
            'urgent_count': len([o for o in opportunities if o.priority == 'urgent'])
        }
        
        return summary
    
    def update_all_lead_scores(self):
        """Update lead scores for all active contacts"""
        active_contacts = Contact.objects.all()
        
        for contact in active_contacts:
            self.update_contact_lead_score(contact)
    
    def update_contact_lead_score(self, contact: Contact):
        """Update lead score for a specific contact"""
        behavior = self.behavior_analyzer.analyze_contact_behavior(contact)
        
        # Get or create lead score
        lead_score, created = LeadScore.objects.get_or_create(contact=contact)
        
        # Update score components
        engagement_score = behavior['engagement_level']['score']
        interest_score = min(1.0, len(behavior['product_interests']['category_interests']) / 3)
        purchase_intent_score = behavior['purchase_intent']['score']
        timing_score = behavior['timing_patterns']['confidence']
        
        lead_score.update_score(
            engagement=engagement_score,
            interest=interest_score,
            purchase_intent=purchase_intent_score,
            timing=timing_score
        )
    
    def process_pending_opportunities(self) -> List[ProactiveAction]:
        """Process opportunities that are ready for action"""
        actions = []
        
        # Get opportunities ready for action
        ready_opportunities = LeadOpportunity.objects.filter(
            status='identified',
            optimal_timing__lte=timezone.now()
        ).order_by('-priority', '-confidence_score')
        
        for opportunity in ready_opportunities[:10]:  # Process max 10 at a time
            action = self._execute_opportunity_action(opportunity)
            if action:
                actions.append(action)
        
        return actions
    
    def _execute_opportunity_action(self, opportunity: LeadOpportunity) -> Optional[ProactiveAction]:
        """Execute action for a specific opportunity"""
        try:
            # Create proactive action record
            action = ProactiveAction.objects.create(
                opportunity=opportunity,
                action_type=self._map_opportunity_to_action_type(opportunity.opportunity_type),
                message_sent=opportunity.suggested_message
            )
            
            # Mark opportunity as action taken
            opportunity.mark_action_taken(opportunity.suggested_message)
            
            # Here you would integrate with the WhatsApp sending service
            # For now, we'll just mark it as processed
            action.message_delivered = True
            action.save()
            
            return action
            
        except Exception as e:
            print(f"Error executing opportunity action: {e}")
            return None
    
    def _map_opportunity_to_action_type(self, opportunity_type: str) -> str:
        """Map opportunity type to action type"""
        mapping = {
            'product_interest': 'product_recommendation',
            'price_inquiry': 'price_alert',
            'engagement_drop': 'engagement_recovery',
            'repeat_customer': 'cross_sell',
            'seasonal_opportunity': 'follow_up_message',
            'referral_potential': 'referral_request'
        }
        return mapping.get(opportunity_type, 'follow_up_message')
    
    def _group_opportunities_by_type(self, opportunities: List[LeadOpportunity]) -> Dict:
        """Group opportunities by type for reporting"""
        groups = {}
        for opportunity in opportunities:
            opp_type = opportunity.opportunity_type
            if opp_type not in groups:
                groups[opp_type] = 0
            groups[opp_type] += 1
        return groups
    
    def get_proactive_insights(self, contact: Contact = None) -> Dict:
        """Get insights about proactive activities"""
        if contact:
            # Contact-specific insights
            opportunities = LeadOpportunity.objects.filter(contact=contact)
            actions = ProactiveAction.objects.filter(opportunity__contact=contact)
        else:
            # Global insights
            opportunities = LeadOpportunity.objects.all()
            actions = ProactiveAction.objects.all()
        
        # Calculate metrics
        total_opportunities = opportunities.count()
        converted_opportunities = opportunities.filter(conversion_achieved=True).count()
        
        conversion_rate = (converted_opportunities / total_opportunities * 100) if total_opportunities > 0 else 0
        
        # Response metrics
        total_actions = actions.count()
        responses_received = actions.filter(response_received=True).count()
        response_rate = (responses_received / total_actions * 100) if total_actions > 0 else 0
        
        return {
            'total_opportunities': total_opportunities,
            'converted_opportunities': converted_opportunities,
            'conversion_rate': conversion_rate,
            'total_actions': total_actions,
            'responses_received': responses_received,
            'response_rate': response_rate,
            'opportunities_by_priority': {
                'urgent': opportunities.filter(priority='urgent').count(),
                'high': opportunities.filter(priority='high').count(),
                'medium': opportunities.filter(priority='medium').count(),
                'low': opportunities.filter(priority='low').count(),
            }
        }


# Global instance
proactive_ai_service = ProactiveAIService()

