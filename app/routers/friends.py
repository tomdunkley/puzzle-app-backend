from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependency import get_current_user_id
from app.models.friends import (
    FriendRequestSummary,
    FriendSummary,
    SendFriendRequest,
    UserSearchResult,
)
from app.services.friend_service import (
    AlreadyFriendsError,
    CannotFriendSelfError,
    FriendRequestAlreadyExistsError,
    FriendRequestNotFoundError,
    accept_friend_request,
    decline_friend_request,
    list_friends,
    list_incoming_requests,
    list_outgoing_requests,
    search_users,
    send_friend_request,
    unfriend,
)

router = APIRouter()


def _to_summary(user: dict) -> dict:
    return {
        "user_id": user["user_id"],
        "display_name": user["display_name"],
        "avatar_id": user.get("avatar_id"),
        "avatar_color_id": user.get("avatar_color_id"),
        "avatar_icon_color": user.get("avatar_icon_color"),
    }


@router.get("/users/search", response_model=list[UserSearchResult])
def search_users_endpoint(q: str, user_id: str = Depends(get_current_user_id)):
    return search_users(q, user_id)


@router.post("/friends/requests", status_code=201)
def send_friend_request_endpoint(body: SendFriendRequest, user_id: str = Depends(get_current_user_id)):
    try:
        send_friend_request(user_id, body.to_user_id)
    except CannotFriendSelfError as exc:
        raise HTTPException(status_code=400, detail="you can't send a friend request to yourself") from exc
    except AlreadyFriendsError as exc:
        raise HTTPException(status_code=409, detail="you're already friends") from exc
    except FriendRequestAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail="a friend request already exists") from exc
    return {"status": "ok"}


@router.get("/friends/requests/incoming", response_model=list[FriendRequestSummary])
def get_incoming_requests(user_id: str = Depends(get_current_user_id)):
    return [_to_summary(u) for u in list_incoming_requests(user_id)]


@router.get("/friends/requests/outgoing", response_model=list[FriendRequestSummary])
def get_outgoing_requests(user_id: str = Depends(get_current_user_id)):
    return [_to_summary(u) for u in list_outgoing_requests(user_id)]


@router.post("/friends/requests/{from_user_id}/accept")
def accept_friend_request_endpoint(from_user_id: str, user_id: str = Depends(get_current_user_id)):
    try:
        accept_friend_request(user_id, from_user_id)
    except FriendRequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail="no pending request from that user") from exc
    return {"status": "ok"}


@router.post("/friends/requests/{from_user_id}/decline")
def decline_friend_request_endpoint(from_user_id: str, user_id: str = Depends(get_current_user_id)):
    try:
        decline_friend_request(user_id, from_user_id)
    except FriendRequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail="no pending request from that user") from exc
    return {"status": "ok"}


@router.get("/friends", response_model=list[FriendSummary])
def get_friends(user_id: str = Depends(get_current_user_id)):
    return [_to_summary(u) for u in list_friends(user_id)]


@router.delete("/friends/{friend_id}")
def unfriend_endpoint(friend_id: str, user_id: str = Depends(get_current_user_id)):
    # No status_code=204 -- Retrofit/OkHttp always reports a null body for a bare 204,
    # which crashes the Android client's non-nullable Unit-returning suspend call.
    unfriend(user_id, friend_id)
    return {"status": "ok"}
