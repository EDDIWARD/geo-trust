const formatScore = (value) => Number(value ?? 0).toFixed(1);
const formatInt = (value) => new Intl.NumberFormat("zh-CN").format(Number(value ?? 0));
const percent = (value) => `${(Number(value ?? 0) * 100).toFixed(1)}%`;
const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

const state = {
  demoDashboard: null,
  adminSummary: null,
  adminRegions: [],
  adminEvents: [],
  activeClusterId: "all",
  activeProductId: null,
  activeTab: "structure",
  reportCache: new Map(),
  llmCache: new Map(),
  atlasRotationX: -0.42,
  atlasRotationY: 0.76,
  atlasDragging: false,
  atlasPointerX: 0,
  atlasPointerY: 0,
  atlasAnimationHandle: null,
  atlasViewMode: "angled",
  tooltipBound: false,
  globalTooltipMoveBound: false,
};

const tabLabels = {
  structure: "价值结构",
  markets: "市场机会",
  actions: "经营动作",
};

const clusterPalette = ["#2563eb", "#0ea5e9", "#14b8a6", "#f59e0b", "#ef4444", "#8b5cf6"];

async function fetchJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`request-failed:${url}`);
  }
  return response.json();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function avg(values) {
  if (!values.length) return 0;
  return values.reduce((sum, item) => sum + Number(item || 0), 0) / values.length;
}

function currentProducts() {
  if (!state.demoDashboard) return [];
  if (state.activeClusterId === "all") return state.demoDashboard.products;
  return state.demoDashboard.products.filter((item) => String(item.cluster_id) === String(state.activeClusterId));
}

function colorByClusterId(clusterId) {
  return clusterPalette[Math.abs(Number(clusterId) || 0) % clusterPalette.length];
}

function countBy(items, key) {
  return items.reduce((acc, item) => {
    const label = item[key] ?? "未分类";
    acc[label] = (acc[label] || 0) + 1;
    return acc;
  }, {});
}

function normalizeSigned(value, values) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (max - min < 0.00001) {
    return 0;
  }
  return ((value - min) / (max - min)) * 2 - 1;
}

function projectPoint(x, y, z, width, height) {
  const cosY = Math.cos(state.atlasRotationY);
  const sinY = Math.sin(state.atlasRotationY);
  const cosX = Math.cos(state.atlasRotationX);
  const sinX = Math.sin(state.atlasRotationX);

  const x1 = x * cosY - z * sinY;
  const z1 = x * sinY + z * cosY;
  const y1 = y * cosX - z1 * sinX;
  const z2 = y * sinX + z1 * cosX;
  const scale = 0.92 + (z2 + 1) * 0.16;

  return {
    x: width / 2 + x1 * 164 * scale,
    y: height * 0.58 - y1 * 154 * scale + z2 * 6,
    depth: z2,
    scale,
  };
}

function lineChartPath(values, width, height, padding = 8) {
  const safeValues = values.length ? values.map((value) => Number(value || 0)) : [0, 0, 0, 0];
  const min = Math.min(...safeValues);
  const max = Math.max(...safeValues);
  const span = Math.max(max - min, 0.0001);
  return safeValues
    .map((value, index) => {
      const x = padding + (index / Math.max(safeValues.length - 1, 1)) * (width - padding * 2);
      const y = height - padding - ((value - min) / span) * (height - padding * 2);
      return `${index === 0 ? "M" : "L"} ${x} ${y}`;
    })
    .join(" ");
}

function lineChartArea(values, width, height, padding = 8) {
  const safeValues = values.length ? values.map((value) => Number(value || 0)) : [0, 0, 0, 0];
  const min = Math.min(...safeValues);
  const max = Math.max(...safeValues);
  const span = Math.max(max - min, 0.0001);
  const points = safeValues.map((value, index) => {
    const x = padding + (index / Math.max(safeValues.length - 1, 1)) * (width - padding * 2);
    const y = height - padding - ((value - min) / span) * (height - padding * 2);
    return { x, y };
  });
  const start = points[0];
  const end = points[points.length - 1];
  return `M ${start.x} ${height - padding} L ${start.x} ${start.y} ${points
    .slice(1)
    .map((point) => `L ${point.x} ${point.y}`)
    .join(" ")} L ${end.x} ${height - padding} Z`;
}

function miniTrend(values, tone = "blue") {
  const width = 180;
  const height = 40;
  return `
    <svg viewBox="0 0 ${width} ${height}" aria-hidden="true">
      <path d="${lineChartArea(values, width, height)}" class="mini-area ${tone}"></path>
      <path d="${lineChartPath(values, width, height)}" class="mini-line ${tone}"></path>
    </svg>
  `;
}

function sparkPoints(product) {
  const values = [
    product.activation_rate,
    product.participation_rate,
    product.cross_region_rate,
    1 - product.abnormal_rate,
    product.stability_score,
  ].map((value) => clamp(value, 0.04, 1));
  return values.map((value, index) => `${index * 58 + 14},${62 - value * 48}`).join(" ");
}

function miniBars(values, tone = "#2563eb") {
  const width = 260;
  const height = 72;
  const max = Math.max(...values, 0.0001);
  const barWidth = 30;
  const gap = 18;
  const startX = 18;
  const baseY = 60;
  return `
    <svg class="catalog-bars" viewBox="0 0 ${width} ${height}" aria-hidden="true">
      ${values
        .map((value, index) => {
          const barHeight = (Number(value || 0) / max) * 40;
          const x = startX + index * (barWidth + gap);
          return `
            <rect x="${x}" y="${baseY - barHeight}" width="${barWidth}" height="${barHeight}" rx="10" fill="${tone}" opacity="${0.48 + index * 0.12}"></rect>
          `;
        })
        .join("")}
    </svg>
  `;
}

function barChart(entries) {
  const values = entries.map((entry) => Number(entry[1]) || 0);
  const max = Math.max(...values, 1);
  const baseY = 176;
  const startX = 34;
  const gap = 18;
  const barWidth = 58;
  return `
    <line x1="18" y1="${baseY}" x2="402" y2="${baseY}" class="mini-axis"></line>
    ${entries
      .map(([label, value], index) => {
        const height = (Number(value) / max) * 116;
        const x = startX + index * (barWidth + gap);
        return `
          <rect x="${x}" y="${baseY - height}" width="${barWidth}" height="${height}" rx="16" fill="${clusterPalette[index % clusterPalette.length]}" class="chart-rise"></rect>
          <text x="${x + barWidth / 2}" y="${baseY + 18}" text-anchor="middle" class="mini-axis-text">${escapeHtml(label)}</text>
          <text x="${x + barWidth / 2}" y="${baseY - height - 8}" text-anchor="middle" class="mini-axis-text">${formatScore(value)}</text>
        `;
      })
      .join("")}
  `;
}

function metricCard(label, value, tag = "") {
  return `
    <article class="metric-card">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      ${tag ? `<p>${escapeHtml(tag)}</p>` : ""}
    </article>
  `;
}

function indicatorCard(title, value, source) {
  return `
    <article class="indicator-card">
      <span>${escapeHtml(title)}</span>
      <strong>${escapeHtml(value)}</strong>
      <p>${escapeHtml(source)}</p>
    </article>
  `;
}

function projectionCard(title, copy, products, xLabel, yLabel, xGetter, yGetter) {
  const width = 340;
  const height = 208;
  const padding = 30;
  const plotWidth = width - padding * 2;
  const plotHeight = height - padding * 2;
  const xValues = products.map((item) => xGetter(item));
  const yValues = products.map((item) => yGetter(item));
  const xMin = Math.min(...xValues);
  const xMax = Math.max(...xValues);
  const yMin = Math.min(...yValues);
  const yMax = Math.max(...yValues);

  return `
    <article class="projection-card">
      <div class="section-head section-head-compact">
        <div>
          <p class="panel-kicker">2D Projection</p>
          <h2>${escapeHtml(title)}</h2>
        </div>
      </div>
      <p class="section-copy">${escapeHtml(copy)}</p>
      <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" aria-label="${escapeHtml(title)}">
        <rect x="${padding}" y="${padding}" width="${plotWidth}" height="${plotHeight}" rx="18" class="projection-base"></rect>
        <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" class="projection-axis"></line>
        <line x1="${padding}" y1="${padding}" x2="${padding}" y2="${height - padding}" class="projection-axis"></line>
        <line x1="${padding}" y1="${padding + plotHeight / 2}" x2="${width - padding}" y2="${padding + plotHeight / 2}" class="projection-guide"></line>
        <line x1="${padding + plotWidth / 2}" y1="${padding}" x2="${padding + plotWidth / 2}" y2="${height - padding}" class="projection-guide"></line>
        <text x="${padding}" y="${padding - 10}" class="scene-axis">${escapeHtml(yLabel)}</text>
        <text x="${width - 84}" y="${height - 8}" class="scene-axis">${escapeHtml(xLabel)}</text>
        ${products
          .map((item) => {
            const x = padding + ((xGetter(item) - xMin) / Math.max(xMax - xMin, 0.0001)) * plotWidth;
            const y = height - padding - ((yGetter(item) - yMin) / Math.max(yMax - yMin, 0.0001)) * plotHeight;
            return `
              <circle
                class="hover-point projection-point"
                cx="${x}"
                cy="${y}"
                r="5"
                fill="${colorByClusterId(item.cluster_id)}"
                stroke="rgba(255,255,255,0.92)"
                stroke-width="1.2"
                data-name="${escapeHtml(item.product_name)}"
                data-meta="${escapeHtml(item.cluster_name)} / ${escapeHtml(item.positioning_status)}"
                data-extra="${escapeHtml(xLabel)} ${percent(xGetter(item))} / ${escapeHtml(yLabel)} ${percent(yGetter(item))}"
              ></circle>
            `;
          })
          .join("")}
      </svg>
    </article>
  `;
}

function toRiskText(value) {
  const risk = String(value || "").toLowerCase();
  if (risk === "high") return "高风险";
  if (risk === "medium") return "中风险";
  if (risk === "low") return "低风险";
  return "关注中";
}

function eventMetricSeries(item) {
  const base = Number(item.speed ?? 0);
  const score = clamp(base / 1500, 0.15, 1);
  const spread = clamp((item.risk_level === "high" ? 0.22 : item.risk_level === "medium" ? 0.14 : 0.08), 0.04, 0.3);
  return [
    score * 0.72,
    score * 0.9,
    Math.max(score - spread * 0.35, 0.08),
    Math.min(score + spread, 1),
  ];
}

function regionMetricSeries(item) {
  return [
    Number(item.todayCount ?? 0),
    Number(item.totalScans ?? 0) / 6,
    Number(item.anomalies ?? 0) * 5 + 1,
    Number(item.todayCount ?? 0) * 2 + Number(item.anomalies ?? 0) * 3 + 1,
  ];
}

function clusterMetricSeries(item) {
  return [
    Number(item.product_count ?? 0),
    Number(item.average_opportunity_score ?? 0),
    Number(item.product_count ?? 0) * (Number(item.average_opportunity_score ?? 0) / 100),
    Number(item.average_opportunity_score ?? 0) * 0.92,
  ];
}

function renderHeader() {
  const summary = state.adminSummary;
  const tags = [
    `今日登记 ${formatInt(summary?.today_registered ?? 0)}`,
    `今日扫码 ${formatInt(summary?.today_scans ?? 0)}`,
    `今日异常 ${formatInt(summary?.today_anomalies ?? 0)}`,
    `分析商品 ${formatInt(state.demoDashboard?.products.length ?? 0)}`,
  ];

  document.querySelector("#masthead-tags").innerHTML = tags.map((item) => `<span class="tag">${escapeHtml(item)}</span>`).join("");

  const topClusters = state.demoDashboard.clusters.slice(0, 3);
  const topRegions = state.adminRegions.slice(0, 4);
  const topEvents = state.adminEvents.slice(0, 3);

  document.querySelector("#hero-visual").innerHTML = `
    <div class="hero-strip">
      <article class="hero-kpi-card">
        <span>累计建档商品</span>
        <strong>${formatInt(summary?.total_products ?? 0)}</strong>
        <p>管理端当前已接入并可追踪的商品总量。</p>
      </article>
      <article class="hero-kpi-card">
        <span>累计扫码次数</span>
        <strong>${formatInt(summary?.total_scans ?? 0)}</strong>
        <p>用于判断传播热度、核销活跃度与触达强度。</p>
      </article>
      <article class="hero-kpi-card">
        <span>分析样本数量</span>
        <strong>${formatInt(state.demoDashboard.products.length)}</strong>
        <p>当前进入经营分析工作台的示例商品样本。</p>
      </article>
    </div>
    <div class="hero-columns">
      <section class="hero-card">
        <div class="hero-card-head">
          <span>分群机会</span>
          <strong>Top Clusters</strong>
        </div>
        <div class="hero-mini-chart">
          ${miniTrend(topClusters.flatMap((item) => clusterMetricSeries(item)), "blue")}
        </div>
        <div class="hero-list compact-scroll">
          ${topClusters
            .map(
              (item) => `
                <article class="hero-row">
                  <div>
                    <strong>${escapeHtml(item.cluster_name)}</strong>
                    <p>${formatInt(item.product_count)} 个样本 / 机会分 ${formatScore(item.average_opportunity_score)}</p>
                  </div>
                  <span class="hero-chip">${formatScore(item.average_opportunity_score)}</span>
                </article>
              `
            )
            .join("")}
        </div>
      </section>
      <section class="hero-card">
        <div class="hero-card-head">
          <span>重点产区</span>
          <strong>Regions</strong>
        </div>
        <div class="hero-mini-chart">
          ${miniTrend(topRegions.flatMap((item) => regionMetricSeries(item)), "amber")}
        </div>
        <div class="hero-list compact-scroll">
          ${topRegions
            .map(
              (item) => `
                <article class="hero-row">
                  <div>
                    <strong>${escapeHtml(item.name)}</strong>
                    <p>${escapeHtml(item.type)} / 异常 ${formatInt(item.anomalies)} / 扫码 ${formatInt(item.totalScans)}</p>
                  </div>
                  <span class="hero-chip">${formatInt(item.todayCount)}</span>
                </article>
              `
            )
            .join("")}
        </div>
      </section>
      <section class="hero-card">
        <div class="hero-card-head">
          <span>重点事件</span>
          <strong>Events</strong>
        </div>
        <div class="hero-mini-chart">
          ${miniTrend(topEvents.flatMap((item) => eventMetricSeries(item).map((value) => value * 100)), "red")}
        </div>
        <div class="hero-list compact-scroll">
          ${topEvents
            .map(
              (item) => `
                <article class="hero-row">
                  <div>
                    <strong>${escapeHtml(item.product_code)}</strong>
                    <p>${escapeHtml(item.region_name)} / ${toRiskText(item.risk_level)}</p>
                  </div>
                  <span class="hero-chip">${formatScore(item.speed ?? 0)}</span>
                </article>
              `
            )
            .join("")}
        </div>
      </section>
    </div>
  `;
}

function buildScenePlanes(width, height) {
  return `
    <rect x="84" y="48" width="${width - 168}" height="${height - 136}" rx="28" class="scene-base"></rect>
    <line x1="84" y1="${height - 88}" x2="${width - 84}" y2="${height - 88}" class="scene-guide"></line>
    <line x1="84" y1="48" x2="84" y2="${height - 88}" class="scene-guide"></line>
    <line x1="${width / 2}" y1="48" x2="${width / 2}" y2="${height - 88}" class="scene-guide"></line>
    <line x1="84" y1="${(height - 88 + 48) / 2}" x2="${width - 84}" y2="${(height - 88 + 48) / 2}" class="scene-guide"></line>
  `;
}

function buildSceneAxes(width, height) {
  return `
    <text x="92" y="38" class="scene-axis">机会分</text>
    <text x="${width - 156}" y="${height - 42}" class="scene-axis">参与率</text>
    <text x="92" y="${height - 58}" class="scene-axis">激活率</text>
  `;
}

function buildAtlasScene(products) {
  const width = 760;
  const height = 500;
  const xValues = products.map((item) => item.activation_rate);
  const yValues = products.map((item) => item.trust_opportunity_score / 100);
  const zValues = products.map((item) => item.participation_rate);

  const points = products
    .map((item) => {
      const nx = normalizeSigned(item.activation_rate, xValues);
      const ny = normalizeSigned(item.trust_opportunity_score / 100, yValues);
      const nz = normalizeSigned(item.participation_rate, zValues);
      const projected = projectPoint(nx, ny, nz, width, height);
      const base = projectPoint(nx, -1, nz, width, height);
      return {
        item,
        projected,
        base,
        color: colorByClusterId(item.cluster_id),
      };
    })
    .sort((left, right) => left.projected.depth - right.projected.depth);

  const origin = projectPoint(-0.98, -0.98, -0.98, width, height);
  const axisX = projectPoint(1, -0.98, -0.98, width, height);
  const axisY = projectPoint(-0.98, 1, -0.98, width, height);
  const axisZ = projectPoint(-0.98, -0.98, 1, width, height);

  return `
    <article class="scene-card">
      <div class="section-head">
        <div>
          <p class="panel-kicker">3D Cluster</p>
          <h2>商品分群三维视图</h2>
        </div>
        <div class="view-switch">
          ${["angled", "top", "front"]
            .map(
              (mode) =>
                `<button class="view-chip${state.atlasViewMode === mode ? " is-active" : ""}" type="button" data-view="${mode}">
                  ${mode === "angled" ? "斜视角" : mode === "top" ? "俯视角" : "正视角"}
                </button>`
            )
            .join("")}
        </div>
      </div>
      <p class="section-copy">以激活率、机会分、参与率构成立体坐标轴。支持拖拽旋转，悬停可查看商品标签。</p>
      <div class="scene-shell">
        <svg id="atlas-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" aria-label="商品分群三维视图">
          ${buildScenePlanes(width, height)}
          ${buildSceneAxes(width, height)}
          <g class="scene-axis-group">
            <line x1="${origin.x}" y1="${origin.y}" x2="${axisX.x}" y2="${axisX.y}" class="scene-axis-line axis-x"></line>
            <line x1="${origin.x}" y1="${origin.y}" x2="${axisY.x}" y2="${axisY.y}" class="scene-axis-line axis-y"></line>
            <line x1="${origin.x}" y1="${origin.y}" x2="${axisZ.x}" y2="${axisZ.y}" class="scene-axis-line axis-z"></line>
            <circle cx="${origin.x}" cy="${origin.y}" r="5" class="scene-origin"></circle>
            <text x="${axisX.x + 8}" y="${axisX.y + 6}" class="scene-axis-label axis-x">激活率 X</text>
            <text x="${axisY.x + 8}" y="${axisY.y - 8}" class="scene-axis-label axis-y">机会分 Y</text>
            <text x="${axisZ.x + 8}" y="${axisZ.y + 4}" class="scene-axis-label axis-z">参与率 Z</text>
          </g>
          ${points
            .map(
              ({ item, projected, base, color }) => `
                <g class="atlas-node">
                  <line x1="${base.x}" y1="${base.y}" x2="${projected.x}" y2="${projected.y}" class="node-line"></line>
                  <circle
                    cx="${projected.x}"
                    cy="${projected.y}"
                    r="${clamp(3.4 + projected.scale * 3.8, 4, 7.6)}"
                    fill="${color}"
                    stroke="rgba(255,255,255,0.95)"
                    stroke-width="1.4"
                    class="hover-point"
                    data-name="${escapeHtml(item.product_name)}"
                    data-meta="${escapeHtml(item.cluster_name)} / ${escapeHtml(item.positioning_status)}"
                    data-extra="激活率 ${percent(item.activation_rate)} / 参与率 ${percent(item.participation_rate)} / 机会分 ${formatScore(item.trust_opportunity_score)}"
                  ></circle>
                </g>
              `
            )
            .join("")}
        </svg>
        <div class="axis-tag axis-left">激活率低</div>
        <div class="axis-tag axis-right">参与率高</div>
        <div class="axis-tag axis-top">机会分高</div>
      </div>
    </article>
  `;
}

function renderAtlas() {
  const products = currentProducts().length ? currentProducts() : state.demoDashboard.products;
  const clusterCards = state.demoDashboard.clusters.map(
    (item) => `
      <article class="cluster-card">
        <div class="cluster-dot" style="background:${colorByClusterId(item.cluster_id)};"></div>
        <div>
          <strong>${escapeHtml(item.cluster_name)}</strong>
          <p>${escapeHtml(item.description)}</p>
          <div class="cluster-meta">
            <span>${formatInt(item.product_count)} 个样本</span>
            <span>机会分 ${formatScore(item.average_opportunity_score)}</span>
          </div>
          <div class="cluster-scoreline">
            <span class="cluster-scoreline-track">
              <span class="cluster-scoreline-fill" style="width:${clamp(item.average_opportunity_score, 0, 100)}%; background:${colorByClusterId(item.cluster_id)};"></span>
            </span>
          </div>
        </div>
      </article>
    `
  );

  document.querySelector("#atlas-grid").innerHTML = `
    <div class="atlas-layout">
      <div class="atlas-main">
        ${buildAtlasScene(products)}
      </div>
      <aside class="meta-panel side-metrics-panel">
        <div class="metric-grid metric-grid-tall">
          ${metricCard("今日登记", formatInt(state.adminSummary?.today_registered ?? 0), "管理端新增")}
          ${metricCard("今日扫码", formatInt(state.adminSummary?.today_scans ?? 0), "管理端更新")}
          ${metricCard("平均激活率", percent(avg(products.map((item) => item.activation_rate))), "当前筛选商品")}
          ${metricCard("平均参与率", percent(avg(products.map((item) => item.participation_rate))), "当前筛选商品")}
        </div>
      </aside>
    </div>
    <section class="meta-panel cluster-panel cluster-panel-wide">
      <div class="section-head section-head-compact">
        <div>
          <p class="panel-kicker">Cluster Layers</p>
          <h2>分群结构</h2>
        </div>
      </div>
      <div class="cluster-card-list cluster-card-list-inline">${clusterCards.join("")}</div>
    </section>
    <div class="projection-grid">
      ${projectionCard("激活率 vs 参与率", "看哪些商品既能拉动用户触达，也能带来后续互动。", products, "激活率", "参与率", (item) => item.activation_rate, (item) => item.participation_rate)}
      ${projectionCard("跨区率 vs 机会分", "看跨区域流通能力与机会分之间是否同步提升。", products, "跨区率", "机会分", (item) => item.cross_region_rate, (item) => item.trust_opportunity_score / 100)}
      ${projectionCard("稳定性 vs 安全表现", "看履约稳定度与异常表现的整体分布。", products, "稳定性", "安全表现", (item) => item.stability_score, (item) => 1 - item.abnormal_rate)}
    </div>
  `;

  bindAtlasControls();
  bindTooltip();
}

function renderOverview() {
  const products = currentProducts().length ? currentProducts() : state.demoDashboard.products;
  const clusterCounts = countBy(products, "positioning_status");
  const topMarkets = state.demoDashboard.market_heat.slice(0, 4);

  document.querySelector("#telemetry-ribbon").innerHTML = `
    <article class="panel soft-panel">
      <div class="section-head section-head-compact">
        <div>
          <p class="panel-kicker">Overview</p>
          <h2>经营概览</h2>
        </div>
      </div>
      <div class="sync-grid">
        <div class="sync-card">
          <span>在管商品</span>
          <strong>${formatInt(state.adminSummary?.total_products ?? 0)}</strong>
          <p>当前后台已纳入追踪的商品总量。</p>
        </div>
        <div class="sync-card">
          <span>累计扫码</span>
          <strong>${formatInt(state.adminSummary?.total_scans ?? 0)}</strong>
          <p>用于评估传播触达和核销热度。</p>
        </div>
        <div class="sync-card">
          <span>重点区域</span>
          <strong>${formatInt(state.adminRegions.length)}</strong>
          <p>当前有监测记录的主要产区和重点区域。</p>
        </div>
        <div class="sync-card">
          <span>异常事件</span>
          <strong>${formatInt(state.adminEvents.length)}</strong>
          <p>近期进入监控列表的事件数量。</p>
        </div>
      </div>
    </article>
    <article class="panel soft-panel">
      <div class="section-head section-head-compact">
        <div>
          <p class="panel-kicker">Positioning</p>
          <h2>定位分布</h2>
        </div>
      </div>
      <div class="segment-list">
        ${Object.entries(clusterCounts)
          .map(
            ([label, count], index) => `
              <div class="segment-row">
                <span>${escapeHtml(label)}</span>
                <div class="segment-track"><span style="width:${(count / Math.max(products.length, 1)) * 100}%;background:${clusterPalette[index % clusterPalette.length]};"></span></div>
                <strong>${formatInt(count)}</strong>
              </div>
            `
          )
          .join("")}
      </div>
    </article>
  `;

  document.querySelector("#telemetry-market").innerHTML = `
    <article class="panel soft-panel">
      <div class="section-head section-head-compact">
        <div>
          <p class="panel-kicker">Markets</p>
          <h2>城市机会</h2>
        </div>
      </div>
      <div class="bar-list">
        ${topMarkets
          .map(
            (item, index) => `
              <div class="bar-row">
                <span>${escapeHtml(item.city)}</span>
                <div class="bar-track"><span style="width:${clamp(item.opportunity_score, 10, 100)}%;background:${clusterPalette[index % clusterPalette.length]};"></span></div>
                <strong>${formatScore(item.opportunity_score)}</strong>
              </div>
            `
          )
          .join("")}
      </div>
    </article>
    <article class="panel soft-panel">
      <div class="section-head section-head-compact">
        <div>
          <p class="panel-kicker">Events</p>
          <h2>重点事件</h2>
        </div>
      </div>
      <div class="event-list event-list-scroll">
        ${state.adminEvents
          .slice(0, 4)
          .map(
            (item) => `
              <article class="event-card">
                <strong>${escapeHtml(item.product_code)}</strong>
                <p>${escapeHtml(item.region_name)} / ${escapeHtml(item.message || "存在跨区流转或异常触发记录")}</p>
                <span>${toRiskText(item.risk_level)} / 速度 ${formatScore(item.speed ?? 0)} km/h</span>
              </article>
            `
          )
          .join("")}
      </div>
    </article>
  `;
}

function renderFilters() {
  const items = [{ cluster_id: "all", cluster_name: "全部商品", product_count: state.demoDashboard.products.length }, ...state.demoDashboard.clusters];
  const markup = items
    .map(
      (item) => `
        <button class="cluster-pill${String(state.activeClusterId) === String(item.cluster_id) ? " is-active" : ""}" type="button" data-cluster-id="${item.cluster_id}">
          ${escapeHtml(item.cluster_name)} ${formatInt(item.product_count)}
        </button>
      `
    )
    .join("");

  document.querySelector("#cluster-pill-row").innerHTML = markup;
  document.querySelector("#catalog-filter-row").innerHTML = markup;
  document.querySelectorAll(".cluster-pill").forEach((button) => {
    button.addEventListener("click", async () => {
      state.activeClusterId = button.dataset.clusterId;
      renderShell();
      const products = currentProducts();
      if (!products.some((item) => item.product_id === state.activeProductId)) {
        await selectProduct(products[0]?.product_id ?? state.demoDashboard.products[0]?.product_id);
      } else {
        highlightCatalog();
      }
    });
  });
}

function catalogTrendValues(item) {
  return [
    item.activation_rate * 100,
    item.participation_rate * 100,
    item.cross_region_rate * 100,
    (1 - item.abnormal_rate) * 100,
    item.stability_score * 100,
  ];
}

function renderCatalog() {
  const products = currentProducts();
  document.querySelector("#catalog-caption").textContent = `当前筛选到 ${products.length} 个商品，可切换查看单品经营分析。`;
  document.querySelector("#catalog-list").innerHTML = products
    .map((item) => {
      const values = catalogTrendValues(item);
      const tone = colorByClusterId(item.cluster_id);
      return `
        <article class="catalog-card${item.product_id === state.activeProductId ? " is-active" : ""}" data-product-id="${item.product_id}">
          <div class="catalog-top">
            <div>
              <span class="tag" style="color:${tone};">${escapeHtml(item.positioning_status)}</span>
              <h3>${escapeHtml(item.product_name)}</h3>
              <p>${escapeHtml(item.region_name)} / ${escapeHtml(item.channel)} / ${escapeHtml(item.price_band)}</p>
            </div>
            <div class="catalog-score">${formatScore(item.trust_opportunity_score)}</div>
          </div>
          <div class="catalog-chart-grid">
            <div class="catalog-chart">
              <span>经营指标走势</span>
              <svg class="catalog-spark" viewBox="0 0 260 72" aria-hidden="true">
                <path d="${lineChartArea(values, 260, 72, 10)}" fill="${tone}" opacity="0.12"></path>
                <path d="${lineChartPath(values, 260, 72, 10)}" fill="none" stroke="${tone}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>
              </svg>
            </div>
          </div>
          <div class="catalog-legend">
            <span>激活 ${percent(item.activation_rate)}</span>
            <span>参与 ${percent(item.participation_rate)}</span>
            <span>跨区 ${percent(item.cross_region_rate)}</span>
            <span>稳定 ${percent(item.stability_score)}</span>
          </div>
        </article>
      `;
    })
    .join("");

  document.querySelectorAll(".catalog-card").forEach((card) => {
    card.addEventListener("click", async () => {
      await selectProduct(card.dataset.productId);
    });
  });
}

function highlightCatalog() {
  document.querySelectorAll(".catalog-card").forEach((card) => {
    card.classList.toggle("is-active", card.dataset.productId === state.activeProductId);
  });
}

function renderLoadingState() {
  document.querySelector("#stage-root").innerHTML = `
    <div class="stage-shell">
      <div class="skeleton"></div>
      <div class="skeleton" style="height:220px;"></div>
      <div class="skeleton" style="height:340px;"></div>
    </div>
  `;
  document.querySelector("#intel-root").innerHTML = `
    <div class="intel-shell">
      <div class="skeleton" style="height:180px;"></div>
      <div class="skeleton" style="height:160px;"></div>
    </div>
  `;
}

function renderStructureTab(report) {
  const positioning = report.positioning_summary;
  const product = report.product;
  const metrics = [
    ["内在价值", positioning.intrinsic_value_score],
    ["呈现价值", positioning.presented_value_score],
    ["市场验证", positioning.market_validation_score],
    ["匹配度", positioning.fit_score],
  ];

  return `
    <div class="stage-grid">
      <section class="card-block">
        <p class="panel-kicker">Structure</p>
        <h3>价值结构拆解</h3>
        <div class="metric-ledger">
          ${metrics
            .map(
              ([label, value]) => `
                <article class="metric-strip">
                  <span>${escapeHtml(label)}</span>
                  <strong>${formatScore(value)}</strong>
                  <div class="track"><span class="track-fill" style="width:${clamp(value, 10, 100)}%; background:#2563eb;"></span></div>
                </article>
              `
            )
            .join("")}
        </div>
        <div class="metric-visual">
          <svg viewBox="0 0 420 220" aria-label="价值结构对比图">
            ${barChart(metrics)}
          </svg>
        </div>
      </section>
      <section class="card-block">
        <p class="panel-kicker">Signals</p>
        <h3>核心经营指标</h3>
        <div class="indicator-stack">
          ${indicatorCard("累计核销量", formatInt(product.verified_scans), "单品历史表现")}
          ${indicatorCard("激活率", percent(product.activation_rate), "当前商品")}
          ${indicatorCard("参与率", percent(product.participation_rate), "当前商品")}
          ${indicatorCard("异常率", percent(product.abnormal_rate), "当前商品")}
          ${indicatorCard("今日异常", formatInt(state.adminSummary?.today_anomalies ?? 0), "全局监测")}
        </div>
      </section>
    </div>
    <div class="stage-grid detail-grid">
      <section class="card-block">
        <p class="panel-kicker">Peer Group</p>
        <h3>同群对照</h3>
        <div class="peer-stack">
          ${report.peer_products
            .slice(0, 4)
            .map(
              (item) => `
                <article class="peer-card">
                  <div class="peer-head">
                    <strong>${escapeHtml(item.product_name)}</strong>
                    <span class="tag">${escapeHtml(item.positioning_status)}</span>
                  </div>
                  <p>${escapeHtml(item.region_name)} / ${escapeHtml(item.channel)} / 机会分 ${formatScore(item.trust_opportunity_score)}</p>
                  <div class="bar-row">
                    <span>参与率</span>
                    <div class="bar-track"><span style="width:${clamp(item.participation_rate * 100, 6, 100)}%;background:${colorByClusterId(item.cluster_id)};"></span></div>
                    <strong>${percent(item.participation_rate)}</strong>
                  </div>
                </article>
              `
            )
            .join("")}
        </div>
      </section>
      <section class="card-block">
        <p class="panel-kicker">Signals</p>
        <h3>原始信号摘要</h3>
        <div class="ledger-grid">
          <article class="ledger-card">
            <span>产地信号</span>
            <strong>${escapeHtml(product.origin_cluster)}</strong>
            <p>当前样本在产地认知与可信表达上的聚类结果。</p>
          </article>
          <article class="ledger-card">
            <span>呈现方式</span>
            <strong>${escapeHtml(product.presentation_cluster)}</strong>
            <p>包装、价格带和渠道组合形成的表达层聚类。</p>
          </article>
          <article class="ledger-card">
            <span>经营反馈</span>
            <strong>${escapeHtml(product.feedback_cluster)}</strong>
            <p>由激活、参与、跨区和异常共同形成的反馈层结果。</p>
          </article>
          <article class="ledger-card">
            <span>稳定性</span>
            <strong>${percent(product.stability_score)}</strong>
            <p>${escapeHtml(product.stability_label || "当前结论稳定")}</p>
          </article>
        </div>
      </section>
    </div>
  `;
}

function renderMarketsTab(report) {
  return `
    <div class="stage-grid">
      <section class="card-block">
        <p class="panel-kicker">Markets</p>
        <h3>城市机会排序</h3>
        <div class="metric-visual">
          <svg viewBox="0 0 420 220" aria-label="城市机会排序图">
            ${barChart(report.market_insights.slice(0, 5).map((item) => [item.city, item.opportunity_score]))}
          </svg>
        </div>
        <div class="city-stack">
          ${report.market_insights
            .slice(0, 5)
            .map(
              (item) => `
                <article class="city-card">
                  <div class="city-card-head">
                    <strong>${escapeHtml(item.city)}</strong>
                    <span class="tag">${escapeHtml(item.market_tier)}</span>
                  </div>
                  <p>${escapeHtml(item.observation)}</p>
                  <div class="bar-row">
                    <span>机会分</span>
                    <div class="bar-track"><span style="width:${clamp(item.opportunity_score, 10, 100)}%;background:#2563eb;"></span></div>
                    <strong>${formatScore(item.opportunity_score)}</strong>
                  </div>
                </article>
              `
            )
            .join("")}
        </div>
      </section>
      <section class="card-block">
        <p class="panel-kicker">Regions</p>
        <h3>重点区域状态</h3>
        <div class="teacher-stack">
          ${state.adminRegions
            .slice(0, 5)
            .map(
              (item) => `
                <article class="teacher-card">
                  <div class="teacher-head">
                    <strong>${escapeHtml(item.name)}</strong>
                    <span class="tag">${escapeHtml(item.type)}</span>
                  </div>
                  <p>累计扫码 ${formatInt(item.totalScans)} / 异常 ${formatInt(item.anomalies)} / 今日新增 ${formatInt(item.todayCount)}</p>
                </article>
              `
            )
            .join("")}
        </div>
      </section>
    </div>
    <div class="stage-grid detail-grid">
      <section class="card-block">
        <p class="panel-kicker">Market Learning</p>
        <h3>市场学习点</h3>
        <div class="learning-stack">
          ${report.market_learning
            .slice(0, 4)
            .map(
              (item) => `
                <article class="learning-card">
                  <strong>${escapeHtml(item.city)}</strong>
                  <p>${escapeHtml(item.learning)}</p>
                </article>
              `
            )
            .join("")}
        </div>
      </section>
      <section class="card-block">
        <p class="panel-kicker">Signals</p>
        <h3>市场验证补充</h3>
        <div class="indicator-stack">
          ${indicatorCard("激活率", percent(report.product.activation_rate), "触达能力")}
          ${indicatorCard("参与率", percent(report.product.participation_rate), "交互深度")}
          ${indicatorCard("跨区率", percent(report.product.cross_region_rate), "外溢能力")}
          ${indicatorCard("稳定性", percent(report.product.stability_score), "结论稳定度")}
        </div>
      </section>
    </div>
  `;
}

function renderActionsTab(report, llm) {
  const actions = llm?.strategy_actions?.length ? llm.strategy_actions : report.strategy_report.actions;
  const scenarios = report.scenarios.slice(0, 3);
  return `
    <div class="stage-split">
      <section class="card-block">
        <p class="panel-kicker">Action Stack</p>
        <h3>经营动作建议</h3>
        <p class="card-copy">${escapeHtml(report.strategy_report.diagnosis)}</p>
        <ul class="action-list">
          ${actions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
        </ul>
      </section>
      <section class="card-block">
        <p class="panel-kicker">Scenario Engine</p>
        <h3>场景推演</h3>
        <div class="scenario-stack">
          ${scenarios
            .map(
              (item) => `
                <article class="scenario-card">
                  <span class="tag">${escapeHtml(item.direction)}</span>
                  <strong>${escapeHtml(item.scenario_name)}</strong>
                  <p>${escapeHtml(item.reason)}</p>
                  <div class="bar-row">
                    <span>验证提升</span>
                    <div class="bar-track"><span style="width:${clamp(item.projected_market_validation_score, 10, 100)}%;background:#14b8a6;"></span></div>
                    <strong>${formatScore(item.projected_market_validation_score)}</strong>
                  </div>
                </article>
              `
            )
            .join("")}
        </div>
      </section>
    </div>
    <div class="stage-grid detail-grid">
      <section class="card-block">
        <p class="panel-kicker">Opportunity</p>
        <h3>机会说明</h3>
        <p class="card-copy">${escapeHtml(report.strategy_report.opportunity)}</p>
      </section>
      <section class="card-block">
        <p class="panel-kicker">Execution</p>
        <h3>执行提醒</h3>
        <ul class="action-list">
          ${(llm?.strategy_actions?.slice(0, 3) || report.strategy_report.actions.slice(0, 3)).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
        </ul>
      </section>
    </div>
  `;
}

function renderStageTab(report, llm) {
  if (state.activeTab === "markets") return renderMarketsTab(report);
  if (state.activeTab === "actions") return renderActionsTab(report, llm);
  return renderStructureTab(report);
}

function renderStage(report, llmReport) {
  const product = report.product;
  const positioning = report.positioning_summary;

  document.querySelector("#stage-root").innerHTML = `
    <div class="stage-shell">
      <section class="stage-hero">
        <div class="stage-hero-copy">
          <p class="panel-kicker">Product Focus</p>
          <div class="chip-row">
            <span class="tag">${escapeHtml(product.positioning_status)}</span>
            <span class="tag">${escapeHtml(product.recommendation_direction)}</span>
            <span class="tag">${escapeHtml(product.region_name)}</span>
          </div>
          <h2 class="stage-title">${escapeHtml(product.product_name)}</h2>
          <p class="stage-copy">${escapeHtml(positioning.summary)}</p>
          <div class="stage-tab-row">
            ${Object.entries(tabLabels)
              .map(
                ([key, label]) => `<button class="tab-chip${state.activeTab === key ? " is-active" : ""}" type="button" data-tab="${key}">${escapeHtml(label)}</button>`
              )
              .join("")}
          </div>
        </div>
        <div class="score-panel">
          <div class="score-label">机会分</div>
          <div class="score-value">${formatScore(product.trust_opportunity_score)}</div>
          <div class="score-ring">
            <svg viewBox="0 0 180 180" aria-hidden="true">
              <circle cx="90" cy="90" r="62" class="ring-base"></circle>
              <circle
                cx="90"
                cy="90"
                r="62"
                class="ring-fill"
                stroke-dasharray="${(product.trust_opportunity_score / 100) * 389} 389"
                transform="rotate(-90 90 90)"
              ></circle>
            </svg>
          </div>
        </div>
      </section>
      <div class="stage-body">${renderStageTab(report, llmReport?.analysis)}</div>
    </div>
  `;

  document.querySelectorAll(".tab-chip").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeTab = button.dataset.tab;
      renderStage(report, llmReport);
    });
  });
}

function renderIntel(report, llmReport) {
  const llm = llmReport?.analysis;

  if (!llm) {
    document.querySelector("#intel-root").innerHTML = `
      <div class="intel-shell">
        <section class="panel intel-summary">
          <div class="section-head section-head-compact">
            <div>
              <p class="panel-kicker">AI Intelligence</p>
              <h2>智能判读</h2>
            </div>
          </div>
          <h3>${escapeHtml(report.positioning_summary.positioning_status)} / ${escapeHtml(report.positioning_summary.recommendation_direction)}</h3>
          <p>${escapeHtml(report.strategy_report.opportunity)}</p>
        </section>
      </div>
    `;
    return;
  }

  document.querySelector("#intel-root").innerHTML = `
    <div class="intel-shell">
      <section class="panel intel-summary">
        <div class="section-head section-head-compact intel-headline">
          <div>
            <p class="panel-kicker">AI Intelligence</p>
            <h2>智能判读</h2>
          </div>
        </div>
        <div class="chip-row">
          <span class="tag">${escapeHtml(report.product.positioning_status)}</span>
          <span class="tag">${escapeHtml(report.product.recommendation_direction)}</span>
        </div>
        <h3>${escapeHtml(llm.core_judgement)}</h3>
        <p>${escapeHtml(llm.executive_summary)}</p>
      </section>
      <section class="panel intel-card">
        <h4>证据摘要</h4>
        <ul class="evidence-list">
          ${llm.evidence_findings.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
        </ul>
      </section>
      <section class="panel intel-card">
        <h4>动作建议</h4>
        <p><strong>价格与包装：</strong>${escapeHtml(llm.pricing_packaging_advice)}</p>
        <p><strong>渠道安排：</strong>${escapeHtml(llm.channel_advice)}</p>
        <p><strong>产地信任：</strong>${escapeHtml(llm.origin_trust_advice)}</p>
        <p><strong>风险提醒：</strong>${escapeHtml(llm.risk_warning)}</p>
      </section>
    </div>
  `;
}

function renderShell() {
  renderHeader();
  renderAtlas();
  renderOverview();
  renderFilters();
  renderCatalog();
}

function positionTooltip(tooltip, event) {
  const maxLeft = Math.max(12, window.innerWidth - tooltip.offsetWidth - 12);
  const maxTop = Math.max(12, window.innerHeight - tooltip.offsetHeight - 12);
  tooltip.style.left = `${clamp(event.clientX + 12, 12, maxLeft)}px`;
  tooltip.style.top = `${clamp(event.clientY + 12, 12, maxTop)}px`;
}

function bindTooltip() {
  const tooltip = document.querySelector("#scatter-tooltip");
  if (!tooltip) return;

  const hideTooltip = () => {
    tooltip.hidden = true;
  };

  const showTooltip = (point, event) => {
    tooltip.hidden = false;
    tooltip.innerHTML = `
      <strong>${point.dataset.name}</strong>
      <p>${point.dataset.meta}</p>
      <p>${point.dataset.extra}</p>
    `;
    positionTooltip(tooltip, event);
  };

  hideTooltip();
  document.querySelectorAll(".hover-point").forEach((point) => {
    point.addEventListener("pointerenter", (event) => showTooltip(point, event));
    point.addEventListener("pointermove", (event) => showTooltip(point, event));
    point.addEventListener("pointerleave", hideTooltip);
    point.addEventListener("pointercancel", hideTooltip);
  });

  document.querySelector("#atlas-grid")?.addEventListener("pointerleave", hideTooltip);
  document.querySelector("#atlas-grid")?.addEventListener("scroll", hideTooltip);

  if (!state.globalTooltipMoveBound) {
    document.addEventListener("pointermove", (event) => {
      if (state.atlasDragging) {
        hideTooltip();
        return;
      }
      const target = event.target;
      if (target instanceof Element && target.closest(".hover-point")) {
        return;
      }
      hideTooltip();
    });
    document.addEventListener("scroll", hideTooltip, true);
    state.globalTooltipMoveBound = true;
  }
}

function setAtlasView(mode) {
  state.atlasViewMode = mode;
  if (mode === "top") {
    state.atlasRotationX = -1.12;
    state.atlasRotationY = 0.02;
  } else if (mode === "front") {
    state.atlasRotationX = -0.05;
    state.atlasRotationY = 0.02;
  } else {
    state.atlasRotationX = -0.42;
    state.atlasRotationY = 0.76;
  }
  renderAtlas();
}

function bindAtlasControls() {
  const svg = document.querySelector("#atlas-svg");
  if (!svg) return;

  document.querySelectorAll(".view-chip").forEach((button) => {
    button.addEventListener("click", () => setAtlasView(button.dataset.view));
  });

  svg.style.touchAction = "none";
  svg.onpointerdown = (event) => {
    state.atlasDragging = true;
    state.atlasPointerX = event.clientX;
    state.atlasPointerY = event.clientY;
    svg.setPointerCapture?.(event.pointerId);
  };

  svg.onpointermove = (event) => {
    if (!state.atlasDragging) return;
    const dx = event.clientX - state.atlasPointerX;
    const dy = event.clientY - state.atlasPointerY;
    state.atlasPointerX = event.clientX;
    state.atlasPointerY = event.clientY;
    state.atlasRotationY += dx * 0.008;
    state.atlasRotationX = clamp(state.atlasRotationX + dy * 0.004, -1.18, 0.08);
    renderAtlas();
  };

  const release = (event) => {
    state.atlasDragging = false;
    if (event?.pointerId !== undefined) {
      svg.releasePointerCapture?.(event.pointerId);
    }
  };

  svg.onpointerup = release;
  svg.onpointercancel = release;
  svg.onlostpointercapture = release;
}

function ensureAtlasAnimation() {
  if (state.atlasAnimationHandle) return;
  const animate = () => {
    if (!state.atlasDragging && state.demoDashboard) {
      state.atlasRotationY += 0.0012;
      if (!document.querySelector(".hover-point:hover")) {
        renderAtlas();
      }
    }
    state.atlasAnimationHandle = requestAnimationFrame(animate);
  };
  state.atlasAnimationHandle = requestAnimationFrame(animate);
}

async function selectProduct(productId) {
  if (!productId) return;
  state.activeProductId = productId;
  renderLoadingState();

  const reportPromise = state.reportCache.has(productId)
    ? Promise.resolve(state.reportCache.get(productId))
    : fetchJson(`/api/analytics/demo/report/${productId}`).then((payload) => {
        state.reportCache.set(productId, payload);
        return payload;
      });

  const llmPromise = state.llmCache.has(productId)
    ? Promise.resolve(state.llmCache.get(productId))
    : fetchJson(`/api/analytics/demo/llm-report/${productId}`)
        .then((payload) => {
          state.llmCache.set(productId, payload);
          return payload;
        })
        .catch(() => null);

  const [report, llmReport] = await Promise.all([reportPromise, llmPromise]);
  renderStage(report, llmReport);
  renderIntel(report, llmReport);
  highlightCatalog();
}

async function loadAllData() {
  const [demoDashboard, adminSummary, adminRegions, adminEvents] = await Promise.all([
    fetchJson("/api/analytics/demo/dashboard"),
    fetchJson("/api/dashboard/summary"),
    fetchJson("/api/dashboard/regions").then((payload) => payload.regions || []),
    fetchJson("/api/dashboard/events?limit=8").then((payload) => payload.events || []),
  ]);

  state.demoDashboard = demoDashboard;
  state.adminSummary = adminSummary;
  state.adminRegions = adminRegions;
  state.adminEvents = adminEvents;
}

async function bootstrap() {
  await loadAllData();
  renderShell();
  ensureAtlasAnimation();
  const firstProduct = currentProducts()[0] || state.demoDashboard.products[0];
  if (firstProduct) {
    await selectProduct(firstProduct.product_id);
  }
}

bootstrap().catch((error) => {
  console.error(error);
  document.querySelector("#stage-root").innerHTML = `
    <div class="stage-empty">
      <p class="panel-kicker">Error</p>
      <h3>分析面板加载失败</h3>
      <p>请检查管理端和分析接口是否都已正常启动。</p>
    </div>
  `;
  document.querySelector("#intel-root").innerHTML = `
    <div class="intel-empty">
      <p class="panel-kicker">Error</p>
      <h3>智能判读暂不可用</h3>
      <p>当前无法获取分析结果，请稍后重试。</p>
    </div>
  `;
});
