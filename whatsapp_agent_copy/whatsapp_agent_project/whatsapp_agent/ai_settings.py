# Configurações para IA Open-Source

# Ollama Configuration
OLLAMA_BASE_URL = 'http://localhost:11434'
OLLAMA_DEFAULT_MODEL = 'gemma2:2b'  # ou 'llama3.1:8b' em produção
OLLAMA_TIMEOUT = 30

# AI Strategy
USE_LOCAL_AI_FIRST = True  # Tenta IA local primeiro
FALLBACK_TO_API = True     # Usa API externa como fallback

# Recomendações de modelos por ambiente:
# Desenvolvimento: gemma2:2b (2GB RAM)
# Produção: llama3.1:8b (8GB RAM) ou mistral:7b (7GB RAM)
# Alta performance: llama3.1:70b (40GB+ RAM)

