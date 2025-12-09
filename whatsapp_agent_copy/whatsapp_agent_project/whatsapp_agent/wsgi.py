"""
wsgi config for whatsapp_agent project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'whatsapp_agent.settings')

application = get_wsgi_application()
