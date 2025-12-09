"""
Open Source AI Service with Ollama Integration
"""
import requests
import json
import time
from typing import Dict, List, Tuple, Optional
from django.conf import settings
from ..models import AIConfig
from .contextual_service import ContextualAIService


class OllamaAIService:
    """AI Service using local Ollama models"""
    
    def __init__(self):
        self.base_url = getattr(settings, 'OLLAMA_BASE_URL', 'http://localhost:11434')
        self.default_model = getattr(settings, 'OLLAMA_DEFAULT_MODEL', 'gemma2:2b')
        self.timeout = getattr(settings, 'OLLAMA_TIMEOUT', 30)
        self.contextual_service = ContextualAIService()
        
    def is_available(self) -> bool:
        """Check if Ollama service is available"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def list_models(self) -> List[str]:
        """List available models in Ollama"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [model['name'] for model in data.get('models', [])]
            return []
        except:
            return []
    
    def generate_response(self, prompt: str, model: str = None) -> Dict:
        """Generate response using Ollama"""
        if not model:
            model = self.default_model
            
        try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "max_tokens": 500
                }
            }
            
            start_time = time.time()
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'response': data.get('response', ''),
                    'model_used': model,
                    'processing_time': time.time() - start_time,
                    'tokens_generated': data.get('eval_count', 0),
                    'tokens_per_second': data.get('eval_count', 0) / data.get('eval_duration', 1) * 1e9
                }
            else:
                return {
                    'success': False,
                    'error': f"Ollama API error: {response.status_code}",
                    'response_text': response.text
                }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': "Ollama request timeout"
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Ollama error: {str(e)}"
            }


class HybridAIService:
    """Hybrid AI Service that can use both local Ollama and external APIs"""
    
    def __init__(self):
        self.ollama_service = OllamaAIService()
        self.use_local_first = getattr(settings, 'USE_LOCAL_AI_FIRST', True)
        self.fallback_to_api = getattr(settings, 'FALLBACK_TO_API', True)
        self.contextual_service = ContextualAIService()
        
        # load external API config as fallback
        self._load_external_config()
    
    def _load_external_config(self):
        """Load external API configuration for fallback"""
        try:
            active_config = AIConfig.objects.filter(is_active=True).first()
            self.external_api_key = active_config.api_key if active_config else None
            self.external_persona = active_config.persona_prompt if active_config else None
        except:
            self.external_api_key = None
            self.external_persona = None
    
    def get_contextual_recommendation(self, user_message, product_catalog, conversation=None, contact=None, message_obj=None):
        """
        Get contextual product recommendations using hybrid AI approach
        """
        # perform contextual analysis
        context_analysis = None
        adapted_persona = self._get_base_persona()
        
        if conversation and message_obj:
            context = self.contextual_service.update_conversation_context(conversation, message_obj)
            adapted_persona = self.contextual_service.get_adapted_persona(conversation)
            
            context_analysis = {
                'sentiment': context.current_sentiment,
                'sentiment_confidence': context.sentiment_confidence,
                'technical_level': context.technical_level,
                'funnel_stage': context.funnel_stage,
                'message_count': context.message_count,
                'adaptation_applied': context.needs_persona_adaptation or 
                                    conversation.persona_adaptations.filter(is_active=True).exists()
            }
        
        # check for contact-specific persona
        if contact and hasattr(contact, 'persona_prompt') and contact.persona_prompt:
            adapted_persona = contact.persona_prompt
        
        # create enhanced prompt
        prompt = self._create_sales_prompt(
            user_message=user_message,
            product_catalog=product_catalog,
            persona=adapted_persona,
            context_analysis=context_analysis,
            conversation=conversation
        )
        
        # try local AI first if enabled
        if self.use_local_first and self.ollama_service.is_available():
            print("Attempting to use local Ollama AI...")
            result = self.ollama_service.generate_response(prompt)
            
            if result['success']:
                return {
                    'success': True,
                    'response': result['response'],
                    'model_used': f"ollama_{result['model_used']}",
                    'processing_time': result['processing_time'],
                    'context_analysis': context_analysis,
                    'persona_adapted': adapted_persona != self._get_base_persona(),
                    'ai_source': 'local_ollama'
                }
            else:
                print(f"Local AI failed: {result['error']}")
        
        # fallback to external API if enabled
        if self.fallback_to_api and self.external_api_key:
            print("Falling back to external API...")
            return self._use_external_api(prompt, context_analysis, adapted_persona)
        
        # final fallback to rule-based response
        return {
            'success': False,
            'error': 'No AI service available',
            'fallback_response': self._get_fallback_response(user_message, product_catalog),
            'context_analysis': context_analysis,
            'ai_source': 'fallback'
        }
    
    def _create_sales_prompt(self, user_message, product_catalog, persona, context_analysis=None, conversation=None):
        """Create optimized prompt for sales AI"""
        
        # format product catalog
        catalog_text = self._format_product_catalog(product_catalog)
        
        # add contextual information
        contextual_info = ""
        if context_analysis:
            contextual_info = f"""
CONTEXTO DO CLIENTE:
- Sentimento atual: {context_analysis['sentiment']}
- Nível técnico: {context_analysis['technical_level']}
- Estágio no funil: {context_analysis['funnel_stage']}
- Mensagens na conversa: {context_analysis['message_count']}

INSTRUÇÕES CONTEXTUAIS:
- Adapte seu estilo baseado no sentimento e nível técnico do cliente
- Se o sentimento for negativo, seja mais empático
- Se o nível for avançado, forneça mais detalhes técnicos
- Se estiver no estágio de compra, foque em facilitar a venda
"""
        
        # conversation history
        history_text = ""
        if conversation:
            from ..models import Message
            recent_messages = Message.objects.filter(conversation=conversation).order_by('-timestamp')[:3]
            if recent_messages:
                history_text = "\nCONVERSA RECENTE:\n" + "\n".join([
                    f"{'Cliente' if msg.message_type == 'received' else 'Vendedor'}: {msg.content}"
                    for msg in reversed(recent_messages)
                ])
        
        prompt = f"""{persona}

{contextual_info}

CATÁLOGO DE PRODUTOS:
{catalog_text}

INSTRUÇÕES ESPECÍFICAS:
- Analise a mensagem do cliente e recomende produtos adequados
- Foque em notebooks (especialmente Asus e Acer) e smartphones
- Seja natural e conversacional em português brasileiro
- Se não encontrar produto adequado, sugira alternativas
- Mantenha respostas concisas mas informativas
- Use emojis moderadamente para tornar a conversa mais amigável
{history_text}

MENSAGEM DO CLIENTE: {user_message}

SUA RESPOSTA:"""
        
        return prompt
    
    def _use_external_api(self, prompt, context_analysis, adapted_persona):
        """Use external API as fallback"""
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=self.external_api_key)
            client = genai.GenerativeModel("gemini-1.5-flash")
            
            response = client.generate_content(contents=prompt)
            
            if response.candidates and response.candidates[0].content.parts:
                return {
                    'success': True,
                    'response': response.text,
                    'model_used': 'gemini-1.5-flash',
                    'context_analysis': context_analysis,
                    'persona_adapted': adapted_persona != self._get_base_persona(),
                    'ai_source': 'external_api'
                }
            else:
                raise ValueError("No content generated from external API")
                
        except Exception as e:
            print(f"External API error: {e}")
            return {
                'success': False,
                'error': f"External API error: {str(e)}",
                'ai_source': 'external_api_failed'
            }
    
    def _get_base_persona(self):
        """Get base persona from config"""
        if self.external_persona:
            return self.external_persona
        return "Você é um assistente de vendas especializado em notebooks e smartphones. Seja útil, amigável e focado em ajudar o cliente a encontrar o produto ideal."
    
    def _format_product_catalog(self, products):
        """Format product catalog for AI prompt"""
        if not products:
            return "Nenhum produto disponível no momento."
        
        formatted_products = []
        for i, product in enumerate(products[:10]):  # limit to 10 products
            if hasattr(product, 'name'):
                formatted_products.append(
                    f"{i+1}. {product.name}\n"
                    f"   Categoria: {getattr(product, 'category', 'N/A')}\n"
                    f"   Preço: R$ {getattr(product, 'price', 'N/A')}\n"
                    f"   Descrição: {getattr(product, 'description', 'N/A')[:100]}...\n"
                )
        
        return "\n".join(formatted_products) if formatted_products else "Nenhum produto válido encontrado."
    
    def _get_fallback_response(self, user_message, product_catalog):
        """Generate rule-based fallback response"""
        user_message_lower = user_message.lower()
        
        # simple keyword matching
        if any(word in user_message_lower for word in ['notebook', 'laptop', 'computador']):
            return "Olá! Temos várias opções de notebooks disponíveis. Você tem preferência por alguma marca específica como Asus ou Acer? Qual seria seu orçamento aproximado?"
        
        elif any(word in user_message_lower for word in ['celular', 'smartphone', 'telefone']):
            return "Oi! Temos smartphones de várias marcas e faixas de preço. Você busca alguma marca específica ou tem um orçamento em mente?"
        
        elif any(word in user_message_lower for word in ['preço', 'valor', 'quanto']):
            return "Os preços variam conforme o modelo e especificações. Pode me dizer que tipo de produto você está procurando para eu dar valores mais específicos?"
        
        else:
            return "Olá! Sou seu assistente de vendas. Posso te ajudar a encontrar notebooks, smartphones e outros produtos. O que você está procurando hoje?"
    
    def get_ai_status(self):
        """Get status of all AI services"""
        status = {
            'local_ai': {
                'available': self.ollama_service.is_available(),
                'models': self.ollama_service.list_models() if self.ollama_service.is_available() else [],
                'base_url': self.ollama_service.base_url
            },
            'external_api': {
                'configured': bool(self.external_api_key),
                'provider': 'gemini' if self.external_api_key else None
            },
            'configuration': {
                'use_local_first': self.use_local_first,
                'fallback_to_api': self.fallback_to_api
            }
        }
        return status


# instantiate the hybrid service
hybrid_ai_service = HybridAIService()

# maintain backward compatibility
ai_service = hybrid_ai_service

