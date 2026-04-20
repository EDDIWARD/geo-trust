import fs from 'node:fs'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

function rawGeoJsonPlugin() {
  return {
    name: 'geo-admin-raw-geojson',
    enforce: 'pre',
    load(id) {
      const cleanId = id.split('?')[0]
      if (!cleanId.endsWith('.geojson')) {
        return null
      }

      return `export default ${JSON.stringify(fs.readFileSync(cleanId, 'utf8'))}`
    }
  }
}

function admin1TraceMapBridgePlugin() {
  return {
    name: 'geo-admin-trace-map-bridge',
    transform(code, id) {
      const normalizedId = id.replace(/\\/g, '/')
      if (!normalizedId.endsWith('/geo-admin/src/App.vue')) {
        return null
      }

      return code.replace(
        "import TraceMap from './components/TraceMap.vue';",
        "import TraceMap from './components/TraceMapBridge.vue';"
      )
    }
  }
}

function admin1DataCompatPlugin() {
  return {
    name: 'geo-admin-data-compat',
    transform(code, id) {
      const normalizedId = id.replace(/\\/g, '/')
      if (normalizedId.endsWith('/geo-admin/src/components/DataAnalysis.vue')) {
        let nextCode = code

        nextCode = nextCode.replace(
          "{ width: item.score + '%', background: item.riskLevel.color }",
          "{ width: item.fillWidth + '%', background: item.riskLevel.color }"
        )

        nextCode = nextCode.replace(
          /const computedRegions = computed\(\(\) => \{[\s\S]*?\n\}\);/,
          `const computedRegions = computed(() => {
  const data = props.regionRawData.length ? props.regionRawData : [
    { name: '待加载...', type: '-', todayCount: 0, anomalies: 0, totalScans: 1 }
  ];
  return data.map(item => {
    const totalScans = item.totalScans || 1;
    const safeScans = Math.max(0, totalScans - (item.anomalies || 0));
    const score = Number(((safeScans / totalScans) * 10).toFixed(1));
    const fillWidth = Math.max(0, Math.min(100, score * 10));

    let risk = { text: '极高可信', class: 'safe', color: '#52c41a' };
    if (score < 9 && score >= 7) risk = { text: '风险预警', class: 'warn', color: '#ffa940' };
    else if (score < 7) risk = { text: '高危拦截', class: 'danger', color: '#ff4d4f' };

    return { ...item, score, fillWidth, riskLevel: risk };
  });
});`
        )

        return nextCode
      }

      if (!normalizedId.endsWith('/geo-admin/src/App.vue')) {
        return null
      }

      let nextCode = code

      nextCode = nextCode.replace(
        "const API_BASE = import.meta.env.VITE_API_BASE_URL || '';",
        "const API_BASE = import.meta.env.VITE_API_BASE_URL || window.location.origin;"
      )

      nextCode = nextCode.replace(
        "  getProvinceMap: () => requestJson('/api/map/provinces'),",
        "  getProvinceMap: () => requestJson('/api/map/provinces'),\n  getRegionData: () => requestJson('/api/dashboard/regions'),"
      )

      nextCode = nextCode.replace(
        /const specialtyNamePool = \[[\s\S]*?\];\n\nfunction stableHash\(str\) \{/,
        `const specialtyNamePool = [
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

const curatedRegionProducts = [
  { regionName: '恩施高山茶区', productName: '恩施玉露', productType: '绿茶', province: '湖北', originCoords: [109.49, 30.28] },
  { regionName: '赤壁砖茶产区', productName: '赤壁青砖茶', productType: '黑茶', province: '湖北', originCoords: [113.88, 29.72] },
  { regionName: '神农架林区', productName: '神农架百花蜜', productType: '蜂蜜', province: '湖北', originCoords: [110.67, 31.75] },
  { regionName: '秭归脐橙核心产区', productName: '秭归脐橙', productType: '鲜果', province: '湖北', originCoords: [110.98, 30.83] },
  { regionName: '宜昌高山柚产带', productName: '宜昌高山柚', productType: '鲜果', province: '湖北', originCoords: [111.29, 30.70] },
  { regionName: '罗田山地板栗产区', productName: '罗田板栗', productType: '干货', province: '湖北', originCoords: [115.40, 30.78] },
  { regionName: '武汉湖区莲藕基地', productName: '武汉莲藕粉', productType: '冲调', province: '湖北', originCoords: [114.31, 30.52] },
  { regionName: '潜江虾稻产区', productName: '潜江小龙虾', productType: '熟食', province: '湖北', originCoords: [112.90, 30.42] },
  { regionName: '武汉近郊菜薹产区', productName: '洪山菜薹', productType: '蔬菜', province: '湖北', originCoords: [114.40, 30.53] },
  { regionName: '梁子湖生态水域', productName: '梁子湖大闸蟹', productType: '水产', province: '湖北', originCoords: [114.62, 30.18] },
  { regionName: '随州香菇产区', productName: '随州香菇', productType: '干货', province: '湖北', originCoords: [113.37, 31.72] },
  { regionName: '孝感米酒产区', productName: '孝感米酒', productType: '饮品', province: '湖北', originCoords: [113.92, 30.93] },
  { regionName: '绍兴黄酒产区', productName: '绍兴黄酒', productType: '饮品', province: '浙江', originCoords: [120.58, 30.01] },
  { regionName: '西湖龙井核心产区', productName: '西湖龙井', productType: '绿茶', province: '浙江', originCoords: [120.10, 30.24] },
  { regionName: '阳澄湖核心湖区', productName: '阳澄湖大闸蟹', productType: '水产', province: '江苏', originCoords: [120.78, 31.43] }
];

const productTypeCategoryMap = {
  鲜果: '生鲜水果',
  水产: '生鲜水果',
  蔬菜: '生鲜水果',
  熟食: '生鲜水果',
  水果类: '生鲜水果',
  水产类: '生鲜水果',
  畜牧类: '生鲜水果',
  蜂蜜: '酒水饮料',
  冲调: '酒水饮料',
  饮品: '酒水饮料',
  饮品类: '酒水饮料',
  调味品类: '酒水饮料',
  黑茶: '茶叶类',
  绿茶: '茶叶类',
  干货: '谷物类',
  粮食类: '谷物类',
  干货类: '谷物类'
};

function normalizeProductType(type) {
  return productTypeCategoryMap[type] || type || '其他';
}

function normalizePieDataset(data) {
  const merged = new Map();

  (data || []).forEach((item) => {
    const name = normalizeProductType(item.name);
    const value = Number(item.value || 0);
    merged.set(name, (merged.get(name) || 0) + value);
  });

  return [
    { name: '谷物类', value: merged.get('谷物类') || 0 },
    { name: '茶叶类', value: merged.get('茶叶类') || 0 },
    { name: '酒水饮料', value: merged.get('酒水饮料') || 0 },
    { name: '生鲜水果', value: merged.get('生鲜水果') || 0 }
  ];
}

function buildLegacyScanProduct(seed) {
  const originProvince = provincePool[seed % provincePool.length];
  const specialties = getProvinceSpecialties(originProvince);
  const product = specialties[seed % specialties.length];

  return {
    productName: product.name,
    productType: product.type,
    province: originProvince,
    originCoords: provinceCenterMap[originProvince] || [116.4, 39.9]
  };
}

function syncRegionStatWithRecord(record) {
  const regionName = record.regionName;
  if (!regionName) return;

  let region = regionData.value.find((item) => item.name === regionName);
  if (!region) {
    region = {
      name: regionName,
      type: record.product_type || '其他',
      province: record.originName || '未知',
      todayCount: 0,
      anomalies: 0,
      totalScans: 0
    };
    regionData.value = [region, ...regionData.value];
  }

  region.todayCount += 1;
  region.totalScans += 1;
  if (record.isClone) {
    region.anomalies += 1;
  }
}

function syncPieDataWithRecord(record) {
  const type = normalizeProductType(record.product_type);
  const target = globalPieData.value.find((item) => item.name === type);
  if (target) {
    target.value += 1;
    return;
  }

  globalPieData.value.push({
    name: type,
    value: 1
  });
}

function stableHash(str) {`
      )

      nextCode = nextCode.replace(
        /function createMockScanRecord\(seed = Math\.floor\(Math\.random\(\) \* 100000\)\) \{[\s\S]*?\n\}\n\nfunction buildMockLogs/,
        `function createMockScanRecord(seed = Math.floor(Math.random() * 100000)) {
  const useCuratedProduct = seed % 5 < 2;
  const product = useCuratedProduct
    ? curatedRegionProducts[seed % curatedRegionProducts.length]
    : buildLegacyScanProduct(seed);
  const scan = scanLocations[(seed * 3) % scanLocations.length];
  const isClone = seed % 7 === 0 || Math.random() < 0.12;

  return {
    event_id: \`mock-\${seed}-\${Math.random().toString(36).slice(2, 8)}\`,
    event_time: new Date(Date.now() - seed * 60000).toISOString(),
    isClone,
    product_code: 'SN-' + String(1000 + (seed * 37) % 9000),
    product_name: product.productName,
    product_type: product.productType,
    regionName: product.regionName || '',
    originName: product.province,
    originCoords: product.originCoords || provinceCenterMap[product.province] || [116.4, 39.9],
    scanName: scan.name,
    scanCoords: scan.coords,
    message: isClone ? '警告：检测到异地瞬移访问，疑似克隆码！' : '首次扫码，防伪校验通过'
  };
}

function buildMockLogs`
      )

      nextCode = nextCode.replace(
        "  const logList = await tryFetch(",
        `  const regionList = await tryFetch(
    () => api.getRegionData(),
    () => [],
    (data) => {
      if (!data) return null;
      const rawArray = Array.isArray(data)
        ? data
        : Array.isArray(data.regions)
          ? data.regions
          : [];

      return rawArray.length ? rawArray : null;
    }
  );

  const logList = await tryFetch(`
      )

      nextCode = nextCode.replace(
        "  provinceMapDataRemote.value = provinceMap || [];\n  logs.value = logList || buildMockLogs(24);",
        "  provinceMapDataRemote.value = provinceMap || [];\n  globalPieData.value = normalizePieDataset(pie || []);\n  regionData.value = regionList || [];\n  logs.value = logList || buildMockLogs(24);"
      )

      nextCode = nextCode.replace(
        /const handleNewScanRecord = \(record\) => \{[\s\S]*?\n\};\n\nconst generateMockScan/,
        `const handleNewScanRecord = (record) => {
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

  syncRegionStatWithRecord(record);
  syncPieDataWithRecord(record);

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

const generateMockScan`
      )

      nextCode = nextCode.replace(
        `const activePieData = computed(() => {
  if (!selectedProvince.value) {
    return globalPieData.value;
  }

  const specialties = getProvinceSpecialties(selectedProvince.value);
  const typeCounts = {};

  specialties.forEach((item) => {
    typeCounts[item.type] = (typeCounts[item.type] || 0) + item.registerCount;
  });

  const chartData = Object.keys(typeCounts).map((type) => ({
    name: type,
    value: typeCounts[type]
  }));

  return chartData.length > 0 ? chartData : [{ name: '暂无数据', value: 0 }];
});`,
        `const activePieData = computed(() => {
  if (!selectedProvince.value) {
    return globalPieData.value;
  }

  const specialties = getProvinceSpecialties(selectedProvince.value);
  const typeCounts = {};

  specialties.forEach((item) => {
    const normalizedType = normalizeProductType(item.type);
    typeCounts[normalizedType] = (typeCounts[normalizedType] || 0) + item.registerCount;
  });

  const chartData = Object.keys(typeCounts).map((type) => ({
    name: type,
    value: typeCounts[type]
  }));

  return chartData.length > 0 ? normalizePieDataset(chartData) : [{ name: '暂无数据', value: 0 }];
});`
      )

      return nextCode
    }
  }
}

export default defineConfig({
  plugins: [rawGeoJsonPlugin(), admin1TraceMapBridgePlugin(), admin1DataCompatPlugin(), vue()],
  base: '/static/admin-vue/',
  assetInclude: ['**/*.geojson'],
  build: {
    outDir: fileURLToPath(new URL('../backend/server/static/admin-vue', import.meta.url)),
    emptyOutDir: true
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    fs: {
      allow: [fileURLToPath(new URL('..', import.meta.url))]
    },
    proxy: {
      '/api': {
        target: 'http://111.229.115.101:8000',
        changeOrigin: true
      },
      '/ai-analysis-report': {
        target: 'http://111.229.115.101:8000',
        changeOrigin: true
      },
      '/trace': {
        target: 'http://111.229.115.101:8000',
        changeOrigin: true
      }
    }
  }
})
