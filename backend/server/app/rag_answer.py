from __future__ import annotations

from datetime import datetime
import re

from .analytics_demo import MODULE_NAME, build_demo_product_report
from .analytics_schemas import (
    DemoLlmAnalysisResponse,
    DemoLlmStrategyAnalysis,
    RagCardHit,
)
from .rag_llm import chat_text, load_rag_llm_settings
from .rag_search import search_rag


SYSTEM_PROMPT = """You are an agricultural product business analysis assistant. You must base your answer only on the provided product metrics, RAG evidence cards, and evidence snippets. Output must be in Chinese. Do not output JSON, Markdown, or code blocks. Do not treat verified traceability scans as actual sales. Do not over-focus on packaging or gift-box upgrades. Do not invent city preferences, consumer psychology, or market facts that are not supported by the evidence. If evidence mainly comes from policy or case materials, explicitly keep the conclusion conservative. Use the required section tags exactly and write only the content for each section."""


def build_llm_strategy_analysis(product_id: str) -> DemoLlmAnalysisResponse:
    report = build_demo_product_report(product_id)
    queries = _build_queries(report.raw_fields, report.positioning_summary.positioning_status, report.product)

    card_hits: list[dict] = []
    insight_hits: list[str] = []
    seen_cards: set[str] = set()
    seen_insights: set[str] = set()
    for query in queries:
        retrieval = search_rag(query, top_k=4)
        for card in retrieval.get("cards", []):
            if card["doc_id"] in seen_cards:
                continue
            seen_cards.add(card["doc_id"])
            card_hits.append(card)
            if len(card_hits) >= 6:
                break
        for insight in retrieval.get("insights", []):
            text = insight["text"]
            if text in seen_insights:
                continue
            seen_insights.add(text)
            insight_hits.append(text)
            if len(insight_hits) >= 12:
                break
        if len(card_hits) >= 6 and len(insight_hits) >= 10:
            break

    llm_payload = _build_prompt(report, queries, card_hits, insight_hits)
    settings = load_rag_llm_settings()
    raw_text = chat_text(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=llm_payload,
        model=settings.answer_model,
        temperature=0.1,
        max_tokens=2600,
        settings=settings,
    )

    analysis = _analysis_from_text(raw_text)
    analysis = _refine_analysis(report, analysis, card_hits, insight_hits)

    return DemoLlmAnalysisResponse(
        module_name=MODULE_NAME,
        generated_at=_now_text(),
        model_name=settings.answer_model,
        product=report.product,
        positioning_summary=report.positioning_summary,
        retrieval_queries=queries,
        retrieved_cards=[RagCardHit(**item) for item in card_hits],
        retrieved_insights=insight_hits,
        analysis=analysis,
    )


def _build_queries(raw_fields: dict, positioning_status: str, product) -> list[str]:
    category = product.category
    region = product.region_name
    channel = product.channel
    price_band = product.price_band
    base = [
        f"{category} {channel} 购买意愿 价格接受度",
        f"{region} 原产地形象 购买意愿 {category}",
        f"{region} 产地信息 品牌历史 标准认证 {category}",
        f"{category} 城市市场分析 渠道承接 经营策略",
    ]
    if positioning_status == "过度定位型":
        base.append(f"{category} 礼盒 包装 过度定位 购买意愿")
        base.append(f"{category} 降价 走量 渠道 经营策略")
    elif positioning_status == "低估潜力型":
        base.append(f"{category} 品牌升级 价值表达 购买意愿")
        base.append(f"{category} 地理标志 产地标签 溢价")
    elif positioning_status == "流通优先型":
        base.append(f"{category} 社区团购 电商 渠道选择")
        base.append(f"{category} 价格敏感 大众消费 经营策略")
    else:
        base.append(f"{category} 跨区域市场拓展 渠道经营")
        base.append(f"{category} 品牌匹配 复制策略")
    if price_band:
        base.append(f"{category} {price_band}价位 购买意愿")
    return base[:6]


def _build_prompt(report, queries: list[str], card_hits: list[dict], insight_hits: list[str]) -> str:
    return (
        f"Please write the final answer in Chinese.\n\n"
        f"Product name: {report.product.product_name}\n"
        f"Category: {report.product.category}\n"
        f"Origin: {report.product.region_name}\n"
        f"Channel: {report.product.channel}\n"
        f"Price band: {report.product.price_band}\n"
        f"Unit price: {report.product.unit_price}\n"
        f"Tags: {report.product.tags}\n"
        f"Positioning status: {report.positioning_summary.positioning_status}\n"
        f"Recommendation direction: {report.positioning_summary.recommendation_direction}\n"
        f"Intrinsic value score: {report.positioning_summary.intrinsic_value_score}\n"
        f"Presented value score: {report.positioning_summary.presented_value_score}\n"
        f"Market validation score: {report.positioning_summary.market_validation_score}\n"
        f"Fit score: {report.positioning_summary.fit_score}\n"
        f"Stability: {report.positioning_summary.stability_label} / {report.positioning_summary.stability_score}\n"
        f"Positioning summary: {report.positioning_summary.summary}\n\n"
        f"Raw fields: {report.raw_fields}\n\n"
        f"Queries: {queries}\n\n"
        f"Evidence cards: {card_hits}\n\n"
        f"Evidence snippets: {insight_hits}\n\n"
        "Priorities:\n"
        "1. Explain what this specific product actually sells: product itself, use case, gift or daily scene, and current price band.\n"
        "2. Explain what this specific origin can concretely support. Do not write vague phrases like authentic, premium, or high quality.\n"
        "3. Explain which cities and channels should be tested first, and why.\n"
        "4. Packaging is only a supporting topic and must not dominate the answer.\n\n"
        "Output with these exact tags, and do not output anything outside them:\n"
        "[executive_summary]\nWrite one short paragraph in Chinese. Mention the product name or category directly.\n\n"
        "[core_judgement]\nWrite one sentence in Chinese. It must mention both the product itself and the origin.\n\n"
        "[evidence_findings]\nWrite 2 to 4 lines in Chinese, one finding per line, no numbering. At least one line must mention the product or price-level, and at least one line must mention origin or channel fit.\n\n"
        "[strategy_actions]\nWrite exactly 4 lines in Chinese, one action per line, no numbering.\n"
        "Line 1: product selling point or use-case.\n"
        "Line 2: origin expression or trust expression.\n"
        "Line 3: city/channel pilot action.\n"
        "Line 4: review metrics.\n"
        "Do not spend more than one line on packaging.\n\n"
        "[pricing_packaging_advice]\nWrite one short paragraph in Chinese, only about how pricing and packaging should support the product.\n\n"
        "[channel_advice]\nWrite one short paragraph in Chinese, naming the first cities or channels to try.\n\n"
        "[origin_trust_advice]\nWrite one short paragraph in Chinese, explaining what this origin is best suited to communicate.\n\n"
        "[risk_warning]\nWrite one short paragraph in Chinese, naming the most likely mistake."
    )


def _analysis_from_text(raw_text: str) -> DemoLlmStrategyAnalysis:
    sections = _parse_tagged_sections(raw_text)
    return DemoLlmStrategyAnalysis(
        executive_summary=_clean_block_text(sections.get("executive_summary", "")),
        core_judgement=_clean_block_text(sections.get("core_judgement", "")),
        evidence_findings=_split_block_items(sections.get("evidence_findings", "")),
        strategy_actions=_split_block_items(sections.get("strategy_actions", "")),
        pricing_packaging_advice=_clean_block_text(sections.get("pricing_packaging_advice", "")),
        channel_advice=_clean_block_text(sections.get("channel_advice", "")),
        origin_trust_advice=_clean_block_text(sections.get("origin_trust_advice", "")),
        risk_warning=_clean_block_text(sections.get("risk_warning", "")),
    )


def _parse_tagged_sections(raw_text: str) -> dict[str, str]:
    pattern = re.compile(
        r"^\[(executive_summary|core_judgement|evidence_findings|strategy_actions|pricing_packaging_advice|channel_advice|origin_trust_advice|risk_warning)\]\s*$",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(raw_text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        key = match.group(1)
        start_pos = match.end()
        end_pos = matches[index + 1].start() if index + 1 < len(matches) else len(raw_text)
        sections[key] = raw_text[start_pos:end_pos].strip()
    return sections


def _split_block_items(text: str) -> list[str]:
    if not text:
        return []
    items: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^[-*?]+\s*", "", line)
        line = re.sub(r"^\d+[.)??: -]*", "", line)
        line = re.sub(r"^[A-Za-z][.)??: -]+", "", line)
        line = _clean_block_text(line)
        if line and line not in items:
            items.append(line)
    return items


def _clean_block_text(text: str) -> str:
    cleaned = text.strip()
    cleaned = cleaned.strip('`').strip('"').strip("'")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _origin_signal_tags(product) -> list[str]:
    region = str(product.region_name)
    category = str(product.category)
    tags: list[str] = []

    if "高山" in region:
        tags.extend(["高山慢生长", "云雾环境", "昼夜温差带来的风味集中度"])
    if "核心产区" in region:
        tags.extend(["核心产区辨识度", "主产带身份", "来源识别清晰"])
    if "湖" in region or "湖区" in region or "水域" in region:
        tags.extend(["湖区生态水环境", "鲜度与生长环境", "水域来源辨识"])
    if "林区" in region:
        tags.extend(["林区生态环境", "林间/林下来源感", "自然生长条件"])
    if "山地" in region:
        tags.extend(["山地坡地环境", "排水和日照条件", "山地风土差异"])
    if "近郊" in region:
        tags.extend(["近郊基地的新鲜度", "短链路供应", "当季到店效率"])

    if category in {"绿茶", "黑茶"}:
        tags.extend(["茶香净度", "耐泡和风味层次", "产区气候带来的辨识度"])
    elif category == "鲜果":
        tags.extend(["成熟产带", "糖酸平衡", "果香和鲜食表现"])
    elif category == "蜂蜜":
        tags.extend(["蜜源环境", "花源季节性", "口感与色泽辨识"])
    elif category == "饮品":
        tags.extend(["地方酿造记忆", "发酵/陈化风味", "佐餐和礼赠场景"])
    elif category == "水产":
        tags.extend(["水域环境对鲜味的影响", "规格稳定度", "鲜活感和产地辨识"])
    elif category == "干货":
        tags.extend(["山地原料辨识", "干香和口感层次", "耐储与日常食用场景"])
    elif category == "熟食":
        tags.extend(["产区原料来源", "地方风味辨识", "佐餐和即食场景"])
    elif category == "蔬菜":
        tags.extend(["当季鲜度", "脆嫩口感", "近产地供应感"])
    elif category == "冲调":
        tags.extend(["原料基地来源", "冲调香气和质地", "早餐/轻食场景"])

    unique_tags: list[str] = []
    for tag in tags:
        if tag not in unique_tags:
            unique_tags.append(tag)
    return unique_tags[:4]


def _origin_promo_advice(product) -> str:
    region = str(product.region_name)
    category = str(product.category)
    name = str(product.product_name)
    tags = _origin_signal_tags(product)
    lead_tags = "、".join(tags[:3]) if tags else "来源清楚、产区稳定、品类适配"

    if category in {"绿茶", "黑茶"}:
        detail = "主标题直接写产区名，副标题突出高山/核心产带带来的香气净度、耐泡和风味层次，详情页补采摘季、产区环境和工艺关键词。"
    elif category == "鲜果":
        detail = "主标题先讲产带和成熟优势，副标题讲糖酸平衡、果香或鲜食口感，详情页补成熟季、规格和食用场景。"
    elif category == "蜂蜜":
        detail = "主标题讲林区或蜜源环境，副标题讲花源特征和口感辨识，详情页补采蜜季和风味范围，避免直接许诺功效。"
    elif category == "饮品":
        detail = "主标题讲地方产区和酿造来源，副标题讲米香、陈香或佐餐场景，详情页补工艺和适饮场景，不要只堆历史故事。"
    elif category == "水产":
        detail = "主标题讲湖区/水域来源，副标题讲鲜味、规格稳定和生态环境，详情页补规格区间、食用场景和可验证入口。"
    else:
        detail = "主标题讲产区名和最强的风土特征，副标题讲消费者一口能理解的口感/用途差异，详情页再补可验证来源和核心规格。"

    return (
        f"{name} 的产地表达可以直接围绕 {region} 展开，不要再泛写“正宗”“优质”。"
        f" 这款更适合主讲 {lead_tags}。{detail}"
        " 门店和详情页统一用一句话把产地优势说成人话，避免只讲认证清单或空泛故事。"
    )


def _origin_action(product) -> str:
    region = str(product.region_name)
    tags = _origin_signal_tags(product)
    first = tags[0] if len(tags) > 0 else "来源清楚"
    second = tags[1] if len(tags) > 1 else "产区辨识"
    third = tags[2] if len(tags) > 2 else "可验证入口"
    return (
        f"先把 {region} 的产地卖点固定成一套可直接上架的话术：主标题讲 {first}，"
        f"副标题讲 {second}，详情页补 {third} 和可验证入口，不要再只写“正宗”“优质”这类空话。"
    )


def _refine_analysis(report, analysis: DemoLlmStrategyAnalysis, card_hits: list[dict], insight_hits: list[str]) -> DemoLlmStrategyAnalysis:
    mode = _analysis_mode(report)
    top_city = report.market_insights[0].city if report.market_insights else "??????"
    second_city = report.market_insights[1].city if len(report.market_insights) > 1 else top_city
    third_city = report.market_insights[2].city if len(report.market_insights) > 2 else second_city
    product = report.product
    positioning = report.positioning_summary
    intrinsic = positioning.intrinsic_value_score
    presented = positioning.presented_value_score
    validation = positioning.market_validation_score
    fit_score = positioning.fit_score
    participation = product.participation_rate * 100
    activation = product.activation_rate * 100
    evidence_hint = _evidence_hint(card_hits)
    origin_action = _origin_action(product)
    origin_advice = _origin_promo_advice(product)

    if mode == "under":
        fallback_judgement = f"{product.product_name} ?????????????????????????????????????????????"
        fallback_summary = (
            f"{product.product_name} ?????? {intrinsic:.1f} ??????? {presented:.1f}???????????????????"
            f" ???????????????????????? {top_city}?{second_city} ???????"
            f" ?????????? {activation:.1f}%???????? {participation:.1f}% ????????? {third_city}?{evidence_hint}"
        )
        fallback_actions = [
            f"?? {product.product_name} ??????????????? {product.category} ? {product.price_band} ????????????????????????????",
            origin_action,
            f"? {top_city} ? {second_city} ????????????????? {product.channel} ???????????????????? {third_city}?",
            f"???????????????????????? {activation:.1f}% / {participation:.1f}%???????????????????",
        ]
    elif mode == "over":
        fallback_judgement = f"{product.product_name} ????????????????????????????????????????????"
        fallback_summary = (
            f"{product.product_name} ?????? {presented:.1f} ????????? {intrinsic:.1f}???????? {validation:.1f}?"
            f" ?????????????????????????????????? {top_city} ???????????? {second_city} ???????{evidence_hint}"
        )
        fallback_actions = [
            f"?? {product.product_name} ????????????????? {product.category} ???????????????????????????",
            origin_action,
            f"??? {top_city} ? {second_city} ???????????????????????????????????????????",
            "?????????????????????????????????????????????",
        ]
    elif mode == "matched":
        fallback_judgement = f"{product.product_name} ???????????????????????????????????????"
        fallback_summary = (
            f"{product.product_name} ??????????????????????? {fit_score:.1f}????????????"
            f" ????????????? {top_city} ????????????????????? {second_city}?{third_city} ????????"
        )
        fallback_actions = [
            f"?? {product.product_name} ??? {product.channel} ???????????????????????????????????????",
            origin_action,
            f"?????? {second_city}?{third_city} ???????????????????????????????????",
            "?????????????????????????????????????",
        ]
    else:
        fallback_judgement = f"{product.product_name} ????????????????????????????????????????"
        fallback_summary = (
            f"{product.product_name} ???????????????????????????????????"
            f" ????????? {top_city} ????????????? {second_city}?{third_city}???????????????????????????{evidence_hint}"
        )
        fallback_actions = [
            f"?? {product.product_name} ???????????? {product.category} ?????????????????????????????",
            origin_action,
            f"? {top_city} ?????{second_city} ???????????????????????????????? {third_city}?",
            "???????????????????????????????????????????",
        ]

    if not analysis.core_judgement:
        analysis.core_judgement = fallback_judgement
    if not analysis.executive_summary:
        analysis.executive_summary = fallback_summary

    existing_actions = [item for item in analysis.strategy_actions if item]
    for action in fallback_actions:
        if len(existing_actions) >= 4:
            break
        if action not in existing_actions:
            existing_actions.append(action)
    analysis.strategy_actions = existing_actions[:4]

    if not analysis.pricing_packaging_advice:
        analysis.pricing_packaging_advice = (
            f"???????? {product.product_name} ?? {product.price_band} ???????????????????????????"
            " ????????????????????????????????????"
        )
    if not analysis.channel_advice:
        analysis.channel_advice = (
            f"?????? {top_city} ??????? {second_city}?{third_city} ??????"
            f" ????????? {product.channel} ??????????????????"
        )
    if not analysis.origin_trust_advice:
        analysis.origin_trust_advice = origin_advice
    if not analysis.risk_warning:
        analysis.risk_warning = (
            f"?????????????????????????? {activation:.1f}%???????? {participation:.1f}%?"
            " ????????????????????????????"
        )

    analysis.evidence_findings = _refine_evidence_findings(analysis.evidence_findings, positioning, card_hits)
    return analysis


def _analysis_mode(report) -> str:
    intrinsic = report.positioning_summary.intrinsic_value_score
    presented = report.positioning_summary.presented_value_score
    validation = report.positioning_summary.market_validation_score
    fit_score = report.positioning_summary.fit_score
    if presented - intrinsic >= 12:
        return "over"
    if intrinsic - presented >= 10 and validation >= 42:
        return "under"
    if fit_score >= 72 and validation >= 45:
        return "matched"
    return "circulation"


def _refine_evidence_findings(existing: list[str], positioning, card_hits: list[dict]) -> list[str]:
    core_vars = []
    for card in card_hits[:4]:
        core_vars.extend(card.get("core_variables", []))
    unique_vars = []
    for item in core_vars:
        if item not in unique_vars:
            unique_vars.append(item)
    evidence_vars = "、".join(unique_vars[:4]) if unique_vars else "产地信息、渠道承接、价格接受度、信任表达"
    findings = [
        f"当前本体价值 {positioning.intrinsic_value_score:.1f} 分、当前呈现 {positioning.presented_value_score:.1f} 分，优先该补的是来源证据和市场判断，而不是先假设商品本身有问题。",
        f"检索证据集中指向 {evidence_vars} 这些变量，它们更接近购买意愿和城市承接差异的形成逻辑，所以建议应先落在产地信息整理、市场分析和信任表达上，包装只是其中一层。",
    ]
    if existing:
        findings.extend(item for item in existing[:2] if item not in findings)
    return findings[:4]


def _evidence_hint(card_hits: list[dict]) -> str:
    if not card_hits:
        return "当前缺少足够外部证据，建议把动作做小、把复盘做细。"
    weak_count = sum(1 for card in card_hits if str(card.get("evidence_strength", "")).lower() not in {"high", "strong", "较强"})
    if weak_count >= len(card_hits) / 2:
        return "当前外部证据里政策和案例类材料占比不低，因此建议先小范围试点，再根据结果扩大。"
    return "当前外部证据足够支持先做小范围验证，再按结果决定是否放大。"


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
