from fastapi import FastAPI

from app.api import batches, files, health, review, rules
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import init_db

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(title=settings.app_name, debug=settings.app_debug)

app.include_router(health.router)
app.include_router(batches.router, prefix="/api/v1")
app.include_router(files.router, prefix="/api/v1")
app.include_router(review.router, prefix="/api/v1")
app.include_router(rules.router, prefix="/api/v1")


@app.on_event("startup")
def on_startup() -> None:
    init_db()
