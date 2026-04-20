from __future__ import annotations

from pydantic import BaseModel


class DemoOverviewMetric(BaseModel):
    key: str
    name: str
    value: str
    description: str


class DemoIndicatorDefinition(BaseModel):
    key: str
    name: str
    formula: str
    meaning: str
    caution: str
    business_value: str
    ai_usage: str


class DemoClusterSummary(BaseModel):
    cluster_id: int
    cluster_name: str
    description: str
    product_count: int
    average_activation_rate: float
    average_participation_rate: float
    average_cross_region_rate: float
    average_opportunity_score: float
    representative_products: list[str]


class DemoProductCard(BaseModel):
    product_id: str
    product_name: str
    family_name: str
    variant_name: str
    category: str
    region_name: str
    season: str
    channel: str
    price_band: str
    unit_price: float
    launch_quantity: int
    declared_sales: int
    verified_scans: int
    activation_rate: float
    participation_rate: float
    repeat_scan_rate: float
    abnormal_rate: float
    cross_region_rate: float
    trust_opportunity_score: float
    cluster_id: int
    cluster_name: str
    product_core_cluster: str
    origin_cluster: str
    presentation_cluster: str
    feedback_cluster: str
    positioning_status: str
    recommendation_direction: str
    stability_score: float
    stability_label: str
    tags: list[str]


class DemoMarketInsight(BaseModel):
    city: str
    verified_scans: int
    opportunity_score: float
    observation: str
    market_tier: str
    rank: int


class DemoStrategyReport(BaseModel):
    title: str
    diagnosis: str
    opportunity: str
    caution: str
    actions: list[str]
    recommended_markets: list[str]
    similar_products: list[str]


class DemoPositioningSummary(BaseModel):
    intrinsic_value_score: float
    presented_value_score: float
    market_validation_score: float
    fit_score: float
    product_core_cluster: str
    origin_cluster: str
    presentation_cluster: str
    feedback_cluster: str
    positioning_status: str
    recommendation_direction: str
    stability_score: float
    stability_label: str
    summary: str


class DemoScenarioPreview(BaseModel):
    scenario_name: str
    direction: str
    changed_fields: list[str]
    projected_presented_value_score: float
    projected_market_validation_score: float
    projected_positioning_status: str
    reason: str


class DemoMarketLearningItem(BaseModel):
    city: str
    learning_type: str
    target_product_name: str
    target_region_name: str
    reason: str
    lesson: str
    match_score: float
    city_advantage_score: float
    scene_similarity_score: float
    category_alignment_score: float


class DemoDashboardResponse(BaseModel):
    module_name: str
    generated_at: str
    narrative: str
    overview_metrics: list[DemoOverviewMetric]
    indicator_definitions: list[DemoIndicatorDefinition]
    clusters: list[DemoClusterSummary]
    products: list[DemoProductCard]
    market_heat: list[DemoMarketInsight]


class DemoProductReportResponse(BaseModel):
    module_name: str
    generated_at: str
    product: DemoProductCard
    positioning_summary: DemoPositioningSummary
    strategy_report: DemoStrategyReport
    prompt_preview: str
    scenarios: list[DemoScenarioPreview]
    market_insights: list[DemoMarketInsight]
    market_learning: list[DemoMarketLearningItem]
    peer_products: list[DemoProductCard]
    notes: list[str]
    vector_preview: dict[str, float]
    raw_fields: dict[str, object]


class RagCardHit(BaseModel):
    doc_id: str
    title: str
    theme_path: str
    score: float
    research_type: str
    evidence_strength: str
    card_summary: str
    core_variables: list[str]
    business_implications: list[str]
    recommended_queries: list[str]


class DemoLlmStrategyAnalysis(BaseModel):
    executive_summary: str
    core_judgement: str
    evidence_findings: list[str]
    strategy_actions: list[str]
    pricing_packaging_advice: str
    channel_advice: str
    origin_trust_advice: str
    risk_warning: str


class DemoLlmAnalysisResponse(BaseModel):
    module_name: str
    generated_at: str
    model_name: str
    product: DemoProductCard
    positioning_summary: DemoPositioningSummary
    retrieval_queries: list[str]
    retrieved_cards: list[RagCardHit]
    retrieved_insights: list[str]
    analysis: DemoLlmStrategyAnalysis
