from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
import os

@csrf_exempt
def whatsapp_webhook_trigger(request):
    """
    Secure endpoint to trigger WhatsApp messages from GitHub Actions.
    Protection: X-Trigger-Token header.
    """
    token = os.environ.get("TRIGGER_TOKEN")
    header_token = request.headers.get("X-Trigger-Token")

    if not token or header_token != token:
        return HttpResponseForbidden("Invalid token")

    # Handle parameters (GET or POST)
    params = request.POST if request.method == "POST" else request.GET
    if not params:
        params = request.GET if request.GET else request.POST

    action = params.get("action")
    target_jid = params.get("jid")  # The group ID
    message = params.get("message")

    # TODO: Initialize your service and use case here
    # svc = EvolutionWhatsAppService()
    # use_case = YourUseCase(svc)
    # success = use_case.execute(target_jid, message)

    return JsonResponse({"status": "received", "action": action})
