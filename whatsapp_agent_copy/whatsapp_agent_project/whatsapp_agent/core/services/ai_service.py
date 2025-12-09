"""
ai_service.py - Integration with Google Gemini AI for product recommendations (Updated for AIConfig)
"""
import os
import google.generativeai as genai
from django.conf import settings
from ..models import AIConfig # Import the new AIConfig model

class AIService:
    """Service for interacting with Google Gemini AI using the latest Client approach"""
    
    DEFAULT_PERSONA = "You are a helpful sales assistant. Analyze the user message and product catalog to provide relevant recommendations in Portuguese (Brazil)."

    def __init__(self):
        """Initialize the AI service placeholders and load initial config"""
        self.api_key = None
        self.client = None
        self.is_configured_flag = False # Renamed to avoid conflict with method
        self.model_name = "gemini-1.5-flash" # Default model
        self.persona_prompt = self.DEFAULT_PERSONA # Initialize with default
        self._load_config() # Load config on initialization

    def _load_config(self):
        """Loads the API key and persona prompt from the active AIConfig or falls back"""
        active_config = None
        db_key = None
        db_persona = None
        
        # 1. Try to get config from the active AIConfig in the database
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

        # 2. Set API Key (DB > Settings/Env > None)
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

        # 3. Set Persona Prompt (DB > Default)
        self.persona_prompt = db_persona if db_persona else self.DEFAULT_PERSONA
        if self.persona_prompt == self.DEFAULT_PERSONA:
             print("Using default Persona Prompt.")

        # Initialize the client with the determined key (or None)
        self._initialize_client()

    def _initialize_client(self):
        """Initializes the genai client if api key is present"""
        if self.api_key:
            try:
                # Configure globally with your API key
                genai.configure(api_key=self.api_key)
                # Instantiate the client with the model name ONLY (no api_key here!)
                self.client = genai.GenerativeModel(self.model_name)
                self.is_configured_flag = True
                print(f"Gemini client initialized successfully for model {self.model_name} with key ending in ...{self.api_key[-4:]}")
            except Exception as e:
                print(f"Failed to initialize Gemini client: {e}")
                self.is_configured_flag = False
                self.client = None # Ensure client is None on failure
        else:
            print("Gemini client initialization skipped: No API key provided.")
            self.is_configured_flag = False
            self.client = None


    def is_configured(self):
        """Returns true if the client is initialized and ready"""
        return self.is_configured_flag

    def reconfigure(self):
        """Public method to reload configuration and re-initialize client"""
        print("Reconfiguring AI Service...")
        self._load_config()

    def get_product_recommendation(self, user_message, product_catalog, conversation_history=None, contact=None):
        """
        Get product recommendations based on user message and product catalog
        
        Args:
            user_message (str): The user's message/query
            product_catalog (list): List of Product objects
            conversation_history (list, optional): Previous conversation messages
            contact (Contact, optional): Contact object for personalized AI behavior
            
        Returns:
            dict: Response containing recommendation and explanation
        """
        if not self.is_configured(): # Use the method here
            return {
                'success': False,
                'error': 'AI Service not configured. Check API Key in AI Configuration or settings.py.',
                'fallback_response': self._get_fallback_response(user_message, product_catalog)
            }
        
        try:
            # Create context with product catalog
            catalog_context = self._format_product_catalog(product_catalog)
            
            # Format conversation history if provided
            history_context = ""
            if conversation_history:
                history_context = "\n\nPrevious conversation:\n" + "\n".join([
                    f"{'User' if msg['message_type'] == 'received' else 'Agent'}: {msg['content']}"
                    for msg in conversation_history[-5:]  # Last 5 messages for context
                ])
            
            # Determine which persona to use (contact-specific or global)
            persona_to_use = self.persona_prompt  # Default to global persona
            
            # Check if contact has a custom persona defined
            if contact and hasattr(contact, 'persona_prompt') and contact.persona_prompt:
                persona_to_use = contact.persona_prompt
                print(f"Using contact-specific persona for {contact.name if contact.name else contact.phone_number}")
            
            # Create the prompt using the selected persona
            prompt = f"""{persona_to_use}

PRODUCT CATALOG:
{catalog_context}

INSTRUCTIONS (Apply these in addition to your main persona):
- Analyze the user's message and recommend suitable products from the catalog.
- If the persona doesn't specify, focus on notebooks (especially Asus and Acer models with at least i3 processor and 4GB RAM) and smartphones.
- Pay attention to the user's preferences and budget constraints mentioned.
- If the user's request is unclear, ask clarifying questions.
- If no suitable product is found, suggest alternatives or ask for more information.
- Be friendly, helpful, and conversational.
- Respond in Portuguese (Brazil) unless the persona dictates otherwise.
- Format your response in a natural, conversational way.
{history_context}

User's message: {user_message}

Your response:"""

            # Generate response from Gemini using the client
            response = self.client.generate_content(contents=prompt)
            
            # Check for potential safety blocks or empty responses
            if not response.candidates or not response.candidates[0].content.parts:
                 # Check for prompt feedback if available
                 prompt_feedback = getattr(response, 'prompt_feedback', None)
                 block_reason = getattr(prompt_feedback, 'block_reason', 'Unknown') if prompt_feedback else 'Unknown'
                 print(f"Warning: AI content generation potentially blocked or empty. Reason: {block_reason}")
                 # Raise a more specific error or return fallback
                 # For now, let's return a generic error and fallback
                 raise ValueError(f"No content generated, potentially blocked (Reason: {block_reason}) or empty response.")

            generated_text = response.text # Accessing text directly is usually correct

            return {
                'success': True,
                'response': generated_text,
                'model_used': self.client.model_name # Get model name from client instance
            }
            
        except Exception as e:
            print(f"Error calling Gemini API: {e}") 
            return {
                'success': False,
                'error': str(e),
                'fallback_response': self._get_fallback_response(user_message, product_catalog)
            }
    
    def _format_product_catalog(self, products):
        """Format product catalog for the AI prompt"""
        formatted_catalog = []
        
        # Ensure products is iterable and contains objects with expected attributes
        if not hasattr(products, '__iter__'):
            print("Warning: product_catalog is not iterable in _format_product_catalog")
            return "No product information available."
            
        for i, product in enumerate(products):
            # Check if product is a valid object before accessing attributes
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
        
        # Ensure product_catalog is iterable
        if not hasattr(product_catalog, '__iter__'):
             print("Warning: product_catalog is not iterable in _get_fallback_response")
             product_catalog = [] # Default to empty list to avoid errors
             
        # Check for notebook keywords
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
        
        # Check for smartphone keywords
        if any(keyword in user_message for keyword in ['celular', 'smartphone', 'telefone', 'iphone', 'samsung']):
            smartphones = [p for p in product_catalog if p and getattr(p, 'category', '').lower() in ['smartphone', 'celular', 'telefone']]
            if smartphones:
                return f"Temos {len(smartphones)} opções de smartphones disponíveis. Você busca alguma marca específica ou tem um orçamento em mente?"
        
        return "Olá! Sou o assistente de vendas da loja. Posso te ajudar a encontrar notebooks (especialmente Asus e Acer) e smartphones. O que você está procurando hoje?"

# Instantiate the service globally for use in views
# The configuration will be loaded on first import
ai_service = AIService()

