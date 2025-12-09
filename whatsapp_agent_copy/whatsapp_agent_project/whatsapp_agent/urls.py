"""
whatsapp_agent URL configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect

def redirect_to_login(request):
    return redirect('admin:login')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('whatsapp_agent.core.urls')),  # include core app urls
    path('api/', include('whatsapp_agent.core.api_urls')),  # API for microservice
    path('accounts/login/', auth_views.LoginView.as_view(template_name='admin/login.html'), name='login'),
]

# serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
