"""
Enhanced AI Service with Contextual Analysis Integration
"""
import os
import google.generativeai as genai
from django.conf import settings
from ..models import AIConfig, Contact, Conversation, Message
from .contextual_service import ContextualAIService


class EnhancedAIService:
    """Enhanced AI Service with contextual analysis and dynamic persona adaptation"""
    
    DEFAULT_PERSONA = "You are a helpful sales assistant. Analyze the user message and product catalog to provide relevant recommendations in Portuguese (Brazil)."

    def __init__(self):
        """Initialize the enhanced AI service with contextual capabilities"""
        self.api_key = None
        self.client = None
        self.is_configured_flag = False
        self.model_name = "gemini-1.5-flash"
        self.persona_prompt = self.DEFAULT_PERSONA
        self.contextual_service = ContextualAIService()
        self._load_config()

    def _load_config(self):
        """Loads the API key and persona prompt from the active AIConfig or falls back"""
        active_config = None
        db_key = None
        db_persona = None
        
        try:
            active_config = AIConfig.objects.get(is_active=True)
            if active_config.api_key:
                db_key = active_config.api_key
                print("Using Gemini API key from active database AIConfig.")
            if active_config.persona_prompt:
                db_persona = active_config.persona_prompt
                print("Using Persona Prompt from active database AIConfig.")
            else:
                print("No Persona Prompt found in active database AIConfig, using default.")
                
        except AIConfig.DoesNotExist:
            print("No active AIConfig found in the database.")
        except AIConfig.MultipleObjectsReturned:
            print("Warning: Multiple active AIConfigs found. Using the first one.")
            active_config = AIConfig.objects.filter(is_active=True).first()
            if active_config:
                if active_config.api_key:
                    db_key = active_config.api_key
                    print("Using Gemini API key from the first active database AIConfig.")
                if active_config.persona_prompt:
                    db_persona = active_config.persona_prompt
                    print("Using Persona Prompt from the first active database AIConfig.")
                else:
                    print("No Persona Prompt found in the first active database AIConfig, using default.")
        except Exception as e:
            print(f"Error fetching AIConfig from database: {e}")

        # set api key (db > settings/env > none)
        if db_key:
            self.api_key = db_key
        else:
            fallback_key = getattr(settings, 'DEFAULT_GEMINI_API_KEY', os.environ.get('DEFAULT_GEMINI_API_KEY', ''))
            if fallback_key:
                self.api_key = fallback_key
                print("Using Gemini API key from settings.py or environment variable (fallback).")
            else:
                self.api_key = None
                print("No Gemini API key found in database, settings, or environment.")

        # set persona prompt (db > default)
        self.persona_prompt = db_persona if db_persona else self.DEFAULT_PERSONA
        if self.persona_prompt == self.DEFAULT_PERSONA:
             print("Using default Persona Prompt.")

        # initialize the client with the determined key (or none)
        self._initialize_client()

    def _initialize_client(self):
        """Initializes the genai client if api key is present"""
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.client = genai.GenerativeModel(self.model_name)
                self.is_configured_flag = True
                print(f"Enhanced Gemini client initialized successfully for model {self.model_name}")
            except Exception as e:
                print(f"Failed to initialize Enhanced Gemini client: {e}")
                self.is_configured_flag = False
                self.client = None
        else:
            print("Enhanced Gemini client initialization skipped: No API key provided.")
            self.is_configured_flag = False
            self.client = None

    def is_configured(self):
        """Returns true if the client is initialized and ready"""
        return self.is_configured_flag

    def reconfigure(self):
        """Public method to reload configuration and re-initialize client"""
        print("Reconfiguring Enhanced AI Service...")
        self._load_config()

    def get_contextual_recommendation(self, user_message, product_catalog, conversation=None, contact=None, message_obj=None):
        """
        Get contextual product recommendations with dynamic persona adaptation
        
        Args:
            user_message (str): The user's message/query
            product_catalog (list): List of Product objects
            conversation (Conversation, optional): Conversation object for context
            contact (Contact, optional): Contact object for personalized AI behavior
            message_obj (Message, optional): Message object for analysis
            
        Returns:
            dict: Response containing recommendation, explanation, and context analysis
        """
        if not self.is_configured():
            return {
                'success': False,
                'error': 'Enhanced AI Service not configured. Check API Key in AI Configuration.',
                'fallback_response': self._get_fallback_response(user_message, product_catalog)
            }
        
        try:
            # perform contextual analysis if conversation and message are provided
            context_analysis = None
            adapted_persona = self.persona_prompt
            
            if conversation and message_obj:
                # update conversation context with new message
                context = self.contextual_service.update_conversation_context(conversation, message_obj)
                
                # get adapted persona based on context
                adapted_persona = self.contextual_service.get_adapted_persona(conversation)
                
                # prepare context analysis for response
                context_analysis = {
                    'sentiment': context.current_sentiment,
                    'sentiment_confidence': context.sentiment_confidence,
                    'technical_level': context.technical_level,
                    'funnel_stage': context.funnel_stage,
                    'message_count': context.message_count,
                    'adaptation_applied': context.needs_persona_adaptation or 
                                        conversation.persona_adaptations.filter(is_active=True).exists()
                }
                
                print(f"Context Analysis - Sentiment: {context.current_sentiment}, "
                      f"Technical: {context.technical_level}, Funnel: {context.funnel_stage}")
            
            # check for contact-specific persona (takes precedence over contextual adaptation)
            if contact and hasattr(contact, 'persona_prompt') and contact.persona_prompt:
                adapted_persona = contact.persona_prompt
                print(f"Using contact-specific persona for {contact.name if contact.name else contact.phone_number}")
            
            # create context with product catalog
            catalog_context = self._format_product_catalog(product_catalog)
            
            # format conversation history if available
            history_context = ""
            if conversation:
                recent_messages = Message.objects.filter(conversation=conversation).order_by('-timestamp')[:5]
                if recent_messages:
                    history_context = "\n\nRecent conversation:\n" + "\n".join([
                        f"{'User' if msg.message_type == 'received' else 'Agent'}: {msg.content}"
                        for msg in reversed(recent_messages)
                    ])
            
            # create enhanced prompt with contextual information
            contextual_instructions = ""
            if context_analysis:
                contextual_instructions = f"""
CONTEXTUAL INFORMATION:
- Customer sentiment: {context_analysis['sentiment']} (confidence: {context_analysis['sentiment_confidence']:.2f})
- Technical level: {context_analysis['technical_level']}
- Sales funnel stage: {context_analysis['funnel_stage']}
- Messages in conversation: {context_analysis['message_count']}

CONTEXTUAL ADAPTATION GUIDELINES:
- Adapt your response style based on the customer's current sentiment and technical level
- Consider their position in the sales funnel when making recommendations
- If sentiment is negative/frustrated, be more empathetic and solution-focused
- If technical level is advanced, provide more detailed specifications
- If in purchase stage, focus on facilitating the buying process
"""
            
            prompt = f"""{adapted_persona}

{contextual_instructions}

PRODUCT CATALOG:
{catalog_context}

INSTRUCTIONS:
- Analyze the user's message and recommend suitable products from the catalog
- Focus on notebooks (especially Asus and Acer models with at least i3 processor and 4GB RAM) and smartphones
- Pay attention to the user's preferences and budget constraints
- If the user's request is unclear, ask clarifying questions
- If no suitable product is found, suggest alternatives
- Be friendly, helpful, and conversational
- Respond in Portuguese (Brazil)
- Format your response naturally and conversationally
{history_context}

User's message: {user_message}

Your response:"""

            # generate response from gemini
            response = self.client.generate_content(contents=prompt)
            
            if not response.candidates or not response.candidates[0].content.parts:
                prompt_feedback = getattr(response, 'prompt_feedback', None)
                block_reason = getattr(prompt_feedback, 'block_reason', 'Unknown') if prompt_feedback else 'Unknown'
                print(f"Warning: Enhanced AI content generation potentially blocked. Reason: {block_reason}")
                raise ValueError(f"No content generated, potentially blocked (Reason: {block_reason})")

            generated_text = response.text

            return {
                'success': True,
                'response': generated_text,
                'model_used': self.client.model_name,
                'context_analysis': context_analysis,
                'persona_adapted': adapted_persona != self.persona_prompt,
                'adaptation_details': {
                    'original_persona': self.persona_prompt,
                    'adapted_persona': adapted_persona
                } if adapted_persona != self.persona_prompt else None
            }
            
        except Exception as e:
            print(f"Error in Enhanced AI Service: {e}") 
            return {
                'success': False,
                'error': str(e),
                'fallback_response': self._get_fallback_response(user_message, product_catalog),
                'context_analysis': context_analysis if 'context_analysis' in locals() else None
            }

    def get_product_recommendation(self, user_message, product_catalog, conversation_history=None, contact=None):
        """
        Backward compatibility method - delegates to contextual recommendation
        """
        return self.get_contextual_recommendation(
            user_message=user_message,
            product_catalog=product_catalog,
            contact=contact
        )
    
    def analyze_conversation_context(self, conversation):
        """
        Get detailed context analysis for a conversation
        
        Args:
            conversation (Conversation): Conversation object to analyze
            
        Returns:
            dict: Detailed context analysis
        """
        try:
            context = conversation.context if hasattr(conversation, 'context') else None
            if not context:
                return {
                    'success': False,
                    'error': 'No context available for this conversation'
                }
            
            # get recent adaptations
            recent_adaptations = conversation.persona_adaptations.filter(
                is_active=True
            ).order_by('-applied_at')[:3]
            
            # get message analyses
            recent_analyses = []
            recent_messages = Message.objects.filter(conversation=conversation).order_by('-timestamp')[:5]
            for message in recent_messages:
                if hasattr(message, 'analysis'):
                    recent_analyses.append({
                        'message_id': message.id,
                        'content': message.content[:100] + '...' if len(message.content) > 100 else message.content,
                        'sentiment': message.analysis.sentiment,
                        'technical_terms': message.analysis.technical_terms,
                        'detected_intent': message.analysis.detected_intent,
                        'urgency': message.analysis.urgency_level
                    })
            
            return {
                'success': True,
                'context': {
                    'current_sentiment': context.current_sentiment,
                    'sentiment_confidence': context.sentiment_confidence,
                    'sentiment_history': context.sentiment_history[-5:],  # last 5
                    'technical_level': context.technical_level,
                    'technical_confidence': context.technical_confidence,
                    'funnel_stage': context.funnel_stage,
                    'funnel_confidence': context.funnel_confidence,
                    'message_count': context.message_count,
                    'conversation_topics': context.conversation_topics,
                    'needs_adaptation': context.needs_persona_adaptation,
                    'last_adaptation_trigger': context.last_adaptation_trigger
                },
                'recent_adaptations': [
                    {
                        'type': adaptation.adaptation_type,
                        'trigger': adaptation.trigger_reason,
                        'applied_at': adaptation.applied_at,
                        'is_active': adaptation.is_active
                    } for adaptation in recent_adaptations
                ],
                'recent_message_analyses': recent_analyses
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Error analyzing conversation context: {str(e)}'
            }
    
    def _format_product_catalog(self, products):
        """Format product catalog for the AI prompt"""
        formatted_catalog = []
        
        if not hasattr(products, '__iter__'):
            print("Warning: product_catalog is not iterable in _format_product_catalog")
            return "No product information available."
            
        for i, product in enumerate(products):
            if not product or not hasattr(product, 'name'): 
                print(f"Warning: Invalid product object at index {i} in catalog.")
                continue
                
            formatted_product = (
                f"Product {i+1}:\n"
                f"- Name: {getattr(product, 'name', 'N/A')}\n"
                f"- Category: {getattr(product, 'category', 'N/A')}\n"
                f"- Description: {getattr(product, 'description', 'N/A')}\n"
                f"- Price: R$ {getattr(product, 'price', 'N/A')}\n"
                f"- Link: {getattr(product, 'affiliate_link', 'N/A')}\n"
            )
            formatted_catalog.append(formatted_product)
        
        return "\n".join(formatted_catalog) if formatted_catalog else "No products listed in catalog."
    
    def _get_fallback_response(self, user_message, product_catalog):
        """Generate a fallback response when AI is not available or fails"""
        user_message = user_message.lower()
        
        if not hasattr(product_catalog, '__iter__'):
             print("Warning: product_catalog is not iterable in _get_fallback_response")
             product_catalog = []
             
        # check for notebook keywords
        if any(keyword in user_message for keyword in ['notebook', 'laptop', 'computador', 'pc']):
            if 'asus' in user_message:
                for product in product_catalog:
                    if product and 'asus' in getattr(product, 'name', '').lower() and getattr(product, 'category', '').lower() == 'notebook':
                        return f"Temos este notebook da Asus que pode te interessar: {product.name} por R$ {product.price}. Posso te dar mais detalhes sobre ele?"
            
            if 'acer' in user_message:
                for product in product_catalog:
                    if product and 'acer' in getattr(product, 'name', '').lower() and getattr(product, 'category', '').lower() == 'notebook':
                        return f"Temos este notebook da Acer que pode te interessar: {product.name} por R$ {product.price}. Posso te dar mais detalhes sobre ele?"
            
            notebooks = [p for p in product_catalog if p and getattr(p, 'category', '').lower() == 'notebook']
            if notebooks:
                return f"Temos {len(notebooks)} opções de notebooks disponíveis. Você tem preferência por alguma marca específica como Asus ou Acer?"
        
        # check for smartphone keywords
        if any(keyword in user_message for keyword in ['celular', 'smartphone', 'telefone', 'iphone', 'samsung']):
            smartphones = [p for p in product_catalog if p and getattr(p, 'category', '').lower() in ['smartphone', 'celular', 'telefone']]
            if smartphones:
                return f"Temos {len(smartphones)} opções de smartphones disponíveis. Você busca alguma marca específica ou tem um orçamento em mente?"
        
        return "Olá! Sou o assistente de vendas da loja. Posso te ajudar a encontrar notebooks (especialmente Asus e Acer) e smartphones. O que você está procurando hoje?"


# instantiate the enhanced service globally
enhanced_ai_service = EnhancedAIService()

# maintain backward compatibility
ai_service = enhanced_ai_service

