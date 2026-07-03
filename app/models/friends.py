from pydantic import BaseModel


class UserSearchResult(BaseModel):
    user_id: str
    display_name: str
    avatar_id: str | None = None
    avatar_color_id: str | None = None
    avatar_icon_color: str | None = None
    friendship_status: str  # "none" | "friends" | "request_sent" | "request_received"


class FriendRequestSummary(BaseModel):
    user_id: str
    display_name: str
    avatar_id: str | None = None
    avatar_color_id: str | None = None
    avatar_icon_color: str | None = None

class FriendSummary(BaseModel):
    user_id: str
    display_name: str
    avatar_id: str | None = None
    avatar_color_id: str | None = None
    avatar_icon_color: str | None = None

class SendFriendRequest(BaseModel):
    to_user_id: str
