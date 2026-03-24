from datetime import datetime
from typing import List, Optional
from core.application.interfaces import NotificationService, AIService
from core.application.repositories import CampaignRepository, ProductRepository
from core.domain.entities import Campaign, CampaignStatus


class ScheduleCampaign:
    """
    Use case to schedule a marketing campaign.
    """

    def __init__(
        self,
        campaign_repo: CampaignRepository,
        product_repo: ProductRepository,
        notification_service: NotificationService,
        ai_service: Optional[AIService] = None,
    ):
        self.campaign_repo = campaign_repo
        self.product_repo = product_repo
        self.notification_service = notification_service
        self.ai_service = ai_service

    async def execute(
        self,
        title: str,
        product_id: int,
        target_groups: List[str],
        scheduled_at: Optional[datetime],
        custom_message: Optional[str] = None,
        is_recurring: bool = False,
        recurrence_days: Optional[str] = None,
        send_time: Optional[str] = None,
        use_ai: bool = True,
        user_id: Optional[int] = None,
        instance_id: Optional[int] = None,
        save_as_draft: bool = False,
    ) -> Campaign:
        # 1. Fetch Product
        product = self.product_repo.get_by_id(product_id)
        if not product:
            raise ValueError(f"Product with ID {product_id} not found")

        # 2. Generate Message Copy (Optional — skip for drafts to save time)
        message_copy = custom_message
        if not message_copy and use_ai and self.ai_service and not save_as_draft:
            prompt = (
                f"Crie uma mensagem persuasiva de vendas para o WhatsApp para o produto: {product.name}. "
                f"Descrição: {product.description}. Preço: R$ {product.price:.2f}. "
                f"Link: {product.affiliate_link}. "
                "Use emojis, bullet points e uma chamada para ação clara. Mantenha um tom amigável e profissional."
            )
            message_copy = await self.ai_service.chat(prompt)

        # 3. Create Campaign Entity
        status = CampaignStatus.DRAFT if save_as_draft else CampaignStatus.SCHEDULED
        campaign = Campaign(
            title=title,
            product=product,
            target_groups=target_groups,
            scheduled_at=scheduled_at or datetime.now(),
            status=status,
            custom_message=message_copy,
            user_id=user_id,
            instance_id=instance_id,
            is_recurring=is_recurring,
            recurrence_days=recurrence_days,
            send_time=send_time,
            is_ai_generated=use_ai,
        )

        # 4. Save to Repository
        return self.campaign_repo.save(campaign)
