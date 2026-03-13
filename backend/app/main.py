from fastapi import FastAPI

from app.api.assets import router as assets_router
from app.api.auth import router as auth_router
from app.api.children import router as children_router
from app.api.health import router as health_router
from app.api.stories import router as stories_router
from app.api.voice import router as voice_router

app = FastAPI(
    title="Vocaleaf API",
    version="0.1.0",
)

app.include_router(health_router, prefix="/api")
app.include_router(auth_router)
app.include_router(assets_router)
app.include_router(children_router)
app.include_router(stories_router)
app.include_router(voice_router)
