from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import api_router
from app.core.database import init_db
from app.services.voice_seed import seed_voice_profiles
from app.web.routes import web_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_voice_profiles()
    yield


app = FastAPI(title="RTH CommsDesk", lifespan=lifespan)
app.include_router(api_router, prefix="/api")
app.include_router(web_router)
app.mount("/static", StaticFiles(directory="app/web"), name="static")
