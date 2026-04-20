<template>
  <div ref="chartRef" style="width: 100%; height: 100%;"></div>
</template>

<script setup>
import { onMounted, watch, onUnmounted, ref } from 'vue';
import * as echarts from 'echarts';

const props = defineProps(['chartData']);
const chartRef = ref(null);
let chart = null;

const initChart = () => {
  if (!chartRef.value) return;
  if (!chart) chart = echarts.init(chartRef.value);
  
  chart.setOption({
    grid: { top: 15, bottom: 25, left: 15, right: 10, containLabel: true },
    tooltip: { trigger: 'axis' },
    xAxis: { 
      type: 'category', 
      data: props.chartData.dates,
      axisLabel: { color: '#666', fontSize: 10 },
      axisLine: { lineStyle: { color: '#333' } }
    },
    yAxis: { 
      type: 'value', 
      splitLine: { lineStyle: { color: '#222' } }, 
      axisLabel: { color: '#666', fontSize: 10 }
    },
    series: [{
      name: '异常',
      data: props.chartData.alerts,
      type: 'line', smooth: true, symbol: 'none',
      lineStyle: { color: '#ff4d4f', width: 2 },
      areaStyle: { 
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(255,77,79,0.3)' }, 
          { offset: 1, color: 'transparent' }
        ]) 
      }
    }]
  });
};

onMounted(() => {
  initChart();
  window.addEventListener('resize', () => chart?.resize());
});
watch(() => props.chartData, () => initChart(), { deep: true });
onUnmounted(() => { window.removeEventListener('resize', () => chart?.resize()); });
</script>