from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.integrations import router as integrations_router
from app.api.v1.deployments import router as deployments_router
from app.api.v1.incidents import router as incidents_router
from app.api.v1.services import router as services_router
from app.api.v1.memory import router as memory_router
from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.approvals import router as approvals_router
from app.api.v1.repositories import router as repositories_router
from app.api.v1.workflows import router as workflows_router
from app.api.v1.events import router as events_router
from app.api.v1.risk import router as risk_router
from app.api.v1.agent import router as agent_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(integrations_router)
api_router.include_router(repositories_router)
api_router.include_router(workflows_router)
api_router.include_router(deployments_router)
api_router.include_router(incidents_router)
api_router.include_router(services_router)
api_router.include_router(memory_router)
api_router.include_router(risk_router)
api_router.include_router(agent_router)
api_router.include_router(recommendations_router)
api_router.include_router(approvals_router)
api_router.include_router(events_router)
