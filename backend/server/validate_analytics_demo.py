from __future__ import annotations

from collections import Counter

from app.analytics_cluster import run_kmeans
from app.analytics_config import load_analytics_weights, load_city_profiles
from app.analytics_demo import _analyze_products, build_demo_dashboard, build_demo_product_report


def main() -> None:
    weights = load_analytics_weights()
    cities = load_city_profiles()
    assert "target_norm" in weights
    assert "武汉" in cities and "上海" in cities

    assignments, centers = run_kmeans(
        [[0.0, 0.1], [0.1, 0.0], [0.92, 0.88], [0.87, 0.94]],
        cluster_count=2,
    )
    assert len(assignments) == 4
    assert len(centers) == 2
    assert len(set(assignments)) == 2

    analysis = _analyze_products()
    products = analysis["products"]
    assert len(products) == 45

    positioning_counter = Counter(item["positioning_status"] for item in products)
    for expected_status in ("低估潜力型", "定位匹配型", "流通优先型", "过度定位型"):
        assert positioning_counter[expected_status] > 0

    for product in products:
        assert 0.0 <= product["price_signal_score"] <= 1.0
        assert 0.0 <= product["stability_score"] <= 1.0
        assert product["stability_label"] in {"高稳定", "中稳定", "待复核"}
        assert product["markets"]
        assert all("city_fit_score" in market for market in product["markets"])

    expected_cases = {
        "P002": "低估潜力型",
        "P035": "定位匹配型",
        "P036": "过度定位型",
        "P043": "流通优先型",
    }
    for product_id, expected_status in expected_cases.items():
        report = build_demo_product_report(product_id)
        assert report.positioning_summary.positioning_status == expected_status
        assert report.positioning_summary.stability_label in {"高稳定", "中稳定", "待复核"}
        assert report.product.stability_score >= 0.0
        assert report.market_insights
        assert report.market_learning
        for item in report.market_learning:
            assert 0.0 <= item.match_score <= 100.0
            assert 0.0 <= item.city_advantage_score <= 100.0
            assert 0.0 <= item.scene_similarity_score <= 100.0
            assert 0.0 <= item.category_alignment_score <= 100.0

    dashboard = build_demo_dashboard()
    assert len(dashboard.products) == 45
    assert len(dashboard.clusters) == 4
    assert any(metric.key == "high_stability" for metric in dashboard.overview_metrics)

    print("analytics-demo-validation: ok")


if __name__ == "__main__":
    main()
