<template>
  <div ref="pieRef" style="width: 100%; height: 100%;"></div>
</template>

<script setup>
import { onMounted, watch, ref, onUnmounted } from 'vue';
import * as echarts from 'echarts';

const props = defineProps(['chartData']);
const pieRef = ref(null);
let chartInstance = null;

const renderChart = () => {
  if (!pieRef.value) return;
  if (!chartInstance) chartInstance = echarts.init(pieRef.value);

  chartInstance.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    legend: { 
      orient: 'vertical', left: '2%', top: 'center',
      textStyle: { color: '#888', fontSize: 10 },
      itemWidth: 8, itemHeight: 8
    },
    series: [{
      name: '产品类型',
      type: 'pie',
      radius: ['45%', '75%'],
      center: ['65%', '50%'],
      itemStyle: { borderRadius: 4, borderColor: '#000', borderWidth: 1 },
      label: { show: false },
      data: props.chartData
    }]
  });
};

onMounted(() => {
  renderChart();
  window.addEventListener('resize', () => chartInstance?.resize());
});
watch(() => props.chartData, () => renderChart(), { deep: true });
onUnmounted(() => {
  chartInstance?.dispose();
});
</script>