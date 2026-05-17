import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import admin as admin_router
from app.api import auth as auth_router
from app.api import listings as listings_router
from app.api import scrapers as scrapers_router
from app.api import stats as stats_router
from app.api import telegram as telegram_router
from app.config import get_settings
from app.scraper_events import get_event_bus
from app.telegram.startup import setup_telegram

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    bus = get_event_bus()
    await bus.start()
    stop = asyncio.Event()
    polling_task = await setup_telegram(stop)
    try:
        yield
    finally:
        stop.set()
        if polling_task is not None:
            polling_task.cancel()
            try:
                await polling_task
            except asyncio.CancelledError:
                pass
        await bus.stop()


app = FastAPI(title="Spider API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth_router.router, prefix="/api")
app.include_router(listings_router.router, prefix="/api")
app.include_router(scrapers_router.router, prefix="/api")
app.include_router(stats_router.router, prefix="/api")
app.include_router(telegram_router.router, prefix="/api")
app.include_router(admin_router.router, prefix="/api")

_STATIC_DIR = Path(__file__).resolve().parent.parent / "public"
if (_STATIC_DIR / "index.html").is_file():
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="spa")
