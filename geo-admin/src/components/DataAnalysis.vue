<template>
  <div class="analysis-view">
    <div class="analysis-grid">
      <div class="data-card card-primary">
        <div class="card-top">
          <h4>累计商品登记</h4>
          <span class="card-badge success">登记中</span>
        </div>
        <div class="val">{{ stats.total_products }} <small>件</small></div>
        <div class="footer">今日新增: <span class="green">{{ stats.today_registered }}</span></div>
      </div>

      <div class="data-card card-secondary">
        <div class="card-top">
          <h4>累计扫码总量</h4>
          <span class="card-badge info">流转中</span>
        </div>
        <div class="val">{{ stats.total_scans }} <small>次</small></div>
        <div class="footer">今日动态: <span class="blue">{{ stats.today_scans }}</span></div>
      </div>

      <div class="data-card card-warning">
        <div class="card-top">
          <h4>系统风险拦截</h4>
          <span class="card-badge danger">重点关注</span>
        </div>
        <div class="val red">{{ stats.today_rejected }} <small>起</small></div>
        <div class="footer">异常告警: <span class="red">{{ stats.today_anomalies }}</span></div>
      </div>
    </div>

    <div class="charts-row">
      <div class="chart-box main-chart">
        <div class="chart-head">
          <h5>业务量对比趋势 (7日)</h5>
          <span class="chart-subtitle">登记 / 扫码变化对比</span>
        </div>
        <div id="reg-scan-chart" class="chart-container"></div>
      </div>

      <div class="chart-box pie-chart">
        <div class="chart-head">
          <h5>异常分布占比</h5>
          <span class="chart-subtitle">带图注的环形图</span>
        </div>
        <div id="type-pie-chart" class="chart-container"></div>
      </div>
    </div>

    <div class="table-section">
      <div class="panel-header-alt">
        <div class="panel-title-alt">产区信誉度实时监控 (基于后端异常数据自动评估)</div>
      </div>

      <div class="table-wrapper">
        <table class="analysis-table">
          <thead>
            <tr>
              <th>产区名称</th><th>产品类型</th><th>今日登记</th><th>风险状态</th><th>综合信誉评分</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in computedRegions" :key="item.name">
              <td>{{ item.name }}</td>
              <td><span class="product-tag">{{ item.type }}</span></td>
              <td>{{ item.todayCount }}</td>
              <td>
                <span :class="['status-tag', item.riskLevel.class]">
                  {{ item.riskLevel.text }}
                </span>
              </td>
              <td class="score-cell">
                <div class="score-bar">
                  <div class="fill" :style="{ width: item.score + '%', background: item.riskLevel.color }"></div>
                </div>
                <span class="score-num">{{ item.score.toFixed(1) }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, watch, onUnmounted } from 'vue';
import * as echarts from 'echarts';

const props = defineProps(['stats', 'trendData', 'regionRawData']);
let trendChart = null, pieChart = null;
let resizeHandler = null;

// ==========================================
// API 接口预留：跳转 AI 分析页面
// ==========================================
const generateAIReport = () => {
  console.log('正在调用 AI 报告生成接口...');
  // 预留接口地址：可以将当前 stats 或 trendData 作为参数传给 AI 页面
  const AI_ANALYSIS_PAGE_URL = '/ai-analysis-report'; // 这里替换成你同学设计的页面路由

  // 模拟跳转
  window.location.href = AI_ANALYSIS_PAGE_URL;

  /* // 如果是内部路由跳转，可以使用 vue-router:
  // router.push({ name: 'AIReport', params: { data: props.stats } });
  */
};

// 评分逻辑：根据异常数和异常率动态计算
const computedRegions = computed(() => {
  const data = props.regionRawData.length ? props.regionRawData : [
    { name: '待加载...', type: '-', todayCount: 0, anomalies: 0, totalScans: 1 }
  ];
  return data.map(item => {
    const anomalyRate = item.anomalies / (item.totalScans || 1);
    let score = Math.max(0, 100 - (item.anomalies * 8) - (anomalyRate * 200));

    let risk = { text: '极高可信', class: 'safe', color: '#52c41a' };
    if (score < 90 && score >= 70) risk = { text: '风险预警', class: 'warn', color: '#ffa940' };
    else if (score < 70) risk = { text: '高危拦截', class: 'danger', color: '#ff4d4f' };

    return { ...item, score, riskLevel: risk };
  });
});

const renderCharts = () => {
  const tDom = document.getElementById('reg-scan-chart');
  if (tDom) {
    if (!trendChart) trendChart = echarts.init(tDom);
    trendChart.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: {
        data: ['登记', '扫码'],
        top: 6,
        left: 'center',
        icon: 'roundRect',
        itemWidth: 14,
        itemHeight: 8,
        textStyle: { color: '#7b8794', fontSize: 12 }
      },
      grid: { left: '4%', right: '4%', top: '22%', bottom: '6%', containLabel: true },
      xAxis: {
        type: 'category',
        data: props.trendData.dates,
        axisLine: { lineStyle: { color: '#d6dbe3' } },
        axisTick: { show: false },
        axisLabel: { color: '#637085' }
      },
      yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: '#edf1f7', type: 'dashed' } },
        axisLabel: { color: '#637085' }
      },
      series: [
        {
          name: '登记',
          type: 'bar',
          data: props.trendData.registrations,
          barWidth: 14,
          itemStyle: {
            borderRadius: [6, 6, 0, 0],
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#60a5fa' },
              { offset: 1, color: '#2563eb' }
            ])
          }
        },
        {
          name: '扫码',
          type: 'line',
          data: props.trendData.scans,
          smooth: true,
          symbol: 'circle',
          symbolSize: 8,
          lineStyle: { width: 3, color: '#14b8a6' },
          itemStyle: { color: '#14b8a6' },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(20,184,166,0.25)' },
              { offset: 1, color: 'rgba(20,184,166,0.02)' }
            ])
          }
        }
      ]
    });
  }

  const pDom = document.getElementById('type-pie-chart');
  if (pDom) {
    if (!pieChart) pieChart = echarts.init(pDom);
    pieChart.setOption({
      tooltip: {
        trigger: 'item',
        formatter: '{b}<br/>数量：{c}<br/>占比：{d}%'
      },
      legend: {
        orient: 'vertical',
        right: 10,
        top: 'center',
        icon: 'circle',
        itemWidth: 10,
        itemHeight: 10,
        itemGap: 14,
        textStyle: { color: '#5f6b7a', fontSize: 12 }
      },
      series: [{
        type: 'pie',
        radius: ['48%', '70%'],
        center: ['38%', '50%'],
        avoidLabelOverlap: true,
        label: {
          show: true,
          color: '#475569',
          formatter: '{b}\n{d}%',
          fontSize: 12
        },
        labelLine: {
          show: true,
          length: 12,
          length2: 8,
          lineStyle: { color: '#94a3b8' }
        },
        data: [
          { value: props.stats.today_rejected, name: '拦截', itemStyle: { color: '#ff4d4f' } },
          { value: props.stats.today_anomalies, name: '异常', itemStyle: { color: '#ffa940' } },
          { value: props.stats.today_scans, name: '正常', itemStyle: { color: '#1e90ff' } }
        ]
      }]
    });
  }
};

onMounted(() => {
  renderCharts();
  resizeHandler = () => {
    trendChart?.resize();
    pieChart?.resize();
  };
  window.addEventListener('resize', resizeHandler);
});
watch(() => [props.stats, props.trendData], () => renderCharts(), { deep: true });

onUnmounted(() => {
  if (resizeHandler) window.removeEventListener('resize', resizeHandler);
  trendChart?.dispose();
  pieChart?.dispose();
  trendChart = null;
  pieChart = null;
});
</script>

<style scoped>
/* 页面容器：让内容更饱满一些 */
.analysis-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 8px 6px 6px;
  box-sizing: border-box;
}

.analysis-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  flex-shrink: 0;
}

.data-card {
  min-height: 132px;
  background: linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(248,250,252,0.96) 100%);
  border: 1px solid rgba(226,232,240,0.95);
  padding: 18px 18px 16px;
  border-radius: 20px;
  box-shadow: 0 14px 30px rgba(15, 23, 42, 0.08);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  position: relative;
  overflow: hidden;
}

.data-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  width: 100%;
  height: 4px;
  background: linear-gradient(90deg, rgba(37,99,235,0.95), rgba(20,184,166,0.9));
}

.card-primary::before { background: linear-gradient(90deg, #2563eb, #60a5fa); }
.card-secondary::before { background: linear-gradient(90deg, #14b8a6, #2dd4bf); }
.card-warning::before { background: linear-gradient(90deg, #f59e0b, #fb7185); }

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.data-card h4 {
  margin: 0;
  color: #556173;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.3px;
}

.card-badge {
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 999px;
  font-weight: 700;
  white-space: nowrap;
}

.card-badge.success {
  color: #15803d;
  background: rgba(34,197,94,0.12);
}

.card-badge.info {
  color: #0369a1;
  background: rgba(14,165,233,0.12);
}

.card-badge.danger {
  color: #b91c1c;
  background: rgba(239,68,68,0.12);
}

.val {
  font-size: 34px;
  font-weight: 800;
  margin: 8px 0 2px;
  letter-spacing: 0.2px;
  line-height: 1;
}

.val small {
  font-size: 14px;
  font-weight: 600;
  color: #94a3b8;
}

.val.red { color: #ef4444; }
.footer { font-size: 12px; color: #64748b; }

.footer .green { color: #16a34a; font-weight: 700; }
.footer .blue { color: #1e90ff; font-weight: 700; }
.footer .red { color: #ef4444; font-weight: 700; }

/* 图表区：增高一点，视觉更舒服 */
.charts-row {
  display: grid;
  grid-template-columns: 1.2fr 0.9fr;
  gap: 16px;
  height: 300px;
  flex-shrink: 0;
}

.main-chart { min-width: 0; }
.pie-chart { min-width: 0; }

.chart-box {
  background: linear-gradient(180deg, rgba(255,255,255,0.9) 0%, rgba(250,252,255,0.92) 100%);
  border: 1px solid rgba(226,232,240,0.95);
  padding: 14px 16px 12px;
  border-radius: 20px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 14px 28px rgba(15, 23, 42, 0.07);
  min-height: 0;
}

.chart-head {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 6px;
}

.chart-container {
  flex: 1;
  min-height: 0;
}

h5 {
  color: #1e3a8a;
  margin: 0;
  font-size: 15px;
  border-left: 4px solid #1e90ff;
  padding-left: 10px;
  font-weight: 800;
}

.chart-subtitle {
  font-size: 12px;
  color: #94a3b8;
  padding-left: 14px;
}

/* 表格区：自适应剩余高度 */
.table-section {
  background: rgba(255,255,255,0.96);
  border: 1px solid rgba(226,232,240,0.95);
  padding: 16px;
  border-radius: 20px;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  box-shadow: 0 14px 28px rgba(15, 23, 42, 0.07);
}

.panel-header-alt {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.panel-title-alt {
  color: #1e3a8a;
  font-size: 15px;
  font-weight: 800;
}

/* AI 按钮样式 */
.ai-report-btn {
  background: linear-gradient(135deg, #1e90ff 0%, #0052cc 100%);
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 999px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  gap: 6px;
  box-shadow: 0 8px 18px rgba(30, 144, 255, 0.22);
}

.ai-report-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(30, 144, 255, 0.32);
  filter: brightness(1.05);
}

.ai-icon { font-size: 14px; }

.table-wrapper { flex: 1; overflow-y: auto; }
.analysis-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.analysis-table th {
  position: sticky;
  top: 0;
  background: #f8fafc;
  text-align: left;
  color: #64748b;
  padding: 10px 10px;
  border-bottom: 1px solid #e2e8f0;
  z-index: 1;
}
.analysis-table td { padding: 11px 10px; border-bottom: 1px solid #eef2f7; }
.analysis-table tbody tr:hover { background: rgba(59,130,246,0.04); }

.status-tag { padding: 3px 9px; border-radius: 999px; font-size: 11px; border: 1px solid; }
.status-tag.safe { color: #52c41a; border-color: rgba(82,196,26,0.35); background: rgba(82,196,26,0.06); }
.status-tag.warn { color: #ffa940; border-color: rgba(255,169,64,0.35); background: rgba(255,169,64,0.06); }
.status-tag.danger { color: #ff4d4f; border-color: rgba(255,77,79,0.35); background: rgba(255,77,79,0.06); }

.score-cell { display: flex; align-items: center; gap: 10px; }
.score-bar { width: 72px; height: 6px; background: #e5e7eb; border-radius: 999px; overflow: hidden; }
.fill { height: 100%; transition: width 0.5s; border-radius: 999px; }
.score-num { font-weight: 700; font-family: monospace; width: 42px; color: #334155; }
.product-tag { background: rgba(30,144,255,0.1); color: #1e90ff; padding: 2px 8px; border-radius: 999px; }

/* 针对窄屏幕的缩放优化 */
@media screen and (max-height: 800px) {
  .charts-row { height: 250px; }
  .val { font-size: 30px; }
  .data-card { min-height: 120px; padding: 14px 14px 12px; }
}
</style>