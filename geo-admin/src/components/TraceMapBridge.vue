<template>
  <div class="map-wrapper">
    <button v-if="currentMap !== 'china'" type="button" class="back-btn" @click="backToChina">
      ↩ 返回全国
    </button>

    <div ref="mapRef" class="map-canvas" @wheel.capture.prevent="handleWheelZoom"></div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import * as echarts from 'echarts';
import chinaGeoJsonRaw from '../assets/china.geojson?raw';

const emit = defineEmits(['province-clicked', 'back-to-china']);

const props = defineProps({
  points: {
    type: Array,
    default: () => []
  },
  lines: {
    type: Array,
    default: () => []
  },
  mapData: {
    type: Array,
    default: () => []
  }
});

const mapRef = ref(null);
const currentMap = ref('china');
const chinaGeoJson = JSON.parse(chinaGeoJsonRaw);

let chartInstance = null;
let resizeHandler = null;

let currentZoomState = {
  zoom: 1,
  center: null
};

const provinceNameMap = {
  北京市: '北京',
  天津市: '天津',
  河北省: '河北',
  山西省: '山西',
  内蒙古自治区: '内蒙古',
  辽宁省: '辽宁',
  吉林省: '吉林',
  黑龙江省: '黑龙江',
  上海市: '上海',
  江苏省: '江苏',
  浙江省: '浙江',
  安徽省: '安徽',
  福建省: '福建',
  江西省: '江西',
  山东省: '山东',
  河南省: '河南',
  湖北省: '湖北',
  湖南省: '湖南',
  广东省: '广东',
  广西壮族自治区: '广西',
  海南省: '海南',
  重庆市: '重庆',
  四川省: '四川',
  贵州省: '贵州',
  云南省: '云南',
  西藏自治区: '西藏',
  陕西省: '陕西',
  甘肃省: '甘肃',
  青海省: '青海',
  宁夏回族自治区: '宁夏',
  新疆维吾尔自治区: '新疆',
  香港特别行政区: '香港',
  澳门特别行政区: '澳门',
  台湾省: '台湾'
};

const provinceGeoJsonMap = {};
let chinaProvinceNames = [];

function normalizeProvinceName(name) {
  return (name || '')
    .replace(/壮族自治区|回族自治区|维吾尔自治区|特别行政区|自治区/g, '')
    .replace(/省|市|地区|盟/g, '')
    .trim();
}

function registerLocalProvinceMaps() {
  const modules = import.meta.glob('../assets/province/*.geojson', {
    eager: true,
    query: '?raw',
    import: 'default'
  });

  Object.entries(modules).forEach(([path, raw]) => {
    try {
      const fileName = path.split('/').pop() || '';
      const baseName = fileName.replace(/\.geojson$/i, '');
      const normalizedName = normalizeProvinceName(baseName);
      const geoJson = JSON.parse(raw);
      provinceGeoJsonMap[baseName] = geoJson;
      provinceGeoJsonMap[normalizedName] = geoJson;
    } catch (error) {
      console.error('解析省份 geojson 失败：', path, error);
    }
  });
}

function resolveProvinceGeoJson(name) {
  const normalized = normalizeProvinceName(name);
  return provinceGeoJsonMap[normalized] || provinceGeoJsonMap[name] || null;
}

function extractChinaProvinceNames() {
  chinaProvinceNames = (chinaGeoJson.features || [])
    .map((feature) => feature?.properties?.name || feature?.properties?.NAME || '')
    .filter(Boolean);
}

function buildChinaMapData() {
  const incomingMap = new Map();

  props.mapData.forEach((item) => {
    const rawName = String(item?.name || '').trim();
    const normalizedName = normalizeProvinceName(rawName);
    const numericValue = Number(item?.value ?? 0);
    const safeValue = Number.isFinite(numericValue) ? numericValue : 0;

    if (rawName) {
      incomingMap.set(rawName, safeValue);
    }
    if (normalizedName) {
      incomingMap.set(normalizedName, safeValue);
    }
  });

  return chinaProvinceNames.map((provinceName) => {
    const normalizedName = normalizeProvinceName(provinceName);
    const displayName = provinceNameMap[provinceName] || provinceNameMap[normalizedName] || normalizedName || provinceName;
    const value = incomingMap.get(provinceName) ?? incomingMap.get(normalizedName) ?? 0;
    return {
      name: displayName,
      value
    };
  });
}

function getCurrentCenter() {
  if (currentZoomState.center) {
    return currentZoomState.center;
  }

  if (!chartInstance) {
    return [104, 35];
  }

  const option = chartInstance.getOption();
  const geo = option.geo;
  if (geo && geo[0] && geo[0].center) {
    return geo[0].center;
  }

  const series = option.series;
  if (series && series[0] && series[0].center) {
    return series[0].center;
  }

  return [104, 35];
}

function handleWheelZoom(event) {
  if (!chartInstance) return;

  const rect = chartInstance.getDom().getBoundingClientRect();
  const mouseX = event.clientX - rect.left;
  const mouseY = event.clientY - rect.top;

  let mouseGeoCoord = null;
  try {
    mouseGeoCoord = chartInstance.convertFromPixel({ geoIndex: 0 }, [mouseX, mouseY]);
  } catch {
    mouseGeoCoord = null;
  }

  const zoomFactor = event.deltaY > 0 ? 0.9 : 1.1;
  const oldZoom = currentZoomState.zoom;
  let newZoom = oldZoom * zoomFactor;
  newZoom = Math.max(0.8, Math.min(newZoom, 20));

  const oldCenter = getCurrentCenter();
  let newCenter = oldCenter;

  if (mouseGeoCoord && Array.isArray(mouseGeoCoord) && mouseGeoCoord.length >= 2) {
    const [mouseLng, mouseLat] = mouseGeoCoord;
    const [oldCenterLng, oldCenterLat] = oldCenter;
    const scaleRatio = oldZoom / newZoom;

    newCenter = [
      mouseLng - (mouseLng - oldCenterLng) * scaleRatio,
      mouseLat - (mouseLat - oldCenterLat) * scaleRatio
    ];
  }

  currentZoomState.zoom = newZoom;
  currentZoomState.center = newCenter;

  chartInstance.setOption(
    {
      geo: {
        zoom: newZoom,
        center: newCenter
      },
      series: [
        {
          zoom: newZoom,
          center: newCenter
        },
        {},
        {}
      ]
    },
    false
  );
}

function render() {
  if (!chartInstance) return;

  const mapData = currentMap.value === 'china' ? buildChinaMapData() : [];
  const maxValue = Math.max(1, ...mapData.map((item) => Number(item.value) || 0));

  chartInstance.setOption(
    {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        formatter: (params) => {
          if (params.seriesType !== 'map') {
            return '';
          }
          const value = Number(params.value ?? 0);
          if (currentMap.value === 'china') {
            return `${params.name}<br/>登记产品种类：${value}`;
          }
          return `${params.name}`;
        }
      },
      visualMap: currentMap.value === 'china'
        ? {
            type: 'piecewise',
            pieces: [
              { value: 0, label: '0', color: '#f1f5f9' },
              { min: 1, max: 3, label: '1-3', color: '#c7ddff' },
              { min: 4, max: 10, label: '4-10', color: '#7eb6f6' },
              { min: 11, label: '11+', color: '#2f8fd8' }
            ],
            left: 20,
            bottom: 20,
            orient: 'vertical',
            text: ['种类多', '种类少'],
            textStyle: { color: '#475569' },
            itemWidth: 16,
            itemHeight: 12,
            itemGap: 8
          }
        : {
            show: false
          },
      geo: {
        map: currentMap.value,
        roam: true,
        zoom: currentZoomState.zoom,
        center: currentZoomState.center,
        silent: false,
        label: {
          show: false
        },
        itemStyle: {
          areaColor: 'transparent',
          borderColor: 'transparent',
          borderWidth: 0
        },
        emphasis: {
          itemStyle: {
            areaColor: 'transparent'
          }
        }
      },
      series: [
        {
          name: '产品种类热力',
          type: 'map',
          map: currentMap.value,
          roam: true,
          zoom: currentZoomState.zoom,
          center: currentZoomState.center,
          nameMap: currentMap.value === 'china' ? provinceNameMap : {},
          data: mapData,
          label: {
            show: true,
            color: '#415066',
            fontSize: 10
          },
          itemStyle: {
            borderColor: '#a9b8ca',
            borderWidth: 1
          },
          emphasis: {
            label: {
              show: true,
              color: '#0f172a',
              fontSize: 12
            },
            itemStyle: {
              areaColor: '#dbeafe'
            }
          }
        },
        {
          name: '地理节点',
          type: 'scatter',
          coordinateSystem: 'geo',
          data: props.points,
          symbolSize: (value, params) => params?.data?.isOrigin ? 8 : 6,
          tooltip: {
            show: false
          },
          label: {
            show: false
          },
          emphasis: {
            label: {
              show: false
            }
          },
          itemStyle: {
            opacity: 1
          },
          zlevel: 3
        },
        {
          name: '扫码轨迹',
          type: 'lines',
          coordinateSystem: 'geo',
          tooltip: {
            show: false
          },
          zlevel: 5,
          effect: {
            show: true,
            period: 3,
            trailLength: 0.22,
            symbolSize: 4,
            color: '#ef4444'
          },
          lineStyle: {
            width: 2.4,
            curveness: 0.22,
            opacity: 0.9
          },
          data: props.lines.map((item) => ({
            ...item,
            lineStyle: {
              width: item?.lineStyle?.color === '#ef4444' ? 3.2 : 2,
              opacity: item?.lineStyle?.color === '#ef4444' ? 0.98 : 0.72,
              curveness: 0.22,
              color: item?.lineStyle?.color || '#2563eb'
            },
            effect: {
              color: item?.lineStyle?.color || '#2563eb'
            }
          }))
        }
      ]
    },
    true
  );
}

function backToChina() {
  currentMap.value = 'china';
  currentZoomState = {
    zoom: 1,
    center: null
  };
  emit('back-to-china');
  render();
}

onMounted(() => {
  registerLocalProvinceMaps();
  extractChinaProvinceNames();
  chartInstance = echarts.init(mapRef.value);
  echarts.registerMap('china', chinaGeoJson);

  chartInstance.on('georoam', () => {
    const option = chartInstance?.getOption();
    const geo = option?.geo?.[0];
    if (!geo) return;
    currentZoomState = {
      zoom: geo.zoom ?? currentZoomState.zoom,
      center: geo.center ?? currentZoomState.center
    };
  });

  chartInstance.on('click', (params) => {
    if (currentMap.value !== 'china' || params.seriesType !== 'map') return;

    const provinceName = normalizeProvinceName(params.name);
    const localGeoJson = resolveProvinceGeoJson(provinceName);

    try {
      if (!localGeoJson) {
        alert(`没有找到【${provinceName}】对应的本地省份地图文件`);
        return;
      }

      echarts.registerMap(provinceName, localGeoJson);
      currentMap.value = provinceName;
      currentZoomState = {
        zoom: 1,
        center: null
      };
      emit('province-clicked', provinceName);
      render();
    } catch (error) {
      console.error('切换省份地图失败：', error);
    }
  });

  resizeHandler = () => chartInstance?.resize();
  window.addEventListener('resize', resizeHandler);
  render();
});

onBeforeUnmount(() => {
  if (resizeHandler) {
    window.removeEventListener('resize', resizeHandler);
  }

  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
});

watch(
  () => [props.points, props.lines, props.mapData],
  () => {
    render();
  },
  { deep: true }
);
</script>

<style scoped>
.map-wrapper {
  width: 100%;
  height: 100%;
  position: relative;
}

.map-canvas {
  width: 100%;
  height: 100%;
  min-height: 400px;
}

.back-btn {
  position: absolute;
  top: 16px;
  left: 16px;
  z-index: 10;
  background: rgba(37, 99, 235, 0.1);
  border: 1px solid rgba(37, 99, 235, 0.35);
  color: #1e3a8a;
  padding: 7px 14px;
  border-radius: 999px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.25s ease;
  box-shadow: 0 8px 18px rgba(31, 41, 55, 0.08);
}

.back-btn:hover {
  background: rgba(37, 99, 235, 0.18);
  transform: translateY(-1px);
}
</style>
