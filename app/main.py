from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from app.routers import achievements, auth, dev, friends, games, health, puzzles, scores, users

app = FastAPI(title="td Puzzles API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/v1")
app.include_router(achievements.router, prefix="/v1")
app.include_router(games.router, prefix="/v1")
app.include_router(puzzles.router, prefix="/v1")
app.include_router(scores.router, prefix="/v1")
app.include_router(auth.router, prefix="/v1")
app.include_router(users.router, prefix="/v1")
app.include_router(friends.router, prefix="/v1")
app.include_router(dev.router, prefix="/v1")

handler = Mangum(app)
