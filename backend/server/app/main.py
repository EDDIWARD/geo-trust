from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .analytics_demo import MODULE_NAME, build_demo_dashboard, build_demo_product_report
from .analytics_schemas import DemoDashboardResponse, DemoLlmAnalysisResponse, DemoProductReportResponse
from .config import get_settings
from .database import get_connection, initialize_database
from .rag_answer import build_llm_strategy_analysis
from .rag_search import search_rag
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


class RagSearchResponse(BaseModel):
    query: str
    documents: list[dict]
    cards: list[dict]
    chunks: list[dict]
    insights: list[dict]


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


@app.get("/insights-demo", include_in_schema=False)
def trusted_value_demo_page() -> FileResponse:
    return FileResponse(
        settings.static_dir / "insights" / "index.html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


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


@app.get("/api/analytics/demo/dashboard", response_model=DemoDashboardResponse)
def analytics_demo_dashboard() -> DemoDashboardResponse:
    return build_demo_dashboard()


@app.get("/api/analytics/demo/report/{product_id}", response_model=DemoProductReportResponse)
def analytics_demo_report(product_id: str) -> DemoProductReportResponse:
    try:
        return build_demo_product_report(product_id)
    except KeyError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"{MODULE_NAME} 中不存在商品 {product_id}") from exc


@app.get("/api/rag/search", response_model=RagSearchResponse)
def rag_search(query: str, top_k: int = 5) -> RagSearchResponse:
    return RagSearchResponse(**search_rag(query, top_k=top_k))


@app.get("/api/analytics/demo/llm-report/{product_id}", response_model=DemoLlmAnalysisResponse)
def analytics_demo_llm_report(product_id: str) -> DemoLlmAnalysisResponse:
    try:
        return build_llm_strategy_analysis(product_id)
    except KeyError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"{MODULE_NAME} 中不存在商品 {product_id}") from exc
