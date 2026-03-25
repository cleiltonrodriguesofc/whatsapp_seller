from typing import List, Optional
from datetime import datetime
from core.application.repositories import StatusCampaignRepository
from core.domain.entities import StatusCampaign, StatusItem, StatusCampaignStatus


class SaveStatusCampaignDraft:
    """
    Use case to save or update a Status Campaign draft.
    Supports auto-saving and manual draft creation.
    """

    def __init__(self, repository: StatusCampaignRepository):
        self.repository = repository

    async def execute(
        self,
        user_id: int,
        title: str,
        items_data: List[dict],  # List of {image_url, caption, link, price}
        campaign_id: Optional[int] = None,
        instance_id: Optional[int] = None,
    ) -> StatusCampaign:
        # Convert dict items to StatusItem entities
        items = [
            StatusItem(
                image_url=item["image_url"],
                caption=item.get("caption"),
                link=item.get("link"),
                price=item.get("price"),
            )
            for item in items_data
        ]

        if campaign_id:
            # Update existing draft
            campaign = self.repository.get_by_id(campaign_id, user_id=user_id)
            if not campaign:
                raise ValueError(f"Status Campaign {campaign_id} not found")
            
            campaign.title = title
            campaign.items = items
            campaign.instance_id = instance_id
            # Keep status as DRAFT or current status if already scheduled but being edited
        else:
            # Create new draft
            campaign = StatusCampaign(
                user_id=user_id,
                title=title,
                items=items,
                instance_id=instance_id,
                status=StatusCampaignStatus.DRAFT,
            )

        return self.repository.save(campaign)
