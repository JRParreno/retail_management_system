from __future__ import annotations

import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import get_logger, request_id_ctx, setup_logging

settings = get_settings()
setup_logging(settings.LOG_LEVEL)
logger = get_logger("rms.api")

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
)

app.add_middleware(
    CORSMiddleware,
    # Localhost + private LAN IPs so tablets/phones on Wi‑Fi can use the app
    # (browser may still hit the API directly from :8000/docs).
    allow_origin_regex=(
        r"https?://("
        r"localhost|127\.0\.0\.1|"
        r"192\.168\.\d{1,3}\.\d{1,3}|"
        r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}"
        r")(:\d+)?"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    incoming = request.headers.get("x-request-id") or request.headers.get("X-Request-Id")
    request_id = (incoming or "").strip() or str(uuid.uuid4())
    token = request_id_ctx.set(request_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-Id"] = request_id
        status = response.status_code
        log_fn = logger.warning if status >= 500 else logger.info
        if status >= 400 or request.method not in ("GET", "HEAD", "OPTIONS"):
            log_fn(
                "%s %s -> %s (%.1fms)",
                request.method,
                request.url.path,
                status,
                duration_ms,
            )
        return response
    finally:
        request_id_ctx.reset(token)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_id = request_id_ctx.get("-")
    if exc.status_code >= 500:
        logger.error(
            "HTTP %s %s %s: %s",
            exc.status_code,
            request.method,
            request.url.path,
            exc.detail,
        )
    elif exc.status_code >= 400 and exc.status_code not in (401, 404):
        logger.warning(
            "HTTP %s %s %s: %s",
            exc.status_code,
            request.method,
            request.url.path,
            exc.detail,
        )

    body: dict = {"detail": exc.detail, "request_id": request_id}
    return JSONResponse(
        status_code=exc.status_code,
        content=body,
        headers={"X-Request-Id": request_id},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = request_id_ctx.get("-")
    logger.warning(
        "Validation error %s %s: %s",
        request.method,
        request.url.path,
        exc.errors(),
    )
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "request_id": request_id},
        headers={"X-Request-Id": request_id},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = request_id_ctx.get("-")
    logger.exception(
        "Unhandled exception %s %s",
        request.method,
        request.url.path,
    )
    detail = str(exc) if settings.DEBUG else "Internal Server Error"
    return JSONResponse(
        status_code=500,
        content={"detail": detail, "request_id": request_id},
        headers={"X-Request-Id": request_id},
    )


uploads_root = Path(__file__).resolve().parent.parent / "uploads"
uploads_root.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_root)), name="uploads")

app.include_router(api_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
