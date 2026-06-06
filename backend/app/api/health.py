from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.readiness import build_readiness_payload


router = APIRouter()


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "execution_mode": settings.execution_mode,
    }


@router.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready")
def health_ready(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    return build_readiness_payload(settings)


@router.get("/health/error-test")
def health_error_test() -> None:
    raise AppError(
        error_code="HEALTH_ERROR_TEST",
        message="Controlled health error for testing.",
        details={"reason": "controlled_test"},
        status_code=400,
    )

__all__ = [name for name in globals() if not name.startswith('_')]
