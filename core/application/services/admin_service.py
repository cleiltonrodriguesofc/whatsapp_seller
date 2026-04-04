from typing import List, Optional
from core.domain.entities import User, ActivityLog
from core.application.repositories import UserRepository, ActivityRepository

class AdminService:
    def __init__(self, user_repo: UserRepository, activity_repo: ActivityRepository):
        self.user_repo = user_repo
        self.activity_repo = activity_repo

    def list_users(self) -> List[User]:
        return self.user_repo.list_all()

    def toggle_user_active(self, user_id: int) -> Optional[User]:
        user = self.user_repo.get_by_id(user_id)
        if user:
            user.is_active = not user.is_active
            return self.user_repo.save(user)
        return None

    def list_activities(self, limit: int = 100, user_id: Optional[int] = None) -> List[ActivityLog]:
        return self.activity_repo.list_all(limit=limit, user_id=user_id)

    def log_activity(self, user_id: int, event_type: str, description: str):
        activity = ActivityLog(
            user_id=user_id,
            event_type=event_type,
            description=description
        )
        return self.activity_repo.save(activity)
