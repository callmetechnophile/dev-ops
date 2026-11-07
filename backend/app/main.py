from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from app.config import settings
from app.core.logging import setup_logging
from app.core.exceptions import DevOpsIntelligenceError
from app.api.router import api_router
from app.redis_client import redis_manager

setup_logging(level="DEBUG" if settings.DEBUG else "INFO")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await redis_manager.connect()
    yield
    # Shutdown
    await redis_manager.disconnect()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Independent AI-powered predictive operational memory and risk assessment platform.",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DevOpsIntelligenceError)
async def devops_exception_handler(request: Request, exc: DevOpsIntelligenceError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"success": False, "message": exc.message, "details": exc.details}
    )


# Mount API V1
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/metrics", tags=["Observability"])
async def metrics_endpoint():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": settings.APP_NAME,
        "version": "1.0.0",
        "status": "operational",
        "docs_url": f"{settings.API_V1_PREFIX}/docs",
        "health_url": f"{settings.API_V1_PREFIX}/health",
        "metrics_url": "/metrics",
    }
