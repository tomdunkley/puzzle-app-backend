from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.data.achievements import ACHIEVEMENTS

_LONDON_TZ = ZoneInfo("Europe/London")
from app.db import achievements_table


def get_unlocked(user_id: str) -> set[str]:
    item = achievements_table.get_item(Key={"user_id": user_id}).get("Item")
    if item is None:
        return set()
    return set(item.get("unlocked_ids", []))


def _get_unlocked_at(user_id: str) -> dict[str, str]:
    item = achievements_table.get_item(Key={"user_id": user_id}).get("Item")
    if item is None:
        return {}
    return dict(item.get("unlocked_at", {}))


def _award(user_id: str, achievement_ids: list[str]) -> None:
    """Adds IDs to the user's unlocked set and records timestamps for newly-unlocked
    achievements. The two-step update ensures the unlocked_at map exists before we
    write nested keys into it (DynamoDB rejects nested SET on a missing parent map)."""
    now = datetime.now(timezone.utc).isoformat()
    # Step 1: add IDs and initialise the timestamp map if this is the user's first award.
    achievements_table.update_item(
        Key={"user_id": user_id},
        UpdateExpression="ADD unlocked_ids :ids SET unlocked_at = if_not_exists(unlocked_at, :empty)",
        ExpressionAttributeValues={":ids": set(achievement_ids), ":empty": {}},
    )
    # Step 2: stamp each newly-awarded ID (if_not_exists preserves original date on re-award).
    for aid in achievement_ids:
        achievements_table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="SET #ua.#aid = if_not_exists(#ua.#aid, :now)",
            ExpressionAttributeNames={"#ua": "unlocked_at", "#aid": aid},
            ExpressionAttributeValues={":now": now},
        )


def unlock_all_achievements(user_id: str) -> None:
    """Dev-only: instantly awards every achievement."""
    _award(user_id, list(ACHIEVEMENTS.keys()))


def reset_achievements(user_id: str) -> None:
    """Dev-only: wipes all achievement progress for the user."""
    achievements_table.delete_item(Key={"user_id": user_id})


def check_and_award_on_score(
    user_id: str,
    game: str,
    rank_today: int | None,
    valid_words: list[str] | None = None,
    validated_steps: list[dict] | None = None,
    puzzle_id: str | None = None,
    distance: int | None = None,
    current_streak: int | None = None,
    all_computed_values: list[int] | None = None,
) -> list[str]:
    """Called after a score is successfully submitted. Returns newly-unlocked achievement IDs."""
    from app.services.puzzle_service import GAMES
    from app.services.score_service import has_played, get_rank

    already = get_unlocked(user_id)
    newly = []

    # --- per-game completion ---
    if game == "numbers" and "play_numbers" not in already:
        newly.append("play_numbers")
    if game == "boggle" and "play_words" not in already:
        newly.append("play_words")

    # --- global rank ---
    if rank_today == 1 and "rank_first_global" not in already:
        newly.append("rank_first_global")
    if rank_today is not None and rank_today <= 10 and "rank_top_ten" not in already:
        newly.append("rank_top_ten")

    # --- time-of-day (UK local time — GMT in winter, BST=UTC+1 in summer) ---
    now_london = datetime.now(_LONDON_TZ)
    if now_london.hour < 5 and "night_owl" not in already:
        newly.append("night_owl")
    if now_london.hour == 8 and now_london.minute < 30 and "early_bird" not in already:
        newly.append("early_bird")

    # --- numbers-game step achievements ---
    # Use all_computed_values (every intermediate result including abandoned branches) when available,
    # falling back to just the submitted best-path steps.
    if game == "numbers":
        all_results = list(all_computed_values or [])
        if validated_steps:
            all_results += [s.get("result", 0) for s in validated_steps]
        if any(r >= 100_000_000 for r in all_results) and "massive" not in already:
            newly.append("massive")
        if any(r == 69 for r in all_results) and "nice" not in already:
            newly.append("nice")

    # --- hit the target exactly ---
    if game == "numbers" and distance == 0 and "hit_target" not in already:
        newly.append("hit_target")

    # --- streak milestones ---
    if current_streak is not None:
        streak_key = "numbers" if game == "numbers" else "words"
        for days in (5, 10, 25, 100, 250, 365, 500, 1000):
            aid = f"{streak_key}_streak_{days}"
            if current_streak >= days and aid not in already and aid in ACHIEVEMENTS:
                newly.append(aid)

    # --- boggle word achievements ---
    if game == "boggle":
        if not valid_words and "goose_egg" not in already:
            newly.append("goose_egg")
        if valid_words:
            words_lower = [w.lower() for w in valid_words]
            if any(len(w) >= 8 for w in words_lower) and "hippopotomonstrosesquippedaliophobia" not in already:
                newly.append("hippopotomonstrosesquippedaliophobia")
            if "words" in words_lower and "meta" not in already:
                newly.append("meta")
            if any("qu" in w for w in words_lower) and "queen" not in already:
                newly.append("queen")

    # --- blackout (all games completed today) ---
    if puzzle_id is not None and "blackout" not in already:
        date_iso = puzzle_id.split("_", 1)[1]
        if all(has_played(f"{g['game']}_{date_iso}", user_id) for g in GAMES):
            newly.append("blackout")

    # --- daily sweep (#1 globally in every puzzle today) ---
    if puzzle_id is not None and "daily_sweep" not in already:
        date_iso = puzzle_id.split("_", 1)[1]
        if all(get_rank(f"{g['game']}_{date_iso}", user_id) == 1 for g in GAMES):
            newly.append("daily_sweep")

    # --- calendar day achievements (based on puzzle date, not wall-clock time) ---
    if puzzle_id is not None:
        from datetime import date as _date
        date_iso = puzzle_id.split("_", 1)[1]
        puzzle_date = _date.fromisoformat(date_iso)
        if date_iso[5:] == "12-25" and "santa" not in already:
            newly.append("santa")
        if puzzle_date.timetuple().tm_yday == 100 and "hundredth_day" not in already:
            newly.append("hundredth_day")

    if newly:
        _award(user_id, newly)
        # Completionist: awarded after all other achievements are unlocked
        all_now = already | set(newly)
        non_completionist = set(ACHIEVEMENTS.keys()) - {"completionist"}
        if "completionist" not in all_now and non_completionist.issubset(all_now):
            _award(user_id, ["completionist"])
            newly.append("completionist")

    return newly


def check_and_award_on_friend_added(user_id: str) -> list[str]:
    """Called when a friendship is created (either direction). Returns newly-unlocked IDs."""
    already = get_unlocked(user_id)
    newly = []
    if "add_friend" not in already:
        newly.append("add_friend")
    if newly:
        _award(user_id, newly)
        all_now = already | set(newly)
        non_completionist = set(ACHIEVEMENTS.keys()) - {"completionist"}
        if "completionist" not in all_now and non_completionist.issubset(all_now):
            _award(user_id, ["completionist"])
            newly.append("completionist")
    return newly


def get_achievement_summary(user_id: str) -> dict:
    """Full summary for the achievements screen: all definitions with unlock status and timestamps."""
    unlocked = get_unlocked(user_id)
    unlocked_at = _get_unlocked_at(user_id)
    items = []
    for ach_id, defn in ACHIEVEMENTS.items():
        items.append({
            "id": ach_id,
            "title": defn["title"],
            "description": defn["description"],
            "unlocked": ach_id in unlocked,
            "unlocked_at": unlocked_at.get(ach_id),
            "unlocks_avatar_id": defn.get("unlocks_avatar_id"),
            "unlocks_color_id": defn.get("unlocks_color_id"),
            "unlocks_icon_color_id": defn.get("unlocks_icon_color_id"),
        })
    return {"achievements": items, "unlocked_ids": list(unlocked)}
