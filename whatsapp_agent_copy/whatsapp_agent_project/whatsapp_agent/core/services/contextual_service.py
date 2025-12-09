"""
AI Contextual Service - Advanced context analysis and persona adaptation
"""
import json
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from django.utils import timezone
from textblob import TextBlob
import google.generativeai as genai
from ..models import Contact, Conversation, Message, AIConfig
from ..contextual_models import (
    ConversationContext, PersonaAdaptation, MessageAnalysis, 
    PersonaTemplate, AdaptationRule
)


class SentimentAnalyzer:
    """Advanced sentiment analysis with context awareness"""
    
    def __init__(self):
        self.sentiment_keywords = {
            'very_positive': ['excelente', 'perfeito', 'maravilhoso', 'fantástico', 'adorei', 'amei'],
            'positive': ['bom', 'legal', 'gostei', 'interessante', 'bacana', 'show'],
            'neutral': ['ok', 'tudo bem', 'normal', 'entendi', 'certo'],
            'negative': ['ruim', 'não gostei', 'problema', 'difícil', 'complicado'],
            'very_negative': ['péssimo', 'horrível', 'terrível', 'odeio', 'detesto'],
            'frustrated': ['irritado', 'chateado', 'estressado', 'cansado', 'não aguento'],
            'excited': ['animado', 'empolgado', 'ansioso', 'mal posso esperar'],
            'confused': ['confuso', 'não entendi', 'como assim', 'não sei', 'dúvida']
        }
    
    def analyze_sentiment(self, text: str) -> Tuple[str, float, Dict]:
        """Analyze sentiment of text with confidence score and details"""
        start_time = time.time()
        
        # normalize text
        text_lower = text.lower()
        
        # keyword-based analysis
        keyword_scores = {}
        for sentiment, keywords in self.sentiment_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                keyword_scores[sentiment] = score
        
        # textblob analysis for additional context
        blob = TextBlob(text)
        polarity = blob.sentiment.polarity  # -1 to 1
        subjectivity = blob.sentiment.subjectivity  # 0 to 1
        
        # combine analyses
        if keyword_scores:
            # use keyword-based if found
            dominant_sentiment = max(keyword_scores.items(), key=lambda x: x[1])
            sentiment = dominant_sentiment[0]
            confidence = min(0.9, 0.5 + (dominant_sentiment[1] * 0.1))
        else:
            # fallback to polarity-based
            if polarity > 0.5:
                sentiment = 'very_positive'
                confidence = polarity
            elif polarity > 0.1:
                sentiment = 'positive'
                confidence = polarity
            elif polarity < -0.5:
                sentiment = 'very_negative'
                confidence = abs(polarity)
            elif polarity < -0.1:
                sentiment = 'negative'
                confidence = abs(polarity)
            else:
                sentiment = 'neutral'
                confidence = 1.0 - abs(polarity)
        
        analysis_data = {
            'polarity': polarity,
            'subjectivity': subjectivity,
            'keyword_matches': keyword_scores,
            'processing_time': time.time() - start_time
        }
        
        return sentiment, confidence, analysis_data


class TechnicalLevelAnalyzer:
    """Analyze technical level of user based on vocabulary and concepts"""
    
    def __init__(self):
        self.technical_terms = {
            'beginner': ['comprar', 'preço', 'quanto custa', 'como funciona', 'é bom'],
            'intermediate': ['especificações', 'características', 'comparar', 'diferença', 'modelo'],
            'advanced': ['performance', 'benchmark', 'compatibilidade', 'configuração', 'otimização'],
            'expert': ['arquitetura', 'protocolo', 'algoritmo', 'framework', 'implementação', 'api']
        }
        
        self.complexity_indicators = [
            'porque', 'devido', 'considerando', 'entretanto', 'portanto', 'consequentemente'
        ]
    
    def analyze_technical_level(self, text: str, conversation_history: List[str] = None) -> Tuple[str, float, Dict]:
        """Analyze technical level with confidence and supporting data"""
        text_lower = text.lower()
        
        # count technical terms by level
        level_scores = {}
        matched_terms = {}
        
        for level, terms in self.technical_terms.items():
            matches = [term for term in terms if term in text_lower]
            if matches:
                level_scores[level] = len(matches)
                matched_terms[level] = matches
        
        # analyze sentence complexity
        sentences = text.split('.')
        avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0
        
        complexity_score = 0
        for indicator in self.complexity_indicators:
            if indicator in text_lower:
                complexity_score += 1
        
        # determine level
        if level_scores:
            dominant_level = max(level_scores.items(), key=lambda x: x[1])
            level = dominant_level[0]
            confidence = min(0.9, 0.3 + (dominant_level[1] * 0.15))
        else:
            # fallback based on complexity
            if avg_sentence_length > 15 and complexity_score > 2:
                level = 'advanced'
                confidence = 0.6
            elif avg_sentence_length > 10 or complexity_score > 0:
                level = 'intermediate'
                confidence = 0.5
            else:
                level = 'beginner'
                confidence = 0.7
        
        indicators = {
            'matched_terms': matched_terms,
            'avg_sentence_length': avg_sentence_length,
            'complexity_score': complexity_score,
            'total_terms_found': sum(level_scores.values()) if level_scores else 0
        }
        
        return level, confidence, indicators


class SalesFunnelAnalyzer:
    """Analyze where the customer is in the sales funnel"""
    
    def __init__(self):
        self.funnel_indicators = {
            'awareness': ['o que é', 'como funciona', 'nunca ouvi', 'não conheço'],
            'interest': ['interessante', 'gostaria de saber', 'me fale mais', 'quero entender'],
            'consideration': ['comparar', 'diferença', 'qual melhor', 'prós e contras'],
            'intent': ['quero comprar', 'onde compro', 'como adquirir', 'preço'],
            'evaluation': ['desconto', 'promoção', 'condições', 'parcelamento'],
            'purchase': ['fechar', 'comprar agora', 'finalizar', 'confirmar pedido'],
            'retention': ['suporte', 'problema', 'dúvida', 'como usar']
        }
    
    def analyze_funnel_stage(self, text: str, conversation_history: List[str] = None) -> Tuple[str, float]:
        """Determine sales funnel stage"""
        text_lower = text.lower()
        
        stage_scores = {}
        for stage, indicators in self.funnel_indicators.items():
            score = sum(1 for indicator in indicators if indicator in text_lower)
            if score > 0:
                stage_scores[stage] = score
        
        if stage_scores:
            dominant_stage = max(stage_scores.items(), key=lambda x: x[1])
            return dominant_stage[0], min(0.9, 0.4 + (dominant_stage[1] * 0.2))
        
        return 'awareness', 0.3  # default


class PersonaAdapter:
    """Adapt AI persona based on context analysis"""
    
    def __init__(self):
        self.base_personas = {
            'empathetic': "Seja mais empático e compreensivo. Use um tom caloroso e acolhedor.",
            'technical': "Use linguagem mais técnica e detalhada. Forneça especificações precisas.",
            'casual': "Seja mais descontraído e use linguagem informal. Use gírias apropriadas.",
            'formal': "Mantenha um tom profissional e formal. Seja respeitoso e direto.",
            'enthusiastic': "Seja mais animado e entusiasmado. Use exclamações e energia positiva.",
            'patient': "Seja muito paciente e didático. Explique passo a passo com calma.",
            'urgent': "Seja mais direto e focado. Priorize informações essenciais.",
            'consultative': "Atue como consultor especialista. Faça perguntas estratégicas."
        }
    
    def adapt_persona(self, base_persona: str, context: ConversationContext) -> str:
        """Generate adapted persona based on context"""
        adaptations = []
        
        # sentiment-based adaptations
        if context.current_sentiment in ['frustrated', 'very_negative', 'negative']:
            adaptations.append(self.base_personas['empathetic'])
            adaptations.append("Reconheça qualquer frustração e ofereça soluções práticas.")
        
        elif context.current_sentiment in ['excited', 'very_positive']:
            adaptations.append(self.base_personas['enthusiastic'])
        
        elif context.current_sentiment == 'confused':
            adaptations.append(self.base_personas['patient'])
        
        # technical level adaptations
        if context.technical_level == 'expert':
            adaptations.append(self.base_personas['technical'])
        elif context.technical_level == 'beginner':
            adaptations.append(self.base_personas['casual'])
            adaptations.append("Evite jargões técnicos. Use analogias simples.")
        
        # funnel stage adaptations
        if context.funnel_stage == 'intent':
            adaptations.append(self.base_personas['consultative'])
        elif context.funnel_stage == 'purchase':
            adaptations.append(self.base_personas['urgent'])
            adaptations.append("Foque em facilitar o processo de compra.")
        
        # combine base persona with adaptations
        if adaptations:
            adapted_persona = f"{base_persona}\n\nAdaptações contextuais:\n" + "\n".join(f"- {adaptation}" for adaptation in adaptations)
        else:
            adapted_persona = base_persona
        
        return adapted_persona


class ContextualAIService:
    """Main service for contextual AI functionality"""
    
    def __init__(self):
        self.sentiment_analyzer = SentimentAnalyzer()
        self.technical_analyzer = TechnicalLevelAnalyzer()
        self.funnel_analyzer = SalesFunnelAnalyzer()
        self.persona_adapter = PersonaAdapter()
    
    def analyze_message(self, message: Message) -> MessageAnalysis:
        """Perform comprehensive analysis of a message"""
        text = message.content
        
        # sentiment analysis
        sentiment, sentiment_conf, sentiment_data = self.sentiment_analyzer.analyze_sentiment(text)
        
        # technical level analysis
        tech_level, tech_conf, tech_indicators = self.technical_analyzer.analyze_technical_level(text)
        
        # intent and topic analysis (simplified for now)
        detected_intent = self._detect_intent(text)
        main_topics = self._extract_topics(text)
        
        # urgency analysis
        urgency = self._analyze_urgency(text)
        
        # create or update analysis
        analysis, created = MessageAnalysis.objects.get_or_create(
            message=message,
            defaults={
                'sentiment': sentiment,
                'sentiment_confidence': sentiment_conf,
                'sentiment_keywords': sentiment_data.get('keyword_matches', {}),
                'technical_terms': tech_indicators.get('matched_terms', {}),
                'complexity_score': tech_indicators.get('complexity_score', 0),
                'detected_intent': detected_intent,
                'intent_confidence': 0.7,  # simplified
                'main_topics': main_topics,
                'urgency_level': urgency,
                'processing_time': sentiment_data.get('processing_time', 0)
            }
        )
        
        return analysis
    
    def update_conversation_context(self, conversation: Conversation, message: Message) -> ConversationContext:
        """Update conversation context based on new message"""
        # get or create context
        context, created = ConversationContext.objects.get_or_create(
            conversation=conversation,
            defaults={
                'current_sentiment': 'neutral',
                'technical_level': 'beginner',
                'funnel_stage': 'awareness'
            }
        )
        
        # analyze the message
        analysis = self.analyze_message(message)
        
        # update sentiment
        context.update_sentiment(
            analysis.sentiment,
            analysis.sentiment_confidence,
            {
                'keywords': analysis.sentiment_keywords,
                'message_id': message.id
            }
        )
        
        # update technical level
        context.update_technical_level(
            self._determine_technical_level(analysis, context),
            analysis.sentiment_confidence,  # reuse for simplicity
            analysis.technical_terms
        )
        
        # update funnel stage
        funnel_stage, funnel_conf = self.funnel_analyzer.analyze_funnel_stage(message.content)
        context.funnel_stage = funnel_stage
        context.funnel_confidence = funnel_conf
        
        # update conversation stats
        context.message_count += 1
        context.save()
        
        # check if persona adaptation is needed
        should_adapt, trigger = context.should_adapt_persona()
        if should_adapt:
            context.needs_persona_adaptation = True
            context.last_adaptation_trigger = trigger
            context.save()
        
        return context
    
    def get_adapted_persona(self, conversation: Conversation) -> str:
        """Get the current adapted persona for a conversation"""
        try:
            # get base persona
            ai_config = AIConfig.objects.filter(is_active=True).first()
            base_persona = ai_config.persona_prompt if ai_config else "Você é um assistente de vendas útil."
            
            # check for contact-specific persona
            contact_persona = conversation.contact.persona_prompt
            if contact_persona:
                base_persona = contact_persona
            
            # get conversation context
            context = ConversationContext.objects.filter(conversation=conversation).first()
            if not context:
                return base_persona
            
            # check if adaptation is needed
            if context.needs_persona_adaptation:
                adapted_persona = self.persona_adapter.adapt_persona(base_persona, context)
                
                # record the adaptation
                PersonaAdaptation.objects.create(
                    conversation=conversation,
                    adaptation_type='sentiment_based',  # simplified
                    original_persona=base_persona,
                    adapted_persona=adapted_persona,
                    trigger_reason=context.last_adaptation_trigger,
                    adaptation_data={
                        'sentiment': context.current_sentiment,
                        'technical_level': context.technical_level,
                        'funnel_stage': context.funnel_stage
                    }
                )
                
                # reset adaptation flag
                context.needs_persona_adaptation = False
                context.save()
                
                return adapted_persona
            
            # check for existing active adaptation
            active_adaptation = PersonaAdaptation.objects.filter(
                conversation=conversation,
                is_active=True
            ).first()
            
            if active_adaptation:
                return active_adaptation.adapted_persona
            
            return base_persona
            
        except Exception as e:
            # fallback to base persona on any error
            ai_config = AIConfig.objects.filter(is_active=True).first()
            return ai_config.persona_prompt if ai_config else "Você é um assistente de vendas útil."
    
    def _detect_intent(self, text: str) -> str:
        """Simple intent detection (can be enhanced with ML models)"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['comprar', 'adquirir', 'quero']):
            return 'purchase_intent'
        elif any(word in text_lower for word in ['preço', 'quanto', 'valor']):
            return 'price_inquiry'
        elif any(word in text_lower for word in ['informação', 'detalhes', 'especificação']):
            return 'information_request'
        elif any(word in text_lower for word in ['problema', 'ajuda', 'suporte']):
            return 'support_request'
        else:
            return 'general_inquiry'
    
    def _extract_topics(self, text: str) -> List[str]:
        """Extract main topics from text (simplified implementation)"""
        # this could be enhanced with NLP libraries or ML models
        topics = []
        text_lower = text.lower()
        
        topic_keywords = {
            'produto': ['produto', 'item', 'mercadoria'],
            'preço': ['preço', 'valor', 'custo', 'quanto'],
            'entrega': ['entrega', 'envio', 'frete'],
            'pagamento': ['pagamento', 'pagar', 'cartão', 'pix'],
            'qualidade': ['qualidade', 'bom', 'ruim', 'avaliação']
        }
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                topics.append(topic)
        
        return topics
    
    def _analyze_urgency(self, text: str) -> str:
        """Analyze urgency level of message"""
        text_lower = text.lower()
        
        urgent_indicators = ['urgente', 'rápido', 'agora', 'hoje', 'imediato']
        high_indicators = ['importante', 'preciso', 'necessário']
        
        if any(indicator in text_lower for indicator in urgent_indicators):
            return 'urgent'
        elif any(indicator in text_lower for indicator in high_indicators):
            return 'high'
        else:
            return 'medium'
    
    def _determine_technical_level(self, analysis: MessageAnalysis, context: ConversationContext) -> str:
        """Determine technical level considering message analysis and context"""
        # use message analysis as primary source
        if analysis.technical_terms:
            # count terms by level
            level_counts = {}
            for level, terms in analysis.technical_terms.items():
                level_counts[level] = len(terms)
            
            if level_counts:
                return max(level_counts.items(), key=lambda x: x[1])[0]
        
        # fallback to existing context level
        return context.technical_level

