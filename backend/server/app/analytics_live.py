from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import datetime

from .analytics_demo import build_demo_dashboard
from .analytics_schemas import (
    DemoClusterSummary,
    DemoDashboardResponse,
    DemoIndicatorDefinition,
    DemoLlmAnalysisResponse,
    DemoLlmStrategyAnalysis,
    DemoMarketInsight,
    DemoMarketLearningItem,
    DemoOverviewMetric,
    DemoPositioningSummary,
    DemoProductCard,
    DemoProductReportResponse,
    DemoScenarioPreview,
    DemoStrategyReport,
)


MODULE_NAME = "可信价值挖掘"
MODEL_NAME = "Geo-Trust Live Analyzer"
CITY_PROFILES = [
    ("杭州", "新一线"),
    ("上海", "一线"),
    ("成都", "新一线"),
    ("武汉", "新一线"),
    ("南京", "新一线"),
    ("深圳", "一线"),
]


def build_live_dashboard(connection: sqlite3.Connection) -> DemoDashboardResponse:
    products = _load_live_products(connection)
    clusters = _build_cluster_summaries(products)
    return DemoDashboardResponse(
        module_name=MODULE_NAME,
        generated_at=_now_text(),
        narrative="本页已切换为真实数据库商品，评分与分群为面向演示的轻量经营分析结果。",
        overview_metrics=_build_overview_metrics(products),
        indicator_definitions=_build_indicator_definitions(),
        clusters=clusters,
        products=products,
        market_heat=_build_global_market_heat(products),
    )


def build_live_product_report(connection: sqlite3.Connection, product_id: str) -> DemoProductReportResponse:
    products = _load_live_products(connection)
    product = next((item for item in products if item.product_id == str(product_id)), None)
    if product is None:
        raise KeyError(product_id)

    peer_products = _select_peer_products(product, products)
    market_insights = _build_product_market_insights(product)
    market_learning = _build_market_learning(product, peer_products, market_insights)
    positioning_summary = _build_positioning_summary(product)
    scenarios = _build_scenarios(product)

    return DemoProductReportResponse(
        module_name=MODULE_NAME,
        generated_at=_now_text(),
        product=product,
        positioning_summary=positioning_summary,
        strategy_report=_build_strategy_report(product, peer_products, market_insights),
        prompt_preview=_build_prompt_preview(product, peer_products, market_insights, scenarios),
        scenarios=scenarios,
        market_insights=market_insights,
        market_learning=market_learning,
        peer_products=peer_products,
        notes=[
            "本页使用当前数据库中的真实商品、扫码与异常统计。",
            "机会分和分群标签为演示用规则计算结果，用于帮助展示经营分析结构。",
            "风险相关指标以扫码异常记录为主，不直接替代人工核验。",
        ],
        vector_preview={
            "activation_rate": round(product.activation_rate, 4),
            "participation_rate": round(product.participation_rate, 4),
            "repeat_scan_rate": round(product.repeat_scan_rate, 4),
            "abnormal_rate": round(product.abnormal_rate, 4),
            "cross_region_rate": round(product.cross_region_rate, 4),
            "stability_score": round(product.stability_score, 4),
        },
        raw_fields={
            "product_id": product.product_id,
            "product_name": product.product_name,
            "region_name": product.region_name,
            "category": product.category,
            "verified_scans": product.verified_scans,
            "declared_sales": product.declared_sales,
            "trust_opportunity_score": product.trust_opportunity_score,
        },
    )


def build_live_llm_report(connection: sqlite3.Connection, product_id: str) -> DemoLlmAnalysisResponse:
    report = build_live_product_report(connection, product_id)
    product = report.product
    summary = report.positioning_summary
    actions = report.strategy_report.actions[:3]

    if product.positioning_status == "低估潜力型":
        core = "该商品更像是货底子强于当前卖法，适合适度升级表达。"
    elif product.positioning_status == "过度定位型":
        core = "当前卖法略高于商品本体和实际扫码反馈承接能力，应先收敛表达。"
    elif product.positioning_status == "流通优先型":
        core = "更适合走稳定流通与高频复购，而不是强行拔高礼赠定位。"
    else:
        core = "当前定位与商品本体较匹配，重点应放在复制有效渠道和城市策略。"

    return DemoLlmAnalysisResponse(
        module_name=MODULE_NAME,
        generated_at=_now_text(),
        model_name=MODEL_NAME,
        product=product,
        positioning_summary=summary,
        retrieval_queries=[
            f"{product.region_name} {product.category} 可信经营",
            f"{product.category} 城市机会 渠道策略",
        ],
        retrieved_cards=[],
        retrieved_insights=[
            f"当前可信核销 {product.verified_scans}，异常率 {_percent(product.abnormal_rate)}。",
            f"机会分 {product.trust_opportunity_score:.1f}，稳定性 {_percent(product.stability_score)}。",
        ],
        analysis=DemoLlmStrategyAnalysis(
            executive_summary=report.strategy_report.diagnosis,
            core_judgement=core,
            evidence_findings=[
                f"商品来自 {product.region_name}，当前品类为 {product.category}。",
                f"累计可信核销 {product.verified_scans}，重复扫码率 {_percent(product.repeat_scan_rate)}。",
                f"异常率 {_percent(product.abnormal_rate)}，跨区表现 {_percent(product.cross_region_rate)}。",
            ],
            strategy_actions=actions,
            pricing_packaging_advice=report.strategy_report.opportunity,
            channel_advice="优先在机会分更高的城市做小范围验证，再决定是否放大投放。",
            origin_trust_advice="保持产地、批次、扫码链路的一致表达，让可信信息服务成交而不是只做展示。",
            risk_warning=report.strategy_report.caution,
        ),
    )


def _load_live_products(connection: sqlite3.Connection) -> list[DemoProductCard]:
    template_map = _build_demo_template_map()
    rows = connection.execute(
        """
        SELECT
            MIN(p.id) AS id,
            p.product_name,
            MIN(p.product_code) AS product_code,
            MIN(p.batch_no) AS batch_no,
            MIN(p.created_at) AS created_at,
            r.name AS region_name,
            r.product_type,
            r.province,
            COUNT(p.id) AS product_count,
            COUNT(sr.id) AS scan_count,
            SUM(CASE WHEN sr.risk_detected = 1 THEN 1 ELSE 0 END) AS anomaly_count,
            SUM(CASE WHEN sr.is_first_scan = 0 THEN 1 ELSE 0 END) AS repeat_count
        FROM products p
        JOIN regions r ON r.id = p.region_id
        LEFT JOIN scan_records sr ON sr.product_id = p.id
        GROUP BY p.product_name, r.name, r.product_type, r.province
        ORDER BY MIN(p.id) ASC
        """
    ).fetchall()

    products: list[DemoProductCard] = []
    for row in rows:
        scans = int(row["scan_count"] or 0)
        anomalies = int(row["anomaly_count"] or 0)
        repeats = int(row["repeat_count"] or 0)
        product_count = int(row["product_count"] or 0)
        template = template_map.get(_normalize_product_key(row["product_name"]))

        repeat_scan_rate = _safe_divide(repeats, max(scans, 1))
        abnormal_rate = _safe_divide(anomalies, max(scans, 1))
        if template is not None:
            scan_shift = _clamp((scans - 20) / 220, -0.05, 0.14)
            activation_rate = _clamp(template.activation_rate + scan_shift - abnormal_rate * 0.05)
            participation_rate = _clamp(template.participation_rate + scan_shift * 0.8 - abnormal_rate * 0.08)
            cross_region_rate = _clamp(template.cross_region_rate + abnormal_rate * 0.35)
            stability_score = _clamp(template.stability_score - abnormal_rate * 0.3)
            opportunity_score = round(
                max(
                    min(
                        template.trust_opportunity_score
                        + min(scans / 80, 1) * 4.5
                        + min(product_count / 14, 1) * 1.8
                        - abnormal_rate * 18,
                        82,
                    ),
                    26,
                ),
                2,
            )
            positioning_status = _positioning_status(template.positioning_status, opportunity_score, abnormal_rate, scans)
            recommendation_direction = _recommendation_direction(positioning_status)
            cluster_name = positioning_status
            cluster_id = _cluster_id(positioning_status)
            product_core_cluster = template.product_core_cluster
            origin_cluster = template.origin_cluster
            presentation_cluster = template.presentation_cluster
            feedback_cluster = template.feedback_cluster
            price_band = template.price_band
            unit_price = template.unit_price
            family_name = template.family_name
            variant_name = template.variant_name
            tags = template.tags
            season = template.season
            channel = template.channel
        else:
            activation_rate = _clamp(0.22 + min(scans, 12) * 0.045 + min(product_count, 8) * 0.02)
            participation_rate = _clamp(0.18 + min(scans, 10) * 0.05 + min(product_count, 10) * 0.015)
            cross_region_rate = _clamp(abnormal_rate * 1.35 + min(scans, 8) * 0.02)
            stability_score = _clamp(1 - abnormal_rate * 1.2)
            raw_score = (
                42
                + activation_rate * 18
                + participation_rate * 22
                + min(scans / 90, 1) * 14
                + min(product_count / 14, 1) * 8
                - abnormal_rate * 95
                - repeat_scan_rate * 18
            )
            opportunity_score = round(max(min(raw_score, 96), 38), 2)
            positioning_status = _positioning_status(None, opportunity_score, abnormal_rate, scans)
            recommendation_direction = _recommendation_direction(positioning_status)
            cluster_name = positioning_status
            cluster_id = _cluster_id(positioning_status)
            product_core_cluster = f"{row['product_type'] or '未分类'}本体"
            origin_cluster = f"{_normalize_place_label(row['province'])}产地"
            presentation_cluster = "稳态表达" if scans >= 4 else "基础表达"
            feedback_cluster = "风险偏低" if abnormal_rate < 0.15 else "风险承压"
            price_band = _guess_price_band(row["product_type"])
            unit_price = _guess_unit_price(row["product_type"])
            family_name = row["product_name"]
            variant_name = row["batch_no"] or row["product_code"]
            tags = [_normalize_place_label(row["province"]), row["region_name"], row["product_type"] or "未分类"]
            season = "常规"
            channel = "线下门店"

        declared_sales = max(product_count, scans * 4 + 12)
        stability_label = "高稳定" if stability_score >= 0.85 else ("中稳定" if stability_score >= 0.65 else "低稳定")

        products.append(
            DemoProductCard(
                product_id=str(row["id"]),
                product_name=row["product_name"],
                family_name=family_name,
                variant_name=variant_name,
                category=row["product_type"] or "未分类",
                region_name=row["region_name"],
                season=season,
                channel=channel,
                price_band=price_band,
                unit_price=unit_price,
                launch_quantity=max(declared_sales + 10, scans + 10),
                declared_sales=declared_sales,
                verified_scans=scans,
                activation_rate=round(activation_rate, 4),
                participation_rate=round(participation_rate, 4),
                repeat_scan_rate=round(repeat_scan_rate, 4),
                abnormal_rate=round(abnormal_rate, 4),
                cross_region_rate=round(cross_region_rate, 4),
                trust_opportunity_score=opportunity_score,
                cluster_id=cluster_id,
                cluster_name=cluster_name,
                product_core_cluster=product_core_cluster,
                origin_cluster=origin_cluster,
                presentation_cluster=presentation_cluster,
                feedback_cluster=feedback_cluster,
                positioning_status=positioning_status,
                recommendation_direction=recommendation_direction,
                stability_score=round(stability_score, 4),
                stability_label=stability_label,
                tags=tags,
            )
        )
    return products


def _build_cluster_summaries(products: list[DemoProductCard]) -> list[DemoClusterSummary]:
    grouped: dict[str, list[DemoProductCard]] = defaultdict(list)
    for product in products:
        grouped[product.cluster_name].append(product)

    descriptions = {
        "低估潜力型": "扫码基础不差，当前表达偏保守，适合小步升级。",
        "定位匹配型": "商品本体与当前表达较匹配，可复制已有打法。",
        "流通优先型": "更适合走稳定流通和高频渠道，少做重礼赠。",
        "过度定位型": "当前表达偏高，需要先回收风险和价格压力。",
    }

    ordered_names = ["低估潜力型", "定位匹配型", "流通优先型", "过度定位型"]
    items: list[DemoClusterSummary] = []
    for name in ordered_names:
        members = grouped.get(name, [])
        if not members:
            continue
        items.append(
            DemoClusterSummary(
                cluster_id=_cluster_id(name),
                cluster_name=name,
                description=descriptions[name],
                product_count=len(members),
                average_activation_rate=round(_avg([item.activation_rate for item in members]), 4),
                average_participation_rate=round(_avg([item.participation_rate for item in members]), 4),
                average_cross_region_rate=round(_avg([item.cross_region_rate for item in members]), 4),
                average_opportunity_score=round(_avg([item.trust_opportunity_score for item in members]), 2),
                representative_products=[item.product_name for item in members[:3]],
            )
        )
    return items


def _build_overview_metrics(products: list[DemoProductCard]) -> list[DemoOverviewMetric]:
    total_scans = sum(item.verified_scans for item in products)
    low_estimate = len([item for item in products if item.positioning_status == "低估潜力型"])
    matched = len([item for item in products if item.positioning_status == "定位匹配型"])
    circulation = len([item for item in products if item.positioning_status == "流通优先型"])
    over = len([item for item in products if item.positioning_status == "过度定位型"])
    return [
        DemoOverviewMetric(key="sku_count", name="商品总数", value=str(len(products)), description="来自当前真实数据库的累计商品总数。"),
        DemoOverviewMetric(key="verified_scans", name="可信核销总量", value=f"{total_scans}", description="来自扫码记录的累计可信核销量。"),
        DemoOverviewMetric(key="low_estimate", name="低估潜力商品", value=str(low_estimate), description="适合小步升级表达的商品数量。"),
        DemoOverviewMetric(key="matched", name="定位匹配商品", value=str(matched), description="当前表达与商品本体较匹配。"),
        DemoOverviewMetric(key="circulation", name="流通优先商品", value=str(circulation), description="更适合稳定流通渠道。"),
        DemoOverviewMetric(key="over", name="过度定位商品", value=str(over), description="需要回收表达和风险。"),
    ]


def _build_indicator_definitions() -> list[DemoIndicatorDefinition]:
    return [
        DemoIndicatorDefinition(
            key="activation_rate",
            name="溯源激活率",
            formula="按累计扫码规模做归一化",
            meaning="反映商品进入市场后二维码是否真正被看到并使用。",
            caution="这里只是演示统计指标，不直接等于转化率。",
            business_value="帮助判断商品是否值得继续加强可信表达。",
            ai_usage="用于判断该商品的基础参与度。",
        ),
        DemoIndicatorDefinition(
            key="participation_rate",
            name="验真参与率",
            formula="按累计扫码规模做归一化",
            meaning="反映已成交用户愿不愿意继续做验真动作。",
            caution="高参与不代表高销量。",
            business_value="判断可信信息是否被消费者真正使用。",
            ai_usage="用于区分高频流通型和低参与型商品。",
        ),
        DemoIndicatorDefinition(
            key="abnormal_rate",
            name="异常率",
            formula="异常扫码次数 / 累计扫码次数",
            meaning="反映当前扫码链路里的异常压力。",
            caution="异常率高时应先排查链路，不应直接拔高定位。",
            business_value="帮助识别先做风控还是先做表达升级。",
            ai_usage="用于风险与稳定性判断。",
        ),
    ]


def _build_global_market_heat(products: list[DemoProductCard]) -> list[DemoMarketInsight]:
    base = _avg([item.trust_opportunity_score for item in products]) if products else 0
    result: list[DemoMarketInsight] = []
    for index, (city, tier) in enumerate(CITY_PROFILES, start=1):
        score = round(max(base - index * 1.6 + (7 - index) * 1.1, 10), 2)
        result.append(
            DemoMarketInsight(
                city=city,
                verified_scans=max(int(base * 2.5) - index * 8, 1),
                opportunity_score=score,
                observation=f"{city} 对当前可信经营表达有承接空间，适合继续观察样板商品表现。",
                market_tier=tier,
                rank=index,
            )
        )
    return result


def _build_product_market_insights(product: DemoProductCard) -> list[DemoMarketInsight]:
    base = product.trust_opportunity_score
    insights: list[DemoMarketInsight] = []
    for index, (city, tier) in enumerate(CITY_PROFILES, start=1):
        modifier = 5 - index
        score = round(max(min(base + modifier * 2.4, 98), 12), 2)
        insights.append(
            DemoMarketInsight(
                city=city,
                verified_scans=max(product.verified_scans * max(1, 6 - index), 1),
                opportunity_score=score,
                observation=f"{city} 对 {product.category} 的可信表达承接度为演示估算值，可用于现场展示城市机会差异。",
                market_tier=tier,
                rank=index,
            )
        )
    return insights


def _build_market_learning(
    product: DemoProductCard,
    peers: list[DemoProductCard],
    market_insights: list[DemoMarketInsight],
) -> list[DemoMarketLearningItem]:
    lessons: list[DemoMarketLearningItem] = []
    peer = peers[0] if peers else product
    for insight in market_insights[:4]:
        lessons.append(
            DemoMarketLearningItem(
                city=insight.city,
                learning_type="same_category",
                target_product_name=peer.product_name,
                target_region_name=peer.region_name,
                reason=f"{insight.city} 对 {product.category} 的机会分更高，适合先复制相近商品打法。",
                lesson="先做轻量表达升级和可信说明，再决定是否扩渠道。",
                match_score=round(min(product.trust_opportunity_score / 100 + 0.12, 0.98), 4),
                city_advantage_score=round(insight.opportunity_score / 100, 4),
                scene_similarity_score=round(max(0.5, 1 - abs(product.abnormal_rate - peer.abnormal_rate)), 4),
                category_alignment_score=1.0 if peer.category == product.category else 0.72,
            )
        )
    return lessons


def _build_positioning_summary(product: DemoProductCard) -> DemoPositioningSummary:
    intrinsic = min(95.0, product.trust_opportunity_score * 0.92 + 6)
    presented = min(95.0, product.trust_opportunity_score * 0.88 + (12 if product.verified_scans < 3 else 4))
    market_validation = min(96.0, product.participation_rate * 100)
    fit_score = max(35.0, 100 - abs(presented - intrinsic))
    return DemoPositioningSummary(
        intrinsic_value_score=round(intrinsic, 2),
        presented_value_score=round(presented, 2),
        market_validation_score=round(market_validation, 2),
        fit_score=round(fit_score, 2),
        product_core_cluster=product.product_core_cluster,
        origin_cluster=product.origin_cluster,
        presentation_cluster=product.presentation_cluster,
        feedback_cluster=product.feedback_cluster,
        positioning_status=product.positioning_status,
        recommendation_direction=product.recommendation_direction,
        stability_score=round(product.stability_score * 100, 2),
        stability_label=product.stability_label,
        summary=f"{product.product_name} 当前更偏向“{product.positioning_status}”，建议沿着“{product.recommendation_direction}”继续优化。",
    )


def _build_strategy_report(
    product: DemoProductCard,
    peer_products: list[DemoProductCard],
    market_insights: list[DemoMarketInsight],
) -> DemoStrategyReport:
    top_cities = [item.city for item in market_insights[:3]]
    peers = [item.product_name for item in peer_products[:3]]
    return DemoStrategyReport(
        title=f"{product.product_name} 经营分析",
        diagnosis=f"当前商品机会分 {product.trust_opportunity_score:.1f}，可信核销 {product.verified_scans}，异常率 {_percent(product.abnormal_rate)}。",
        opportunity=f"建议优先关注 {', '.join(top_cities)} 这类机会分更高的城市，并围绕 {product.region_name} 做稳定可信表达。",
        caution="如异常率继续抬升，应先排查链路和扫码风险，再做放量或高端化动作。",
        actions=[
            "保持产地、批次、扫码链路的一致说明，避免前端信息与实际记录脱节。",
            "先在高机会城市做小范围验证，再决定是否扩渠道或提价。",
            "若异常率偏高，优先做链路核验和重点事件排查。",
        ],
        recommended_markets=top_cities,
        similar_products=peers,
    )


def _build_scenarios(product: DemoProductCard) -> list[DemoScenarioPreview]:
    return [
        DemoScenarioPreview(
            scenario_name="轻量升级表达",
            direction="升级",
            changed_fields=["包装表达", "可信说明"],
            projected_presented_value_score=round(min(product.trust_opportunity_score + 6, 98), 2),
            projected_market_validation_score=round(min(product.trust_opportunity_score + 4, 96), 2),
            projected_positioning_status="定位匹配型" if product.positioning_status == "低估潜力型" else product.positioning_status,
            reason="适合机会分较高且异常率不高的商品先做小步升级。",
        ),
        DemoScenarioPreview(
            scenario_name="维持表达扩城市",
            direction="保持",
            changed_fields=["城市投放", "渠道复制"],
            projected_presented_value_score=round(product.trust_opportunity_score, 2),
            projected_market_validation_score=round(min(product.trust_opportunity_score + 2, 95), 2),
            projected_positioning_status=product.positioning_status,
            reason="适合当前定位已基本成立的商品复制样板城市打法。",
        ),
        DemoScenarioPreview(
            scenario_name="收敛风险后放量",
            direction="收敛",
            changed_fields=["风控排查", "链路校验"],
            projected_presented_value_score=round(max(product.trust_opportunity_score - 2, 10), 2),
            projected_market_validation_score=round(min(product.trust_opportunity_score + 5, 95), 2),
            projected_positioning_status="流通优先型" if product.positioning_status == "过度定位型" else product.positioning_status,
            reason="异常率偏高时，应先收敛风险，再扩大经营动作。",
        ),
    ]


def _build_prompt_preview(
    product: DemoProductCard,
    peers: list[DemoProductCard],
    markets: list[DemoMarketInsight],
    scenarios: list[DemoScenarioPreview],
) -> str:
    return (
        f"当前商品：{product.product_name}；产区：{product.region_name}；品类：{product.category}；"
        f"可信核销 {product.verified_scans}，异常率 {_percent(product.abnormal_rate)}，机会分 {product.trust_opportunity_score:.1f}。"
        f"可参考商品：{'、'.join(item.product_name for item in peers[:3]) or '暂无'}；"
        f"优先城市：{'、'.join(item.city for item in markets[:3]) or '暂无'}；"
        f"策略推演：{'；'.join(item.scenario_name for item in scenarios)}。"
        "请基于这些结构化信息输出经营建议。"
    )


def _select_peer_products(product: DemoProductCard, products: list[DemoProductCard]) -> list[DemoProductCard]:
    peers = [
        item
        for item in products
        if item.product_id != product.product_id and item.category == product.category
    ]
    peers.sort(key=lambda item: (-item.trust_opportunity_score, item.product_name))
    return peers[:4]


def _positioning_status(template_status: str | None, opportunity_score: float, abnormal_rate: float, scans: int) -> str:
    if abnormal_rate >= 0.19:
        return "过度定位型"
    if template_status == "低估潜力型" and abnormal_rate <= 0.1:
        return "低估潜力型"
    if template_status == "过度定位型" and abnormal_rate >= 0.12:
        return "过度定位型"
    if template_status == "定位匹配型" and 46 <= opportunity_score <= 66 and abnormal_rate <= 0.12:
        return "定位匹配型"
    if template_status == "流通优先型" and scans >= 20 and abnormal_rate <= 0.14:
        return "流通优先型"
    if opportunity_score >= 82 and scans <= 28:
        return "低估潜力型"
    if scans >= 55 and abnormal_rate <= 0.12 and opportunity_score < 78:
        return "流通优先型"
    if opportunity_score < 70:
        return "流通优先型"
    return "定位匹配型"


def _recommendation_direction(positioning_status: str) -> str:
    mapping = {
        "低估潜力型": "适度升级",
        "定位匹配型": "维持并复制",
        "流通优先型": "稳定流通",
        "过度定位型": "先收敛风险",
    }
    return mapping[positioning_status]


def _cluster_id(positioning_status: str) -> int:
    mapping = {
        "低估潜力型": 0,
        "定位匹配型": 1,
        "流通优先型": 2,
        "过度定位型": 3,
    }
    return mapping[positioning_status]


def _guess_price_band(product_type: str | None) -> str:
    high = {"绿茶", "黑茶", "饮品"}
    middle = {"干货", "鲜果", "蜂蜜", "水产"}
    product_type = product_type or ""
    if product_type in high:
        return "中高"
    if product_type in middle:
        return "中"
    return "大众"


def _guess_unit_price(product_type: str | None) -> float:
    mapping = {
        "绿茶": 88.0,
        "黑茶": 96.0,
        "饮品": 78.0,
        "鲜果": 49.0,
        "干货": 66.0,
        "蜂蜜": 72.0,
        "水产": 84.0,
        "蔬菜": 36.0,
        "熟食": 58.0,
        "冲调": 42.0,
        "大米": 68.0,
    }
    return mapping.get(product_type or "", 45.0)


def _normalize_place_label(value: str | None) -> str:
    if not value:
        return "未分类"
    return str(value).replace("省", "").replace("市", "")


def _normalize_product_key(value: str) -> str:
    return value.replace("·", "路").replace("•", "路").strip()


def _build_demo_template_map() -> dict[str, DemoProductCard]:
    dashboard = build_demo_dashboard()
    return {
        _normalize_product_key(item.product_name): item
        for item in dashboard.products
    }


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
