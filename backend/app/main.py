import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from app.api import app as api_router
from app.config import UPLOAD_DIR, settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware
from app.services import reservation_service
from app.services.email_outbox_service import run_email_outbox_scan
from app.services.email_sender import build_email_sender

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app_started")
    email_sender = (
        build_email_sender(settings) if settings.email_worker_enabled else None
    )
    tasks = [asyncio.create_task(reservation_service.run_expire_scan())]
    if email_sender is not None:
        tasks.append(asyncio.create_task(run_email_outbox_scan(email_sender)))
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            # 捕获并忽略取消异常
            with suppress(asyncio.CancelledError):
                await task
        logger.info("app_stopped")


app = FastAPI(lifespan=lifespan)

app.include_router(api_router)

origins = ["http://127.0.0.1:5173", "http://localhost:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_headers=["*"],
    allow_methods=["*"],
    allow_credentials=True,
)
app.add_middleware(RequestContextMiddleware)

register_exception_handlers(app)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/")
def root():
    return {"message": "FastAPI is running!"}
