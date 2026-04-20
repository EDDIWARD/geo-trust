const state = {
  summary: null,
  events: [],
  mapData: null,
  trends: null,
  regions: [],
  map: null,
  layers: [],
  chart: null,
};

function requestJson(path) {
  return fetch(path).then(async (response) => {
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload?.detail || `请求失败: ${response.status}`);
    }
    return payload;
  });
}

async function bootstrap() {
  const [summary, eventsResp, mapResp, trendsResp, regionsResp] = await Promise.all([
    requestJson('/api/dashboard/summary'),
    requestJson('/api/dashboard/events?limit=36'),
    requestJson('/api/dashboard/map-data'),
    requestJson('/api/dashboard/trends?days=7'),
    requestJson('/api/dashboard/regions'),
  ]);

  state.summary = summary;
  state.events = eventsResp.events;
  state.mapData = mapResp;
  state.trends = trendsResp;
  state.regions = regionsResp.regions;

  renderHero();
  renderMetrics();
  renderMap();
  renderEvents();
  renderTrendChart();
  renderRegionTable();
}

function formatInt(value) {
  return new Intl.NumberFormat('zh-CN').format(Number(value || 0));
}

function riskMeta(level, anomalyCount = 0) {
  if (level === 'high' || anomalyCount >= 8) {
    return { label: '高风险', className: 'high', color: '#d88484' };
  }
  if (level === 'medium' || anomalyCount >= 3) {
    return { label: '预警', className: 'warn', color: '#e29a6f' };
  }
  return { label: '稳定', className: 'safe', color: '#67c3a0' };
}

function renderHero() {
  const heroMeta = document.getElementById('hero-meta');
  heroMeta.innerHTML = `
    <span class="tag">登记商品 ${formatInt(state.summary.total_products)}</span>
    <span class="tag">总扫码 ${formatInt(state.summary.total_scans)}</span>
    <span class="tag">异常事件 ${formatInt(state.summary.today_anomalies)}</span>
  `;

  document.getElementById('system-status').textContent = state.summary.today_anomalies > 0 ? '监测中' : '运行稳定';
  document.getElementById('system-note').textContent = state.summary.today_anomalies > 0
    ? `今日已识别 ${formatInt(state.summary.today_anomalies)} 次异常扫码，需要人工复核。`
    : '当前未出现明显异常峰值，适合切到 AI 经营分析页继续看商品结构。';

  const topEvent = state.events.find((item) => item.risk_level === 'high') || state.events[0];
  const spotlight = document.getElementById('spotlight-card');
  spotlight.innerHTML = topEvent
    ? `
      <span>当前焦点</span>
      <strong>${topEvent.product_code || '系统事件'}</strong>
      <p>${topEvent.message}</p>
      <div class="hero-meta">
        <span class="risk-pill ${riskMeta(topEvent.risk_level).className}">${riskMeta(topEvent.risk_level).label}</span>
        <span class="tag">${formatTime(topEvent.event_time)}</span>
      </div>
    `
    : `
      <span>当前焦点</span>
      <strong>暂无高风险事件</strong>
      <p>可以先看区域结构和 AI 分析入口。</p>
    `;

  document.getElementById('map-note').textContent = `${state.mapData.anomaly_lines.length} 条异常连线 / ${state.mapData.scan_points.length} 个扫码点`;
}

function metricItem(label, value, note, ratio) {
  return `
    <article class="metric-card">
      <span>${label}</span>
      <strong>${value}</strong>
      <p>${note}</p>
      <div class="metric-track"><span style="width:${Math.max(12, Math.min(100, ratio))}%"></span></div>
    </article>
  `;
}

function renderMetrics() {
  const metrics = [
    metricItem('今日登记', formatInt(state.summary.today_registered), '来自登记接口的新增记录。', state.summary.today_registered * 8),
    metricItem('今日扫码', formatInt(state.summary.today_scans), '消费者实际触发的扫码行为。', state.summary.today_scans * 4),
    metricItem('今日拦截', formatInt(state.summary.today_rejected), '越界或设备风险导致的登记拒绝。', state.summary.today_rejected * 18),
    metricItem('今日异常', formatInt(state.summary.today_anomalies), '速度异常触发的风险扫描。', state.summary.today_anomalies * 22),
    metricItem('累计商品', formatInt(state.summary.total_products), '当前数据库中的演示商品总数。', state.summary.total_products / 4),
    metricItem('累计扫码', formatInt(state.summary.total_scans), '用于管理端趋势和风险分析。', state.summary.total_scans / 18),
  ];
  document.getElementById('metric-grid').innerHTML = metrics.join('');
}

function renderMap() {
  if (!state.map) {
    state.map = L.map('dashboard-map', { zoomControl: true }).setView([30.6, 114.3], 5);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18,
      attribution: '© OpenStreetMap',
    }).addTo(state.map);
  }

  state.layers.forEach((layer) => state.map.removeLayer(layer));
  state.layers = [];

  const registerLayer = L.layerGroup();
  state.mapData.register_points.slice(0, 120).forEach((point) => {
    const marker = L.circleMarker([point.lat, point.lng], {
      radius: 5,
      color: '#d5b061',
      weight: 1,
      fillColor: '#d5b061',
      fillOpacity: 0.76,
    }).bindPopup(`<strong>${point.product_code}</strong><br>登记点<br>${point.region_name || '-'}`);
    registerLayer.addLayer(marker);
  });
  registerLayer.addTo(state.map);

  const scanLayer = L.layerGroup();
  state.mapData.scan_points.slice(0, 120).forEach((point) => {
    const marker = L.circleMarker([point.lat, point.lng], {
      radius: 4,
      color: '#4b9f84',
      weight: 1,
      fillColor: '#4b9f84',
      fillOpacity: 0.72,
    }).bindPopup(`<strong>${point.product_code}</strong><br>扫码点<br>${formatTime(point.scan_time)}`);
    scanLayer.addLayer(marker);
  });
  scanLayer.addTo(state.map);

  const anomalyLayer = L.layerGroup();
  state.mapData.anomaly_lines.forEach((line) => {
    const meta = riskMeta(line.risk_level);
    const polyline = L.polyline([
      [line.from_lat, line.from_lng],
      [line.to_lat, line.to_lng],
    ], {
      color: meta.color,
      weight: line.risk_level === 'high' ? 3 : 2,
      opacity: 0.82,
      dashArray: line.risk_level === 'high' ? '' : '8 6',
    }).bindPopup(`<strong>${line.product_code}</strong><br>${line.reason}<br>${line.speed ? `${line.speed} km/h` : ''}`);
    anomalyLayer.addLayer(polyline);
  });
  anomalyLayer.addTo(state.map);

  state.layers.push(registerLayer, scanLayer, anomalyLayer);

  const allLatLngs = [];
  state.mapData.register_points.slice(0, 60).forEach((point) => allLatLngs.push([point.lat, point.lng]));
  state.mapData.scan_points.slice(0, 60).forEach((point) => allLatLngs.push([point.lat, point.lng]));
  if (allLatLngs.length) {
    state.map.fitBounds(allLatLngs, { padding: [30, 30] });
  }
}

function renderEvents() {
  document.getElementById('event-count-tag').textContent = `${state.events.length} 条`;
  document.getElementById('event-list').innerHTML = state.events.map((event) => {
    const meta = riskMeta(event.risk_level);
    return `
      <article class="event-item">
        <div class="event-top">
          <strong>${event.product_code || '系统事件'}</strong>
          <span class="risk-pill ${meta.className}">${meta.label}</span>
        </div>
        <p>${event.message}</p>
        <div class="event-meta">
          <span class="tag">${formatTime(event.event_time)}</span>
          <span class="tag">${event.event_type}</span>
          ${event.speed != null ? `<span class="tag">${Math.round(event.speed)} km/h</span>` : ''}
        </div>
      </article>
    `;
  }).join('');
}

function renderTrendChart() {
  const chartDom = document.getElementById('trend-chart');
  if (!state.chart) {
    state.chart = echarts.init(chartDom);
    window.addEventListener('resize', () => state.chart?.resize());
  }

  state.chart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { top: 0, textStyle: { color: '#9eb1aa' } },
    grid: { left: 48, right: 24, top: 52, bottom: 30 },
    xAxis: {
      type: 'category',
      data: state.trends.dates,
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.12)' } },
      axisLabel: { color: '#9eb1aa' },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } },
      axisLabel: { color: '#9eb1aa' },
    },
    series: [
      {
        name: '登记',
        type: 'bar',
        data: state.trends.registrations,
        itemStyle: { color: '#d5b061', borderRadius: [8, 8, 0, 0] },
      },
      {
        name: '扫码',
        type: 'line',
        smooth: true,
        data: state.trends.scans,
        lineStyle: { color: '#4b9f84', width: 3 },
        itemStyle: { color: '#4b9f84' },
      },
      {
        name: '异常',
        type: 'line',
        smooth: true,
        data: state.trends.alerts,
        lineStyle: { color: '#d88484', width: 2.5 },
        itemStyle: { color: '#d88484' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(216,132,132,0.26)' },
            { offset: 1, color: 'rgba(216,132,132,0.02)' },
          ]),
        },
      },
    ],
  });
}

function renderRegionTable() {
  document.getElementById('region-count-tag').textContent = `${state.regions.length} 个产区`;
  const maxAnomalies = Math.max(...state.regions.map((item) => item.anomalies), 1);
  document.getElementById('region-table-body').innerHTML = state.regions.map((region) => {
    const meta = riskMeta('none', region.anomalies);
    const barWidth = (region.anomalies / maxAnomalies) * 100;
    return `
      <tr>
        <td>${region.name}</td>
        <td>${region.type}</td>
        <td>${formatInt(region.todayCount)}</td>
        <td>${formatInt(region.totalScans)}</td>
        <td>
          ${formatInt(region.anomalies)}
          <div class="region-bar"><span style="width:${Math.max(region.anomalies ? 12 : 0, barWidth)}%;background:${meta.color};"></span></div>
        </td>
        <td><span class="risk-pill ${meta.className}">${meta.label}</span></td>
      </tr>
    `;
  }).join('');
}

function formatTime(value) {
  if (!value) {
    return '--';
  }
  return value.replace('T', ' ').slice(0, 16);
}

bootstrap().catch((error) => {
  console.error(error);
  document.getElementById('system-status').textContent = '加载失败';
  document.getElementById('system-note').textContent = error.message || '后端接口暂不可用';
  document.getElementById('spotlight-card').innerHTML = '<span>错误</span><strong>管理端加载失败</strong><p>请确认后端已启动并完成 demo 数据建库。</p>';
});
