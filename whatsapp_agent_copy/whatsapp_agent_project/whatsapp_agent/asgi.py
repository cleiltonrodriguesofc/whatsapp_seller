"""
asgi config for whatsapp_agent project.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'whatsapp_agent.settings')

application = get_asgi_application()
