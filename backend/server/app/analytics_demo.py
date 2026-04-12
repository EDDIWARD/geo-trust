from __future__ import annotations

import json
import math
import random
from collections import defaultdict
from datetime import datetime
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from .analytics_cluster import run_kmeans
from .analytics_config import load_analytics_weights, load_city_profiles
from .analytics_schemas import (
    DemoClusterSummary,
    DemoDashboardResponse,
    DemoIndicatorDefinition,
    DemoMarketLearningItem,
    DemoMarketInsight,
    DemoOverviewMetric,
    DemoPositioningSummary,
    DemoProductCard,
    DemoProductReportResponse,
    DemoScenarioPreview,
    DemoStrategyReport,
)

MODULE_NAME = "可信价值挖掘 Demo"
DATA_PATH = Path(__file__).resolve().parents[1] / "mock_data" / "trusted_value_demo_data.json"
WEIGHTS = load_analytics_weights()
CITIES = load_city_profiles()
PRICE_BAND_SCORE = WEIGHTS["price_band_score"]
POSITIONING_ORDER = {
    "低估潜力型": 0,
    "定位匹配型": 1,
    "流通优先型": 2,
    "过度定位型": 3,
}


@lru_cache(maxsize=1)
def _load_dataset() -> dict:
    with DATA_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_demo_dashboard() -> DemoDashboardResponse:
    analysis = _analyze_products()
    return DemoDashboardResponse(
        module_name=MODULE_NAME,
        generated_at=_now_text(),
        narrative=(
            "这一版分析把商品拆成产品本体、产地信号、当前呈现方式、市场反馈四个视角，"
            "再判断当前位置是低估、匹配、流通优先还是过度定位。"
        ),
        overview_metrics=_build_overview_metrics(analysis["products"]),
        indicator_definitions=_build_indicator_definitions(),
        clusters=analysis["clusters"],
        products=[_to_product_card(item) for item in analysis["ordered_products"]],
        market_heat=_build_global_market_heat(analysis["products"]),
    )


def build_demo_product_report(product_id: str) -> DemoProductReportResponse:
    analysis = _analyze_products()
    product = next((item for item in analysis["products"] if item["product_id"] == product_id), None)
    if product is None:
        raise KeyError(product_id)

    peer_products = _select_peer_products(product, analysis["products"])
    market_insights = _build_product_market_insights(product)
    market_learning = _build_market_learning(product, analysis["products"], market_insights)
    positioning_summary = _build_positioning_summary(product)
    scenarios = _build_scenarios(product)

    return DemoProductReportResponse(
        module_name=MODULE_NAME,
        generated_at=_now_text(),
        product=_to_product_card(product),
        positioning_summary=positioning_summary,
        strategy_report=_build_strategy_report(product, peer_products, market_insights),
        prompt_preview=_build_prompt_preview(product, peer_products, market_insights, scenarios),
        scenarios=scenarios,
        market_insights=market_insights,
        market_learning=market_learning,
        peer_products=[_to_product_card(item) for item in peer_products],
        notes=[
            "这组数据采用“基础产品 + 不同经营版本”的方式构造，用来展示同一种商品在不同定位下的变化。",
            "总销量为经营侧填报值或模拟推演值，可信核销与异常行为则由规则模型推演得出。",
            "稳定性分数来自参数扰动后的重复测算，用来观察当前定位结论是否容易因为权重变化而翻转。",
            "AI 只负责把结构化诊断写成正式建议，不负责替代前面的指标计算与定位判断。",
        ],
        vector_preview={key: round(value, 4) for key, value in product["all_vector"].items()},
        raw_fields={
            "reference_note": product["reference_note"],
            "core": product["core"],
            "origin": product["origin"],
            "presentation": product["presentation"],
            "markets": product["markets"],
            "price_signal_score": round(product["price_signal_score"], 4),
            "price_acceptance_score": round(product["price_acceptance_score"], 4),
            "declared_sales": product["declared_sales"],
            "verified_scans": product["verified_scans"],
            "stability_distribution": product["stability_distribution"],
        },
    )


def _analyze_products(weights: dict | None = None, include_stability: bool = True) -> dict:
    raw_dataset = _load_dataset()
    effective_weights = deepcopy(weights or WEIGHTS)
    products = _expand_products(raw_dataset)
    dataset_stats = _build_dataset_stats(products)
    _run_demo_simulator(products, dataset_stats, effective_weights)

    _assign_view_clusters(products, "core", _core_vector_keys(), 4, _label_core_cluster)
    _assign_view_clusters(products, "origin", _origin_vector_keys(), 4, _label_origin_cluster)
    _assign_view_clusters(products, "presentation", _presentation_vector_keys(), 4, _label_presentation_cluster)
    _assign_view_clusters(products, "feedback", _feedback_vector_keys(), 4, _label_feedback_cluster)

    for product in products:
        product["presentation_cluster"] = _calibrate_presentation_cluster(product)
        product["feedback_cluster"] = _calibrate_feedback_cluster(product)
        _finalize_positioning(product)

    if include_stability:
        stability_map = _build_stability_index(products, effective_weights)
        for product in products:
            stability = stability_map[product["product_id"]]
            product["stability_score"] = stability["score"]
            product["stability_label"] = stability["label"]
            product["stability_distribution"] = stability["distribution"]
    else:
        for product in products:
            product["stability_score"] = 1.0
            product["stability_label"] = "未评估"
            product["stability_distribution"] = {product["positioning_status"]: 1.0}

    grouped = _group_by_positioning(products)
    ordered_products = sorted(
        products,
        key=lambda item: (
            POSITIONING_ORDER.get(item["positioning_status"], 9),
            -item["trust_opportunity_score"],
        ),
    )

    return {
        "products": products,
        "ordered_products": ordered_products,
        "clusters": grouped,
        "dataset_stats": dataset_stats,
    }


def _expand_products(dataset: dict) -> list[dict]:
    products: list[dict] = []
    for base in dataset["base_products"]:
        for variant in base["variants"]:
            product = {
                "product_id": variant["variant_id"],
                "product_name": f"{base['family_name']}·{variant['variant_name']}",
                "family_name": base["family_name"],
                "variant_name": variant["variant_name"],
                "category": base["category"],
                "region_name": base["region_name"],
                "season": base["season"],
                "channel": variant["channel"],
                "price_band": variant["price_band"],
                "unit_price": float(variant["unit_price"]),
                "launch_quantity": int(variant["launch_quantity"]),
                "tags": base["tags"],
                "reference_note": base["reference_note"],
                "core": base["core"],
                "origin": base["origin"],
                "presentation": variant["presentation"],
            }
            products.append(product)
    return products


def _build_dataset_stats(products: list[dict]) -> dict:
    category_prices: dict[str, list[float]] = defaultdict(list)
    family_prices: dict[str, list[float]] = defaultdict(list)
    for product in products:
        category_prices[product["category"]].append(product["unit_price"])
        family_prices[product["family_name"]].append(product["unit_price"])
    return {
        "category_prices": {
            category: {
                "min": min(values),
                "max": max(values),
                "avg": _avg(values),
            }
            for category, values in category_prices.items()
        },
        "family_prices": {
            family: {
                "min": min(values),
                "max": max(values),
                "avg": _avg(values),
            }
            for family, values in family_prices.items()
        },
    }


def _run_demo_simulator(products: list[dict], dataset_stats: dict, weights: dict) -> None:
    for product in products:
        simulation = _simulate_product_metrics(product, dataset_stats, weights)
        product.update(simulation)
        _attach_vectors(product)


def _simulate_product_metrics(product: dict, dataset_stats: dict, weights: dict) -> dict:
    core = product["core"]
    origin = product["origin"]
    presentation = product["presentation"]

    price_signal_score = _price_signal_score(product, dataset_stats)
    intrinsic_norm = _intrinsic_value_norm(core, origin, weights)
    presented_norm = _presented_value_norm(presentation, weights)
    target_norm = (
        weights["target_norm"]["intrinsic_norm"] * intrinsic_norm
        + weights["target_norm"]["giftability"] * core["giftability"]
        + weights["target_norm"]["traceability_fit"] * origin["traceability_fit"]
    )

    over_gap = max(presented_norm - target_norm, 0.0)
    under_gap = max(target_norm - presented_norm, 0.0)
    fit_score = _clamp(1.0 - abs(presented_norm - target_norm) * weights["fit_score"]["gap_multiplier"])

    price_stress = (
        weights["price_stress"]["price_x_daily"] * presentation["price_position"] * core["daily_consumption_fit"]
        + weights["price_stress"]["price_x_freshness"] * presentation["price_position"] * core["freshness_sensitivity"]
        + weights["price_stress"]["package_vs_giftability"] * presentation["package_intensity"] * (1.0 - core["giftability"])
        + weights["price_stress"]["over_gap"] * over_gap
    )
    price_acceptance = _clamp(
        weights["price_acceptance"]["base"]
        + weights["price_acceptance"]["fit_score"] * fit_score
        + weights["price_acceptance"]["standardization"] * core["standardization"]
        + weights["price_acceptance"]["shelf_stability"] * (1.0 - core["perishability"])
        + weights["price_acceptance"]["giftability"] * core["giftability"]
        - weights["price_acceptance"]["price_stress_penalty"] * price_stress
        + weights["price_acceptance"]["under_gap_bonus"] * under_gap
    )

    activation_rate = _clamp(
        weights["activation_rate"]["base"]
        + weights["activation_rate"]["authenticity_sensitivity"] * core["authenticity_sensitivity"]
        + weights["activation_rate"]["traceability_fit"] * origin["traceability_fit"]
        + weights["activation_rate"]["fit_score"] * fit_score
        + weights["activation_rate"]["narrative_alignment"] * presentation["narrative_intensity"] * core["narrative_affinity"]
        + weights["activation_rate"]["channel_premium"] * presentation["channel_premium"]
        - weights["activation_rate"]["perishability_penalty"] * core["perishability"]
    )
    participation_rate = _clamp(
        weights["participation_rate"]["base"]
        + weights["participation_rate"]["fit_score"] * fit_score
        + weights["participation_rate"]["authenticity_sensitivity"] * core["authenticity_sensitivity"]
        + weights["participation_rate"]["origin_fame"] * origin["origin_fame"]
        + weights["participation_rate"]["gift_package_alignment"] * core["giftability"] * presentation["package_intensity"]
        - weights["participation_rate"]["over_gap_penalty"] * over_gap
        - weights["participation_rate"]["price_stress_penalty"] * price_stress
        + weights["participation_rate"]["under_gap_bonus"] * under_gap
    )
    cross_region_rate = _clamp(
        weights["cross_region_rate"]["base"]
        + weights["cross_region_rate"]["transportability"] * core["transportability"]
        + weights["cross_region_rate"]["origin_fame"] * origin["origin_fame"]
        + weights["cross_region_rate"]["channel_premium"] * presentation["channel_premium"]
        + weights["cross_region_rate"]["giftability"] * core["giftability"]
        - weights["cross_region_rate"]["freshness_penalty"] * core["freshness_sensitivity"]
        - weights["cross_region_rate"]["perishability_penalty"] * core["perishability"]
        - weights["cross_region_rate"]["over_gap_penalty"] * over_gap
        - weights["cross_region_rate"]["price_daily_penalty"] * presentation["price_position"] * core["daily_consumption_fit"]
    )
    repeat_scan_rate = _clamp(
        weights["repeat_scan_rate"]["base"]
        + weights["repeat_scan_rate"]["giftability"] * core["giftability"]
        + weights["repeat_scan_rate"]["origin_fame"] * origin["origin_fame"]
        + weights["repeat_scan_rate"]["narrative_intensity"] * presentation["narrative_intensity"]
        - weights["repeat_scan_rate"]["fit_score_penalty"] * fit_score
    )
    abnormal_rate = _clamp(
        weights["abnormal_rate"]["base"]
        + weights["abnormal_rate"]["perishability"] * core["perishability"]
        + weights["abnormal_rate"]["non_standardization"] * (1.0 - core["standardization"])
        + weights["abnormal_rate"]["channel_premium"] * presentation["channel_premium"]
        - weights["abnormal_rate"]["fit_score_bonus"] * fit_score,
        weights["abnormal_rate"]["min"],
        weights["abnormal_rate"]["max"],
    )

    sales_rate = _clamp(
        weights["sales_rate"]["base"]
        + weights["sales_rate"]["fit_score"] * fit_score
        + weights["sales_rate"]["price_acceptance"] * price_acceptance
        + weights["sales_rate"]["daily_consumption_fit"] * core["daily_consumption_fit"]
        + weights["sales_rate"]["origin_fame"] * origin["origin_fame"]
        - weights["sales_rate"]["over_gap_penalty"] * over_gap
        - weights["sales_rate"]["perishability_penalty"] * core["perishability"]
    )
    declared_sales = max(1, int(round(product["launch_quantity"] * sales_rate)))
    verified_scans = max(1, int(round(declared_sales * participation_rate)))
    unique_device_ratio = _clamp(0.72 + 0.14 * fit_score - 0.05 * core["giftability"] + 0.05 * price_acceptance)
    unique_scan_devices = max(1, int(round(verified_scans * unique_device_ratio)))
    repeat_scans = max(0, int(round(verified_scans * repeat_scan_rate)))
    abnormal_scans = max(0, int(round(verified_scans * abnormal_rate)))
    cross_region_scans = max(0, int(round(verified_scans * cross_region_rate)))

    market_validation = _clamp(
        weights["market_validation"]["participation_rate"] * participation_rate
        + weights["market_validation"]["activation_rate"] * activation_rate
        + weights["market_validation"]["cross_region_rate"] * cross_region_rate
        + weights["market_validation"]["price_acceptance"] * price_acceptance
        + weights["market_validation"]["fit_score"] * fit_score
        + weights["market_validation"]["stability_score"] * (1.0 - abnormal_rate)
    )
    trust_opportunity_score = 100 * (
        weights["trust_opportunity"]["market_validation"] * market_validation
        + weights["trust_opportunity"]["intrinsic_norm"] * intrinsic_norm
        + weights["trust_opportunity"]["price_acceptance"] * price_acceptance
        + weights["trust_opportunity"]["activation_rate"] * activation_rate
        + weights["trust_opportunity"]["participation_rate"] * participation_rate
        + weights["trust_opportunity"]["cross_region_rate"] * cross_region_rate
        + weights["trust_opportunity"]["fit_score"] * fit_score
    )

    simulated = {
        "price_signal_score": price_signal_score,
        "intrinsic_value_norm": intrinsic_norm,
        "presented_value_norm": presented_norm,
        "target_value_norm": target_norm,
        "value_gap": presented_norm - target_norm,
        "fit_score": fit_score,
        "price_acceptance_score": price_acceptance,
        "activation_rate": activation_rate,
        "participation_rate": participation_rate,
        "cross_region_rate": cross_region_rate,
        "repeat_scan_rate": repeat_scan_rate,
        "abnormal_rate": abnormal_rate,
        "declared_sales": declared_sales,
        "verified_scans": verified_scans,
        "unique_scan_devices": unique_scan_devices,
        "repeat_scans": repeat_scans,
        "abnormal_scans": abnormal_scans,
        "cross_region_scans": cross_region_scans,
        "market_validation_score": market_validation,
        "trust_opportunity_score": round(trust_opportunity_score, 2),
    }
    simulated["markets"] = _build_city_breakdown({**product, **simulated}, weights)
    return simulated


def _attach_vectors(product: dict) -> None:
    core = product["core"]
    origin = product["origin"]
    presentation = product["presentation"]
    product["core_vector"] = {
        "giftability": core["giftability"],
        "narrative_affinity": core["narrative_affinity"],
        "daily_consumption_fit": core["daily_consumption_fit"],
        "freshness_sensitivity": core["freshness_sensitivity"],
        "transportability": core["transportability"],
        "premium_capacity": core["premium_capacity"],
    }
    product["origin_vector"] = {
        "origin_fame": origin["origin_fame"],
        "gi_strength": origin["gi_strength"],
        "natural_uniqueness": origin["natural_uniqueness"],
        "seasonal_signal": origin["seasonal_signal"],
        "traceability_fit": origin["traceability_fit"],
    }
    product["presentation_vector"] = {
        "package_intensity": presentation["package_intensity"],
        "narrative_intensity": presentation["narrative_intensity"],
        "channel_premium": presentation["channel_premium"],
        "price_position": presentation["price_position"],
        "price_signal_score": product["price_signal_score"],
    }
    product["feedback_vector"] = {
        "activation_rate": product["activation_rate"],
        "participation_rate": product["participation_rate"],
        "cross_region_rate": product["cross_region_rate"],
        "price_acceptance_score": product["price_acceptance_score"],
        "market_validation_score": product["market_validation_score"],
        "value_gap": product["value_gap"],
        "stability_score": 1.0 - product["abnormal_rate"],
        "fit_score": product["fit_score"],
    }
    product["all_vector"] = {
        **product["core_vector"],
        **product["origin_vector"],
        **product["presentation_vector"],
        **product["feedback_vector"],
    }


def _price_signal_score(product: dict, dataset_stats: dict) -> float:
    category_stats = dataset_stats["category_prices"][product["category"]]
    family_stats = dataset_stats["family_prices"][product["family_name"]]
    category_score = _safe_divide(
        product["unit_price"] - category_stats["min"],
        max(category_stats["max"] - category_stats["min"], 1.0),
    )
    family_score = _safe_divide(
        product["unit_price"] - family_stats["min"],
        max(family_stats["max"] - family_stats["min"], 1.0),
    )
    band_prior = PRICE_BAND_SCORE.get(product["price_band"], 0.54)
    return _clamp(0.5 * category_score + 0.2 * family_score + 0.3 * band_prior)


def _build_stability_index(products: list[dict], weights: dict) -> dict[str, dict]:
    config = weights["sensitivity"]
    rng = random.Random(config["seed"])
    tracked_groups = config["tracked_groups"]
    run_count = config["runs"]
    base_statuses = {product["product_id"]: product["positioning_status"] for product in products}
    counters: dict[str, dict[str, int]] = {
        product["product_id"]: defaultdict(int)
        for product in products
    }

    for _ in range(run_count):
        perturbed_weights = _perturb_weights(weights, tracked_groups, config["noise"], rng)
        sensitivity_products = _analyze_products(weights=perturbed_weights, include_stability=False)["products"]
        for item in sensitivity_products:
            counters[item["product_id"]][item["positioning_status"]] += 1

    stability = {}
    for product in products:
        distribution_counts = counters[product["product_id"]]
        base_status = base_statuses[product["product_id"]]
        same_status_count = distribution_counts.get(base_status, 0)
        score = _safe_divide(same_status_count, run_count)
        if score >= 0.84:
            label = "高稳定"
        elif score >= 0.68:
            label = "中稳定"
        else:
            label = "待复核"
        stability[product["product_id"]] = {
            "score": round(score, 4),
            "label": label,
            "distribution": {
                status: round(_safe_divide(count, run_count), 4)
                for status, count in sorted(distribution_counts.items())
            },
        }
    return stability


def _perturb_weights(base_weights: dict, tracked_groups: list[str], noise: float, rng: random.Random) -> dict:
    mutated = deepcopy(base_weights)
    for group_path in tracked_groups:
        group = _nested_get(mutated, group_path)
        if not isinstance(group, dict):
            continue
        for key_path in _collect_numeric_leaf_paths(group_path, group):
            leaf_name = key_path.split(".")[-1]
            if leaf_name in {"min", "max", "runs", "noise", "seed"} or leaf_name.endswith("_floor"):
                continue
            current = _nested_get(mutated, key_path)
            if not isinstance(current, (int, float)):
                continue
            factor = 1.0 + rng.uniform(-noise, noise)
            _nested_set(mutated, key_path, max(current * factor, 1e-6))
    return mutated


def _collect_numeric_leaf_paths(prefix: str, node: dict) -> list[str]:
    paths: list[str] = []
    for key, value in node.items():
        next_prefix = f"{prefix}.{key}"
        if isinstance(value, dict):
            paths.extend(_collect_numeric_leaf_paths(next_prefix, value))
        elif isinstance(value, (int, float)):
            paths.append(next_prefix)
    return paths


def _nested_get(payload: dict, dotted_path: str):
    current = payload
    for part in dotted_path.split("."):
        current = current[part]
    return current


def _nested_set(payload: dict, dotted_path: str, value: float) -> None:
    parts = dotted_path.split(".")
    current = payload
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = value


def _assign_view_clusters(
    products: list[dict],
    view_name: str,
    feature_names: list[str],
    cluster_count: int,
    labeler,
) -> None:
    vectors = [[product[f"{view_name}_vector"][name] for name in feature_names] for product in products]
    assignments, centers = run_kmeans(vectors, cluster_count)

    members: dict[int, list[dict]] = defaultdict(list)
    for product, cluster_id in zip(products, assignments):
        members[cluster_id].append(product)

    labels = {cluster_id: labeler(centers[cluster_id], members[cluster_id]) for cluster_id in members}
    key = {
        "core": "product_core_cluster",
        "origin": "origin_cluster",
        "presentation": "presentation_cluster",
        "feedback": "feedback_cluster",
    }[view_name]
    for product, cluster_id in zip(products, assignments):
        product[key] = labels[cluster_id]


def _label_core_cluster(center: list[float], members: list[dict]) -> str:
    giftability, narrative, daily, freshness, transport, premium = center
    if freshness >= 0.68:
        return "鲜食时令型"
    if giftability >= 0.72 and premium >= 0.72:
        return "高信任礼赠型"
    if daily >= 0.72 and giftability < 0.6:
        return "日常民生型"
    if transport >= 0.8 and narrative >= 0.5:
        return "地方伴手礼型"
    return "区域特色型"


def _label_origin_cluster(center: list[float], members: list[dict]) -> str:
    fame, gi_strength, natural, seasonal, traceability = center
    if fame >= 0.8 and gi_strength >= 0.78:
        return "强地标名产型"
    if seasonal >= 0.75 and natural >= 0.68:
        return "时令产地型"
    if traceability >= 0.72:
        return "可信产源型"
    return "一般产区型"


def _label_presentation_cluster(center: list[float], members: list[dict]) -> str:
    package_intensity, narrative, channel_premium, price_position, price_band_score = center
    if package_intensity >= 0.72 and narrative >= 0.68 and (price_position >= 0.62 or channel_premium >= 0.68):
        return "高叙事高礼盒型"
    if price_position <= 0.3 and package_intensity <= 0.28:
        return "大众走量型"
    if package_intensity >= 0.38 or narrative >= 0.4:
        return "轻礼表达型"
    return "平衡零售型"


def _label_feedback_cluster(center: list[float], members: list[dict]) -> str:
    activation, participation, cross_region, price_acceptance, validation, value_gap, stability, fit_score = center
    if participation >= 0.39 and price_acceptance >= 0.71 and validation >= 0.52 and fit_score >= 0.82:
        return "高认可外拓型"
    if price_acceptance < 0.66 and (fit_score < 0.7 or value_gap > 0.1):
        return "高价受阻型"
    if activation >= 0.24 and participation < 0.3 and validation < 0.46:
        return "可见但未转化型"
    return "本地稳销型"


def _calibrate_feedback_cluster(product: dict) -> str:
    if (
        product["market_validation_score"] >= 0.52
        and product["participation_rate"] >= 0.39
        and product["price_acceptance_score"] >= 0.71
        and product["cross_region_rate"] >= 0.24
    ):
        return "高认可外拓型"
    if (
        product["price_acceptance_score"] < 0.66
        and (product["value_gap"] > 0.1 or product["market_validation_score"] < 0.43)
    ):
        return "高价受阻型"
    if (
        product["activation_rate"] >= 0.24
        and product["participation_rate"] < 0.3
        and product["market_validation_score"] < 0.46
    ):
        return "可见但未转化型"
    return "本地稳销型"


def _calibrate_presentation_cluster(product: dict) -> str:
    presentation = product["presentation"]
    if (
        presentation["package_intensity"] >= 0.72
        and presentation["narrative_intensity"] >= 0.68
        and (presentation["price_position"] >= 0.62 or presentation["channel_premium"] >= 0.68)
    ):
        return "高叙事高礼盒型"
    if presentation["price_position"] <= 0.3 and presentation["package_intensity"] <= 0.28:
        return "大众走量型"
    if presentation["package_intensity"] >= 0.38 or presentation["narrative_intensity"] >= 0.4:
        return "轻礼表达型"
    return "平衡零售型"


def _finalize_positioning(product: dict) -> None:
    presented = product["presented_value_norm"]
    target = product["target_value_norm"]
    validation = product["market_validation_score"]
    fit_score = product["fit_score"]
    over_gap = presented - target
    under_gap = target - presented

    if over_gap >= 0.14 and validation < 0.48:
        status = "过度定位型"
        direction = "降价去包装"
        description = "当前包装和定价明显高于商品本体与产地所能承载的价值，市场反馈不足。"
    elif (
        under_gap >= 0.13
        and product["intrinsic_value_norm"] >= 0.62
        and validation >= 0.49
        and product["price_acceptance_score"] >= 0.66
    ):
        status = "低估潜力型"
        direction = "适度升级"
        description = "商品本体和产地信号具备更高的表达空间，但当前呈现偏保守。"
    elif fit_score >= 0.74 and validation >= 0.46 and over_gap < 0.16:
        status = "定位匹配型"
        direction = "保持并放大"
        description = "当前呈现方式与商品本体较匹配，市场也给出了正向反馈。"
    else:
        status = "流通优先型"
        direction = "稳流通轻包装"
        description = "更适合强调稳定供应、价格接受度和流通效率，而不是进一步抬高叙事。"

    product["positioning_status"] = status
    product["recommendation_direction"] = direction
    product["positioning_description"] = description
    product["cluster_name"] = status
    product["cluster_id"] = POSITIONING_ORDER.get(status, 9)


def _group_by_positioning(products: list[dict]) -> list[DemoClusterSummary]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for product in products:
        buckets[product["positioning_status"]].append(product)

    descriptions = {
        "低估潜力型": "商品本体与产地信号比当前卖法更强，适合适度升级包装、渠道或可信表达。",
        "定位匹配型": "当前位置比较合适，重点不是大改，而是复制有效策略、稳步扩面。",
        "流通优先型": "这类商品更吃稳定供给和价格效率，可信价值应服务流通而不是硬抬高端。",
        "过度定位型": "当前包装或价格抬得过高，市场并没有为这套叙事充分买单。",
    }

    results = []
    for status, items in sorted(buckets.items(), key=lambda row: POSITIONING_ORDER.get(row[0], 9)):
        results.append(
            DemoClusterSummary(
                cluster_id=POSITIONING_ORDER.get(status, 9),
                cluster_name=status,
                description=descriptions[status],
                product_count=len(items),
                average_activation_rate=round(_avg([item["activation_rate"] for item in items]), 4),
                average_participation_rate=round(_avg([item["participation_rate"] for item in items]), 4),
                average_cross_region_rate=round(_avg([item["cross_region_rate"] for item in items]), 4),
                average_opportunity_score=round(_avg([item["trust_opportunity_score"] for item in items]), 2),
                representative_products=[
                    item["product_name"]
                    for item in sorted(items, key=lambda row: row["trust_opportunity_score"], reverse=True)[:3]
                ],
            )
        )
    return results


def _build_city_breakdown(product: dict, weights: dict | None = None) -> list[dict]:
    effective_weights = weights or WEIGHTS
    breakdown_weights = effective_weights["city_breakdown"]
    city_fit_weights = effective_weights["city_fit_score"]
    weights = []
    for city, profile in CITIES.items():
        local_bonus = 0.18 if city in product["region_name"] else 0.0
        category_fit = _city_category_fit(product, city)
        scene_fit = _city_scene_fit(product, city, effective_weights)
        price_fit = _city_price_fit(product, city, effective_weights)
        city_fit_score = _clamp(
            city_fit_weights["category_fit"] * category_fit
            + city_fit_weights["scene_fit"] * scene_fit
            + city_fit_weights["price_fit"] * price_fit
            + city_fit_weights["price_acceptance_score"] * product["price_acceptance_score"]
            + city_fit_weights["fit_score"] * product["fit_score"]
        )
        overreach_penalty = max(
            product["presented_value_norm"]
            - (
                effective_weights["target_norm"]["intrinsic_norm"] * product["intrinsic_value_norm"]
                + effective_weights["target_norm"]["giftability"] * _city_premium_capacity(profile, effective_weights)
            ),
            0.0,
        )
        score_weights = breakdown_weights["score"]
        score = (
            score_weights["city_fit_score"] * city_fit_score
            + score_weights["price_acceptance_score"] * product["price_acceptance_score"]
            + score_weights["market_validation_score"] * product["market_validation_score"]
            + score_weights["activation_rate"] * product["activation_rate"]
            + score_weights["cross_region_rate"] * product["cross_region_rate"]
            + score_weights["origin_fame"] * product["origin"]["origin_fame"]
            + score_weights["local_bonus"] * local_bonus
            - score_weights["overreach_penalty"] * overreach_penalty
            - score_weights["price_fit_shortfall"] * max(breakdown_weights["price_fit_floor"] - price_fit, 0.0)
            - score_weights["category_fit_shortfall"] * max(breakdown_weights["category_fit_floor"] - category_fit, 0.0)
        )
        weights.append(
            (
                city,
                {
                    "weight": max(score, 0.03) ** breakdown_weights["weight_power"],
                    "category_fit": category_fit,
                    "scene_fit": scene_fit,
                    "price_fit": price_fit,
                    "city_fit_score": city_fit_score,
                    "overreach_penalty": overreach_penalty,
                    "local_bonus": local_bonus,
                },
            )
        )

    weight_sum = sum(row["weight"] for _, row in weights)
    rows = []
    allocated = 0
    for index, (city, row) in enumerate(weights):
        if index == len(weights) - 1:
            scans = max(product["verified_scans"] - allocated, 0)
        else:
            scans = int(round(product["verified_scans"] * row["weight"] / weight_sum))
            allocated += scans
        abnormal_weights = breakdown_weights["abnormal_rate"]
        city_abnormal_rate = _clamp(
            product["abnormal_rate"]
            + abnormal_weights["price_fit_gap"] * (1.0 - row["price_fit"])
            + abnormal_weights["scene_fit_gap"] * (1.0 - row["scene_fit"])
            + abnormal_weights["category_fit_gap"] * (1.0 - row["category_fit"])
            + abnormal_weights["overreach_penalty"] * row["overreach_penalty"]
            - abnormal_weights["local_bonus"] * row["local_bonus"],
            abnormal_weights["min"],
            abnormal_weights["max"],
        )
        abnormal_scans = int(round(scans * city_abnormal_rate))
        rows.append(
            {
                "city": city,
                "verified_scans": scans,
                "abnormal_scans": max(0, min(scans, abnormal_scans)),
                "category_fit": row["category_fit"],
                "scene_fit": row["scene_fit"],
                "price_fit": row["price_fit"],
                "city_fit_score": row["city_fit_score"],
                "overreach_penalty": row["overreach_penalty"],
            }
        )
    return rows


def _city_category_fit(product: dict, city: str) -> float:
    profile = CITIES[city]
    category = product["category"]
    if category in {"绿茶", "黑茶"}:
        return 0.58 * profile["tea"] + 0.22 * profile["gift"] + 0.2 * profile["premium"]
    if category == "饮品":
        return 0.5 * profile["beverage"] + 0.3 * profile["culture"] + 0.2 * profile["mass"]
    if category in {"水产", "熟食"}:
        return 0.46 * profile["seafood"] + 0.28 * profile["fresh"] + 0.26 * profile["gift"]
    if category in {"鲜果", "蔬菜"}:
        return 0.46 * profile["fresh"] + 0.34 * profile["mass"] + 0.2 * profile["gift"]
    if category in {"冲调", "干货"}:
        return 0.42 * profile["culture"] + 0.32 * profile["mass"] + 0.26 * profile["gift"]
    return 0.34 * profile["mass"] + 0.33 * profile["premium"] + 0.33 * profile["culture"]


def _city_premium_capacity(profile: dict, weights: dict | None = None) -> float:
    effective_weights = weights or WEIGHTS
    premium_weights = effective_weights["city_premium_capacity"]
    return (
        premium_weights["premium"] * profile["premium"]
        + premium_weights["gift"] * profile["gift"]
        + premium_weights["culture"] * profile["culture"]
    )


def _city_scene_fit(product: dict, city: str, weights: dict | None = None) -> float:
    effective_weights = weights or WEIGHTS
    scene_weights = effective_weights["city_scene_fit"]
    profile = CITIES[city]
    gift_scene_need = (
        scene_weights["gift_scene_need"]["giftability"] * product["core"]["giftability"]
        + scene_weights["gift_scene_need"]["package_intensity"] * product["presentation"]["package_intensity"]
        + scene_weights["gift_scene_need"]["narrative_intensity"] * product["presentation"]["narrative_intensity"]
        + scene_weights["gift_scene_need"]["channel_premium"] * product["presentation"]["channel_premium"]
    )
    daily_scene_need = (
        scene_weights["daily_scene_need"]["daily_consumption_fit"] * product["core"]["daily_consumption_fit"]
        + scene_weights["daily_scene_need"]["package_lightness"] * (1.0 - product["presentation"]["package_intensity"])
        + scene_weights["daily_scene_need"]["price_lightness"] * (1.0 - product["presentation"]["price_position"])
        + scene_weights["daily_scene_need"]["transportability"] * product["core"]["transportability"]
    )
    city_gift_scene = (
        scene_weights["city_gift_scene"]["gift"] * profile["gift"]
        + scene_weights["city_gift_scene"]["premium"] * profile["premium"]
        + scene_weights["city_gift_scene"]["culture"] * profile["culture"]
    )
    city_daily_scene = (
        scene_weights["city_daily_scene"]["mass"] * profile["mass"]
        + scene_weights["city_daily_scene"]["fresh"] * profile["fresh"]
        + scene_weights["city_daily_scene"]["beverage"] * profile["beverage"]
    )
    gift_share = _clamp(
        scene_weights["gift_share"]["giftability"] * product["core"]["giftability"]
        + scene_weights["gift_share"]["package_intensity"] * product["presentation"]["package_intensity"]
        + scene_weights["gift_share"]["price_position"] * product["presentation"]["price_position"]
    )
    gift_fit = 1.0 - scene_weights["gift_penalty"] * abs(gift_scene_need - city_gift_scene)
    daily_fit = 1.0 - scene_weights["daily_penalty"] * abs(daily_scene_need - city_daily_scene)
    return _clamp(gift_share * gift_fit + (1.0 - gift_share) * daily_fit)


def _city_price_fit(product: dict, city: str, weights: dict | None = None) -> float:
    effective_weights = weights or WEIGHTS
    price_weights = effective_weights["city_price_fit"]
    profile = CITIES[city]
    city_price_ceiling = (
        price_weights["city_price_ceiling"]["premium"] * profile["premium"]
        + price_weights["city_price_ceiling"]["gift"] * profile["gift"]
        + price_weights["city_price_ceiling"]["culture"] * profile["culture"]
        + price_weights["city_price_ceiling"]["mass"] * profile["mass"]
    )
    product_price_need = (
        price_weights["product_price_need"]["price_position"] * product["presentation"]["price_position"]
        + price_weights["product_price_need"]["package_intensity"] * product["presentation"]["package_intensity"]
        + price_weights["product_price_need"]["narrative_intensity"] * product["presentation"]["narrative_intensity"]
        + price_weights["product_price_need"]["price_band_score"] * product["price_signal_score"]
    )
    intrinsic_support = (
        price_weights["intrinsic_support"]["premium_capacity"] * product["core"]["premium_capacity"]
        + price_weights["intrinsic_support"]["giftability"] * product["core"]["giftability"]
        + price_weights["intrinsic_support"]["origin_fame"] * product["origin"]["origin_fame"]
        + price_weights["intrinsic_support"]["gi_strength"] * product["origin"]["gi_strength"]
    )
    supported_price_need = (
        price_weights["supported_mix"]["intrinsic_support"] * intrinsic_support
        + price_weights["supported_mix"]["city_price_ceiling"] * city_price_ceiling
    )
    over_price_gap = max(product_price_need - supported_price_need, 0.0)
    return _clamp(
        1.0
        - price_weights["abs_penalty"] * abs(product_price_need - supported_price_need)
        - price_weights["over_price_penalty"] * over_price_gap
    )


def _select_peer_products(product: dict, products: list[dict]) -> list[dict]:
    same_family = []
    same_category_other_region = []
    same_core = []
    for candidate in products:
        if candidate["product_id"] == product["product_id"]:
            continue
        if candidate["market_validation_score"] <= product["market_validation_score"]:
            continue
        if candidate["family_name"] == product["family_name"]:
            same_family.append(candidate)
        elif candidate["category"] == product["category"] and candidate["region_name"] != product["region_name"]:
            same_category_other_region.append(candidate)
        elif candidate["product_core_cluster"] == product["product_core_cluster"]:
            same_core.append(candidate)

    def sort_key(item: dict) -> tuple:
        return (
            abs(item["intrinsic_value_norm"] - product["intrinsic_value_norm"]),
            abs(item["presented_value_norm"] - product["target_value_norm"]),
            -item["market_validation_score"],
        )

    same_family.sort(key=sort_key)
    same_category_other_region.sort(key=sort_key)
    same_core.sort(key=sort_key)

    picked: list[dict] = []
    seen: set[str] = set()
    for group in (same_family, same_category_other_region, same_core):
        for item in group:
            if item["product_id"] in seen:
                continue
            picked.append(item)
            seen.add(item["product_id"])
            if len(picked) >= 4:
                return picked
    return picked


def _build_global_market_heat(products: list[dict]) -> list[DemoMarketInsight]:
    bucket: dict[str, dict[str, float]] = defaultdict(lambda: {"verified": 0, "score": 0.0, "count": 0})
    for product in products:
        for market in product["markets"]:
            city = market["city"]
            city_validation = (
                0.46 * _safe_divide(market["verified_scans"], max(product["verified_scans"], 1))
                + 0.22 * (1.0 - _safe_divide(market["abnormal_scans"], max(market["verified_scans"], 1)))
                + 0.18 * product["market_validation_score"]
                + 0.14 * product["fit_score"]
            )
            bucket[city]["verified"] += market["verified_scans"]
            bucket[city]["score"] += city_validation
            bucket[city]["count"] += 1

    rows = []
    for city, row in bucket.items():
        score = row["score"] / row["count"]
        rows.append(
            {
                "city": city,
                "verified_scans": int(row["verified"]),
                "score": score,
            }
        )
    return _finalize_market_insights(rows, scope="global")


def _build_product_market_insights(product: dict) -> list[DemoMarketInsight]:
    rows = []
    for market in product["markets"]:
        market_score = _city_market_score(product, market)
        rows.append(
            {
                "city": market["city"],
                "verified_scans": market["verified_scans"],
                "score": market_score,
            }
        )
    return _finalize_market_insights(rows, scope="product")


def _city_market_score(product: dict, market: dict) -> float:
    score_weights = WEIGHTS["city_market_score"]
    max_scans = max(row["verified_scans"] for row in product["markets"]) or 1
    city_fit = _city_category_fit(product, market["city"])
    city_fit_score = market.get(
        "city_fit_score",
        _clamp(
            0.4 * city_fit
            + 0.32 * _city_scene_fit(product, market["city"])
            + 0.28 * _city_price_fit(product, market["city"])
        ),
    )
    price_fit = market.get("price_fit", _city_price_fit(product, market["city"]))
    scene_fit = market.get("scene_fit", _city_scene_fit(product, market["city"]))
    city_abnormal_rate = _safe_divide(market["abnormal_scans"], max(market["verified_scans"], 1))
    overreach_penalty = market.get("overreach_penalty", 0.0)
    return _clamp(
        score_weights["scan_share"] * _safe_divide(market["verified_scans"], max_scans)
        + score_weights["normality"] * (1.0 - city_abnormal_rate)
        + score_weights["city_fit_score"] * city_fit_score
        + score_weights["price_fit"] * price_fit
        + score_weights["scene_fit"] * scene_fit
        + score_weights["category_fit"] * city_fit
        + score_weights["market_validation_score"] * product["market_validation_score"]
        - score_weights["overreach_penalty"] * overreach_penalty
        - score_weights["price_fit_shortfall"] * max(score_weights["price_fit_floor"] - price_fit, 0.0)
        - score_weights["scene_fit_shortfall"] * max(score_weights["scene_fit_floor"] - scene_fit, 0.0)
        - score_weights["category_fit_shortfall"] * max(score_weights["category_fit_floor"] - city_fit, 0.0)
    )


def _finalize_market_insights(rows: list[dict], scope: str) -> list[DemoMarketInsight]:
    if not rows:
        return []
    ordered = sorted(rows, key=lambda item: item["score"], reverse=True)
    top_score = ordered[0]["score"]
    bottom_score = ordered[-1]["score"]
    spread = max(top_score - bottom_score, 0.01)
    results: list[DemoMarketInsight] = []
    for index, row in enumerate(ordered):
        tier, observation = _market_observation(
            score=row["score"],
            rank=index,
            total=len(ordered),
            top_score=top_score,
            spread=spread,
            scope=scope,
        )
        results.append(
            DemoMarketInsight(
                city=row["city"],
                verified_scans=row["verified_scans"],
                opportunity_score=round(row["score"] * 100, 2),
                observation=observation,
                market_tier=tier,
                rank=index + 1,
            )
        )
    return results


def _market_observation(
    score: float,
    rank: int,
    total: int,
    top_score: float,
    spread: float,
    scope: str,
) -> tuple[str, str]:
    score_pct = score * 100
    close_to_top = score >= top_score - max(0.035, spread * 0.22)
    watch_threshold = max(55.0, top_score * 100 - max(16.0, spread * 100 * 0.6))

    if score_pct >= 78 or (rank <= 2 and score_pct >= 68 and close_to_top):
        if scope == "global":
            return "priority", "全国样本里表现靠前，适合当作重点参考市场。"
        return "priority", "在当前样本里排在前列，建议作为首批重点城市。"

    if rank >= max(total - 2, 0) and score_pct <= watch_threshold:
        if scope == "global":
            return "watch", "当前更适合作为补充覆盖市场，暂不建议优先投入。"
        return "watch", "短期不适合作为首选扩量城市，更适合先优化表达后再进入。"

    if score_pct >= 60 or rank < max(4, total // 2):
        if scope == "global":
            return "potential", "整体承接能力中上，适合继续做渠道拓展和验证。"
        return "potential", "这个城市能承接当前定位，适合小规模试投并继续观察。"

    if scope == "global":
        return "watch", "当前更适合作为补充覆盖市场，暂不建议优先投入。"
    return "watch", "这个城市当前反馈偏弱，暂不建议作为第一扩量方向。"


def _scene_similarity(product: dict, candidate: dict) -> float:
    return _clamp(
        1.0
        - (
            0.34 * abs(product["presented_value_norm"] - candidate["presented_value_norm"])
            + 0.26 * abs(product["intrinsic_value_norm"] - candidate["intrinsic_value_norm"])
            + 0.2 * abs(product["unit_price"] - candidate["unit_price"]) / max(product["unit_price"], candidate["unit_price"], 1)
            + 0.2 * abs(product["price_acceptance_score"] - candidate["price_acceptance_score"])
        )
    )


def _scene_group(product: dict) -> str:
    category = product["category"]
    if category in {"绿茶", "黑茶", "饮品", "蜂蜜", "冲调"}:
        return "文化礼赠"
    if category in {"鲜果", "蔬菜", "水产", "熟食"}:
        return "鲜食流通"
    if category in {"干货"}:
        return "居家伴手"
    return "综合"


def _build_market_learning(
    product: dict,
    products: list[dict],
    market_insights: list[DemoMarketInsight],
) -> list[DemoMarketLearningItem]:
    items: list[DemoMarketLearningItem] = []
    low_markets = [item for item in market_insights if item.market_tier == "watch"][:2]
    if len(low_markets) < 2:
        low_markets = market_insights[-2:]

    high_markets = [item for item in market_insights if item.market_tier == "priority"][:2]
    if not high_markets:
        high_markets = market_insights[:2]

    for market in low_markets:
        same_category_teacher = _find_market_teacher(product, products, market.city, mode="same_category")
        cross_scene_teacher = _find_market_teacher(product, products, market.city, mode="cross_scene")
        for teacher in (same_category_teacher, cross_scene_teacher):
            if teacher is None:
                continue
            items.append(
                DemoMarketLearningItem(
                    city=market.city,
                    learning_type="异地同类参考" if teacher["category"] == product["category"] else "跨品类同层级参考",
                    target_product_name=teacher["product_name"],
                    target_region_name=teacher["region_name"],
                    reason=(
                        f"{product['product_name']} 在 {market.city} 的当前定位接受度偏弱，"
                        f"但 {teacher['product_name']} 在同城的市场验证更强。"
                    ),
                    lesson=_build_market_lesson(product, teacher, market.city),
                    match_score=round(teacher["_teacher_match_score"] * 100, 2),
                    city_advantage_score=round(teacher["_teacher_city_advantage"] * 100, 2),
                    scene_similarity_score=round(teacher["_teacher_scene_similarity"] * 100, 2),
                    category_alignment_score=round((1.0 - teacher["_teacher_category_fit_delta"]) * 100, 2),
                )
            )

    for market in high_markets:
        candidate = _find_market_teacher(product, products, market.city, stronger_only=False, mode="same_or_scene")
        if candidate is None:
            continue
        items.append(
            DemoMarketLearningItem(
                city=market.city,
                learning_type="可复制市场",
                target_product_name=candidate["product_name"],
                target_region_name=candidate["region_name"],
                reason=(
                    f"{market.city} 对当前定位更友好，可以直接对照该城市中表现稳定的类似商品。"
                ),
                lesson=_build_market_lesson(product, candidate, market.city),
                match_score=round(candidate["_teacher_match_score"] * 100, 2),
                city_advantage_score=round(candidate["_teacher_city_advantage"] * 100, 2),
                scene_similarity_score=round(candidate["_teacher_scene_similarity"] * 100, 2),
                category_alignment_score=round((1.0 - candidate["_teacher_category_fit_delta"]) * 100, 2),
            )
        )

    dedup: list[DemoMarketLearningItem] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (item.city, item.target_product_name)
        if key in seen:
            continue
        seen.add(key)
        dedup.append(item)
    return dedup[:4]


def _find_market_teacher(
    product: dict,
    products: list[dict],
    city: str,
    stronger_only: bool = True,
    mode: str = "same_or_scene",
) -> dict | None:
    product_market = next((row for row in product["markets"] if row["city"] == city), None)
    product_city_strength = _city_market_score(product, product_market) if product_market else 0.0
    candidates = []
    for candidate in products:
        if candidate["product_id"] == product["product_id"]:
            continue
        candidate_market = next((row for row in candidate["markets"] if row["city"] == city), None)
        if candidate_market is None:
            continue

        same_category = candidate["category"] == product["category"]
        same_level = candidate["presentation_cluster"] == product["presentation_cluster"] or candidate["cluster_name"] == product["cluster_name"]
        same_core = candidate["product_core_cluster"] == product["product_core_cluster"]
        same_scene_group = _scene_group(candidate) == _scene_group(product)
        scene_similarity = _scene_similarity(product, candidate)
        if mode == "same_category" and not same_category:
            continue
        if mode == "cross_scene" and same_category:
            continue
        if mode == "cross_scene" and not same_scene_group:
            continue
        if mode == "cross_scene" and scene_similarity < 0.72:
            continue
        if mode != "cross_scene" and not (same_category or same_level or same_core):
            continue

        city_strength = _city_market_score(candidate, candidate_market)
        if stronger_only and city_strength <= product_city_strength + 0.05:
            continue
        category_fit_delta = abs(_city_category_fit(product, city) - _city_category_fit(candidate, city))
        if mode == "cross_scene" and _city_category_fit(candidate, city) <= _city_category_fit(product, city) + 0.04:
            continue
        city_advantage = max(city_strength - product_city_strength, 0.0)
        score = (
            0.28 * (1.0 if same_category else 0.0)
            + 0.18 * (1.0 if same_level else 0.0)
            + 0.12 * (1.0 if same_core else 0.0)
            + 0.16 * candidate["market_validation_score"]
            + 0.14 * city_strength
            + 0.08 * city_advantage
            + 0.08 * scene_similarity
            + 0.1 * (1.0 - category_fit_delta)
        )
        candidates.append((
            score,
            {
                **candidate,
                "_teacher_match_score": score,
                "_teacher_city_advantage": city_advantage,
                "_teacher_scene_similarity": scene_similarity,
                "_teacher_category_fit_delta": category_fit_delta,
            },
        ))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _build_market_lesson(product: dict, candidate: dict, city: str) -> str:
    product_market = next((row for row in product["markets"] if row["city"] == city), None)
    candidate_market = next((row for row in candidate["markets"] if row["city"] == city), None)
    if product_market and candidate_market:
        weakest = min(
            (
                ("价格承接", product_market.get("price_fit", 0.0)),
                ("进入场景", product_market.get("scene_fit", 0.0)),
                ("品类接受度", product_market.get("category_fit", 0.0)),
            ),
            key=lambda item: item[1],
        )[0]
        strongest = max(
            (
                ("价格承接", candidate_market.get("price_fit", 0.0)),
                ("进入场景", candidate_market.get("scene_fit", 0.0)),
                ("品类接受度", candidate_market.get("category_fit", 0.0)),
            ),
            key=lambda item: item[1],
        )[0]
    else:
        weakest = "进入方式"
        strongest = "进入方式"

    if candidate["category"] == product["category"] and candidate["region_name"] != product["region_name"]:
        return (
            f"同类商品在 {city} 的表现更强，说明问题不只是城市容量，"
            f"更可能卡在 {weakest}。可以重点参考 {candidate['product_name']} 在 {strongest} 上的做法。"
        )
    return (
        f"{city} 并不是不能接受这一级别的可信定位，"
        f"而是更偏好 {candidate['presentation_cluster']} 这一类进入方式。"
        f" 如果当前版本在 {weakest} 上偏弱，可以借鉴它在 {strongest} 上的处理逻辑。"
    )


def _build_positioning_summary(product: dict) -> DemoPositioningSummary:
    return DemoPositioningSummary(
        intrinsic_value_score=round(product["intrinsic_value_norm"] * 100, 2),
        presented_value_score=round(product["presented_value_norm"] * 100, 2),
        market_validation_score=round(product["market_validation_score"] * 100, 2),
        fit_score=round(product["fit_score"] * 100, 2),
        product_core_cluster=product["product_core_cluster"],
        origin_cluster=product["origin_cluster"],
        presentation_cluster=product["presentation_cluster"],
        feedback_cluster=product["feedback_cluster"],
        positioning_status=product["positioning_status"],
        recommendation_direction=product["recommendation_direction"],
        stability_score=round(product["stability_score"] * 100, 2),
        stability_label=product["stability_label"],
        summary=product["positioning_description"],
    )


def _build_strategy_report(
    product: dict,
    peers: list[dict],
    market_insights: list[DemoMarketInsight],
) -> DemoStrategyReport:
    mode = _strategy_mode(product)
    top_city = market_insights[0].city if market_insights else "优先样本城市"
    second_city = market_insights[1].city if len(market_insights) > 1 else top_city
    market_text = "、".join(item.city for item in market_insights[:3]) or "当前样本城市"
    family_name = product["family_name"]
    intrinsic = product["intrinsic_value_norm"] * 100
    presented = product["presented_value_norm"] * 100
    validation = product["market_validation_score"] * 100
    fit_score = product["fit_score"] * 100
    participation = product["participation_rate"] * 100
    price_acceptance = product["price_acceptance_score"] * 100

    if mode == "under":
        diagnosis = (
            f"{family_name} 当前更像“货底子比卖法强”的商品。本体价值 {intrinsic:.1f} 分，"
            f"比当前呈现高出 {intrinsic - presented:.1f} 分，问题更像出在包装表达、价格锚点和渠道层级，而不是商品本身。"
            f" 现在市场验证 {validation:.1f} 分、参与率 {participation:.1f}%，已经说明用户愿意买、也愿意验，但前台表达还没有把这股意愿放大。"
        )
        opportunity = (
            f"这类商品不要一步跳到重礼盒，而要先在 {top_city}、{second_city} 做轻升级试点。"
            f" 先把规格、产地、可验证入口和送礼理由讲清，再看激活率和参与率能不能同步抬升；"
            f" 如果这两个城市能跑顺，再向 {market_text} 复制，胜率会比一开始大幅提价更高。"
        )
    elif mode == "over":
        diagnosis = (
            f"{family_name} 当前更像“表达跑到商品前面去了”。当前呈现 {presented:.1f} 分，高于本体价值 {intrinsic:.1f} 分，"
            f"但价格接受度只有 {price_acceptance:.1f} 分，说明消费者没有完整接住这套高表达、高价锚的卖法。"
            " 如果继续堆礼盒、堆故事，最容易先掉的是成交后的参与和复购，而不是单次曝光。"
        )
        opportunity = (
            f"更好的做法是先在 {top_city} 把包装和价格压力降下来，恢复接受度，再观察 {second_city} 是否能跟上。"
            " 只要价格接受度和参与率回升，就说明这不是需求差，而是当前表达过重。"
        )
    elif mode == "matched":
        diagnosis = (
            f"{family_name} 当前属于相对匹配型商品。本体价值 {intrinsic:.1f} 分、当前呈现 {presented:.1f} 分、适配度 {fit_score:.1f} 分，"
            "说明商品、产地、表达和反馈基本站在同一层级上，当前打法不需要推翻重做。"
        )
        opportunity = (
            f"这时重点不是改定位，而是把已有打法从 {top_city} 复制到 {market_text}。"
            " 只要复制过程中不明显拉低激活率、参与率和异常率，这类商品更适合作为稳定放量样本，而不是继续冒险做高配改版。"
        )
    else:
        diagnosis = (
            f"{family_name} 更适合走效率型流通，而不是走重故事、高礼赠的表达。"
            f" 它的市场验证 {validation:.1f} 分不算差，但更依赖价格友好、规格清楚和渠道效率，而不是靠高溢价叙事去拉动购买。"
        )
        opportunity = (
            f"这类商品最适合先守住 {top_city} 这样的承接城市，做轻包装、清规格、稳价格，再向 {market_text} 扩。"
            " 如果后面要升级，也应先试轻伴手礼版本，而不是直接推成高价礼盒。"
        )

    caution = (
        f"当前异常率 {product['abnormal_rate'] * 100:.1f}%，稳定性 {product['stability_score'] * 100:.1f} 分。"
        " 真正要盯的不是表面热度，而是改版后激活率、参与率、价格接受度是否一起变好。"
        " 如果只有包装分上去了，但参与率没抬、价格接受度反而掉，就说明动作做重了。"
    )

    actions = _build_actions(product, market_insights)
    return DemoStrategyReport(
        title=f"{product['product_name']} 定位诊断与经营建议",
        diagnosis=diagnosis,
        opportunity=opportunity,
        caution=caution,
        actions=actions,
        recommended_markets=[item.city for item in market_insights[:3]],
        similar_products=[item["product_name"] for item in peers],
    )


def _origin_pitch_action(product: dict) -> str:
    region = str(product["region_name"])
    category = str(product["category"])
    signals: list[str] = []

    if "高山" in region:
        signals.extend(["高山慢生长", "云雾环境", "风味集中度"])
    if "核心产区" in region:
        signals.extend(["核心产区辨识度", "主产带身份", "来源识别清晰"])
    if "湖" in region or "湖区" in region or "水域" in region:
        signals.extend(["湖区生态水环境", "鲜度和生长环境", "水域来源辨识"])
    if "林区" in region:
        signals.extend(["林区生态环境", "自然生长条件", "林间来源感"])
    if "山地" in region:
        signals.extend(["山地风土", "坡地日照与排水", "山地口感差异"])
    if "近郊" in region:
        signals.extend(["近郊基地新鲜度", "短链路供应", "当季到店效率"])

    if category in {"绿茶", "黑茶"}:
        signals.extend(["茶香净度", "耐泡层次"])
    elif category == "鲜果":
        signals.extend(["成熟产带", "糖酸平衡"])
    elif category == "蜂蜜":
        signals.extend(["蜜源环境", "花源特征"])
    elif category == "饮品":
        signals.extend(["地方酿造记忆", "发酵风味"])
    elif category == "水产":
        signals.extend(["鲜味辨识", "规格稳定"])

    unique_signals: list[str] = []
    for signal in signals:
        if signal not in unique_signals:
            unique_signals.append(signal)

    first = unique_signals[0] if len(unique_signals) > 0 else "来源清楚"
    second = unique_signals[1] if len(unique_signals) > 1 else "产区辨识"
    third = unique_signals[2] if len(unique_signals) > 2 else "可验证入口"
    return (
        f"先把 {region} 的产地卖点直接改成对外话术：主标题讲 {first}，副标题讲 {second}，"
        f"详情页补 {third} 和规格入口，不要再只写“正宗”“优质”这种空话。"
    )


def _build_actions(product: dict, market_insights: list[DemoMarketInsight]) -> list[str]:
    top_city = market_insights[0].city if market_insights else "优先样本城市"
    second_city = market_insights[1].city if len(market_insights) > 1 else top_city
    third_city = market_insights[2].city if len(market_insights) > 2 else second_city
    mode = _strategy_mode(product)
    activation = product["activation_rate"] * 100
    participation = product["participation_rate"] * 100
    acceptance = product["price_acceptance_score"] * 100
    price_step = max(round(product["unit_price"] * 0.08), 3)
    origin_action = _origin_pitch_action(product)

    if mode == "under":
        return [
            origin_action,
            f"先把 {top_city}、{second_city} 当成试点城市做市场拆分，比较两个城市当前 {product['channel']} 渠道下的机会分、参与率和价格接受度差异，判断更适合走伴手礼、日常消费还是区域尝鲜，而不是所有城市用同一套话术。",
            f"包装和价格只做轻量验证：正面先补商品名、产地、规格、可验证入口，单次调价控制在 {price_step} 元以内；如果提价后参与率比当前 {participation:.1f}% 下降超过 2 个点，就停止放大。",
            f"复盘标准写清：第一看产地主话术上线后激活率能否从 {activation:.1f}% 提升，第二看试点城市之间哪一类渠道更吃产地表达，第三才看包装升级是否值得继续做大。",
        ]
    if mode == "over":
        return [
            origin_action,
            f"先比较 {top_city} 和 {second_city} 对当前高表达版本的承接差异，判断到底是城市错了、渠道错了，还是表达太重。先用数据把问题拆开，不要一上来把所有责任都推给包装。",
            f"再在 {top_city} 上一版轻包装、直给价格表达的版本，把价格接受度从 {acceptance:.1f} 分往上拉；先恢复接受度和参与率，再决定是否保留部分礼赠表达。",
            f"复盘时重点看三件事：来源信息简化后用户是否更容易理解，{top_city} 的参与率是否回升，以及当前 {product['channel']} 是否仍值得保留为主渠道。只有这三件事同时变好，才说明方向对。",
        ]
    if mode == "matched":
        return [
            origin_action,
            f"围绕 {top_city} 已经跑顺的版本做城市复制，但复制前先比较 {second_city}、{third_city} 的渠道结构和价格带承接，看哪些城市适合原样复制，哪些城市只适合缩减版本。",
            f"包装和价格不要大动，只允许微调二维码可见性、产地证明位置和标题顺序；对匹配型商品来说，市场复制和执行一致性比重新讲一套新故事更重要。",
            "每周盯一次新城市复盘：先看城市承接是否接近样板城市，再看来源信息是否被稳定看到，最后才看有没有必要加新的包装表达。",
        ]
    return [
        origin_action,
        f"把 {top_city} 当主战场、{second_city} 当对照城市，比较两个城市当前渠道效率和价格承接差异，优先判断哪里适合继续放量，哪里只适合做补充覆盖。",
        "包装只保留轻量信息表达，不做重礼盒；如果后面要升级，也应先试轻伴手礼版本，而不是直接推高价礼赠。",
        "供应端优先保证到货稳定和规格一致，把市场分析、渠道效率和价格友好度放在前面，把包装叙事放在后面。",
    ]


def _strategy_mode(product: dict) -> str:
    intrinsic = product["intrinsic_value_norm"] * 100
    presented = product["presented_value_norm"] * 100
    validation = product["market_validation_score"] * 100
    fit_score = product["fit_score"] * 100
    price_acceptance = product["price_acceptance_score"] * 100
    if presented - intrinsic >= 12 and price_acceptance < 60:
        return "over"
    if intrinsic - presented >= 10 and validation >= 42:
        return "under"
    if fit_score >= 72 and validation >= 45:
        return "matched"
    return "circulation"


def _build_scenarios(product: dict) -> list[DemoScenarioPreview]:
    scenarios = []
    current = product["presentation"]
    if product["positioning_status"] == "低估潜力型":
        scenarios.append(_simulate_scenario(
            product,
            "轻礼升级",
            "适度升级",
            {
                "package_intensity": min(current["package_intensity"] + 0.16, 1.0),
                "narrative_intensity": min(current["narrative_intensity"] + 0.18, 1.0),
                "channel_premium": min(current["channel_premium"] + 0.14, 1.0),
                "price_position": min(current["price_position"] + 0.12, 1.0),
            },
            ["包装强度", "渠道层级", "可信叙事", "价格带"],
            "该商品本体和产地并不弱，先做轻礼升级比直接重礼盒更稳。",
        ))
        scenarios.append(_simulate_scenario(
            product,
            "文旅伴手礼化",
            "适度升级",
            {
                "package_intensity": min(current["package_intensity"] + 0.1, 1.0),
                "narrative_intensity": min(current["narrative_intensity"] + 0.16, 1.0),
                "channel_premium": min(current["channel_premium"] + 0.18, 1.0),
                "price_position": min(current["price_position"] + 0.08, 1.0),
            },
            ["包装强度", "文旅渠道", "可信叙事"],
            "优先往伴手礼场景靠，比一步做成高礼赠风险更低。",
        ))
    elif product["positioning_status"] == "过度定位型":
        scenarios.append(_simulate_scenario(
            product,
            "轻包装降价版",
            "降定位",
            {
                "package_intensity": max(current["package_intensity"] - 0.26, 0.0),
                "narrative_intensity": max(current["narrative_intensity"] - 0.22, 0.0),
                "channel_premium": max(current["channel_premium"] - 0.18, 0.0),
                "price_position": max(current["price_position"] - 0.2, 0.0),
            },
            ["包装强度", "价格带", "叙事强度", "渠道层级"],
            "这类商品更需要回到合理价格和自然消费场景。",
        ))
        scenarios.append(_simulate_scenario(
            product,
            "大众流通版",
            "降定位",
            {
                "package_intensity": max(current["package_intensity"] - 0.34, 0.0),
                "narrative_intensity": max(current["narrative_intensity"] - 0.3, 0.0),
                "channel_premium": max(current["channel_premium"] - 0.26, 0.0),
                "price_position": max(current["price_position"] - 0.26, 0.0),
            },
            ["包装强度", "价格带", "渠道层级"],
            "如果轻降还不能恢复接受度，就应该回归更大众的流通逻辑。",
        ))
    elif product["positioning_status"] == "定位匹配型":
        scenarios.append(_simulate_scenario(
            product,
            "维持定位扩城",
            "保持",
            {
                "package_intensity": current["package_intensity"],
                "narrative_intensity": min(current["narrative_intensity"] + 0.04, 1.0),
                "channel_premium": min(current["channel_premium"] + 0.06, 1.0),
                "price_position": current["price_position"],
            },
            ["渠道层级", "叙事细化"],
            "目标不是重构定位，而是复制有效策略到更适合的城市。",
        ))
    else:
        scenarios.append(_simulate_scenario(
            product,
            "轻伴手礼试水",
            "微调",
            {
                "package_intensity": min(current["package_intensity"] + 0.12, 1.0),
                "narrative_intensity": min(current["narrative_intensity"] + 0.1, 1.0),
                "channel_premium": min(current["channel_premium"] + 0.08, 1.0),
                "price_position": min(current["price_position"] + 0.06, 1.0),
            },
            ["包装强度", "叙事强度"],
            "只建议做轻量升级，不能大幅抬高价位。",
        ))
    return scenarios


def _simulate_scenario(
    product: dict,
    scenario_name: str,
    direction: str,
    presentation: dict[str, float],
    changed_fields: list[str],
    reason: str,
) -> DemoScenarioPreview:
    core = product["core"]
    origin = product["origin"]
    intrinsic_norm = product["intrinsic_value_norm"]
    presented_norm = _presented_value_norm(presentation)
    target_norm = 0.72 * intrinsic_norm + 0.18 * core["giftability"] + 0.10 * origin["traceability_fit"]
    fit_score = _clamp(1.0 - abs(presented_norm - target_norm) * 1.18)
    scenario_price_stress = (
        0.36 * presentation["price_position"] * core["daily_consumption_fit"]
        + 0.32 * presentation["price_position"] * core["freshness_sensitivity"]
        + 0.18 * presentation["package_intensity"] * (1.0 - core["giftability"])
        + 0.14 * max(presented_norm - target_norm, 0.0)
    )
    price_acceptance = _clamp(
        0.26
        + 0.32 * fit_score
        + 0.12 * core["standardization"]
        + 0.08 * (1.0 - core["perishability"])
        + 0.05 * core["giftability"]
        - 0.24 * scenario_price_stress
        + 0.04 * max(target_norm - presented_norm, 0.0)
    )
    activation_rate = _clamp(
        0.04
        + 0.12 * core["authenticity_sensitivity"]
        + 0.1 * origin["traceability_fit"]
        + 0.08 * fit_score
        + 0.06 * presentation["narrative_intensity"] * core["narrative_affinity"]
        + 0.04 * presentation["channel_premium"]
        - 0.04 * core["perishability"]
    )
    participation_rate = _clamp(
        0.02
        + 0.18 * fit_score
        + 0.12 * core["authenticity_sensitivity"]
        + 0.08 * origin["origin_fame"]
        + 0.08 * core["giftability"] * presentation["package_intensity"]
        - 0.22 * max(presented_norm - target_norm, 0.0)
        - 0.06 * scenario_price_stress
        + 0.08 * max(target_norm - presented_norm, 0.0)
    )
    cross_region_rate = _clamp(
        0.04
        + 0.17 * core["transportability"]
        + 0.1 * origin["origin_fame"]
        + 0.08 * presentation["channel_premium"]
        + 0.07 * core["giftability"]
        - 0.14 * core["freshness_sensitivity"]
        - 0.08 * core["perishability"]
        - 0.08 * max(presented_norm - target_norm, 0.0)
        - 0.05 * presentation["price_position"] * core["daily_consumption_fit"]
    )
    abnormal_rate = _clamp(
        0.012
        + 0.028 * core["perishability"]
        + 0.026 * (1.0 - core["standardization"])
        + 0.012 * presentation["channel_premium"]
        - 0.012 * fit_score,
        0.01,
        0.09,
    )
    validation = _clamp(
        0.3 * participation_rate
        + 0.18 * activation_rate
        + 0.14 * cross_region_rate
        + 0.24 * price_acceptance
        + 0.08 * fit_score
        + 0.06 * (1.0 - abnormal_rate)
    )

    if presented_norm - target_norm >= 0.14 and validation < 0.48:
        projected_status = "过度定位型"
    elif (
        target_norm - presented_norm >= 0.13
        and intrinsic_norm >= 0.62
        and validation >= 0.49
        and price_acceptance >= 0.66
    ):
        projected_status = "低估潜力型"
    elif fit_score >= 0.74 and validation >= 0.46 and (presented_norm - target_norm) < 0.16:
        projected_status = "定位匹配型"
    else:
        projected_status = "流通优先型"

    return DemoScenarioPreview(
        scenario_name=scenario_name,
        direction=direction,
        changed_fields=changed_fields,
        projected_presented_value_score=round(presented_norm * 100, 2),
        projected_market_validation_score=round(validation * 100, 2),
        projected_positioning_status=projected_status,
        reason=reason,
    )


def _build_prompt_preview(
    product: dict,
    peers: list[dict],
    markets: list[DemoMarketInsight],
    scenarios: list[DemoScenarioPreview],
) -> str:
    strong_markets = "、".join(f"{item.city}（{item.opportunity_score:.1f}）" for item in markets[:3]) or "暂无明显强势城市"
    weak_markets = "、".join(
        f"{item.city}（{item.opportunity_score:.1f}）" for item in sorted(markets, key=lambda row: row.opportunity_score)[:2]
    ) or "暂无明显弱势城市"
    peer_text = "；".join(
        f"{item['product_name']}（{item['positioning_status']}，验证分 {item['market_validation_score'] * 100:.1f}）"
        for item in peers[:3]
    ) or "暂无同层可参考样本"
    scenario_text = "；".join(
        f"{item.scenario_name} -> {item.projected_positioning_status}，预计验证分 {item.projected_market_validation_score:.1f}"
        for item in scenarios
    )
    return (
        "你是一个可信经营分析助手。请基于结构化指标输出正式、克制、可执行的经营分析。"
        " 输出前必须先判断该商品属于低估潜力型、定位匹配型、流通优先型还是过度定位型，再给建议。"
        " 绝对禁止三件事：1）把可信核销量直接说成真实销量；2）在没有证据时编造消费者偏好；"
        "3）看到礼盒就机械地判断应该继续高端化。"
        f" 当前商品：{product['product_name']}。品类：{product['category']}；产地：{product['region_name']}；"
        f" 当前渠道：{product['channel']}；价格带：{product['price_band']}；单价：{product['unit_price']:.0f} 元。"
        f" 聚类结果：产品本体={product['product_core_cluster']}；产地信号={product['origin_cluster']}；"
        f" 当前呈现={product['presentation_cluster']}；经营反馈={product['feedback_cluster']}。"
        f" 核心分数：本体价值分 {product['intrinsic_value_norm'] * 100:.1f}；当前呈现分 {product['presented_value_norm'] * 100:.1f}；"
        f" 目标呈现分 {product['target_value_norm'] * 100:.1f}；适配度 {product['fit_score'] * 100:.1f}；"
        f" 价格接受度 {product['price_acceptance_score'] * 100:.1f}；市场验证分 {product['market_validation_score'] * 100:.1f}；"
        f" 当前定位结论：{product['positioning_status']}；稳定性 {product['stability_label']}（{product['stability_score'] * 100:.1f}）。"
        " 指标释义：总销量用于描述商家申报的销售规模；可信核销量只表示成交后主动验真、愿意扫描并触发可信行为的人群规模；"
        "销量与可信核销量的比值反映的是验真参与深度和信任敏感度，不能直接替代销量分析。"
        " 溯源激活率衡量二维码是否被看到并被使用；验真参与率衡量已成交用户是否愿意进一步验证；"
        "跨区渗透率衡量可信消费是否走出本地；价格接受度衡量当前价格和表达方式是否被市场承接。"
        f" 当前强势城市：{strong_markets}。当前弱势城市：{weak_markets}。"
        f" 可参考样本：{peer_text}。"
        f" 方案推演：{scenario_text}。"
        " 请按以下顺序作答：先下结论，再解释指标意味着什么，再说明该学谁、学什么，最后给出 2 到 3 条可执行动作。"
    )


def _build_overview_metrics(products: list[dict]) -> list[DemoOverviewMetric]:
    total_launch = sum(item["launch_quantity"] for item in products)
    total_sales = sum(item["declared_sales"] for item in products)
    total_scans = sum(item["verified_scans"] for item in products)
    family_count = len({item["family_name"] for item in products})

    underestimated = len([item for item in products if item["positioning_status"] == "低估潜力型"])
    over_positioned = len([item for item in products if item["positioning_status"] == "过度定位型"])
    matched = len([item for item in products if item["positioning_status"] == "定位匹配型"])
    high_stability = len([item for item in products if item["stability_score"] >= 0.84])

    return [
        DemoOverviewMetric(
            key="sku_count",
            name="经营版本总数",
            value=str(len(products)),
            description=f"{family_count} 个基础产品，每个产品拆成 3 个经营版本，用来观察定位变化。",
        ),
        DemoOverviewMetric(
            key="declared_sales",
            name="模拟总销量",
            value=f"{total_sales:,}",
            description="用于对照可信核销，不直接等于系统原生可信数据。",
        ),
        DemoOverviewMetric(
            key="verified_scans",
            name="可信核销总量",
            value=f"{total_scans:,}",
            description="由经营定位和商品属性共同影响的可信行为总量。",
        ),
        DemoOverviewMetric(
            key="activation_rate",
            name="加权溯源激活率",
            value=_percent(_safe_divide(total_scans, total_launch)),
            description="反映商品进入市场后，二维码是否真正被看见并使用。",
        ),
        DemoOverviewMetric(
            key="underestimated",
            name="低估潜力 SKU",
            value=str(underestimated),
            description="说明这些商品更适合适度升级，而不是继续低配出售。",
        ),
        DemoOverviewMetric(
            key="matched",
            name="定位匹配 SKU",
            value=str(matched),
            description="说明这些商品已找到较合适的信任价值表达。",
        ),
        DemoOverviewMetric(
            key="over_positioned",
            name="过度定位 SKU",
            value=str(over_positioned),
            description="说明这些商品更需要降包装、降价格或回到更自然的消费场景。",
        ),
        DemoOverviewMetric(
            key="high_stability",
            name="高稳定结论",
            value=str(high_stability),
            description="表示这些商品在参数扰动后，定位结论仍然较稳定，不容易翻转。",
        ),
    ]


def _build_indicator_definitions() -> list[DemoIndicatorDefinition]:
    return [
        DemoIndicatorDefinition(
            key="intrinsic_value_score",
            name="本体价值分",
            formula="产品本体属性 + 产地信号加权",
            meaning="衡量商品本身与产地究竟能承载多强的信任价值表达。",
            caution="它不是市场售价上限，只是判断商品有没有资格讲更强的故事。",
            business_value="防止把不适合的商品硬做高价重礼盒。",
            ai_usage="作为判断该不该升级定位的基础前提。",
        ),
        DemoIndicatorDefinition(
            key="presented_value_score",
            name="当前呈现分",
            formula="包装强度 + 渠道层级 + 叙事强度 + 价格位置加权",
            meaning="衡量商家当前把这个商品卖成了什么样子。",
            caution="它描述的是卖法，不代表商品本体真的值这个定位。",
            business_value="用于识别过度包装、过度溢价或表达偏弱。",
            ai_usage="用于判断商品现在的卖法是否过高或过低。",
        ),
        DemoIndicatorDefinition(
            key="market_validation_score",
            name="市场验证分",
            formula="参与率 + 激活率 + 跨区率 + 价格接受度 + 稳定性加权",
            meaning="衡量消费者是否接受当前这套可信定位。",
            caution="它仍然不是销量预测，而是定位被市场认可的程度。",
            business_value="判断当前卖法有没有被消费者买账。",
            ai_usage="作为升、降、保持建议的直接依据。",
        ),
        DemoIndicatorDefinition(
            key="positioning_status",
            name="定位结论",
            formula="本体价值分、当前呈现分、市场验证分联动判断",
            meaning="区分低估潜力、定位匹配、流通优先和过度定位。",
            caution="它是经营判断结果，不是单一数学分数。",
            business_value="直接指导是该升级、保持还是降定位。",
            ai_usage="作为建议报告的核心结论。",
        ),
        DemoIndicatorDefinition(
            key="scenario_preview",
            name="策略推演",
            formula="仅修改可调整变量后重新估算验证表现",
            meaning="模拟轻礼升级、降价去包装或扩渠道后的潜在变化。",
            caution="它是推演，不是现实承诺收益。",
            business_value="帮助商家先做小步试验，而不是盲目改大。",
            ai_usage="让 AI 不只描述现状，还能解释为什么某种改法更合理。",
        ),
    ]


def _to_product_card(product: dict) -> DemoProductCard:
    return DemoProductCard(
        product_id=product["product_id"],
        product_name=product["product_name"],
        family_name=product["family_name"],
        variant_name=product["variant_name"],
        category=product["category"],
        region_name=product["region_name"],
        season=product["season"],
        channel=product["channel"],
        price_band=product["price_band"],
        unit_price=product["unit_price"],
        launch_quantity=product["launch_quantity"],
        declared_sales=product["declared_sales"],
        verified_scans=product["verified_scans"],
        activation_rate=round(product["activation_rate"], 4),
        participation_rate=round(product["participation_rate"], 4),
        repeat_scan_rate=round(product["repeat_scan_rate"], 4),
        abnormal_rate=round(product["abnormal_rate"], 4),
        cross_region_rate=round(product["cross_region_rate"], 4),
        trust_opportunity_score=product["trust_opportunity_score"],
        cluster_id=product["cluster_id"],
        cluster_name=product["cluster_name"],
        product_core_cluster=product["product_core_cluster"],
        origin_cluster=product["origin_cluster"],
        presentation_cluster=product["presentation_cluster"],
        feedback_cluster=product["feedback_cluster"],
        positioning_status=product["positioning_status"],
        recommendation_direction=product["recommendation_direction"],
        stability_score=round(product["stability_score"], 4),
        stability_label=product["stability_label"],
        tags=product["tags"],
    )


def _intrinsic_value_norm(core: dict, origin: dict, weights: dict | None = None) -> float:
    effective_weights = weights or WEIGHTS
    intrinsic_weights = effective_weights["intrinsic_value"]
    return _clamp(
        intrinsic_weights["premium_capacity"] * core["premium_capacity"]
        + intrinsic_weights["giftability"] * core["giftability"]
        + intrinsic_weights["authenticity_sensitivity"] * core["authenticity_sensitivity"]
        + intrinsic_weights["narrative_affinity"] * core["narrative_affinity"]
        + intrinsic_weights["origin_fame"] * origin["origin_fame"]
        + intrinsic_weights["gi_strength"] * origin["gi_strength"]
    )


def _presented_value_norm(presentation: dict, weights: dict | None = None) -> float:
    effective_weights = weights or WEIGHTS
    presentation_weights = effective_weights["presented_value"]
    return _clamp(
        presentation_weights["price_position"] * presentation["price_position"]
        + presentation_weights["package_intensity"] * presentation["package_intensity"]
        + presentation_weights["narrative_intensity"] * presentation["narrative_intensity"]
        + presentation_weights["channel_premium"] * presentation["channel_premium"]
    )


def _core_vector_keys() -> list[str]:
    return [
        "giftability",
        "narrative_affinity",
        "daily_consumption_fit",
        "freshness_sensitivity",
        "transportability",
        "premium_capacity",
    ]


def _origin_vector_keys() -> list[str]:
    return [
        "origin_fame",
        "gi_strength",
        "natural_uniqueness",
        "seasonal_signal",
        "traceability_fit",
    ]


def _presentation_vector_keys() -> list[str]:
    return [
        "package_intensity",
        "narrative_intensity",
        "channel_premium",
        "price_position",
        "price_signal_score",
    ]


def _feedback_vector_keys() -> list[str]:
    return [
        "activation_rate",
        "participation_rate",
        "cross_region_rate",
        "price_acceptance_score",
        "market_validation_score",
        "value_gap",
        "stability_score",
        "fit_score",
    ]


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _distance_list(left: list[float], right: list[float]) -> float:
    return math.sqrt(sum((l - r) ** 2 for l, r in zip(left, right)))


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
