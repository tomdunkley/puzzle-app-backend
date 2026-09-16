from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependency import get_verified_user_id
from app.models.challenges import (
    ChallengeCreateResponse,
    ChallengePlayRequest,
    ChallengePlayResult,
    CreateChallengeRequest,
    FriendChallengeSummaryResponse,
    PendingChallengesResponse,
)
from app.models.scores import ScoreDetail
from app.services import challenge_service

router = APIRouter()


@router.post("/challenges", response_model=ChallengeCreateResponse, status_code=201)
def create_challenge(req: CreateChallengeRequest, user_id: str = Depends(get_verified_user_id)):
    try:
        challenge = challenge_service.create_challenge(
            challenger_id=user_id,
            friend_id=req.friend_id,
            game=req.game,
            seed=req.seed,
            puzzle_data=req.puzzle_data,
        )
    except challenge_service.ChallengeAlreadyExistsError:
        raise HTTPException(status_code=409, detail="Open challenge already exists for this game")
    return ChallengeCreateResponse(challenge_id=challenge["challenge_id"])


@router.get("/challenges/pending", response_model=PendingChallengesResponse)
def get_pending(user_id: str = Depends(get_verified_user_id)):
    data = challenge_service.get_pending_challenges(user_id)
    return PendingChallengesResponse(**data)


@router.get("/challenges/friends/{friend_id}", response_model=FriendChallengeSummaryResponse)
def get_friend_challenges(friend_id: str, user_id: str = Depends(get_verified_user_id)):
    games = challenge_service.get_friend_challenge_summary(user_id, friend_id)
    return FriendChallengeSummaryResponse(games=games)


@router.post("/challenges/{challenge_id}/play", response_model=ChallengePlayResult)
def play_challenge(
    challenge_id: str,
    req: ChallengePlayRequest,
    user_id: str = Depends(get_verified_user_id),
):
    try:
        updated = challenge_service.submit_challenge_play(
            challenge_id=challenge_id,
            user_id=user_id,
            duration_seconds=req.duration_seconds,
            words=req.words,
            result_value=req.result_value,
            steps=req.steps or [],
        )
    except challenge_service.ChallengeNotFoundError:
        raise HTTPException(status_code=404, detail="Challenge not found")
    except challenge_service.ChallengeNotOpenError:
        raise HTTPException(status_code=409, detail="Challenge is not open")
    except challenge_service.AlreadyPlayedError:
        raise HTTPException(status_code=409, detail="You have already played this challenge")
    except challenge_service.NotAParticipantError:
        raise HTTPException(status_code=403, detail="Not a participant in this challenge")

    both_played = (
        updated.get("challenger_result") is not None
        and updated.get("challengee_result") is not None
    )
    return ChallengePlayResult(
        challenge_id=challenge_id,
        status=updated["status"],
        both_played=both_played,
    )


@router.get("/challenges/{challenge_id}/result/{target_user_id}", response_model=ScoreDetail)
def get_challenge_result(
    challenge_id: str,
    target_user_id: str,
    user_id: str = Depends(get_verified_user_id),
):
    try:
        detail = challenge_service.get_challenge_result(challenge_id, target_user_id, user_id)
    except challenge_service.ChallengeNotFoundError:
        raise HTTPException(status_code=404, detail="Challenge not found")
    except challenge_service.NotAParticipantError:
        raise HTTPException(status_code=403, detail="Not a participant in this challenge")
    except challenge_service.PlayNotFoundError:
        raise HTTPException(status_code=404, detail="Player hasn't played this challenge yet")
    return ScoreDetail(**detail)
