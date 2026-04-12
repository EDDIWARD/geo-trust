const formatScore = (value) => Number(value).toFixed(1);
const formatInt = (value) => new Intl.NumberFormat("zh-CN").format(value);
const percent = (value) => `${(value * 100).toFixed(1)}%`;
const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

const state = {
  dashboard: null,
  activeClusterId: "all",
  activeProductId: null,
  activeTab: "structure",
  reportCache: new Map(),
  llmCache: new Map(),
  atlasRotationX: -0.32,
  atlasRotationY: 0.56,
  atlasDragging: false,
  atlasPointerX: 0,
  atlasPointerY: 0,
  atlasAnimationHandle: null,
  atlasInteractionBound: false,
  atlasViewMode: "angled",
};

const tierStyles = {
  priority: { label: "优先城市", className: "is-priority" },
  potential: { label: "可测试", className: "is-potential" },
  watch: { label: "观察项", className: "is-watch" },
};

const tabLabels = {
  structure: "价值结构",
  markets: "城市机会",
  actions: "动作推演",
};

async function loadDashboard() {
  state.dashboard = await fetchJson("/api/analytics/demo/dashboard");
  renderShell();
  const firstProduct = filteredProducts()[0] || state.dashboard.products[0];
  if (firstProduct) {
    await selectProduct(firstProduct.product_id);
  }
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`request-failed:${url}`);
  }
  return response.json();
}

function filteredProducts() {
  if (!state.dashboard) {
    return [];
  }
  if (state.activeClusterId === "all") {
    return state.dashboard.products;
  }
  return state.dashboard.products.filter((item) => String(item.cluster_id) === String(state.activeClusterId));
}

function tierMeta(tier) {
  return tierStyles[tier] || tierStyles.potential;
}

function normalizeByRange(value, values, floor = 14, ceil = 100) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (max - min < 0.001) {
    return (floor + ceil) / 2;
  }
  return floor + ((value - min) / (max - min)) * (ceil - floor);
}

function metricWave(seed) {
  const values = Array.from({ length: 14 }, (_, index) => {
    const sin = Math.sin((index + seed * 0.7) * 0.65);
    const cos = Math.cos((index + seed * 0.35) * 0.4);
    return 26 + sin * 12 + cos * 6 + index * 0.6;
  });
  return values.map((value, index) => `${index * 18},${54 - value}`).join(" ");
}

function renderShell() {
  renderMasthead();
  renderAtlas();
  renderTelemetry();
  renderClusterFilters();
  renderCatalog();
}

function renderMasthead() {
  const tagHost = document.querySelector("#masthead-tags");
  const overview = state.dashboard.overview_metrics.slice(0, 4);
  tagHost.innerHTML = overview
    .map((item) => `<span class="tag">${item.name} ${item.value}</span>`)
    .join("");

  const heroVisual = document.querySelector("#hero-visual");
  const cities = state.dashboard.market_heat.slice(0, 6);
  const cityValues = cities.map((item) => item.opportunity_score);
  const topClusters = state.dashboard.clusters
    .slice()
    .sort((left, right) => right.average_opportunity_score - left.average_opportunity_score)
    .slice(0, 3);
  const verifiedScanMetric = state.dashboard.overview_metrics.find((item) => item.key === "verified_scans")?.value ?? "--";

  heroVisual.innerHTML = `
    <div class="hero-visual-frame hero-visual-dashboard">
      <div class="hero-kpi-strip">
        <article class="hero-kpi-card">
          <span>可信核销样本</span>
          <strong>${verifiedScanMetric}</strong>
          <p>当前全样本主动验真规模</p>
        </article>
        <article class="hero-kpi-card">
          <span>商品样本</span>
          <strong>${state.dashboard.products.length}</strong>
          <p>当前进入分析池的商品数</p>
        </article>
        <article class="hero-kpi-card">
          <span>城市样本</span>
          <strong>${state.dashboard.market_heat.length}</strong>
          <p>当前已形成承接反馈的城市</p>
        </article>
      </div>

      <div class="hero-city-shell">
        <section class="hero-city-board">
          <div class="hero-section-head">
            <span>城市承接样本</span>
            <strong>机会分 / 可信核销</strong>
          </div>
          <div class="hero-city-list">
            ${cities
              .map((item, index) => `
                <article class="hero-city-row">
                  <div class="hero-city-rank">${String(index + 1).padStart(2, "0")}</div>
                  <div class="hero-city-main">
                    <div class="hero-city-meta">
                      <strong>${item.city}</strong>
                      <span>可信核销 ${formatInt(item.verified_scans)}</span>
                    </div>
                    <div class="hero-city-track">
                      <span style="width:${normalizeByRange(item.opportunity_score, cityValues, 26, 100)}%"></span>
                    </div>
                  </div>
                  <div class="hero-city-score">${formatScore(item.opportunity_score)}</div>
                </article>
              `)
              .join("")}
          </div>
        </section>

        <section class="hero-cluster-board">
          <div class="hero-section-head">
            <span>高机会簇</span>
            <strong>适合优先复盘</strong>
          </div>
          <div class="hero-cluster-list">
            ${topClusters
              .map((cluster) => `
                <article class="hero-cluster-card">
                  <div>
                    <strong>${cluster.cluster_name}</strong>
                    <p>${cluster.product_count} 个商品 · 均分 ${formatScore(cluster.average_opportunity_score)}</p>
                  </div>
                  <span class="hero-cluster-chip">${formatScore(cluster.average_opportunity_score)}</span>
                </article>
              `)
              .join("")}
          </div>
        </section>
      </div>
    </div>
  `;
}

function renderAtlasLegacyScatter() {
  const host = document.querySelector("#atlas-grid");
  const products = filteredProducts().length ? filteredProducts() : state.dashboard.products;
  const cards = [
    {
      title: "本体聚类视角",
      note: "看高机会商品在本体信号上的聚合。",
      xLabel: "参与率",
      yLabel: "机会分",
      groupKey: "product_core_cluster",
      xValue: (item) => item.participation_rate,
      yValue: (item) => item.trust_opportunity_score / 100,
    },
    {
      title: "产地聚类视角",
      note: "看产地信号能否带动跨区扩散。",
      xLabel: "跨区率",
      yLabel: "机会分",
      groupKey: "origin_cluster",
      xValue: (item) => item.cross_region_rate,
      yValue: (item) => item.trust_opportunity_score / 100,
    },
    {
      title: "呈现聚类视角",
      note: "看当前表达方式能否拉动激活与参与。",
      xLabel: "激活率",
      yLabel: "参与率",
      groupKey: "presentation_cluster",
      xValue: (item) => item.activation_rate,
      yValue: (item) => item.participation_rate,
    },
    {
      title: "反馈聚类视角",
      note: "看稳定性和低异常反馈是否形成集中带。",
      xLabel: "稳定性",
      yLabel: "安全度",
      groupKey: "feedback_cluster",
      xValue: (item) => item.stability_score / 100,
      yValue: (item) => 1 - item.abnormal_rate,
    },
  ];

  host.innerHTML = cards.map((config, index) => buildScatterCard(products, config, index)).join("");
  bindScatterTooltip();
}

function projectAtlasPoint(x, y, z, width, height) {
  const cosY = Math.cos(state.atlasRotationY);
  const sinY = Math.sin(state.atlasRotationY);
  const cosX = Math.cos(state.atlasRotationX);
  const sinX = Math.sin(state.atlasRotationX);

  const x1 = x * cosY - z * sinY;
  const z1 = x * sinY + z * cosY;
  const y1 = y * cosX - z1 * sinX;
  const z2 = y * sinX + z1 * cosX;
  const scale = 0.88 + (z2 + 1) * 0.18;

  return {
    x: width / 2 + x1 * 158 * scale,
    y: height * 0.58 - y1 * 156 * scale + z2 * 6,
    depth: z2,
    scale,
  };
}

function setupAtlasInteraction() {
  if (state.atlasInteractionBound) {
    return;
  }
  const svg = document.querySelector("#atlas-svg");
  svg.style.touchAction = "none";
  svg.addEventListener("pointerdown", (event) => {
    state.atlasDragging = true;
    state.atlasPointerX = event.clientX;
    state.atlasPointerY = event.clientY;
    svg.setPointerCapture?.(event.pointerId);
  });
  svg.addEventListener("pointermove", (event) => {
    if (!state.atlasDragging) {
      return;
    }
    const deltaX = event.clientX - state.atlasPointerX;
    const deltaY = event.clientY - state.atlasPointerY;
    state.atlasPointerX = event.clientX;
    state.atlasPointerY = event.clientY;
    state.atlasRotationY += deltaX * 0.008;
    state.atlasRotationX = Math.max(-1.05, Math.min(-0.08, state.atlasRotationX + deltaY * 0.004));
    renderAtlas();
  });
  const release = (event) => {
    state.atlasDragging = false;
    if (event?.pointerId !== undefined) {
      svg.releasePointerCapture?.(event.pointerId);
    }
  };
  svg.addEventListener("pointerup", release);
  svg.addEventListener("pointerleave", release);
  state.atlasInteractionBound = true;
}

function ensureAtlasAnimation() {
  if (state.atlasAnimationHandle) {
    return;
  }
  const animate = () => {
    if (!state.atlasDragging && state.dashboard) {
      state.atlasRotationY += 0.0026;
      renderAtlas();
    }
    state.atlasAnimationHandle = requestAnimationFrame(animate);
  };
  state.atlasAnimationHandle = requestAnimationFrame(animate);
}

function renderClusterFilters() {
  const host = document.querySelector("#cluster-pill-row");
  const filterHost = document.querySelector("#catalog-filter-row");
  const items = [
    { cluster_id: "all", cluster_name: "全部商品", product_count: state.dashboard.products.length },
    ...state.dashboard.clusters,
  ];
  const markup = items
    .map((item) => `
      <button class="cluster-pill${String(state.activeClusterId) === String(item.cluster_id) ? " is-active" : ""}" type="button" data-cluster-id="${item.cluster_id}">
        ${item.cluster_name} · ${item.product_count}
      </button>
    `)
    .join("");
  host.innerHTML = markup;
  filterHost.innerHTML = markup;

  document.querySelectorAll(".cluster-pill").forEach((button) => {
    button.addEventListener("click", async () => {
      await setActiveCluster(button.getAttribute("data-cluster-id"));
    });
  });
}

async function setActiveCluster(clusterId) {
  state.activeClusterId = clusterId;
  renderAtlas();
  renderTelemetry();
  renderClusterFilters();
  renderCatalog();
  const products = filteredProducts();
  if (!products.length) {
    return;
  }
  if (!products.some((item) => item.product_id === state.activeProductId)) {
    await selectProduct(products[0].product_id);
  } else {
    updateCatalogActive();
  }
}

function renderTelemetry() {
  const ribbon = document.querySelector("#telemetry-ribbon");
  const products = filteredProducts().length ? filteredProducts() : state.dashboard.products;
  const statuses = [...new Set(products.map((item) => item.positioning_status))];
  const statusCounts = statuses.map((status) => ({
    label: status,
    count: products.filter((item) => item.positioning_status === status).length,
  }));
  const clusters = state.dashboard.clusters.slice().sort((a, b) => b.average_opportunity_score - a.average_opportunity_score);
  ribbon.innerHTML = `
    <article class="telemetry-grid-card">
      <h4>定位结构分布</h4>
      <p>先看整个样本里，商品主要落在哪些经营状态。</p>
      <div class="telemetry-segments">
        ${statusCounts
          .map((item, index) => {
            const width = (item.count / products.length) * 100;
            return `
              <div class="telemetry-segment-row">
                <div class="telemetry-bar-row">
                  <span>${item.label}</span>
                  <div class="telemetry-segment-track">
                    <span class="telemetry-segment-part" style="width:${width}%;background:${paletteColor(index)};"></span>
                  </div>
                  <strong>${item.count}</strong>
                </div>
              </div>
            `;
          })
          .join("")}
      </div>
    </article>
    <article class="telemetry-grid-card">
      <h4>机会簇排行</h4>
      <p>看哪一类簇整体更容易跑出高机会商品。</p>
      <div class="telemetry-bars">
        ${clusters
          .slice(0, 4)
          .map((cluster, index) => `
            <div class="telemetry-bar-row">
              <span>${cluster.cluster_name}</span>
              <div class="track"><span class="track-fill" style="width:${cluster.average_opportunity_score}%"></span></div>
              <strong>${formatScore(cluster.average_opportunity_score)}</strong>
            </div>
          `)
          .join("")}
      </div>
    </article>
  `;

  const marketHost = document.querySelector("#telemetry-market");
  const topMarkets = state.dashboard.market_heat.slice(0, 4);
  const values = topMarkets.map((item) => item.opportunity_score);
  const activationValues = products.map((item) => item.activation_rate * 100);
  const participationValues = products.map((item) => item.participation_rate * 100);
  marketHost.innerHTML = `
    <article class="telemetry-grid-card">
      <h4>城市承接排行</h4>
      <p>这里直接看哪几个城市对整套系统最有承接力。</p>
      <div class="telemetry-bars">
        ${topMarkets
          .map((item, index) => `
            <div class="telemetry-bar-row">
              <span>${item.city}</span>
              <div class="track"><span class="track-fill" style="width:${normalizeByRange(item.opportunity_score, values, 24, 100)}%"></span></div>
              <strong>${formatScore(item.opportunity_score)}</strong>
            </div>
          `)
          .join("")}
      </div>
    </article>
    <article class="telemetry-grid-card">
      <h4>用户反馈双指标</h4>
      <p>把激活率和参与率分开看，避免一堆曲线都长得一样。</p>
      <div class="telemetry-micro-grid">
        <article class="market-pulse-card">
          <span class="tag">激活率分布</span>
          <strong>${formatScore(Math.max(...activationValues))}</strong>
          <div class="market-lane"><span class="market-lane-fill" style="width:100%"></span></div>
          <p>峰值商品激活率，越高说明用户更愿意主动验真。</p>
        </article>
        <article class="market-pulse-card">
          <span class="tag">参与率分布</span>
          <strong>${formatScore(Math.max(...participationValues))}</strong>
          <div class="market-lane"><span class="market-lane-fill" style="width:100%"></span></div>
          <p>峰值商品参与率，越高说明后续互动更容易形成。</p>
        </article>
      </div>
    </article>
  `;
}

function paletteColor(index) {
  const palette = ["#205643", "#bf6a3d", "#e4b14b", "#8c3838", "#4d6c97", "#6e5b93", "#3b8b7a"];
  return palette[index % palette.length];
}

function buildScatterCard(products, config, chartIndex) {
  const width = 380;
  const height = 210;
  const padding = 34;
  const plotWidth = width - padding * 2;
  const plotHeight = height - padding * 2;
  const groups = [...new Set(products.map((item) => item[config.groupKey]))];
  const colorMap = new Map(groups.map((group, index) => [group, paletteColor(index + chartIndex)]));
  const xValues = products.map((item) => config.xValue(item));
  const yValues = products.map((item) => config.yValue(item));
  const xMin = Math.min(...xValues);
  const xMax = Math.max(...xValues);
  const yMin = Math.min(...yValues);
  const yMax = Math.max(...yValues);

  const dots = products
    .map((item) => {
      const x = padding + ((config.xValue(item) - xMin) / Math.max(xMax - xMin, 0.0001)) * plotWidth;
      const y = height - padding - ((config.yValue(item) - yMin) / Math.max(yMax - yMin, 0.0001)) * plotHeight;
      const radius = state.activeClusterId === "all" || String(item.cluster_id) === String(state.activeClusterId) ? 6 : 4.5;
      const opacity = state.activeClusterId === "all" || String(item.cluster_id) === String(state.activeClusterId) ? 0.95 : 0.42;
      return `
        <circle
          class="scatter-point"
          cx="${x}"
          cy="${y}"
          r="${radius}"
          fill="${colorMap.get(item[config.groupKey])}"
          opacity="${opacity}"
          data-name="${item.product_name}"
          data-meta="${item[config.groupKey]} / 机会分 ${formatScore(item.trust_opportunity_score)}"
          data-extra="${config.xLabel} ${formatScore(config.xValue(item) * (config.xValue(item) <= 1.2 ? 100 : 1))} / ${config.yLabel} ${formatScore(config.yValue(item) * (config.yValue(item) <= 1.2 ? 100 : 1))}"
        ></circle>
      `;
    })
    .join("");

  const legend = groups
    .slice(0, 4)
    .map(
      (group) => `
        <span class="scatter-dot-tag">
          <span class="scatter-dot" style="background:${colorMap.get(group)};"></span>
          ${group}
        </span>
      `
    )
    .join("");

  return `
    <article class="scatter-card">
      <div class="scatter-card-head">
        <div>
          <strong>${config.title}</strong>
          <p>${config.note}</p>
        </div>
        <span class="tag">${config.xLabel} × ${config.yLabel}</span>
      </div>
      <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-label="${config.title}">
        <rect x="${padding}" y="${padding}" width="${plotWidth}" height="${plotHeight}" rx="18" fill="rgba(32,86,67,0.035)"></rect>
        <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" stroke="rgba(23,37,32,0.14)"></line>
        <line x1="${padding}" y1="${padding}" x2="${padding}" y2="${height - padding}" stroke="rgba(23,37,32,0.14)"></line>
        <text x="${padding}" y="${padding - 8}" class="atlas-axis">${config.yLabel}</text>
        <text x="${width - padding - 42}" y="${height - 10}" class="atlas-axis">${config.xLabel}</text>
        ${dots}
      </svg>
      <div class="scatter-legend">${legend}</div>
    </article>
  `;
}

function bindScatterTooltip() {
  const tooltip = getSharedTooltip();
  document.querySelectorAll(".scatter-point").forEach((point) => {
    point.addEventListener("pointerenter", (event) => {
      tooltip.hidden = false;
      tooltip.innerHTML = `
        <strong>${point.getAttribute("data-name")}</strong>
        <p>${point.getAttribute("data-meta")}</p>
        <p>${point.getAttribute("data-extra")}</p>
      `;
      positionHoverTooltip(tooltip, event, point);
    });
    point.addEventListener("pointermove", (event) => {
      positionHoverTooltip(tooltip, event, point);
    });
    point.addEventListener("pointerleave", () => {
      tooltip.hidden = true;
    });
  });
}

function getSharedTooltip() {
  const tooltip = document.querySelector("#scatter-tooltip");
  if (!tooltip) {
    return null;
  }
  if (tooltip.parentElement !== document.body) {
    document.body.appendChild(tooltip);
  }
  return tooltip;
}

function renderAtlasLegacyAtlasA() {
  const host = document.querySelector("#atlas-grid");
  const products = filteredProducts().length ? filteredProducts() : state.dashboard.products;
  const sceneConfig = {
    title: "三维信号场",
    note: "把激活、核销、机会三个维度压进同一空间，拖动查看谁在真正向上生长，谁只是停留在单一平面。",
    xLabel: "激活率",
    yLabel: "机会分",
    zLabel: "核销率",
    xValue: (item) => item.activation_rate,
    yValue: (item) => item.trust_opportunity_score / 100,
    zValue: (item) => item.participation_rate,
  };
  const projections = [
    {
      title: "产品-经营面",
      xLabel: "激活率",
      yLabel: "核销率",
      xValue: (item) => item.activation_rate,
      yValue: (item) => item.participation_rate,
      groupKey: "presentation_cluster",
    },
    {
      title: "产地-价值面",
      xLabel: "跨区流通",
      yLabel: "机会分",
      xValue: (item) => item.cross_region_rate,
      yValue: (item) => item.trust_opportunity_score / 100,
      groupKey: "origin_cluster",
    },
    {
      title: "反馈-稳定面",
      xLabel: "稳定度",
      yLabel: "异常抑制",
      xValue: (item) => item.stability_score / 100,
      yValue: (item) => 1 - item.abnormal_rate,
      groupKey: "feedback_cluster",
    },
  ];

  host.innerHTML = `
    <div class="atlas-composition">
      ${buildAtlasScene(products, sceneConfig)}
      <div class="atlas-projection-grid">
        ${projections.map((config, index) => buildProjectionCard(products, config, index)).join("")}
      </div>
    </div>
  `;
  bindAtlasInteraction();
  bindAtlasViewControls();
  bindHoverTooltip();
}

function bindAtlasInteraction() {
  const svg = document.querySelector("#atlas-svg");
  if (!svg || svg.dataset.bound === "1") {
    return;
  }
  const handleMove = (event) => {
    if (!state.atlasDragging) {
      return;
    }
    const deltaX = event.clientX - state.atlasPointerX;
    const deltaY = event.clientY - state.atlasPointerY;
    state.atlasPointerX = event.clientX;
    state.atlasPointerY = event.clientY;
    state.atlasRotationY += deltaX * 0.008;
    state.atlasRotationX = clamp(state.atlasRotationX + deltaY * 0.004, -1.16, 0.08);
    state.atlasViewMode = "custom";
    renderAtlas();
  };
  const release = (event) => {
    state.atlasDragging = false;
    window.removeEventListener("pointermove", handleMove);
    window.removeEventListener("pointerup", release);
    window.removeEventListener("pointercancel", release);
    if (event?.pointerId !== undefined) {
      svg.releasePointerCapture?.(event.pointerId);
    }
  };
  svg.style.touchAction = "none";
  svg.addEventListener("pointerdown", (event) => {
    state.atlasDragging = true;
    state.atlasPointerX = event.clientX;
    state.atlasPointerY = event.clientY;
    svg.setPointerCapture?.(event.pointerId);
    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", release);
    window.addEventListener("pointercancel", release);
  });
  svg.dataset.bound = "1";
}

function bindAtlasViewControls() {
  document.querySelectorAll(".atlas-view-chip").forEach((button) => {
    if (button.dataset.bound === "1") {
      return;
    }
    button.addEventListener("click", () => {
      const mode = button.getAttribute("data-view");
      setAtlasView(mode);
    });
    button.dataset.bound = "1";
  });
}

function setAtlasView(mode) {
  const presets = {
    angled: { x: -0.32, y: 0.56 },
    top: { x: -1.02, y: 0.18 },
    front: { x: -0.08, y: 0.04 },
  };
  const preset = presets[mode] || presets.angled;
  state.atlasRotationX = preset.x;
  state.atlasRotationY = preset.y;
  state.atlasViewMode = mode in presets ? mode : "custom";
  renderAtlas();
}

function buildAtlasSceneLegacyA(products, config) {
  const scopedProducts = filteredProducts().length ? filteredProducts() : products;
  const width = 700;
  const height = 500;
  const colorMap = buildClusterColorMap(scopedProducts);
  const xValues = scopedProducts.map((item) => config.xValue(item));
  const yValues = scopedProducts.map((item) => config.yValue(item));
  const zValues = scopedProducts.map((item) => config.zValue(item));
  const points = scopedProducts
    .map((item) => {
      const nx = normalizeSigned(config.xValue(item), xValues);
      const ny = normalizeSigned(config.yValue(item), yValues);
      const nz = normalizeSigned(config.zValue(item), zValues);
      const projected = projectAtlasPoint(nx, ny, nz, width, height);
      const base = projectAtlasPoint(nx, -1, nz, width, height);
      const active = state.activeClusterId === "all" || String(item.cluster_id) === String(state.activeClusterId);
      return {
        item,
        projected,
        base,
        active,
        color: colorMap.get(String(item.cluster_id)) || paletteColor(0),
      };
    })
    .sort((left, right) => left.projected.depth - right.projected.depth);

  const pointMarkup = points
    .map(({ item, projected, base, active, color }) => {
      const radius = clamp(2.4 + projected.scale * 4, 3.2, 7.2);
      const opacity = active ? clamp(0.58 + (projected.depth + 1) * 0.2, 0.74, 1) : 0.2;
      return `
        <g class="atlas-node">
          <line
            x1="${base.x}"
            y1="${base.y}"
            x2="${projected.x}"
            y2="${projected.y}"
            stroke="rgba(255,255,255,0.14)"
            stroke-width="1"
            stroke-dasharray="4 6"
            opacity="${active ? 0.34 : 0.12}"
          ></line>
          <circle cx="${projected.x}" cy="${projected.y}" r="${radius * 1.5}" fill="${color}" opacity="${opacity * 0.14}"></circle>
          <circle
            class="hover-point atlas-point"
            cx="${projected.x}"
            cy="${projected.y}"
            r="${radius}"
            fill="${color}"
            stroke="rgba(255,255,255,0.92)"
            stroke-width="${active ? 1.8 : 1.1}"
            opacity="${opacity}"
            data-name="${item.product_name}"
            data-meta="${item.cluster_name} / 机会分 ${formatScore(item.trust_opportunity_score)}"
            data-extra="激活 ${percent(item.activation_rate)} / 核销 ${percent(item.participation_rate)} / 稳定 ${formatScore(item.stability_score)}"
          ></circle>
        </g>
      `;
    })
    .join("");

  const legendRows = state.dashboard.clusters
    .map((cluster, index) => {
      const active = state.activeClusterId === "all" || String(cluster.cluster_id) === String(state.activeClusterId);
      return `
        <div class="atlas-legend-row${active ? " is-active" : ""}">
          <span class="atlas-legend-dot" style="background:${colorMap.get(String(cluster.cluster_id)) || paletteColor(index)};"></span>
          <div>
            <strong>${cluster.cluster_name}</strong>
            <p>${cluster.product_count} 个商品 · 均分 ${formatScore(cluster.average_opportunity_score)}</p>
          </div>
        </div>
      `;
    })
    .join("");

  const avgActivation =
    scopedProducts.reduce((sum, item) => sum + item.activation_rate, 0) / Math.max(scopedProducts.length, 1);
  const avgParticipation =
    scopedProducts.reduce((sum, item) => sum + item.participation_rate, 0) / Math.max(scopedProducts.length, 1);
  const avgOpportunity =
    scopedProducts.reduce((sum, item) => sum + item.trust_opportunity_score, 0) / Math.max(scopedProducts.length, 1);

  return `
    <div class="atlas-hero">
      <article class="atlas-scene-card">
        <div class="atlas-card-head">
          <div>
            <strong>${config.title}</strong>
            <p>${config.note}</p>
          </div>
          <span class="tag">拖动旋转</span>
        </div>
        <div class="atlas-scene-shell">
          <svg id="atlas-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" aria-label="${config.title}">
            ${buildAtlasPlanes(width, height)}
            ${buildAtlasAxes(width, height, config)}
            ${pointMarkup}
          </svg>
          <div class="atlas-overlay-chip atlas-overlay-chip-left">高激活</div>
          <div class="atlas-overlay-chip atlas-overlay-chip-right">高核销</div>
          <div class="atlas-overlay-chip atlas-overlay-chip-top">高机会</div>
        </div>
      </article>

      <aside class="atlas-meta-card">
        <div class="atlas-meta-top">
          <span class="panel-kicker">Cluster Layers</span>
          <h3>空间分层</h3>
          <p>颜色对应综合聚类，点越靠上代表机会越高，越靠近前景代表核销参与更强。</p>
        </div>
        <div class="atlas-legend-stack">${legendRows}</div>
        <div class="atlas-metric-stack">
          ${atlasMetricStrip("平均激活率", percent(avgActivation), avgActivation * 100)}
          ${atlasMetricStrip("平均核销率", percent(avgParticipation), avgParticipation * 100)}
          ${atlasMetricStrip("平均机会分", formatScore(avgOpportunity), avgOpportunity)}
        </div>
      </aside>
    </div>
  `;
}

function buildAtlasPlanes(width, height) {
  const ticks = [-1, -0.5, 0, 0.5, 1];
  const floorLines = ticks
    .flatMap((tick) => {
      const a = projectAtlasPoint(-1, -1, tick, width, height);
      const b = projectAtlasPoint(1, -1, tick, width, height);
      const c = projectAtlasPoint(tick, -1, -1, width, height);
      const d = projectAtlasPoint(tick, -1, 1, width, height);
      return [
        `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" class="atlas-grid-line"></line>`,
        `<line x1="${c.x}" y1="${c.y}" x2="${d.x}" y2="${d.y}" class="atlas-grid-line"></line>`,
      ];
    })
    .join("");
  const wallLines = ticks
    .flatMap((tick) => {
      const leftBottom = projectAtlasPoint(-1, -1, tick, width, height);
      const leftTop = projectAtlasPoint(-1, 1, tick, width, height);
      const backBottom = projectAtlasPoint(tick, -1, -1, width, height);
      const backTop = projectAtlasPoint(tick, 1, -1, width, height);
      return [
        `<line x1="${leftBottom.x}" y1="${leftBottom.y}" x2="${leftTop.x}" y2="${leftTop.y}" class="atlas-wall-line"></line>`,
        `<line x1="${backBottom.x}" y1="${backBottom.y}" x2="${backTop.x}" y2="${backTop.y}" class="atlas-wall-line"></line>`,
      ];
    })
    .join("");
  const floorPolygon = [
    projectAtlasPoint(-1, -1, -1, width, height),
    projectAtlasPoint(1, -1, -1, width, height),
    projectAtlasPoint(1, -1, 1, width, height),
    projectAtlasPoint(-1, -1, 1, width, height),
  ]
    .map((point) => `${point.x},${point.y}`)
    .join(" ");
  return `
    <polygon points="${floorPolygon}" fill="rgba(255,255,255,0.05)" stroke="rgba(255,255,255,0.05)" stroke-width="1"></polygon>
    ${floorLines}
    ${wallLines}
  `;
}

function buildAtlasAxes(width, height, config) {
  const origin = projectAtlasPoint(-1, -1, -1, width, height);
  const xAxis = projectAtlasPoint(1, -1, -1, width, height);
  const yAxis = projectAtlasPoint(-1, 1, -1, width, height);
  const zAxis = projectAtlasPoint(-1, -1, 1, width, height);
  return `
    <g class="atlas-axis-set">
      <line x1="${origin.x}" y1="${origin.y}" x2="${xAxis.x}" y2="${xAxis.y}" class="atlas-axis-line"></line>
      <line x1="${origin.x}" y1="${origin.y}" x2="${yAxis.x}" y2="${yAxis.y}" class="atlas-axis-line"></line>
      <line x1="${origin.x}" y1="${origin.y}" x2="${zAxis.x}" y2="${zAxis.y}" class="atlas-axis-line"></line>
      <text x="${xAxis.x + 12}" y="${xAxis.y + 4}" class="atlas-axis-text">${config.xLabel}</text>
      <text x="${yAxis.x - 18}" y="${yAxis.y - 12}" class="atlas-axis-text">${config.yLabel}</text>
      <text x="${zAxis.x - 18}" y="${zAxis.y + 8}" class="atlas-axis-text">${config.zLabel}</text>
    </g>
  `;
}

function buildProjectionCardLegacyA(products, config, chartIndex) {
  const width = 340;
  const height = 192;
  const padding = 28;
  const plotWidth = width - padding * 2;
  const plotHeight = height - padding * 2;
  const colorMap = buildClusterColorMap(products);
  const xValues = products.map((item) => config.xValue(item));
  const yValues = products.map((item) => config.yValue(item));
  const xMin = Math.min(...xValues);
  const xMax = Math.max(...xValues);
  const yMin = Math.min(...yValues);
  const yMax = Math.max(...yValues);
  const dots = products
    .map((item) => {
      const x = padding + ((config.xValue(item) - xMin) / Math.max(xMax - xMin, 0.0001)) * plotWidth;
      const y = height - padding - ((config.yValue(item) - yMin) / Math.max(yMax - yMin, 0.0001)) * plotHeight;
      const active = state.activeClusterId === "all" || String(item.cluster_id) === String(state.activeClusterId);
      return `
        <circle
          class="hover-point projection-point"
          cx="${x}"
          cy="${y}"
          r="${active ? 5.2 : 3.9}"
          fill="${colorMap.get(String(item.cluster_id)) || paletteColor(chartIndex)}"
          opacity="${active ? 0.95 : 0.24}"
          data-name="${item.product_name}"
          data-meta="${config.title} / ${item[config.groupKey]}"
          data-extra="${config.xLabel} ${formatMetricValue(config.xValue(item))} / ${config.yLabel} ${formatMetricValue(config.yValue(item))}"
        ></circle>
      `;
    })
    .join("");

  return `
    <article class="projection-card">
      <div class="projection-head">
        <strong>${config.title}</strong>
        <span class="tag">${config.xLabel} · ${config.yLabel}</span>
      </div>
      <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-label="${config.title}">
        <rect x="${padding}" y="${padding}" width="${plotWidth}" height="${plotHeight}" rx="20" fill="rgba(255,255,255,0.06)"></rect>
        <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" class="projection-axis"></line>
        <line x1="${padding}" y1="${padding}" x2="${padding}" y2="${height - padding}" class="projection-axis"></line>
        <line x1="${padding}" y1="${padding + plotHeight * 0.5}" x2="${width - padding}" y2="${padding + plotHeight * 0.5}" class="projection-guide"></line>
        <line x1="${padding + plotWidth * 0.5}" y1="${padding}" x2="${padding + plotWidth * 0.5}" y2="${height - padding}" class="projection-guide"></line>
        <text x="${padding}" y="${padding - 8}" class="atlas-axis">${config.yLabel}</text>
        <text x="${width - padding - 38}" y="${height - 8}" class="atlas-axis">${config.xLabel}</text>
        ${dots}
      </svg>
    </article>
  `;
}

function buildClusterColorMap(products) {
  const uniqueClusterIds = [...new Set(products.map((item) => String(item.cluster_id)))];
  const atlasPalette = ["#8fb7a3", "#d7b26d", "#7ea6d8", "#d08b73", "#8c9d7a", "#9c84c6", "#6cb8b2"];
  return new Map(uniqueClusterIds.map((clusterId, index) => [clusterId, atlasPalette[index % atlasPalette.length]]));
}

function normalizeSigned(value, values) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (Math.abs(max - min) < 0.0001) {
    return 0;
  }
  return ((value - min) / (max - min)) * 2 - 1;
}

function formatMetricValue(value) {
  return value <= 1.2 ? percent(value) : formatScore(value);
}

function atlasMetricStrip(label, value, width) {
  return `
    <div class="atlas-metric-strip">
      <span>${label}</span>
      <strong>${value}</strong>
      <div class="atlas-metric-track"><span style="width:${clamp(width, 8, 100)}%"></span></div>
    </div>
  `;
}

function bindHoverTooltipLegacy() {
  const tooltip = document.querySelector("#scatter-tooltip");
  document.querySelectorAll(".hover-point").forEach((point) => {
    point.addEventListener("pointerenter", (event) => {
      tooltip.hidden = false;
      tooltip.innerHTML = `
        <strong>${point.getAttribute("data-name")}</strong>
        <p>${point.getAttribute("data-meta")}</p>
        <p>${point.getAttribute("data-extra")}</p>
      `;
      positionHoverTooltip(tooltip, event);
    });
    point.addEventListener("pointermove", (event) => {
      positionHoverTooltip(tooltip, event);
    });
    point.addEventListener("pointerleave", () => {
      tooltip.hidden = true;
    });
  });
}

function positionHoverTooltipLegacyA(tooltip, event) {
  const offsetX = 4;
  const offsetY = 4;
  const maxLeft = window.innerWidth - tooltip.offsetWidth - 12;
  const maxTop = window.innerHeight - tooltip.offsetHeight - 12;
  let left = event.clientX + offsetX;
  let top = event.clientY + offsetY;
  if (left > maxLeft) {
    left = event.clientX - tooltip.offsetWidth - 8;
  }
  if (top > maxTop) {
    top = event.clientY - tooltip.offsetHeight - 8;
  }
  left = clamp(left, 12, maxLeft);
  top = clamp(top, 12, maxTop);
  tooltip.style.left = `${left}px`;
  tooltip.style.top = `${top}px`;
}

function buildAtlasSceneLegacyB(products, config) {
  const scopedProducts = filteredProducts().length ? filteredProducts() : products;
  const width = 700;
  const height = 500;
  const colorMap = buildClusterColorMap(scopedProducts);
  const xValues = scopedProducts.map((item) => config.xValue(item));
  const yValues = scopedProducts.map((item) => config.yValue(item));
  const zValues = scopedProducts.map((item) => config.zValue(item));
  const points = scopedProducts
    .map((item) => {
      const nx = normalizeSigned(config.xValue(item), xValues);
      const ny = normalizeSigned(config.yValue(item), yValues);
      const nz = normalizeSigned(config.zValue(item), zValues);
      const projected = projectAtlasPoint(nx, ny, nz, width, height);
      const base = projectAtlasPoint(nx, -1, nz, width, height);
      const active = state.activeClusterId === "all" || String(item.cluster_id) === String(state.activeClusterId);
      return {
        item,
        projected,
        base,
        active,
        color: colorMap.get(String(item.cluster_id)) || paletteColor(0),
      };
    })
    .sort((left, right) => left.projected.depth - right.projected.depth);

  const pointMarkup = points
    .map(({ item, projected, base, active, color }) => {
      const radius = clamp(2.4 + projected.scale * 4, 3.2, 7.2);
      const opacity = active ? clamp(0.58 + (projected.depth + 1) * 0.2, 0.74, 1) : 0.2;
      return `
        <g class="atlas-node">
          <line
            x1="${base.x}"
            y1="${base.y}"
            x2="${projected.x}"
            y2="${projected.y}"
            stroke="rgba(255,255,255,0.12)"
            stroke-width="1"
            stroke-dasharray="4 6"
            opacity="${active ? 0.34 : 0.12}"
          ></line>
          <circle cx="${projected.x}" cy="${projected.y}" r="${radius * 1.5}" fill="${color}" opacity="${opacity * 0.14}"></circle>
          <circle
            class="hover-point atlas-point"
            cx="${projected.x}"
            cy="${projected.y}"
            r="${radius}"
            fill="${color}"
            stroke="rgba(255,255,255,0.92)"
            stroke-width="${active ? 1.6 : 1}"
            opacity="${opacity}"
            data-name="${item.product_name}"
            data-meta="${item.cluster_name} / 机会分 ${formatScore(item.trust_opportunity_score)}"
            data-extra="激活 ${percent(item.activation_rate)} / 核销 ${percent(item.participation_rate)} / 稳定 ${formatScore(item.stability_score)}"
          ></circle>
        </g>
      `;
    })
    .join("");

  const legendRows = state.dashboard.clusters
    .map((cluster, index) => {
      const active = state.activeClusterId === "all" || String(cluster.cluster_id) === String(state.activeClusterId);
      return `
        <div class="atlas-legend-row${active ? " is-active" : ""}">
          <span class="atlas-legend-dot" style="background:${colorMap.get(String(cluster.cluster_id)) || paletteColor(index)};"></span>
          <div>
            <strong>${cluster.cluster_name}</strong>
            <p>${cluster.product_count} 个商品 · 均分 ${formatScore(cluster.average_opportunity_score)}</p>
          </div>
        </div>
      `;
    })
    .join("");

  const avgActivation =
    scopedProducts.reduce((sum, item) => sum + item.activation_rate, 0) / Math.max(scopedProducts.length, 1);
  const avgParticipation =
    scopedProducts.reduce((sum, item) => sum + item.participation_rate, 0) / Math.max(scopedProducts.length, 1);
  const avgOpportunity =
    scopedProducts.reduce((sum, item) => sum + item.trust_opportunity_score, 0) / Math.max(scopedProducts.length, 1);

  return `
    <div class="atlas-hero">
      <article class="atlas-scene-card">
        <div class="atlas-card-head">
          <div>
            <strong>${config.title}</strong>
            <p>${config.note}</p>
          </div>
          <div class="atlas-view-row">
            ${buildAtlasViewChip("angled", "斜视")}
            ${buildAtlasViewChip("top", "俯视")}
            ${buildAtlasViewChip("front", "正视")}
          </div>
        </div>
        <div class="atlas-scene-shell">
          <svg id="atlas-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" aria-label="${config.title}">
            ${buildAtlasPlanes(width, height)}
            ${buildAtlasAxes(width, height, config)}
            ${pointMarkup}
          </svg>
          <div class="atlas-overlay-chip atlas-overlay-chip-left">高激活</div>
          <div class="atlas-overlay-chip atlas-overlay-chip-right">高核销</div>
          <div class="atlas-overlay-chip atlas-overlay-chip-top">高机会</div>
        </div>
      </article>

      <aside class="atlas-meta-card">
        <div class="atlas-meta-top">
          <span class="panel-kicker">Cluster Layers</span>
          <h3>空间分层</h3>
          <p>颜色对应综合聚类，点越高代表机会越强，越靠前代表核销参与更强。可以直接切到俯视看平面分布。</p>
        </div>
        <div class="atlas-legend-stack">${legendRows}</div>
        <div class="atlas-metric-stack">
          ${atlasMetricStrip("平均激活率", percent(avgActivation), avgActivation * 100)}
          ${atlasMetricStrip("平均核销率", percent(avgParticipation), avgParticipation * 100)}
          ${atlasMetricStrip("平均机会分", formatScore(avgOpportunity), avgOpportunity)}
        </div>
      </aside>
    </div>
  `;
}

function buildAtlasViewChip(mode, label) {
  return `<button class="atlas-view-chip${state.atlasViewMode === mode ? " is-active" : ""}" type="button" data-view="${mode}">${label}</button>`;
}

function buildProjectionCardLegacyB(products, config, chartIndex) {
  const width = 340;
  const height = 192;
  const padding = 28;
  const plotWidth = width - padding * 2;
  const plotHeight = height - padding * 2;
  const colorMap = buildClusterColorMap(products);
  const xValues = products.map((item) => config.xValue(item));
  const yValues = products.map((item) => config.yValue(item));
  const xMin = Math.min(...xValues);
  const xMax = Math.max(...xValues);
  const yMin = Math.min(...yValues);
  const yMax = Math.max(...yValues);
  const dots = products
    .map((item) => {
      const x = padding + ((config.xValue(item) - xMin) / Math.max(xMax - xMin, 0.0001)) * plotWidth;
      const y = height - padding - ((config.yValue(item) - yMin) / Math.max(yMax - yMin, 0.0001)) * plotHeight;
      const active = state.activeClusterId === "all" || String(item.cluster_id) === String(state.activeClusterId);
      const color = colorMap.get(String(item.cluster_id)) || paletteColor(chartIndex);
      return `
        <g>
          <circle
            class="hover-point projection-point"
            cx="${x}"
            cy="${y}"
            r="${active ? 4.8 : 3.5}"
            fill="${color}"
            opacity="${active ? 0.95 : 0.24}"
            data-name="${item.product_name}"
            data-meta="${config.title} / ${item[config.groupKey]}"
            data-extra="${config.xLabel} ${formatMetricValue(config.xValue(item))} / ${config.yLabel} ${formatMetricValue(config.yValue(item))}"
          ></circle>
        </g>
      `;
    })
    .join("");

  return `
    <article class="projection-card">
      <div class="projection-head">
        <strong>${config.title}</strong>
        <span class="tag">${config.xLabel} · ${config.yLabel}</span>
      </div>
      <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" aria-label="${config.title}">
        <rect x="${padding}" y="${padding}" width="${plotWidth}" height="${plotHeight}" rx="20" fill="rgba(255,255,255,0.06)"></rect>
        <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" class="projection-axis"></line>
        <line x1="${padding}" y1="${padding}" x2="${padding}" y2="${height - padding}" class="projection-axis"></line>
        <line x1="${padding}" y1="${padding + plotHeight * 0.5}" x2="${width - padding}" y2="${padding + plotHeight * 0.5}" class="projection-guide"></line>
        <line x1="${padding + plotWidth * 0.5}" y1="${padding}" x2="${padding + plotWidth * 0.5}" y2="${height - padding}" class="projection-guide"></line>
        <text x="${padding}" y="${padding - 8}" class="atlas-axis">${config.yLabel}</text>
        <text x="${width - padding - 38}" y="${height - 8}" class="atlas-axis">${config.xLabel}</text>
        ${dots}
      </svg>
    </article>
  `;
}

function shortProjectionName(name) {
  return name.length > 8 ? `${name.slice(0, 8)}…` : name;
}

function escapeSvgText(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderCatalog() {
  const products = filteredProducts();
  const host = document.querySelector("#catalog-list");
  document.querySelector("#catalog-caption").textContent = `当前展示 ${products.length} 个商品，点击任意商品进入分析舞台。`;
  host.innerHTML = products
    .map((product) => `
      <button class="catalog-card${product.product_id === state.activeProductId ? " is-active" : ""}" type="button" data-product-id="${product.product_id}">
        <div class="catalog-top">
          <div>
            <div class="chip-row">
              <span class="tag">${product.cluster_name}</span>
              <span class="tag">${product.recommendation_direction}</span>
            </div>
            <h3>${product.product_name}</h3>
            <p>${product.family_name} / ${product.variant_name} / ${product.channel}</p>
          </div>
          <strong class="catalog-score">${formatScore(product.trust_opportunity_score)}</strong>
        </div>
        <svg class="catalog-spark" viewBox="0 0 280 60" preserveAspectRatio="none">
          ${buildCatalogSpark(product)}
        </svg>
        <div class="chip-row">
          <span class="tag">${product.product_core_cluster}</span>
          <span class="tag">${product.origin_cluster}</span>
          <span class="tag">${product.stability_label}</span>
        </div>
      </button>
    `)
    .join("");

  host.querySelectorAll(".catalog-card").forEach((button) => {
    button.addEventListener("click", async () => {
      await selectProduct(button.getAttribute("data-product-id"));
    });
  });
}

function buildCatalogSpark(product) {
  const values = [
    product.activation_rate * 100,
    product.participation_rate * 100,
    product.cross_region_rate * 100,
    (1 - product.abnormal_rate) * 100,
  ];
  const points = values
    .map((value, index) => `${20 + index * 80},${52 - value * 0.38}`)
    .join(" ");
  const columns = values
    .map((value, index) => {
      const height = Math.max(8, value * 0.44);
      const x = 10 + index * 80;
      return `<rect x="${x}" y="${56 - height}" width="22" height="${height}" rx="8" fill="rgba(191,106,61,${0.2 + index * 0.12})"></rect>`;
    })
    .join("");
  return `
    ${columns}
    <polyline points="${points}" fill="none" stroke="rgba(32,86,67,0.94)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></polyline>
    ${values
      .map((value, index) => `<circle cx="${20 + index * 80}" cy="${52 - value * 0.38}" r="4" fill="white" stroke="rgba(32,86,67,0.94)" stroke-width="2"></circle>`)
      .join("")}
  `;
}

function updateCatalogActive() {
  document.querySelectorAll(".catalog-card").forEach((card) => {
    card.classList.toggle("is-active", card.getAttribute("data-product-id") === state.activeProductId);
  });
}

async function selectProduct(productId) {
  state.activeProductId = productId;
  updateCatalogActive();
  renderLoadingState();
  const [report, llmReport] = await Promise.all([getReport(productId), getLlmReport(productId)]);
  renderStage(report, llmReport);
  renderIntel(report, llmReport);
}

function renderLoadingState() {
  document.querySelector("#stage-root").innerHTML = `
    <div class="stage-shell">
      <div class="skeleton"></div>
      <div class="skeleton" style="height:240px;"></div>
      <div class="skeleton" style="height:420px;"></div>
    </div>
  `;
  document.querySelector("#intel-root").innerHTML = `
    <div class="intel-shell">
      <div class="skeleton" style="height:220px;"></div>
      <div class="skeleton" style="height:160px;"></div>
      <div class="skeleton" style="height:280px;"></div>
    </div>
  `;
}

async function getReport(productId) {
  if (!state.reportCache.has(productId)) {
    state.reportCache.set(productId, await fetchJson(`/api/analytics/demo/report/${productId}`));
  }
  return state.reportCache.get(productId);
}

async function getLlmReport(productId) {
  if (!state.llmCache.has(productId)) {
    state.llmCache.set(productId, await fetchJson(`/api/analytics/demo/llm-report/${productId}`));
  }
  return state.llmCache.get(productId);
}

function renderStage(report, llmReport) {
  const product = report.product;
  const positioning = report.positioning_summary;
  const root = document.querySelector("#stage-root");
  root.innerHTML = `
    <div class="stage-shell">
      <section class="stage-hero">
        <div>
          <div class="chip-row">
            <span class="tag">${product.cluster_name}</span>
            <span class="tag">${product.positioning_status}</span>
            <span class="tag">${product.recommendation_direction}</span>
            <span class="tag">${product.stability_label}</span>
          </div>
          <h3 class="stage-title">${product.product_name}</h3>
          <p class="stage-copy">${product.family_name} / ${product.variant_name} / ${product.category} / ${product.region_name} / ${product.channel}</p>
          <p class="stage-copy">${positioning.summary}</p>
          <div class="chip-row">
            <span class="tag">${product.product_core_cluster}</span>
            <span class="tag">${product.origin_cluster}</span>
            <span class="tag">${product.presentation_cluster}</span>
            <span class="tag">${product.feedback_cluster}</span>
          </div>
        </div>
        <div class="score-dial">
          ${buildScoreDial(product.trust_opportunity_score)}
        </div>
      </section>

      <div class="stage-tab-row">
        ${Object.entries(tabLabels)
          .map(
            ([key, label]) => `<button class="tab-chip${state.activeTab === key ? " is-active" : ""}" type="button" data-tab="${key}">${label}</button>`
          )
          .join("")}
      </div>

      <div class="stage-body">
        ${renderStageTab(report, llmReport)}
      </div>
    </div>
  `;

  root.querySelectorAll(".tab-chip").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeTab = button.getAttribute("data-tab");
      renderStage(report, llmReport);
    });
  });
}

function renderStageTab(report, llmReport) {
  if (state.activeTab === "markets") {
    return renderMarketsTab(report);
  }
  if (state.activeTab === "actions") {
    return renderActionsTab(report, llmReport);
  }
  return renderStructureTab(report);
}

function renderStructureTab(report) {
  const product = report.product;
  const positioning = report.positioning_summary;
  return `
    <div class="stage-grid">
      <article class="card-block">
        <div class="stage-head">
          <div>
            <p class="panel-kicker">Structure</p>
            <h2>价值结构视图</h2>
          </div>
          <p class="stage-tab-note">把商品本体、当前包装表达和市场反馈拆开看。</p>
        </div>
        <div class="structure-rings">
          <div class="structure-orbital">${buildStructureOrbital(positioning, product)}</div>
        </div>
      </article>

      <article class="card-block">
        <div class="stage-head">
          <div>
            <p class="panel-kicker">Metrics</p>
            <h2>经营反馈</h2>
          </div>
          <p class="stage-tab-note">这里看的是消费者是否愿意主动验证、参与和跨区承接。</p>
        </div>
        <div class="metric-ledger">
          ${detailStrip("激活率", percent(product.activation_rate), product.activation_rate * 100)}
          ${detailStrip("参与率", percent(product.participation_rate), product.participation_rate * 100)}
          ${detailStrip("跨区率", percent(product.cross_region_rate), product.cross_region_rate * 100)}
          ${detailStrip("异常率", percent(product.abnormal_rate), product.abnormal_rate * 100)}
        </div>
        <div class="metric-ledger-visual">
          ${buildVerticalBars(
            [
              ["本体", positioning.intrinsic_value_score],
              ["呈现", positioning.presented_value_score],
              ["验证", positioning.market_validation_score],
              ["适配", positioning.fit_score],
              ["稳定", positioning.stability_score],
            ],
            "价值张力柱状图"
          )}
        </div>
      </article>
    </div>
  `;
}

function renderMarketsTab(report) {
  const values = report.market_insights.map((item) => item.opportunity_score);
  return `
    <div class="stage-grid">
      <article class="card-block">
        <div class="stage-head">
          <div>
            <p class="panel-kicker">Markets</p>
            <h2>城市跑道</h2>
          </div>
          <p class="stage-tab-note">不是简单“高低分”，而是看同一商品内部哪些城市更该先打。</p>
        </div>
        <div class="market-scene-chart">
          ${buildVerticalBars(
            report.market_insights.slice(0, 6).map((item) => [item.city, item.opportunity_score]),
            "城市机会柱状图"
          )}
        </div>
        <div class="city-runway">
          ${report.market_insights
            .map((item) => {
              const tier = tierMeta(item.market_tier);
              const width = normalizeByRange(item.opportunity_score, values, 22, 100);
              return `
                <div class="runway-row">
                  <span class="tier-badge ${tier.className}">${item.city}</span>
                  <div class="track"><span class="track-fill" style="width:${width}%"></span></div>
                  <strong>${formatScore(item.opportunity_score)}</strong>
                </div>
              `;
            })
            .join("")}
        </div>
        <p class="runway-note stage-copy">${report.market_insights[0]?.observation ?? ""}</p>
      </article>

      <article class="card-block">
        <div class="stage-head">
          <div>
            <p class="panel-kicker">Market Notes</p>
            <h2>承接解释</h2>
          </div>
          <p class="stage-tab-note">每个城市都给出对应解释，不再是单一结论。</p>
        </div>
        <div class="city-stack">
          ${report.market_insights
            .slice(0, 6)
            .map((item) => {
              const tier = tierMeta(item.market_tier);
              return `
                <article class="city-card">
                  <div class="city-card-head">
                    <div>
                      <span>排名 #${item.rank}</span>
                      <strong>${item.city}</strong>
                    </div>
                    <span class="tier-badge ${tier.className}">${tier.label}</span>
                  </div>
                  <p class="card-copy">${item.observation}</p>
                  <div class="chip-row">
                    <span class="tag">机会分 ${formatScore(item.opportunity_score)}</span>
                    <span class="tag">核销量 ${formatInt(item.verified_scans)}</span>
                  </div>
                </article>
              `;
            })
            .join("")}
        </div>
      </article>
    </div>
  `;
}

function renderActionsTab(report, llmReport) {
  return `
    <div class="stage-split">
      <article class="card-block">
        <div class="stage-head">
          <div>
            <p class="panel-kicker">Action Stack</p>
            <h2>${report.strategy_report.title}</h2>
          </div>
          <p class="stage-tab-note">偏规则化的动作建议，适合直接拿来讲经营动作。</p>
        </div>
        <p class="stage-copy">${report.strategy_report.diagnosis}</p>
        <p class="stage-copy">${report.strategy_report.opportunity}</p>
        <p class="stage-copy">${report.strategy_report.caution}</p>
        <ul class="list-reset">
          ${report.strategy_report.actions.map((item) => `<li>${item}</li>`).join("")}
        </ul>
      </article>

      <article class="card-block">
        <div class="stage-head">
          <div>
            <p class="panel-kicker">Scenario Engine</p>
            <h2>情景推演</h2>
          </div>
          <p class="stage-tab-note">看包装、价格表达变化之后，定位可能向哪里移动。</p>
        </div>
        <div class="scenario-stack">
          ${report.scenarios
            .map((item) => `
              <article class="scenario-card">
                <span class="tag">${item.scenario_name}</span>
                <strong>${item.projected_positioning_status}</strong>
                <p class="card-copy">${item.direction}</p>
                <p class="card-copy">${item.reason}</p>
                <div class="chip-row">
                  ${item.changed_fields.map((field) => `<span class="tag">${field}</span>`).join("")}
                </div>
                <div class="scenario-bar"><span class="scenario-bar-fill" style="width:${item.projected_presented_value_score}%"></span></div>
              </article>
            `)
            .join("")}
        </div>
      </article>

      <article class="card-block">
        <div class="stage-head">
          <div>
            <p class="panel-kicker">Teacher Set</p>
            <h2>可学习样本</h2>
          </div>
          <p class="stage-tab-note">既看同品类，也看同层级、同场景的参考对象。</p>
        </div>
        <div class="teacher-stack">
          ${report.market_learning
            .map((item) => `
              <article class="teacher-card">
                <div class="teacher-head">
                  <span class="tag">${item.city} / ${item.learning_type}</span>
                  <strong>${formatScore(item.match_score)}</strong>
                </div>
                <strong>${item.target_product_name}</strong>
                <p class="card-copy">${item.reason}</p>
                <p class="card-copy">${item.lesson}</p>
                <div class="chip-row">
                  <span class="tag">城市优势 ${formatScore(item.city_advantage_score)}</span>
                  <span class="tag">场景相似 ${formatScore(item.scene_similarity_score)}</span>
                </div>
              </article>
            `)
            .join("")}
        </div>
      </article>

      <article class="card-block">
        <div class="stage-head">
          <div>
            <p class="panel-kicker">LLM Notes</p>
            <h2>AI 补充动作</h2>
          </div>
          <p class="stage-tab-note">这一部分是结合当前商品、市场承接和样本线索整理出来的具体建议。</p>
        </div>
        <ul class="list-reset">
          ${llmReport.analysis.strategy_actions.map((item) => `<li>${item}</li>`).join("")}
        </ul>
      </article>
    </div>
  `;
}

function detailStrip(label, value, width) {
  return `
    <article class="metric-strip">
      <span>${label}</span>
      <strong>${value}</strong>
      <div class="track"><span class="track-fill" style="width:${Math.max(6, width)}%"></span></div>
    </article>
  `;
}

function buildScoreDial(score) {
  const circumference = 2 * Math.PI * 70;
  const offset = circumference * (1 - score / 100);
  return `
    <svg viewBox="0 0 180 180" aria-hidden="true">
      <circle cx="90" cy="90" r="70" fill="none" stroke="rgba(255,255,255,0.12)" stroke-width="14"></circle>
      <circle cx="90" cy="90" r="70" fill="none" stroke="rgba(228,177,75,0.92)" stroke-width="14" stroke-linecap="round"
        stroke-dasharray="${circumference}" stroke-dashoffset="${offset}" transform="rotate(-90 90 90)"></circle>
      <circle cx="90" cy="90" r="44" fill="rgba(255,255,255,0.06)"></circle>
      <text x="90" y="74" text-anchor="middle" fill="rgba(246,240,231,0.72)" font-size="12" font-weight="700">机会分</text>
      <text x="90" y="106" text-anchor="middle" dominant-baseline="middle" fill="rgba(246,240,231,1)" font-size="42" font-weight="800">${formatScore(score)}</text>
    </svg>
  `;
}

function buildStructureOrbital(positioning, product) {
  const metrics = [
    { label: "本体", value: positioning.intrinsic_value_score, display: formatScore(positioning.intrinsic_value_score), color: "#205643" },
    { label: "呈现", value: positioning.presented_value_score, display: formatScore(positioning.presented_value_score), color: "#bf6a3d" },
    { label: "验证", value: positioning.market_validation_score, display: formatScore(positioning.market_validation_score), color: "#e4b14b" },
    { label: "适配", value: positioning.fit_score, display: formatScore(positioning.fit_score), color: "#205643" },
    { label: "稳定", value: positioning.stability_score, display: formatScore(positioning.stability_score), color: "#8c3838" },
    { label: "参与", value: product.participation_rate * 100, display: percent(product.participation_rate), color: "#15392d" },
  ];
  const cx = 210;
  const cy = 182;
  const radius = 118;
  const rings = [0.25, 0.5, 0.75, 1];

  const polygons = rings
    .map((ring) => {
      const points = metrics
        .map((_, index) => {
          const angle = -Math.PI / 2 + (Math.PI * 2 * index) / metrics.length;
          return `${cx + Math.cos(angle) * radius * ring},${cy + Math.sin(angle) * radius * ring}`;
        })
        .join(" ");
      return `<polygon points="${points}" fill="none" stroke="rgba(23,37,32,0.1)" stroke-width="1"></polygon>`;
    })
    .join("");

  const axes = metrics
    .map((item, index) => {
      const angle = -Math.PI / 2 + (Math.PI * 2 * index) / metrics.length;
      const x = cx + Math.cos(angle) * radius;
      const y = cy + Math.sin(angle) * radius;
      const labelRadius = radius + 40;
      const lx = cx + Math.cos(angle) * labelRadius;
      const ly = cy + Math.sin(angle) * labelRadius;
      const anchor =
        Math.cos(angle) > 0.34 ? "start" : Math.cos(angle) < -0.34 ? "end" : "middle";
      const valueY = ly + (Math.sin(angle) < -0.25 ? 24 : 22);
      return `
        <line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="rgba(23,37,32,0.12)" stroke-width="1"></line>
        <text x="${lx}" y="${ly}" text-anchor="${anchor}" style="fill:rgba(95,111,101,0.92);font-size:12px;font-weight:700;">${item.label}</text>
        <text x="${lx}" y="${valueY}" text-anchor="${anchor}" style="fill:${item.color};font-size:18px;font-weight:800;">${item.display}</text>
      `;
    })
    .join("");

  const pointData = metrics.map((item, index) => {
    const angle = -Math.PI / 2 + (Math.PI * 2 * index) / metrics.length;
    return {
      x: cx + Math.cos(angle) * radius * (item.value / 100),
      y: cy + Math.sin(angle) * radius * (item.value / 100),
      color: item.color,
    };
  });

  return `
    <svg viewBox="0 0 420 360" aria-hidden="true">
      ${polygons}
      ${axes}
      <polygon points="${pointData.map((item) => `${item.x},${item.y}`).join(" ")}" fill="rgba(32,86,67,0.18)" stroke="rgba(32,86,67,0.88)" stroke-width="2.5"></polygon>
      ${pointData.map((item) => `<circle cx="${item.x}" cy="${item.y}" r="5" fill="${item.color}" stroke="white" stroke-width="2"></circle>`).join("")}
      <circle cx="${cx}" cy="${cy}" r="5" fill="rgba(23,37,32,0.9)"></circle>
    </svg>
  `;
}

function buildVerticalBars(entries, title) {
  const width = 420;
  const height = 220;
  const baseY = 170;
  const values = entries.map((entry) => Number(entry[1]));
  const max = Math.max(...values, 1);
  const barWidth = 36;
  const gap = 28;
  const totalWidth = entries.length * barWidth + (entries.length - 1) * gap;
  const startX = (width - totalWidth) / 2;

  const bars = entries
    .map(([label, value], index) => {
      const barHeight = Math.max(16, (value / max) * 112);
      const x = startX + index * (barWidth + gap);
      const delay = (index * 0.08).toFixed(2);
      return `
        <g>
          <rect x="${x}" y="${baseY - barHeight}" width="${barWidth}" height="${barHeight}" rx="12" fill="rgba(191,106,61,0.88)" class="chart-rise" style="animation-delay:${delay}s;"></rect>
          <rect x="${x + 7}" y="${baseY - barHeight + 10}" width="10" height="${Math.max(10, barHeight - 18)}" rx="5" fill="rgba(255,255,255,0.22)" class="chart-rise" style="animation-delay:${delay}s;"></rect>
          <text x="${x + barWidth / 2}" y="${baseY + 20}" text-anchor="middle" class="atlas-axis">${label}</text>
          <text x="${x + barWidth / 2}" y="${baseY - barHeight - 10}" text-anchor="middle" class="atlas-axis">${formatScore(value)}</text>
        </g>
      `;
    })
    .join("");

  return `
    <svg viewBox="0 0 ${width} ${height}" aria-label="${title}">
      <text x="0" y="18" class="atlas-axis">${title}</text>
      <line x1="18" y1="${baseY}" x2="${width - 18}" y2="${baseY}" stroke="rgba(23,37,32,0.12)"></line>
      <line x1="18" y1="36" x2="18" y2="${baseY}" stroke="rgba(23,37,32,0.08)"></line>
      ${bars}
    </svg>
  `;
}

function renderIntel(report, llmReport) {
  const product = report.product;
  const llm = llmReport.analysis;
  const root = document.querySelector("#intel-root");
  root.innerHTML = `
    <div class="intel-shell">
      <section class="intel-summary">
        <div class="intel-head">
          <div>
            <p class="panel-kicker">AI Summary</p>
            <h2>经营判读</h2>
          </div>
          <span class="tag">${llmReport.model_name}</span>
        </div>
        <div class="chip-row">
          <span class="tag">${product.positioning_status}</span>
          <span class="tag">${product.recommendation_direction}</span>
        </div>
        <h3>${llm.core_judgement}</h3>
        <p class="intel-copy">${llm.executive_summary}</p>
      </section>

      <section class="intel-card">
        <h4>直接动作</h4>
        <ul class="action-list">
          ${llm.strategy_actions.map((item) => `<li>${item}</li>`).join("")}
        </ul>
      </section>

      <section class="intel-card">
        <h4>定价与渠道提醒</h4>
        <p class="intel-copy"><strong>价格与包装：</strong>${llm.pricing_packaging_advice}</p>
        <p class="intel-copy"><strong>渠道：</strong>${llm.channel_advice}</p>
        <p class="intel-copy"><strong>产地与信任：</strong>${llm.origin_trust_advice}</p>
        <p class="intel-copy"><strong>风险：</strong>${llm.risk_warning}</p>
      </section>
    </div>
  `;
}

function renderAtlas() {
  const host = document.querySelector("#atlas-grid");
  const products = filteredProducts().length ? filteredProducts() : state.dashboard.products;
  const sceneConfig = {
    title: "三维信号场",
    note: "把激活、核销、机会三个维度压进同一空间，拖动或切换视角查看商品在信任价值中的真实位置。",
    xLabel: "激活率",
    yLabel: "机会分",
    zLabel: "核销率",
    xValue: (item) => item.activation_rate,
    yValue: (item) => item.trust_opportunity_score / 100,
    zValue: (item) => item.participation_rate,
  };
  const projections = [
    {
      title: "产品-经营面",
      xLabel: "激活率",
      yLabel: "核销率",
      xValue: (item) => item.activation_rate,
      yValue: (item) => item.participation_rate,
      groupKey: "presentation_cluster",
    },
    {
      title: "产地-价值面",
      xLabel: "跨区流通",
      yLabel: "机会分",
      xValue: (item) => item.cross_region_rate,
      yValue: (item) => item.trust_opportunity_score / 100,
      groupKey: "origin_cluster",
    },
    {
      title: "反馈-稳定面",
      xLabel: "稳定度",
      yLabel: "异常抑制",
      xValue: (item) => item.stability_score / 100,
      yValue: (item) => 1 - item.abnormal_rate,
      groupKey: "feedback_cluster",
    },
  ];

  host.innerHTML = `
    <div class="atlas-composition">
      ${buildAtlasScene(products, sceneConfig)}
      <div class="atlas-projection-grid">
        ${projections.map((config, index) => buildProjectionCard(products, config, index)).join("")}
      </div>
    </div>
  `;
  bindAtlasInteraction();
  bindAtlasViewControls();
  bindHoverTooltip();
}

function buildAtlasScene(products, config) {
  const scopedProducts = filteredProducts().length ? filteredProducts() : products;
  const width = 700;
  const height = 500;
  const colorMap = buildClusterColorMap(scopedProducts);
  const xValues = scopedProducts.map((item) => config.xValue(item));
  const yValues = scopedProducts.map((item) => config.yValue(item));
  const zValues = scopedProducts.map((item) => config.zValue(item));
  const points = scopedProducts
    .map((item) => {
      const nx = normalizeSigned(config.xValue(item), xValues);
      const ny = normalizeSigned(config.yValue(item), yValues);
      const nz = normalizeSigned(config.zValue(item), zValues);
      const projected = projectAtlasPoint(nx, ny, nz, width, height);
      const base = projectAtlasPoint(nx, -1, nz, width, height);
      return {
        item,
        projected,
        base,
        color: colorMap.get(String(item.cluster_id)) || paletteColor(0),
      };
    })
    .sort((left, right) => left.projected.depth - right.projected.depth);

  const pointMarkup = points
    .map(({ item, projected, base, color }) => {
      const radius = clamp(2.4 + projected.scale * 4, 3.2, 7.2);
      const opacity = clamp(0.58 + (projected.depth + 1) * 0.2, 0.74, 1);
      return `
        <g class="atlas-node">
          <line
            x1="${base.x}"
            y1="${base.y}"
            x2="${projected.x}"
            y2="${projected.y}"
            stroke="rgba(255,255,255,0.12)"
            stroke-width="1"
            stroke-dasharray="4 6"
            opacity="0.24"
          ></line>
          <circle cx="${projected.x}" cy="${projected.y}" r="${radius * 1.5}" fill="${color}" opacity="${opacity * 0.14}"></circle>
          <circle
            class="hover-point atlas-point"
            cx="${projected.x}"
            cy="${projected.y}"
            r="${radius}"
            fill="${color}"
            stroke="rgba(255,255,255,0.92)"
            stroke-width="1.4"
            opacity="${opacity}"
            data-name="${item.product_name}"
            data-meta="${item.cluster_name} / 机会分 ${formatScore(item.trust_opportunity_score)}"
            data-extra="激活 ${percent(item.activation_rate)} / 核销 ${percent(item.participation_rate)} / 稳定 ${formatScore(item.stability_score)}"
          ></circle>
        </g>
      `;
    })
    .join("");

  const clusterGroups = [...new Map(scopedProducts.map((item) => [String(item.cluster_id), item])).values()];
  const legendRows = clusterGroups
    .map((sample, index) => {
      const clusterProducts = scopedProducts.filter((item) => String(item.cluster_id) === String(sample.cluster_id));
      const clusterScore =
        clusterProducts.reduce((sum, item) => sum + item.trust_opportunity_score, 0) / Math.max(clusterProducts.length, 1);
      return `
        <div class="atlas-legend-row is-active">
          <span class="atlas-legend-dot" style="background:${colorMap.get(String(sample.cluster_id)) || paletteColor(index)};"></span>
          <div>
            <strong>${sample.cluster_name}</strong>
            <p>${clusterProducts.length} 个商品 · 均分 ${formatScore(clusterScore)}</p>
          </div>
        </div>
      `;
    })
    .join("");

  const avgActivation =
    scopedProducts.reduce((sum, item) => sum + item.activation_rate, 0) / Math.max(scopedProducts.length, 1);
  const avgParticipation =
    scopedProducts.reduce((sum, item) => sum + item.participation_rate, 0) / Math.max(scopedProducts.length, 1);
  const avgOpportunity =
    scopedProducts.reduce((sum, item) => sum + item.trust_opportunity_score, 0) / Math.max(scopedProducts.length, 1);

  return `
    <div class="atlas-hero">
      <article class="atlas-scene-card">
        <div class="atlas-card-head">
          <div>
            <strong>${config.title}</strong>
            <p>${config.note}</p>
          </div>
          <div class="atlas-view-row">
            ${buildAtlasViewChip("angled", "斜视")}
            ${buildAtlasViewChip("top", "俯视")}
            ${buildAtlasViewChip("front", "正视")}
          </div>
        </div>
        <div class="atlas-scene-shell">
          <svg id="atlas-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" aria-label="${config.title}">
            ${buildAtlasPlanes(width, height)}
            ${buildAtlasAxes(width, height, config)}
            ${pointMarkup}
          </svg>
          <div class="atlas-overlay-chip atlas-overlay-chip-left">高激活</div>
          <div class="atlas-overlay-chip atlas-overlay-chip-right">高核销</div>
          <div class="atlas-overlay-chip atlas-overlay-chip-top">高机会</div>
        </div>
      </article>

      <aside class="atlas-meta-card">
        <div class="atlas-meta-top">
          <span class="panel-kicker">Cluster Layers</span>
          <h3>空间分层</h3>
          <p>这里的平均值和簇摘要完全跟随当前筛选结果变化，不再沿用全量数据。</p>
        </div>
        <div class="atlas-legend-stack">${legendRows}</div>
        <div class="atlas-metric-stack">
          ${atlasMetricStrip("平均激活率", percent(avgActivation), avgActivation * 100)}
          ${atlasMetricStrip("平均核销率", percent(avgParticipation), avgParticipation * 100)}
          ${atlasMetricStrip("平均机会分", formatScore(avgOpportunity), avgOpportunity)}
        </div>
      </aside>
    </div>
  `;
}

function buildAtlasViewChip(mode, label) {
  return `<button class="atlas-view-chip${state.atlasViewMode === mode ? " is-active" : ""}" type="button" data-view="${mode}">${label}</button>`;
}

function buildProjectionCard(products, config, chartIndex) {
  const width = 340;
  const height = 192;
  const padding = 28;
  const plotWidth = width - padding * 2;
  const plotHeight = height - padding * 2;
  const colorMap = buildClusterColorMap(products);
  const xValues = products.map((item) => config.xValue(item));
  const yValues = products.map((item) => config.yValue(item));
  const xMin = Math.min(...xValues);
  const xMax = Math.max(...xValues);
  const yMin = Math.min(...yValues);
  const yMax = Math.max(...yValues);

  const dots = products
    .map((item) => {
      const x = padding + ((config.xValue(item) - xMin) / Math.max(xMax - xMin, 0.0001)) * plotWidth;
      const y = height - padding - ((config.yValue(item) - yMin) / Math.max(yMax - yMin, 0.0001)) * plotHeight;
      const active = state.activeClusterId === "all" || String(item.cluster_id) === String(state.activeClusterId);
      return `
        <circle
          class="hover-point projection-point"
          cx="${x}"
          cy="${y}"
          r="${active ? 4.8 : 3.5}"
          fill="${colorMap.get(String(item.cluster_id)) || paletteColor(chartIndex)}"
          opacity="${active ? 0.95 : 0.24}"
          data-name="${item.product_name}"
          data-meta="${config.title} / ${item[config.groupKey]}"
          data-extra="${config.xLabel} ${formatMetricValue(config.xValue(item))} / ${config.yLabel} ${formatMetricValue(config.yValue(item))}"
        ></circle>
      `;
    })
    .join("");

  return `
    <article class="projection-card">
      <div class="projection-head">
        <strong>${config.title}</strong>
        <span class="tag">${config.xLabel} · ${config.yLabel}</span>
      </div>
      <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" aria-label="${config.title}">
        <rect x="${padding}" y="${padding}" width="${plotWidth}" height="${plotHeight}" rx="20" fill="rgba(255,255,255,0.06)"></rect>
        <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" class="projection-axis"></line>
        <line x1="${padding}" y1="${padding}" x2="${padding}" y2="${height - padding}" class="projection-axis"></line>
        <line x1="${padding}" y1="${padding + plotHeight * 0.5}" x2="${width - padding}" y2="${padding + plotHeight * 0.5}" class="projection-guide"></line>
        <line x1="${padding + plotWidth * 0.5}" y1="${padding}" x2="${padding + plotWidth * 0.5}" y2="${height - padding}" class="projection-guide"></line>
        <text x="${padding}" y="${padding - 8}" class="atlas-axis">${config.yLabel}</text>
        <text x="${width - padding - 38}" y="${height - 8}" class="atlas-axis">${config.xLabel}</text>
        ${dots}
      </svg>
    </article>
  `;
}

function bindHoverTooltip() {
  const tooltip = getSharedTooltip();
  document.querySelectorAll(".hover-point").forEach((point) => {
    point.addEventListener("pointerenter", (event) => {
      tooltip.hidden = false;
      tooltip.innerHTML = `
        <strong>${point.getAttribute("data-name")}</strong>
        <p>${point.getAttribute("data-meta")}</p>
        <p>${point.getAttribute("data-extra")}</p>
      `;
      positionHoverTooltip(tooltip, event, point);
    });
    point.addEventListener("pointermove", (event) => {
      positionHoverTooltip(tooltip, event, point);
    });
    point.addEventListener("pointerleave", () => {
      tooltip.hidden = true;
    });
  });
}

function positionHoverTooltipLegacyB(tooltip, event) {
  const offset = 8;
  const maxLeft = window.innerWidth - tooltip.offsetWidth - 12;
  const maxTop = window.innerHeight - tooltip.offsetHeight - 12;
  const left = clamp(event.clientX + offset, 12, maxLeft);
  const top = clamp(event.clientY - tooltip.offsetHeight - offset, 12, maxTop);
  tooltip.style.left = `${left}px`;
  tooltip.style.top = `${top}px`;
}

loadDashboard().catch((error) => {
  console.error(error);
  document.querySelector("#stage-root").innerHTML = `
    <div class="stage-empty">
      <p class="eyebrow">Error</p>
      <h3>页面加载失败</h3>
      <p>请确认后端接口已经启动，然后刷新重试。</p>
    </div>
  `;
  document.querySelector("#intel-root").innerHTML = `
    <div class="intel-empty">
      <p class="eyebrow">Error</p>
      <h3>智能侧栏加载失败</h3>
      <p>后端接口不可用时，这里不会显示内容。</p>
    </div>
  `;
});

function positionHoverTooltip(tooltip, event, anchorElement = event?.currentTarget) {
  const offsetX = 8;
  const offsetY = 8;
  const maxLeft = Math.max(12, window.innerWidth - tooltip.offsetWidth - 12);
  const maxTop = Math.max(12, window.innerHeight - tooltip.offsetHeight - 12);
  let left = event.clientX + offsetX;
  let top = event.clientY + offsetY;

  if (anchorElement?.getBoundingClientRect) {
    const rect = anchorElement.getBoundingClientRect();
    left = rect.right + 8;
    top = rect.top + rect.height / 2 - tooltip.offsetHeight / 2;
  }

  if (left > maxLeft) {
    if (anchorElement?.getBoundingClientRect) {
      const rect = anchorElement.getBoundingClientRect();
      left = rect.left - tooltip.offsetWidth - 8;
    } else {
      left = event.clientX - tooltip.offsetWidth - offsetX;
    }
  }
  if (top > maxTop) {
    top = maxTop;
  }
  left = clamp(left, 12, maxLeft);
  top = clamp(top, 12, maxTop);
  tooltip.style.left = `${left}px`;
  tooltip.style.top = `${top}px`;
}
