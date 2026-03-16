import os

class SendDailyGreetingUseCase:
    """Template for sending greetings or scheduled messages."""
    def __init__(self, whatsapp_svc):
        self.whatsapp_svc = whatsapp_svc

    def execute(self, group_jid: str, message: str):
        if not group_jid:
            raise ValueError("Group JID is required")
        
        return self.whatsapp_svc.send_group_text(group_jid, message)

class SalesAgentCampaignUseCase:
    """Template for a sales agent sending product links."""
    def __init__(self, whatsapp_svc):
        self.whatsapp_svc = whatsapp_svc

    def execute(self, group_jid: str, product_name: str, link: str):
        message = (
            f"🚀 *CAMPANHA DO DIA* 🚀\n\n"
            f"Confira nosso novo produto: *{product_name}*\n"
            f"Acesse agora: {link}\n\n"
            f"Aproveite a oferta! 📢"
        )
        return self.whatsapp_svc.send_group_text(group_jid, message)
