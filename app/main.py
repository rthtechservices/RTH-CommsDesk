from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import api_router
from app.core.auth import validate_auth_configuration, verify_api_token, verify_session_token
from app.core.config import get_settings
from app.core.database import init_db
from app.core.logging_config import configure_logging
from app.services.voice_seed import seed_voice_profiles
from app.web.routes import web_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings)
    validate_auth_configuration(settings)
    init_db()
    seed_voice_profiles()
    yield


app = FastAPI(title="RTH CommsDesk", lifespan=lifespan)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    settings = get_settings()
    if not settings.auth_required:
        return await call_next(request)

    path = request.url.path
    if path.startswith("/static") or path in {"/login", "/healthz"}:
        return await call_next(request)
    if path.startswith("/api/notifications/webhook"):
        return await call_next(request)

    if path.startswith("/api"):
        if not verify_api_token(
            settings,
            x_api_key=request.headers.get("x-api-key"),
            authorization=request.headers.get("authorization"),
        ):
            return JSONResponse(status_code=401, content={"detail": "API authentication required"})
        return await call_next(request)

    token = request.cookies.get(settings.auth_session_cookie_name)
    if verify_session_token(token, settings):
        return await call_next(request)

    next_path = request.url.path
    if request.url.query:
        next_path = f"{next_path}?{request.url.query}"
    return RedirectResponse(url=f"/login?next={quote(next_path, safe='/?=&')}", status_code=303)


@app.get("/healthz")
def health_check() -> dict:
    return {"status": "ok"}


app.include_router(api_router, prefix="/api")
app.include_router(web_router)
app.mount("/static", StaticFiles(directory="app/web"), name="static")
