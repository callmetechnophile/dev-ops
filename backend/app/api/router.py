from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.integrations import router as integrations_router
from app.api.v1.deployments import router as deployments_router
from app.api.v1.incidents import router as incidents_router
from app.api.v1.services import router as services_router
from app.api.v1.memory import router as memory_router
from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.approvals import router as approvals_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(integrations_router)
api_router.include_router(deployments_router)
api_router.include_router(incidents_router)
api_router.include_router(services_router)
api_router.include_router(memory_router)
api_router.include_router(recommendations_router)
api_router.include_router(approvals_router)
