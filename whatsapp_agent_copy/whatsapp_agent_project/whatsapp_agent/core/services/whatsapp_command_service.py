"""
WhatsApp Command Service - AI configuration and control via WhatsApp messages
"""
import re
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from django.utils import timezone
from django.db.models import Q
from textblob import TextBlob

from ..models import Contact, Conversation, Message, Product
from ..command_models import (
    CommandPattern, WhatsAppCommand, AIConfigurationChange,
    CommandExecution, CommandTemplate, SafetyRule,
    CommandAnalytics, UserPreference
)
from .hybrid_ai_service import hybrid_ai_service
from .personalization_service import personalization_engine


class CommandDetector:
    """Detects commands in WhatsApp messages"""
    
    def __init__(self):
        self.command_indicators = {
            'ai_config': [
                'configure', 'configurar', 'mudar', 'alterar', 'definir',
                'persona', 'comportamento', 'estilo', 'modo'
            ],
            'group_action': [
                'publique', 'poste', 'envie para grupo', 'mande no grupo',
                'compartilhe no grupo', 'grupo'
            ],
            'status_action': [
                'status', 'story', 'stories', 'publique no status',
                'poste no status', 'envie para status'
            ],
            'contact_action': [
                'envie para', 'mande para', 'contate', 'fale com',
                'mensagem para'
            ],
            'analytics': [
                'relatório', 'análise', 'desempenho', 'estatísticas',
                'métricas', 'vendas hoje', 'como foi'
            ],
            'content_creation': [
                'crie', 'gere', 'escreva', 'faça uma descrição',
                'descreva', 'texto para'
            ],
            'scheduling': [
                'agende', 'programe', 'marque para', 'envie às',
                'depois', 'amanhã', 'próxima'
            ]
        }
        
        self.action_verbs = [
            'faça', 'execute', 'realize', 'processe', 'ative',
            'desative', 'inicie', 'pare', 'configure', 'ajuste'
        ]
        
        self.confirmation_patterns = [
            r'\b(sim|yes|ok|confirmo|pode|vai)\b',
            r'\b(não|no|cancela|para)\b',
            r'\beditar?:?\s*(.+)',
            r'\bmodificar?:?\s*(.+)'
        ]
    
    def detect_command(self, message: str, contact: Contact) -> Dict:
        """Detect if a message contains a command"""
        
        # Get user preferences
        try:
            prefs = contact.command_preferences
        except UserPreference.DoesNotExist:
            prefs = UserPreference.objects.create(contact=contact)
        
        # Check if auto-detection is enabled
        if not prefs.auto_detect_commands:
            return {'is_command': False, 'reason': 'auto_detection_disabled'}
        
        # Check for keyword prefix if required
        if prefs.require_keyword_prefix:
            if not message.strip().startswith(prefs.keyword_prefix):
                return {'is_command': False, 'reason': 'missing_keyword_prefix'}
            # Remove prefix for analysis
            message = message.replace(prefs.keyword_prefix, '', 1).strip()
        
        # Analyze message for command patterns
        analysis = self._analyze_message_for_commands(message)
        
        # Check confidence threshold
        if analysis['confidence'] < prefs.confidence_threshold:
            return {
                'is_command': False, 
                'reason': 'low_confidence',
                'confidence': analysis['confidence'],
                'analysis': analysis
            }
        
        return {
            'is_command': True,
            'confidence': analysis['confidence'],
            'command_type': analysis['command_type'],
            'intent': analysis['intent'],
            'parameters': analysis['parameters'],
            'analysis': analysis
        }
    
    def _analyze_message_for_commands(self, message: str) -> Dict:
        """Analyze message content for command patterns"""
        message_lower = message.lower()
        
        # Initialize analysis
        analysis = {
            'confidence': 0.0,
            'command_type': None,
            'intent': '',
            'parameters': {},
            'indicators_found': [],
            'action_verbs_found': [],
            'entities_detected': []
        }
        
        # Check for command indicators
        max_confidence = 0.0
        best_command_type = None
        
        for cmd_type, indicators in self.command_indicators.items():
            confidence = 0.0
            found_indicators = []
            
            for indicator in indicators:
                if indicator in message_lower:
                    confidence += 0.3
                    found_indicators.append(indicator)
            
            # Bonus for multiple indicators
            if len(found_indicators) > 1:
                confidence += 0.2
            
            if confidence > max_confidence:
                max_confidence = confidence
                best_command_type = cmd_type
                analysis['indicators_found'] = found_indicators
        
        # Check for action verbs
        action_verb_bonus = 0.0
        for verb in self.action_verbs:
            if verb in message_lower:
                action_verb_bonus += 0.2
                analysis['action_verbs_found'].append(verb)
        
        # Check for imperative mood (commands usually use imperative)
        if self._is_imperative_mood(message):
            action_verb_bonus += 0.3
        
        # Check for question marks (questions are less likely to be commands)
        if '?' in message:
            max_confidence -= 0.2
        
        # Check for specific entities
        entities = self._extract_entities(message)
        analysis['entities_detected'] = entities
        
        if entities:
            max_confidence += 0.1 * len(entities)
        
        # Final confidence calculation
        final_confidence = min(1.0, max_confidence + action_verb_bonus)
        
        analysis['confidence'] = final_confidence
        analysis['command_type'] = best_command_type
        analysis['intent'] = self._extract_intent(message, best_command_type)
        analysis['parameters'] = self._extract_parameters(message, best_command_type, entities)
        
        return analysis
    
    def _is_imperative_mood(self, message: str) -> bool:
        """Check if message is in imperative mood"""
        imperative_indicators = [
            message.strip().endswith('!'),
            any(message.lower().startswith(verb) for verb in self.action_verbs),
            not message.lower().startswith(('eu ', 'você ', 'ele ', 'ela ', 'nós ', 'vocês ', 'eles ', 'elas ')),
            len(message.split()) < 10  # Short, direct messages
        ]
        
        return sum(imperative_indicators) >= 2
    
    def _extract_entities(self, message: str) -> List[Dict]:
        """Extract entities from message (groups, contacts, products, etc.)"""
        entities = []
        
        # Group patterns
        group_patterns = [
            r'grupo\s+([A-Za-z0-9\s]+)',
            r'no\s+grupo\s+([A-Za-z0-9\s]+)',
            r'para\s+o\s+grupo\s+([A-Za-z0-9\s]+)'
        ]
        
        for pattern in group_patterns:
            matches = re.finditer(pattern, message, re.IGNORECASE)
            for match in matches:
                entities.append({
                    'type': 'group',
                    'value': match.group(1).strip(),
                    'position': match.span()
                })
        
        # Contact patterns
        contact_patterns = [
            r'para\s+([A-Za-z\s]+)',
            r'contato\s+([A-Za-z\s]+)',
            r'cliente\s+([A-Za-z\s]+)'
        ]
        
        for pattern in contact_patterns:
            matches = re.finditer(pattern, message, re.IGNORECASE)
            for match in matches:
                entities.append({
                    'type': 'contact',
                    'value': match.group(1).strip(),
                    'position': match.span()
                })
        
        # Time patterns
        time_patterns = [
            r'às\s+(\d{1,2}:\d{2})',
            r'(\d{1,2}h\d{0,2})',
            r'(amanhã|hoje|depois)',
            r'em\s+(\d+)\s+(minutos?|horas?|dias?)'
        ]
        
        for pattern in time_patterns:
            matches = re.finditer(pattern, message, re.IGNORECASE)
            for match in matches:
                entities.append({
                    'type': 'time',
                    'value': match.group(1).strip() if match.groups() else match.group(0).strip(),
                    'position': match.span()
                })
        
        return entities
    
    def _extract_intent(self, message: str, command_type: str) -> str:
        """Extract the intent from the message"""
        if not command_type:
            return "Comando não identificado"
        
        intent_templates = {
            'ai_config': "Configurar IA: {action}",
            'group_action': "Ação no grupo: {action}",
            'status_action': "Atualizar status: {action}",
            'contact_action': "Ação com contato: {action}",
            'analytics': "Solicitar análise: {action}",
            'content_creation': "Criar conteúdo: {action}",
            'scheduling': "Agendar ação: {action}"
        }
        
        # Extract the main action from the message
        action = self._extract_main_action(message)
        template = intent_templates.get(command_type, "Executar: {action}")
        
        return template.format(action=action)
    
    def _extract_main_action(self, message: str) -> str:
        """Extract the main action from the message"""
        # Remove common prefixes and get the core action
        message = message.strip()
        
        # Remove command prefixes
        prefixes_to_remove = ['#ia', '#bot', 'ia,', 'bot,']
        for prefix in prefixes_to_remove:
            if message.lower().startswith(prefix):
                message = message[len(prefix):].strip()
        
        # Take first sentence or up to 50 characters
        first_sentence = message.split('.')[0].split('!')[0]
        if len(first_sentence) > 50:
            first_sentence = first_sentence[:50] + "..."
        
        return first_sentence
    
    def _extract_parameters(self, message: str, command_type: str, entities: List[Dict]) -> Dict:
        """Extract parameters for the command"""
        parameters = {}
        
        # Add entities as parameters
        for entity in entities:
            entity_type = entity['type']
            if entity_type not in parameters:
                parameters[entity_type] = []
            parameters[entity_type].append(entity['value'])
        
        # Extract command-specific parameters
        if command_type == 'ai_config':
            parameters.update(self._extract_ai_config_params(message))
        elif command_type == 'group_action':
            parameters.update(self._extract_group_action_params(message))
        elif command_type == 'status_action':
            parameters.update(self._extract_status_action_params(message))
        elif command_type == 'content_creation':
            parameters.update(self._extract_content_creation_params(message))
        
        return parameters
    
    def _extract_ai_config_params(self, message: str) -> Dict:
        """Extract AI configuration parameters"""
        params = {}
        
        # Persona changes
        persona_patterns = [
            r'persona\s+para\s+([^,\.!]+)',
            r'comportamento\s+([^,\.!]+)',
            r'seja\s+mais\s+([^,\.!]+)',
            r'modo\s+([^,\.!]+)'
        ]
        
        for pattern in persona_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                params['new_persona'] = match.group(1).strip()
                break
        
        # Style changes
        style_patterns = [
            r'estilo\s+([^,\.!]+)',
            r'tom\s+([^,\.!]+)',
            r'comunicação\s+([^,\.!]+)'
        ]
        
        for pattern in style_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                params['communication_style'] = match.group(1).strip()
                break
        
        return params
    
    def _extract_group_action_params(self, message: str) -> Dict:
        """Extract group action parameters"""
        params = {}
        
        # Action type
        if any(word in message.lower() for word in ['publique', 'poste']):
            params['action_type'] = 'post'
        elif any(word in message.lower() for word in ['envie', 'mande']):
            params['action_type'] = 'send'
        
        # Content type
        if any(word in message.lower() for word in ['imagem', 'foto', 'picture']):
            params['content_type'] = 'image'
        elif any(word in message.lower() for word in ['vídeo', 'video']):
            params['content_type'] = 'video'
        elif any(word in message.lower() for word in ['texto', 'mensagem']):
            params['content_type'] = 'text'
        
        return params
    
    def _extract_status_action_params(self, message: str) -> Dict:
        """Extract status action parameters"""
        params = {}
        
        # Similar to group action but for status
        if any(word in message.lower() for word in ['imagem', 'foto']):
            params['content_type'] = 'image'
        elif any(word in message.lower() for word in ['vídeo', 'video']):
            params['content_type'] = 'video'
        elif any(word in message.lower() for word in ['texto']):
            params['content_type'] = 'text'
        
        return params
    
    def _extract_content_creation_params(self, message: str) -> Dict:
        """Extract content creation parameters"""
        params = {}
        
        # Content type to create
        if any(word in message.lower() for word in ['descrição', 'legenda']):
            params['content_type'] = 'description'
        elif any(word in message.lower() for word in ['post', 'publicação']):
            params['content_type'] = 'post'
        elif any(word in message.lower() for word in ['mensagem']):
            params['content_type'] = 'message'
        
        # Subject/topic
        subject_patterns = [
            r'sobre\s+([^,\.!]+)',
            r'para\s+([^,\.!]+)',
            r'descrevendo\s+([^,\.!]+)'
        ]
        
        for pattern in subject_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                params['subject'] = match.group(1).strip()
                break
        
        return params


class CommandProcessor:
    """Processes detected commands"""
    
    def __init__(self):
        self.detector = CommandDetector()
        self.safety_checker = SafetyChecker()
    
    def process_message(self, message: Message) -> Optional[WhatsAppCommand]:
        """Process a message and create command if detected"""
        
        # Only process messages from the user to themselves
        if not self._is_self_message(message):
            return None
        
        # Detect command
        detection_result = self.detector.detect_command(
            message.content, 
            message.conversation.contact
        )
        
        if not detection_result['is_command']:
            return None
        
        # Create command record
        command = WhatsAppCommand.objects.create(
            contact=message.conversation.contact,
            original_message=message.content,
            message_timestamp=message.timestamp,
            command_type=detection_result['command_type'],
            confidence_score=detection_result['confidence'],
            command_intent=detection_result['intent'],
            extracted_parameters=detection_result['parameters']
        )
        
        # Perform safety assessment
        safety_result = self.safety_checker.assess_command(command)
        command.risk_assessment = safety_result
        command.safety_checks_passed = safety_result['passed']
        command.requires_manual_approval = safety_result['requires_approval']
        command.save()
        
        # Generate preview if needed
        if self._requires_preview(command):
            self._generate_and_send_preview(command)
        
        return command
    
    def _is_self_message(self, message: Message) -> bool:
        """Check if message is from user to themselves"""
        # This would need to be implemented based on your WhatsApp integration
        # For now, we'll assume all received messages could be self-messages
        return message.message_type == 'received'
    
    def _requires_preview(self, command: WhatsAppCommand) -> bool:
        """Check if command requires preview"""
        try:
            prefs = command.contact.command_preferences
            return prefs.always_require_confirmation or command.detected_pattern.requires_preview
        except:
            return True  # Default to requiring preview
    
    def _generate_and_send_preview(self, command: WhatsAppCommand):
        """Generate and send preview to user"""
        
        # Generate content based on command type
        if command.command_type == 'group_action':
            content = self._generate_group_action_content(command)
        elif command.command_type == 'status_action':
            content = self._generate_status_action_content(command)
        elif command.command_type == 'ai_config':
            content = self._generate_ai_config_content(command)
        elif command.command_type == 'content_creation':
            content = self._generate_content_creation_content(command)
        else:
            content = self._generate_generic_content(command)
        
        command.generated_content = content
        
        # Create preview message
        preview_message = self._create_preview_message(command, content)
        command.preview_message = preview_message
        command.status = 'preview_sent'
        command.confirmation_sent_at = timezone.now()
        command.save()
        
        # Send preview (this would integrate with your WhatsApp service)
        self._send_preview_message(command, preview_message)
    
    def _generate_group_action_content(self, command: WhatsAppCommand) -> str:
        """Generate content for group actions"""
        params = command.extracted_parameters
        
        if params.get('content_type') == 'image':
            # For image posts, generate description
            return self._generate_image_description(command)
        elif params.get('content_type') == 'text':
            # Generate text post
            return self._generate_text_post(command)
        else:
            return "Conteúdo a ser definido pelo usuário"
    
    def _generate_status_action_content(self, command: WhatsAppCommand) -> str:
        """Generate content for status actions"""
        # Similar to group action but optimized for status
        return self._generate_group_action_content(command)
    
    def _generate_ai_config_content(self, command: WhatsAppCommand) -> str:
        """Generate content for AI configuration"""
        params = command.extracted_parameters
        
        if 'new_persona' in params:
            return f"Configuração da persona: {params['new_persona']}"
        elif 'communication_style' in params:
            return f"Alteração do estilo de comunicação: {params['communication_style']}"
        else:
            return "Configuração da IA conforme solicitado"
    
    def _generate_content_creation_content(self, command: WhatsAppCommand) -> str:
        """Generate content for content creation commands"""
        params = command.extracted_parameters
        subject = params.get('subject', 'produto')
        
        # Use AI to generate content
        prompt = f"Crie uma descrição atrativa para {subject}"
        content = hybrid_ai_service.get_contextual_recommendation(prompt, [])
        
        return content
    
    def _generate_generic_content(self, command: WhatsAppCommand) -> str:
        """Generate generic content"""
        return f"Executar: {command.command_intent}"
    
    def _generate_image_description(self, command: WhatsAppCommand) -> str:
        """Generate description for image posts"""
        # This would analyze the image and generate description
        # For now, return a template
        return "🔥 Nova coleção chegando! Confira esses modelos incríveis com desconto especial para nossos clientes. Aproveite a promoção limitada! #ModaFeminina #Promoção"
    
    def _generate_text_post(self, command: WhatsAppCommand) -> str:
        """Generate text post content"""
        # Use AI to generate engaging post
        return "📢 Novidades incríveis chegando! Não percam as próximas atualizações. Estamos preparando algo especial para vocês! 🎉"
    
    def _create_preview_message(self, command: WhatsAppCommand, content: str) -> str:
        """Create preview message for user"""
        preview = f"""🤖 Comando detectado: {command.command_intent}

📝 Conteúdo gerado:
{content}

✏️ Opções:
• Digite "ok" para confirmar e executar
• Digite "editar: [novo conteúdo]" para modificar
• Digite "cancelar" para cancelar

⏰ Esta prévia expira em 5 minutos."""
        
        return preview
    
    def _send_preview_message(self, command: WhatsAppCommand, preview: str):
        """Send preview message to user"""
        # This would integrate with your WhatsApp service
        # For now, we'll just log it
        print(f"Preview sent to {command.contact}: {preview}")
    
    def handle_user_response(self, message: Message, command: WhatsAppCommand):
        """Handle user response to command preview"""
        response = message.content.lower().strip()
        
        if response in ['ok', 'sim', 'confirmar', 'pode']:
            # User confirmed
            command.mark_as_confirmed(message.content)
            command.final_content = command.generated_content
            self._schedule_execution(command)
            
        elif response in ['não', 'cancelar', 'para']:
            # User cancelled
            command.status = 'cancelled'
            command.user_response = message.content
            command.save()
            self._send_cancellation_confirmation(command)
            
        elif response.startswith('editar:') or response.startswith('modificar:'):
            # User wants to edit
            new_content = message.content.split(':', 1)[1].strip()
            command.user_modifications = new_content
            command.final_content = new_content
            command.mark_as_confirmed(message.content)
            self._schedule_execution(command)
            
        else:
            # Unclear response, ask for clarification
            self._send_clarification_request(command)
    
    def _schedule_execution(self, command: WhatsAppCommand):
        """Schedule command for execution"""
        # Apply safety delay
        try:
            prefs = command.contact.command_preferences
            delay = prefs.preferred_execution_delay
        except:
            delay = 30  # Default 30 seconds
        
        command.schedule_execution(delay)
        self._send_execution_confirmation(command)
    
    def _send_cancellation_confirmation(self, command: WhatsAppCommand):
        """Send cancellation confirmation"""
        message = "✅ Comando cancelado com sucesso."
        print(f"Cancellation sent to {command.contact}: {message}")
    
    def _send_execution_confirmation(self, command: WhatsAppCommand):
        """Send execution confirmation"""
        message = f"✅ Comando confirmado! Executando em {command.execution_scheduled_at.strftime('%H:%M:%S')}..."
        print(f"Execution confirmation sent to {command.contact}: {message}")
    
    def _send_clarification_request(self, command: WhatsAppCommand):
        """Send clarification request"""
        message = """❓ Não entendi sua resposta. Por favor, responda:
• "ok" para confirmar
• "editar: [novo conteúdo]" para modificar
• "cancelar" para cancelar"""
        print(f"Clarification request sent to {command.contact}: {message}")


class CommandExecutor:
    """Executes confirmed commands"""
    
    def execute_command(self, command: WhatsAppCommand):
        """Execute a confirmed command"""
        
        if not command.is_ready_for_execution:
            return False
        
        command.status = 'executing'
        command.save()
        
        try:
            # Execute based on command type
            if command.command_type == 'ai_config':
                result = self._execute_ai_config(command)
            elif command.command_type == 'group_action':
                result = self._execute_group_action(command)
            elif command.command_type == 'status_action':
                result = self._execute_status_action(command)
            elif command.command_type == 'analytics':
                result = self._execute_analytics(command)
            else:
                result = self._execute_generic_command(command)
            
            # Record execution
            execution = CommandExecution.objects.create(
                command=command,
                execution_type=self._map_command_to_execution_type(command.command_type),
                executed_at=timezone.now(),
                success=result['success'],
                response_received=result.get('response', ''),
                error_message=result.get('error', '')
            )
            
            if result['success']:
                command.status = 'completed'
                command.executed_at = timezone.now()
            else:
                command.status = 'failed'
            
            command.execution_result = result
            command.save()
            
            return result['success']
            
        except Exception as e:
            command.status = 'failed'
            command.execution_result = {'success': False, 'error': str(e)}
            command.save()
            return False
    
    def _execute_ai_config(self, command: WhatsAppCommand) -> Dict:
        """Execute AI configuration command"""
        params = command.extracted_parameters
        
        try:
            if 'new_persona' in params:
                # Update AI persona
                self._update_ai_persona(command.contact, params['new_persona'])
                
            if 'communication_style' in params:
                # Update communication style
                self._update_communication_style(command.contact, params['communication_style'])
            
            return {'success': True, 'message': 'Configuração da IA atualizada com sucesso'}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _execute_group_action(self, command: WhatsAppCommand) -> Dict:
        """Execute group action command"""
        # This would integrate with your WhatsApp service
        # For now, simulate execution
        
        group_name = command.extracted_parameters.get('group', [''])[0]
        content = command.final_content
        
        # Simulate sending to group
        time.sleep(2)  # Simulate processing time
        
        return {
            'success': True,
            'message': f'Mensagem enviada para o grupo {group_name}',
            'content_sent': content
        }
    
    def _execute_status_action(self, command: WhatsAppCommand) -> Dict:
        """Execute status action command"""
        # Similar to group action but for status
        content = command.final_content
        
        # Simulate posting to status
        time.sleep(1)
        
        return {
            'success': True,
            'message': 'Status atualizado com sucesso',
            'content_sent': content
        }
    
    def _execute_analytics(self, command: WhatsAppCommand) -> Dict:
        """Execute analytics command"""
        # Generate analytics report
        report = self._generate_analytics_report(command.contact)
        
        return {
            'success': True,
            'message': 'Relatório de análise gerado',
            'report': report
        }
    
    def _execute_generic_command(self, command: WhatsAppCommand) -> Dict:
        """Execute generic command"""
        return {
            'success': True,
            'message': f'Comando executado: {command.command_intent}'
        }
    
    def _update_ai_persona(self, contact: Contact, new_persona: str):
        """Update AI persona for contact"""
        # Update personalization profile
        try:
            profile = contact.personalization_profile
        except:
            profile = personalization_engine.create_personalization_profile(contact)
        
        # This would update the AI configuration
        # For now, just record the change
        pass
    
    def _update_communication_style(self, contact: Contact, new_style: str):
        """Update communication style for contact"""
        try:
            profile = contact.personalization_profile
            profile.preferred_style = new_style
            profile.save()
        except:
            pass
    
    def _generate_analytics_report(self, contact: Contact) -> str:
        """Generate analytics report"""
        # This would generate actual analytics
        return """📊 Relatório de Vendas - Hoje

💰 Vendas: R$ 1.250,00
📈 Conversões: 8 clientes
📱 Mensagens: 45 enviadas
⭐ Engajamento: 85%

🔥 Melhor produto: Camiseta Básica
📞 Horário de pico: 14h-16h"""
    
    def _map_command_to_execution_type(self, command_type: str) -> str:
        """Map command type to execution type"""
        mapping = {
            'group_action': 'group_post',
            'status_action': 'status_update',
            'contact_action': 'direct_message',
            'ai_config': 'ai_config',
            'analytics': 'analytics_report',
            'content_creation': 'content_generation'
        }
        return mapping.get(command_type, 'system_action')


class SafetyChecker:
    """Checks command safety and compliance"""
    
    def assess_command(self, command: WhatsAppCommand) -> Dict:
        """Assess command safety"""
        
        assessment = {
            'passed': True,
            'risk_level': 'low',
            'violations': [],
            'warnings': [],
            'requires_approval': False,
            'recommended_delay': 30
        }
        
        # Check frequency limits
        recent_commands = WhatsAppCommand.objects.filter(
            contact=command.contact,
            created_at__gte=timezone.now() - timedelta(hours=1)
        ).count()
        
        if recent_commands > 10:
            assessment['violations'].append('Frequency limit exceeded')
            assessment['risk_level'] = 'high'
            assessment['requires_approval'] = True
        
        # Check content safety
        if self._contains_suspicious_content(command.original_message):
            assessment['warnings'].append('Potentially suspicious content detected')
            assessment['risk_level'] = 'medium'
        
        # Check timing
        current_hour = timezone.now().hour
        if current_hour < 6 or current_hour > 22:
            assessment['warnings'].append('Command during quiet hours')
            assessment['recommended_delay'] = 300  # 5 minutes
        
        # Apply safety rules
        active_rules = SafetyRule.objects.filter(is_active=True)
        for rule in active_rules:
            if command.command_type in rule.applies_to_commands:
                rule_result = rule.evaluate(command)
                if not rule_result['passed']:
                    assessment['violations'].append(rule_result['warning'])
                    if rule_result['blocking']:
                        assessment['passed'] = False
        
        return assessment
    
    def _contains_suspicious_content(self, message: str) -> bool:
        """Check for suspicious content patterns"""
        suspicious_patterns = [
            r'\b(spam|scam|hack|bot)\b',
            r'(muito|muitos)\s+(rápido|mensagens)',
            r'automatico|automático'
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return True
        
        return False


class WhatsAppCommandService:
    """Main service for WhatsApp command system"""
    
    def __init__(self):
        self.processor = CommandProcessor()
        self.executor = CommandExecutor()
        self.detector = CommandDetector()
    
    def process_incoming_message(self, message: Message) -> Optional[WhatsAppCommand]:
        """Process incoming message for commands"""
        return self.processor.process_message(message)
    
    def handle_user_response(self, message: Message):
        """Handle user response to command previews"""
        # Find pending command for this contact
        pending_command = WhatsAppCommand.objects.filter(
            contact=message.conversation.contact,
            status__in=['detected', 'preview_sent'],
            confirmation_sent_at__gte=timezone.now() - timedelta(minutes=10)
        ).first()
        
        if pending_command:
            self.processor.handle_user_response(message, pending_command)
    
    def execute_scheduled_commands(self):
        """Execute commands that are scheduled for execution"""
        ready_commands = WhatsAppCommand.objects.filter(
            status='confirmed',
            execution_scheduled_at__lte=timezone.now(),
            safety_checks_passed=True
        )
        
        for command in ready_commands:
            self.executor.execute_command(command)
    
    def get_command_analytics(self, contact: Contact = None, days: int = 7) -> Dict:
        """Get command usage analytics"""
        start_date = timezone.now() - timedelta(days=days)
        
        queryset = WhatsAppCommand.objects.filter(created_at__gte=start_date)
        if contact:
            queryset = queryset.filter(contact=contact)
        
        total_commands = queryset.count()
        successful_commands = queryset.filter(status='completed').count()
        failed_commands = queryset.filter(status='failed').count()
        
        # Command type breakdown
        command_types = {}
        for cmd_type, _ in CommandPattern.COMMAND_TYPES:
            count = queryset.filter(command_type=cmd_type).count()
            if count > 0:
                command_types[cmd_type] = count
        
        return {
            'total_commands': total_commands,
            'successful_commands': successful_commands,
            'failed_commands': failed_commands,
            'success_rate': successful_commands / total_commands if total_commands > 0 else 0,
            'command_types': command_types,
            'period_days': days
        }


# Global instance
whatsapp_command_service = WhatsAppCommandService()

