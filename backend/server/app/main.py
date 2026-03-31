from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import get_connection, initialize_database
from .schemas import (
    BootstrapResponse,
    RegisterProductRequest,
    RegisterProductResponse,
    RiskPolicyResponse,
    RegionResponse,
    ValidateLocationRequest,
    ValidateLocationResponse,
)
from .services import list_enabled_regions, register_product, validate_location

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database(settings)
    yield


app = FastAPI(
    title="Geo-Trust Android Backend",
    version="0.1.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/mobile/bootstrap", response_model=BootstrapResponse)
def mobile_bootstrap() -> BootstrapResponse:
    with get_connection(settings.database_path) as connection:
        regions = list_enabled_regions(connection)

    return BootstrapResponse(
        app_name=settings.app_name,
        register_enabled=settings.register_enabled,
        location_required=settings.location_required,
        risk_policy=RiskPolicyResponse(
            reject_mock_location=settings.reject_mock_location,
            reject_emulator=settings.reject_emulator,
            reject_debugger=settings.reject_debugger,
            reject_root=settings.reject_root,
        ),
        regions=[
            RegionResponse(
                id=row["id"],
                code=row["code"],
                name=row["name"],
                product_type=row["product_type"],
                province=row["province"],
                city=row["city"],
                center_lng=row["center_lng"],
                center_lat=row["center_lat"],
            )
            for row in regions
        ],
    )


@app.post("/api/mobile/register-product", response_model=RegisterProductResponse)
def mobile_register_product(payload: RegisterProductRequest) -> RegisterProductResponse:
    with get_connection(settings.database_path) as connection:
        return register_product(connection, payload, settings)


@app.post("/api/mobile/validate-location", response_model=ValidateLocationResponse)
def mobile_validate_location(payload: ValidateLocationRequest) -> ValidateLocationResponse:
    with get_connection(settings.database_path) as connection:
        return validate_location(connection, payload, settings)
