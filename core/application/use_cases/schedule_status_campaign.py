from typing import List, Optional
from datetime import datetime
from core.application.repositories import StatusCampaignRepository
from core.application.interfaces import AIService
from core.domain.entities import StatusCampaign, StatusItem, StatusCampaignStatus


class ScheduleStatusCampaign:
    """
    Use case to schedule a Status Campaign for immediate or future sending.
    Supports AI generation for captions.
    """

    def __init__(
        self,
        repository: StatusCampaignRepository,
        ai_service: Optional[AIService] = None,
    ):
        self.repository = repository
        self.ai_service = ai_service

    async def execute(
        self,
        user_id: int,
        title: str,
        items_data: List[dict],
        scheduled_at: Optional[datetime] = None,
        is_recurring: bool = False,
        recurrence_days: Optional[str] = None,
        send_time: Optional[str] = None,
        use_ai: bool = False,
        campaign_id: Optional[int] = None,
        instance_id: Optional[int] = None,
    ) -> StatusCampaign:

        # 1. Prepare items and optionally use AI for captions
        items = []
        for item_data in items_data:
            caption = item_data.get("caption")

            if not caption and use_ai and self.ai_service:
                # Generate simple AI caption if missing
                prompt = f"Crie uma legenda curta e vendedora para um status de WhatsApp. O foco é: {title}."
                if item_data.get("price"):
                    prompt += f" Preço: R$ {item_data['price']}"
                caption = await self.ai_service.chat(prompt)

            items.append(
                StatusItem(
                    image_url=item_data["image_url"],
                    caption=caption,
                    link=item_data.get("link"),
                    price=item_data.get("price"),
                )
            )

        # 2. Determine Status
        # If scheduled_at is now or None, and it's not recurring, it might be "PENDING" for immediate pick up
        # or we just mark as SCHEDULED and let the worker pick it up.
        status = StatusCampaignStatus.SCHEDULED

        if campaign_id:
            campaign = self.repository.get_by_id(campaign_id, user_id=user_id)
            if not campaign:
                raise ValueError(f"Status Campaign {campaign_id} not found")

            campaign.title = title
            campaign.items = items
            campaign.scheduled_at = scheduled_at or datetime.utcnow()
            campaign.is_recurring = is_recurring
            campaign.recurrence_days = recurrence_days
            campaign.send_time = send_time
            campaign.status = status
            campaign.instance_id = instance_id
        else:
            campaign = StatusCampaign(
                user_id=user_id,
                title=title,
                items=items,
                scheduled_at=scheduled_at or datetime.utcnow(),
                is_recurring=is_recurring,
                recurrence_days=recurrence_days,
                send_time=send_time,
                status=status,
                instance_id=instance_id,
            )

        return self.repository.save(campaign)
