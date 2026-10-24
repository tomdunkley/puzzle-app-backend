import logging

from app.services.stats_service import award_first_places, rebuild_all_stats

logging.getLogger().setLevel(logging.INFO)

_JOBS = {
    "award_first_places": award_first_places,
    "rebuild_stats": rebuild_all_stats,
}


def handler(event, context):
    job = (event or {}).get("job")
    if job not in _JOBS:
        raise ValueError(f"unknown job: {job!r}")
    result = _JOBS[job]()
    logging.info("%s finished: %s", job, result)
    return result
