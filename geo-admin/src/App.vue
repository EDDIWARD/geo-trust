<template>
  <div class="app-shell">
    <header class="top-navbar">
      <div class="logo">『时空印记』Geo-Trust 溯源管理后台</div>

      <nav class="nav-links">
        <button :class="{ active: currentTab === 'map' }" @click="currentTab = 'map'">
          <span class="icon">🌐</span> 态势感知大屏
        </button>
        <button :class="{ active: currentTab === 'data' }" @click="currentTab = 'data'">
          <span class="icon">📊</span> 数据分析中心
        </button>
        <button class="ai-nav-btn" @click="handleAIReportNavigation">
          <span class="icon">✨</span> 生成 AI 深度分析报告
        </button>
      </nav>

      <div class="sys-time">
        系统状态：<span class="pulse-green">●</span> 实时API监听中
      </div>
    </header>

    <main class="content-area">
      <div v-if="currentTab === 'map'" class="tab-content dashboard">
        <div class="stats-header">
          <div class="stat-card">
            <span class="stat-label">{{ selectedProvince ? selectedProvince : '全国' }}登记</span>
            <span class="num">{{ activeStats.today_registered }}</span>
          </div>
          <div class="stat-card">今日扫码 <span class="num blue">{{ activeStats.today_scans }}</span></div>
          <div class="stat-card">今日拦截 <span class="num red">{{ activeStats.today_rejected }}</span></div>
          <div class="stat-card">今日异常 <span class="num orange">{{ activeStats.today_anomalies }}</span></div>
          <div class="stat-card">累计商品 <span class="num grey">{{ activeStats.total_products }}</span></div>
          <div class="stat-card">累计扫码 <span class="num blue-alt">{{ activeStats.total_scans }}</span></div>
        </div>

        <div class="main-layout">
          <div class="side-column left-charts">
            <div class="sub-panel flex-item">
              <div class="panel-title">
                {{ selectedProvince ? `${selectedProvince} 核心特产名录` : '拦截风险趋势' }}
              </div>
              <div class="chart-box">
                <TrendChart v-if="!selectedProvince" :chartData="trendData" />

                <div v-else class="specialty-scroll-window">
                  <div class="specialty-item" v-for="(item, index) in provinceSpecialties" :key="index">
                    <div class="specialty-left">
                      <div class="s-name">✨ {{ item.name }}</div>
                      <div class="s-tag">{{ item.type }}</div>
                    </div>
                    <div class="specialty-right">登记数：{{ item.registerCount }}</div>
                  </div>

                  <div v-if="provinceSpecialties.length === 0" class="no-data">
                    暂无该省份特产记录
                  </div>
                </div>
              </div>
            </div>

            <div class="sub-panel flex-item">
              <div class="panel-title">
                {{ selectedProvince ? `${selectedProvince} 登记产品类型分布` : '产品登记类型分布' }}
              </div>
              <div class="chart-box">
                <ProductPieChart :chartData="activePieData" />
              </div>
            </div>
          </div>

          <div class="map-section">
            <div class="panel-header-row">
              <div class="panel-title">
                {{ selectedProvince ? `${selectedProvince} 市区划分地图` : '时空安全监测 (动态流转链路)' }}
              </div>
              <div class="legend-group">
                <span class="legend"><i style="background:#52c41a"></i>产地</span>
                <span class="legend"><i style="background:#fadb14"></i>扫码地</span>
                <span class="legend"><i class="line" style="background:#1e90ff"></i>正常</span>
                <span class="legend"><i class="line" style="background:#ff4d4f"></i>克隆</span>
              </div>
            </div>

            <div class="map-tip">
              全国地图按“登记产品种类数”渐变着色，颜色越深表示该省登记的产品种类越多。
            </div>

            <div class="map-container">
              <TraceMap
                :points="activeMapData.points"
                :lines="activeMapData.lines"
                :mapData="provinceMapData"
                @province-clicked="onProvinceClicked"
                @back-to-china="onBackToChina"
              />
            </div>
          </div>

          <div class="side-column right-logs">
            <div class="sub-panel log-full-panel">
              <div class="panel-header-row no-border">
                <div class="panel-title">
                  {{ selectedProvince ? `${selectedProvince} 产地流转日志` : '实时防御与流转日志' }}
                </div>
              </div>

              <div class="log-marquee-container">
                <transition-group name="list" tag="div" class="log-list-wrapper">
                  <div v-for="log in activeLogs" :key="log.event_id"
                       class="log-row" @click="showDetail(log)">
                    <div class="log-top">
                      <span class="time">{{ formatTime(log.event_time) }}</span>
                      <span :class="['tag', getLogClass(log.isClone)]">
                        {{ log.isClone ? '克隆拦截' : '正常' }}
                      </span>
                    </div>

                    <div class="log-mid">
                      <span class="prod-info">📦 {{ log.product_name }} [{{ log.product_code }}]</span>
                    </div>

                    <div class="log-bottom">
                      <span class="loc">📍 {{ log.scanName }}</span>
                      <span class="msg" :class="{ 'red-text': log.isClone }">{{ log.message }}</span>
                    </div>
                  </div>
                </transition-group>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="tab-content analysis-wrapper">
        <DataAnalysis
          :stats="globalStats"
          :trendData="trendData"
          :regionRawData="regionData"
          @requestAI="handleAIReportNavigation"
        />
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, computed } from 'vue';
import TraceMap from './components/TraceMapBridge.vue';
import TrendChart from './components/TrendChart.vue';
import ProductPieChart from './components/ProductPieChart.vue';
import DataAnalysis from './components/DataAnalysis.vue';

/**
 * 你后端以后建议统一返回这种结构：
 * {
 *   code: 0,
 *   message: "ok",
 *   data: ...
 * }
 *
 * 现在前端会先用模拟数据；
 * 如果你以后配置了 VITE_API_BASE_URL，前端就会优先尝试请求后端。
 */
const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

async function requestJson(path, options = {}) {
  if (!API_BASE) return null;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 8000);

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method: options.method || 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {})
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: controller.signal
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return await response.json();
  } finally {
    clearTimeout(timeoutId);
  }
}

function unwrapApiPayload(payload) {
  if (payload === null || payload === undefined) return null;
  if (typeof payload !== 'object') return payload;

  if (payload.code === 0 || payload.success === true || payload.status === 200) {
    return payload.data ?? payload.result ?? null;
  }

  if (Object.prototype.hasOwnProperty.call(payload, 'data')) {
    return payload.data;
  }

  return payload;
}

async function tryFetch(requestFn, fallbackFactory, transform = (data) => data) {
  if (!API_BASE) {
    return fallbackFactory();
  }

  try {
    const raw = await requestFn();
    const data = unwrapApiPayload(raw);
    const result = transform(data);

    if (result !== null && result !== undefined) {
      return result;
    }
  } catch (error) {
    console.warn('接口请求失败，自动切换到模拟数据：', error);
  }

  return fallbackFactory();
}

const api = {
  getSummary: () => requestJson('/api/dashboard/summary'),
  getTrend: (days = 7) => requestJson(`/api/dashboard/trend?days=${days}`),
  getPie: () => requestJson('/api/dashboard/pie'),
  getProvinceMap: () => requestJson('/api/map/provinces'),
  getMapData: () => requestJson('/api/dashboard/map-data'),
  getRealtimeLogs: (limit = 80, province = '') => {
    const query = new URLSearchParams();
    query.set('limit', String(limit));
    if (province) query.set('province', province);
    return requestJson(`/api/logs/realtime?${query.toString()}`);
  },
  getProvinceSpecialties: (province) =>
    requestJson(`/api/province/specialties?province=${encodeURIComponent(province)}`),
  generateAIReport: (payload) =>
    requestJson('/api/ai/report/generate', {method: 'POST',body: payload})
};

const currentTab = ref('map');
const selectedLog = ref(null);
const selectedProvince = ref(null);

const globalStats = ref({
  today_registered: 0,
  today_scans: 0,
  today_rejected: 0,
  today_anomalies: 0,
  total_products: 0,
  total_scans: 0
});

const provinceStatsMap = ref({});
const provinceSpecialtyCache = ref({});
const provinceMapDataRemote = ref([]);
const provinceSpecialtiesRemote = ref({});
const anomalyLinesRemote = ref([]);

const logs = ref([]);
const trendData = ref({ dates: [], registrations: [], scans: [], alerts: [] });
const globalPieData = ref([]);
const regionData = ref([]);

const scanLocations = [
  { name: '北京', coords: [116.4, 39.9] },
  { name: '上海', coords: [121.4, 31.2] },
  { name: '广州', coords: [113.2, 23.1] },
  { name: '成都', coords: [104.06, 30.67] },
  { name: '杭州', coords: [120.15, 30.28] },
  { name: '南京', coords: [118.78, 32.04] }
];

const provincePool = [
  '北京', '天津', '河北', '山西', '内蒙古', '辽宁', '吉林', '黑龙江',
  '上海', '江苏', '浙江', '安徽', '福建', '江西', '山东', '河南',
  '湖北', '湖南', '广东', '广西', '海南', '重庆', '四川', '贵州',
  '云南', '西藏', '陕西', '甘肃', '青海', '宁夏', '新疆', '香港',
  '澳门', '台湾'
];

const provinceCenterMap = {
  '北京': [116.4074, 39.9042],
  '天津': [117.2000, 39.1333],
  '河北': [114.5025, 38.0455],
  '山西': [112.5492, 37.8570],
  '内蒙古': [111.6708, 40.8183],
  '辽宁': [123.4315, 41.8057],
  '吉林': [125.3245, 43.8868],
  '黑龙江': [126.6424, 45.7560],
  '上海': [121.4737, 31.2304],
  '江苏': [118.7674, 32.0415],
  '浙江': [120.1551, 30.2741],
  '安徽': [117.2830, 31.8612],
  '福建': [119.2965, 26.0745],
  '江西': [115.8922, 28.6765],
  '山东': [117.0009, 36.6758],
  '河南': [113.6654, 34.7570],
  '湖北': [114.3054, 30.5931],
  '湖南': [112.9389, 28.2282],
  '广东': [113.2644, 23.1291],
  '广西': [108.3669, 22.8170],
  '海南': [110.3312, 20.0311],
  '重庆': [106.5516, 29.5630],
  '四川': [104.0665, 30.5723],
  '贵州': [106.7135, 26.5783],
  '云南': [102.7123, 25.0406],
  '西藏': [91.1322, 29.6604],
  '陕西': [108.9398, 34.3416],
  '甘肃': [103.8343, 36.0611],
  '青海': [101.7782, 36.6232],
  '宁夏': [106.2587, 38.4712],
  '新疆': [87.6177, 43.7928],
  '香港': [114.1694, 22.3193],
  '澳门': [113.5439, 22.1987],
  '台湾': [121.5654, 25.0330]
};

const specialtyTypePool = [
  '粮食类',
  '茶叶类',
  '水果类',
  '畜牧类',
  '水产类',
  '干货类',
  '饮品类',
  '调味品类'
];

const specialtyNamePool = [
  '高原青稞',
  '有机大米',
  '生态茶',
  '精品苹果',
  '富硒蔬菜',
  '山地蜂蜜',
  '山珍菌菇',
  '特色牛羊肉',
  '生态枸杞',
  '湖鲜水产'
];

function stableHash(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (hash * 31 + str.charCodeAt(i)) % 100000;
  }
  return hash;
}

function getProvinceSpecialties(province) {
  if (!provinceSpecialtyCache.value[province]) {
    const seed = stableHash(province);
    const count = 5 + (seed % 4);

    provinceSpecialtyCache.value[province] = Array.from({ length: count }, (_, index) => {
      const type = specialtyTypePool[(seed + index * 2) % specialtyTypePool.length];
      const name = `${province}${specialtyNamePool[(seed + index) % specialtyNamePool.length]}`;
      const registerCount = 10 + ((seed >> (index % 8)) % 40);

      return {
        name,
        type,
        registerCount
      };
    });
  }

  return provinceSpecialtyCache.value[province];
}

function getProvinceTypeCount(province) {
  const specialties = getProvinceSpecialties(province);
  return new Set(specialties.map((item) => item.type)).size;
}

function ensureProvinceStats(province) {
  if (!provinceStatsMap.value[province]) {
    const seed = stableHash(province);
    const specialties = getProvinceSpecialties(province);
    const specialtyTotal = specialties.reduce((sum, item) => sum + item.registerCount, 0);

    provinceStatsMap.value[province] = {
      today_registered: Math.max(8, Math.floor(specialtyTotal / 6)),
      today_scans: Math.max(20, Math.floor(specialtyTotal / 2)),
      today_rejected: seed % 7,
      today_anomalies: seed % 5,
      total_products: 1000 + specialtyTotal * 12 + (seed % 500),
      total_scans: 4000 + specialtyTotal * 35 + (seed % 1200)
    };
  }

  return provinceStatsMap.value[province];
}

function buildTraceSeries(records) {
  const points = [];
  const blueLineMap = new Map();
  const redLineMap = new Map();
  const recentCloneRecords = new Set(
    records
      .filter((record) => record.isClone)
      .slice(0, 5)
  );

  records.forEach((record) => {
    points.push(
      {
        name: record.originName,
        value: record.originCoords,
        isOrigin: true,
        itemStyle: { color: '#16a34a' }
      },
      {
        name: record.scanName,
        value: record.scanCoords,
        isOrigin: false,
        itemStyle: { color: '#f59e0b' }
      }
    );

    const originCoords = Array.isArray(record.originCoords) ? record.originCoords : [116.4, 39.9];
    const scanCoords = Array.isArray(record.scanCoords) ? record.scanCoords : [116.4, 39.9];
    const blueKey = `${originCoords.join(',')}->${scanCoords.join(',')}`;
    if (!blueLineMap.has(blueKey)) {
      blueLineMap.set(blueKey, {
        coords: [originCoords, scanCoords],
        lineStyle: {
          color: '#2563eb'
        }
      });
    }

    if (
      record.isClone &&
      recentCloneRecords.has(record) &&
      Array.isArray(record.previousScanCoords) &&
      record.previousScanCoords.length === 2
    ) {
      const redKey = `${record.previousScanCoords.join(',')}->${scanCoords.join(',')}`;
      if (!redLineMap.has(redKey)) {
        redLineMap.set(redKey, {
          coords: [record.previousScanCoords, scanCoords],
          lineStyle: {
            color: '#ef4444'
          }
        });
      }
    }
  });

  return {
    points,
    lines: [
      ...Array.from(blueLineMap.values()),
      ...Array.from(redLineMap.values())
    ]
  };
}

function buildMockSummary() {
  return {
    today_registered: 125,
    today_scans: 842,
    today_rejected: 12,
    today_anomalies: 5,
    total_products: 15600,
    total_scans: 89420
  };
}

function buildMockTrend() {
  return {
    dates: ['04-01', '04-02', '04-03', '04-04', '04-05', '04-06', '04-07'],
    registrations: [100, 120, 150, 130, 180, 210, 190],
    scans: [400, 500, 450, 600, 550, 700, 650],
    alerts: [2, 1, 5, 3, 4, 8, 2]
  };
}

function buildMockPie() {
  return [
    { value: 1048, name: '谷物类' },
    { value: 735, name: '茶叶类' },
    { value: 580, name: '酒水饮料' },
    { value: 484, name: '生鲜水果' }
  ];
}

function buildMockProvinceMapData() {
  return provincePool.map((province) => ({
    name: province,
    value: getProvinceTypeCount(province)
  }));
}

function createMockScanRecord(seed = Math.floor(Math.random() * 100000)) {
  const originProvince = provincePool[seed % provincePool.length];
  const specialties = getProvinceSpecialties(originProvince);
  const product = specialties[seed % specialties.length];
  const scan = scanLocations[(seed * 3) % scanLocations.length];
  const isClone = seed % 7 === 0 || Math.random() < 0.12;

  return {
    event_id: `mock-${seed}-${Math.random().toString(36).slice(2, 8)}`,
    event_time: new Date(Date.now() - seed * 60000).toISOString(),
    isClone,
    product_code: 'SN-' + String(1000 + (seed * 37) % 9000),
    product_name: product.name,
    product_type: product.type,
    originName: originProvince,
    originCoords: provinceCenterMap[originProvince] || [116.4, 39.9],
    scanName: scan.name,
    scanCoords: scan.coords,
    message: isClone ? '警告：检测到异地瞬移访问，疑似克隆码！' : '首次扫码，防伪校验通过'
  };
}

function buildMockLogs(count = 24) {
  return Array.from({ length: count }, (_, index) => createMockScanRecord(index)).reverse();
}

const activeStats = computed(() => {
  if (selectedProvince.value) {
    return ensureProvinceStats(selectedProvince.value);
  }
  return globalStats.value;
});

const activeLogs = computed(() => {
  if (selectedProvince.value) {
    return logs.value.filter((log) => log.originName === selectedProvince.value);
  }
  return logs.value;
});

const provinceSpecialties = computed(() => {
  if (!selectedProvince.value) return [];
  return provinceSpecialtiesRemote.value[selectedProvince.value] || [];
});

const activePieData = computed(() => {
  if (!selectedProvince.value) {
    return globalPieData.value;
  }

  const specialties =
    provinceSpecialties.value.length > 0 ? provinceSpecialties.value : getProvinceSpecialties(selectedProvince.value);
  const typeCounts = {};

  specialties.forEach((item) => {
    typeCounts[item.type] = (typeCounts[item.type] || 0) + item.registerCount;
  });

  const chartData = Object.keys(typeCounts).map((type) => ({
    name: type,
    value: typeCounts[type]
  }));

  return chartData.length > 0 ? chartData : [{ name: '暂无数据', value: 0 }];
});

const provinceMapData = computed(() => {
  if (provinceMapDataRemote.value.length > 0) {
    return provinceMapDataRemote.value;
  }
  return buildMockProvinceMapData();
});

const activeMapData = computed(() => {
  const sourceLogs = selectedProvince.value
    ? logs.value.filter((log) => log.originName === selectedProvince.value)
    : logs.value;

  return buildTraceSeries(sourceLogs);
});

const onProvinceClicked = (provinceName) => {
  selectedProvince.value = provinceName;
  ensureProvinceStats(provinceName);
};

const onBackToChina = () => {
  selectedProvince.value = null;
};

async function handleAIReportNavigation() {
  const payload = {
    scope: selectedProvince.value || '全国',
    stats: activeStats.value,
    trendData: trendData.value,
    provinceMapData: provinceMapData.value,
    logsCount: activeLogs.value.length,
    timestamp: new Date().toISOString()
  };

  try {
    const raw = await api.generateAIReport(payload);
    const data = unwrapApiPayload(raw);

    if (data?.url) {
      window.location.href = data.url;
      return;
    }
    if (data?.reportUrl) {
      window.location.href = data.reportUrl;
      return;
    }
    if (data?.path) {
      window.location.href = data.path;
      return;
    }
    if (data?.id) {
      window.location.href = `/ai-analysis-report/${encodeURIComponent(data.id)}`;
      return;
    }
  } catch (error) {
    console.warn('AI 报告生成失败，已跳转到分析首页', error);
  }

  window.location.href = '/ai-analysis-report';
}

watch(selectedProvince, async (provinceName) => {
  if (!provinceName || provinceSpecialtiesRemote.value[provinceName]) return;

  const specialties = await tryFetch(
    () => api.getProvinceSpecialties(provinceName),
    () => [],
    (data) => {
      if (!data) return [];
      const rawArray = Array.isArray(data)
        ? data
        : Array.isArray(data.items)
          ? data.items
          : [];
      return rawArray.map((item) => ({
        name: item.name,
        type: item.type || '??',
        registerCount: Number(item.registerCount ?? item.register_count ?? item.value ?? 0)
      }));
    }
  );

  provinceSpecialtiesRemote.value = {
    ...provinceSpecialtiesRemote.value,
    [provinceName]: specialties
  };
});

async function fetchInitialData() {
  const summaryData = await tryFetch(
    () => api.getSummary(),
    buildMockSummary
  );

  const trend = await tryFetch(
    () => api.getTrend(7),
    buildMockTrend
  );

  const pie = await tryFetch(
    () => api.getPie(),
    buildMockPie
  );

  const provinceMap = await tryFetch(
    () => api.getProvinceMap(),
    buildMockProvinceMapData,
    (data) => {
      if (!data) return null;

      const rawArray = Array.isArray(data)
        ? data
        : Array.isArray(data.provinces)
          ? data.provinces
          : [];

      if (!rawArray.length) return null;

      return rawArray.map((item) => ({
        name: item.name,
        value: Number(item.product_count ?? item.productCount ?? item.type_count ?? item.typeCount ?? item.value ?? item.count ?? 0)
      }));
    }
  );

  const mapData = await tryFetch(
    () => api.getMapData(),
    () => ({ anomaly_lines: [] }),
    (data) => {
      if (!data || typeof data !== 'object') return { anomaly_lines: [] };
      return data;
    }
  );

  const logList = await tryFetch(
    () => api.getRealtimeLogs(80),
    () => buildMockLogs(24),
    (data) => {
      if (!data) return null;
      const rawArray = Array.isArray(data)
        ? data
        : Array.isArray(data.records)
          ? data.records
          : Array.isArray(data.logs)
            ? data.logs
            : [];

      return rawArray.length ? rawArray : null;
    }
  );

  const anomalyLines = Array.isArray(mapData?.anomaly_lines)
    ? mapData.anomaly_lines.map((item) => ({
        product_code: item.product_code,
        risk_level: item.risk_level,
        fromCoords: [Number(item.from_lng), Number(item.from_lat)],
        toCoords: [Number(item.to_lng), Number(item.to_lat)]
      })).filter((item) =>
        item.fromCoords.every((value) => Number.isFinite(value)) &&
        item.toCoords.every((value) => Number.isFinite(value))
      )
    : [];

  const anomalyByProduct = new Map(
    anomalyLines.map((item) => [item.product_code, item])
  );

  const normalizedLogs = (logList || buildMockLogs(24)).map((item) => ({
    ...item,
    previousScanCoords: anomalyByProduct.get(item.product_code)?.fromCoords || null
  }));

  globalStats.value = summaryData;
  trendData.value = trend;
  globalPieData.value = pie;
  provinceMapDataRemote.value = provinceMap || [];
  anomalyLinesRemote.value = anomalyLines;
  regionData.value = Array.isArray(mapData?.regions) ? mapData.regions : [];
  logs.value = normalizedLogs;
}

const handleNewScanRecord = (record) => {
  logs.value.unshift(record);
  if (logs.value.length > 120) logs.value.pop();

  globalStats.value.today_registered += 1;
  globalStats.value.today_scans += 1;
  globalStats.value.total_products += 1;
  globalStats.value.total_scans += 1;

  if (record.isClone) {
    globalStats.value.today_rejected += 1;
    globalStats.value.today_anomalies += 1;
  }

  const prov = record.originName;
  const provinceStats = ensureProvinceStats(prov);

  provinceStats.today_registered += 1;
  provinceStats.today_scans += 1;
  provinceStats.total_products += 1;
  provinceStats.total_scans += 1;

  if (record.isClone) {
    provinceStats.today_rejected += 1;
    provinceStats.today_anomalies += 1;
  }
};

const generateMockScan = () => {
  const seed = Math.floor(Math.random() * 100000);
  const record = createMockScanRecord(seed);
  handleNewScanRecord(record);
};

let mockWsInterval = null;

onMounted(async () => {
  await fetchInitialData();
});

onBeforeUnmount(() => {
  if (mockWsInterval) {
    clearInterval(mockWsInterval);
  }
});

const getLogClass = (isClone) => (isClone ? 'A' : 'N');

const formatTime = (ts) => {
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return '--:--:--';
  return date.toTimeString().slice(0, 8);
};

const showDetail = (log) => {
  selectedLog.value = log;
};
</script>

<style>
:root {
  --bg-page: #f7f2ea;
  --bg-page-2: #fbf7f1;
  --surface: rgba(255, 255, 255, 0.92);
  --surface-strong: #ffffff;
  --surface-soft: #fcf7ef;
  --border: #eadfce;
  --text-main: #243244;
  --text-muted: #6b7280;
  --p-blue: #2563eb;
  --p-blue-2: #4f46e5;
  --p-green: #16a34a;
  --d-red: #ef4444;
  --warn: #f59e0b;
  --shadow: 0 14px 35px rgba(31, 41, 55, 0.08);
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: var(--bg-page);
  color: var(--text-main);
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  overflow: hidden;
}

.app-shell {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, var(--bg-page) 0%, var(--bg-page-2) 100%);
}

.top-navbar {
  height: 56px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 20px;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(12px);
  z-index: 100;
  box-shadow: 0 4px 20px rgba(31, 41, 55, 0.04);
}

.logo {
  font-weight: 700;
  color: var(--text-main);
  letter-spacing: 0.5px;
}

.nav-links {
  display: flex;
  gap: 10px;
}

.nav-links button {
  background: #f3f4f6;
  border: 1px solid transparent;
  color: #516074;
  padding: 8px 16px;
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.25s ease;
  font-size: 14px;
  box-shadow: 0 4px 12px rgba(31, 41, 55, 0.04);
}

.nav-links button:hover {
  transform: translateY(-1px);
  background: #eef2ff;
  color: #1e3a8a;
}

.nav-links button.active {
  color: #fff;
  font-weight: 700;
  background: linear-gradient(135deg, var(--p-blue), var(--p-blue-2));
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.22);
}

.sys-time {
  color: #5b6b7d;
  font-size: 14px;
}

.content-area {
  flex: 1;
  padding: 12px;
  overflow: hidden;
  background: linear-gradient(180deg, #faf7f2 0%, #f4efe8 100%);
}

.tab-content {
  height: 100%;
}

.dashboard {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 12px;
}

.stats-header {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 10px;
  flex-shrink: 0;
}

.stat-card {
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 12px 10px;
  border-radius: 14px;
  text-align: center;
  box-shadow: var(--shadow);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 18px 30px rgba(31, 41, 55, 0.10);
}

.stat-label {
  font-size: 13px;
  color: var(--text-muted);
}

.num {
  display: block;
  font-size: 24px;
  font-weight: 800;
  margin-top: 4px;
  color: var(--text-main);
}

.num.blue {
  color: #0ea5e9;
}

.num.blue-alt {
  color: #2563eb;
}

.num.red {
  color: var(--d-red);
}

.num.orange {
  color: var(--warn);
}

.num.grey {
  color: #475569;
}

.main-layout {
  display: flex;
  gap: 12px;
  flex: 1;
  min-height: 0;
}

.side-column.left-charts {
  flex: 3;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.map-section {
  flex: 6.5;
  border: 1px solid var(--border);
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #fbf8f3 100%);
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow);
  overflow: hidden;
}

.side-column.right-logs {
  flex: 3;
  display: flex;
  flex-direction: column;
}

.sub-panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 18px;
  box-shadow: var(--shadow);
}

.flex-item {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 14px;
}

.chart-box {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.map-container {
  flex: 1;
  position: relative;
  min-height: 0;
}

.map-tip {
  padding: 0 14px 10px 14px;
  color: #64748b;
  font-size: 12px;
}

/* 左上角特产滑动窗口 */
.specialty-scroll-window {
  flex: 1;
  overflow-y: auto;
  padding-right: 5px;
}

.specialty-scroll-window::-webkit-scrollbar {
  width: 6px;
}

.specialty-scroll-window::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 6px;
}

.specialty-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(180deg, #f8fbff 0%, #eef4ff 100%);
  border: 1px solid #dbeafe;
  border-left: 4px solid #2563eb;
  padding: 12px;
  margin-bottom: 10px;
  border-radius: 14px;
  transition: transform 0.2s, box-shadow 0.2s;
  gap: 10px;
}

.specialty-item:hover {
  transform: translateX(4px);
  box-shadow: 0 10px 20px rgba(37, 99, 235, 0.10);
}

.specialty-left {
  min-width: 0;
}

.specialty-right {
  font-size: 12px;
  color: #1d4ed8;
  white-space: nowrap;
}

.s-name {
  font-size: 14px;
  font-weight: 700;
  color: #1e3a8a;
}

.s-tag {
  font-size: 11px;
  background: rgba(37, 99, 235, 0.08);
  padding: 3px 8px;
  border-radius: 999px;
  color: #475569;
  border: 1px solid #dbeafe;
  display: inline-block;
  margin-top: 6px;
}

.no-data {
  text-align: center;
  color: #94a3b8;
  margin-top: 40px;
  font-size: 13px;
}

.panel-title {
  font-size: 14px;
  color: #1e3a8a;
  border-left: 4px solid var(--p-blue);
  padding-left: 10px;
  margin-bottom: 10px;
  font-weight: 800;
}

.log-marquee-container {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.log-marquee-container::-webkit-scrollbar {
  width: 6px;
}

.log-marquee-container::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 6px;
}

.log-row {
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  padding: 12px;
  margin-bottom: 10px;
  border-radius: 14px;
  border: 1px solid #e5eefb;
  border-left: 4px solid #cbd5e1;
  font-size: 12px;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.log-row:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 26px rgba(37, 99, 235, 0.10);
  border-color: #bfdbfe;
}

.log-top {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}

.log-mid {
  margin-bottom: 6px;
  color: #0f4c81;
  font-weight: 700;
}

.log-bottom {
  display: flex;
  gap: 8px;
  color: #64748b;
  flex-wrap: wrap;
}

.loc {
  color: #b45309;
  font-weight: 700;
  white-space: nowrap;
}

.red-text {
  color: var(--d-red);
  font-weight: 600;
}

.tag {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 999px;
  line-height: 1.2;
}

.tag.A {
  color: var(--d-red);
  border: 1px solid rgba(239, 68, 68, 0.35);
  background: rgba(239, 68, 68, 0.06);
}

.tag.N {
  color: var(--p-green);
  border: 1px solid rgba(22, 163, 74, 0.35);
  background: rgba(22, 163, 74, 0.06);
}

.panel-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 14px 10px 14px;
  border-bottom: 1px solid #e5e7eb;
}

.panel-header-row.no-border {
  border-bottom: none;
  padding-bottom: 0;
}

.legend-group {
  display: flex;
  gap: 10px;
  font-size: 11px;
  color: #475569;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.legend {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 999px;
}

.legend i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
  vertical-align: middle;
}

.legend i.line {
  width: 14px;
  height: 3px;
  border-radius: 2px;
  display: inline-block;
}

.pulse-green {
  color: #16a34a;
  text-shadow: 0 0 5px rgba(22, 163, 74, 0.25);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
  100% {
    opacity: 1;
  }
}

.analysis-wrapper {
  height: 100%;
  overflow: hidden;
}
</style>
