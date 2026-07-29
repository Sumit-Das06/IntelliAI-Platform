"""Health endpoints.

- ``GET /health/live``  — is the process alive? Instant, checks nothing.
  A failure here means "restart me" (hung/dead process).
- ``GET /health/ready`` — can we serve traffic right now? Probes every
  registered dependency. A failure here means "stop routing to me, do NOT
  restart me" — restarting the app does not fix a down database.
"""

from fastapi import APIRouter, Response, status

from intelliai_api.api.deps import HealthDep
from intelliai_api.core.health import HealthReport, HealthStatus

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live(health: HealthDep) -> HealthReport:
    return health.liveness()


@router.get("/ready", responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthReport}})
async def ready(health: HealthDep, response: Response) -> HealthReport:
    report = await health.readiness()
    if report.status is HealthStatus.UNHEALTHY:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return report
