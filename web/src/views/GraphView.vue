<template>
  <div class="graph-view">
    <div class="graph-toolbar">
      <span class="graph-title">知识图谱</span>
      <el-radio-group v-model="filterType" size="small" @change="updateChart">
        <el-radio-button value="all">全部</el-radio-button>
        <el-radio-button value="entity">实体</el-radio-button>
        <el-radio-button value="concept">概念</el-radio-button>
      </el-radio-group>
      <el-button size="small" @click="loadGraph">
        <el-icon><Refresh /></el-icon>
      </el-button>
      <div class="legend">
        <span class="legend-dot entity" />实体
        <span class="legend-dot concept" style="margin-left: 12px" />概念
      </div>
    </div>

    <div ref="chartEl" class="graph-canvas" v-loading="loading" />

    <el-empty v-if="!loading && !graphData" description="图谱数据还未生成，请先运行流水线" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { wikiApi } from '../api'

const route = useRoute()
const router = useRouter()
const chartEl = ref<HTMLElement | null>(null)
const loading = ref(false)
const filterType = ref('all')
const graphData = ref<any>(null)

let chart: echarts.ECharts | null = null
const kbId = computed(() => route.params.kbId as string)

async function loadGraph() {
  if (!kbId.value) return
  loading.value = true
  try {
    const resp = await wikiApi.getGraph(kbId.value)
    graphData.value = resp.data
    updateChart()
  } catch (e) {
    graphData.value = null
  } finally {
    loading.value = false
  }
}

function updateChart() {
  if (!chart || !graphData.value) return

  const { nodes, edges } = graphData.value
  const filtered = filterType.value === 'all'
    ? nodes
    : nodes.filter((n: any) => n.type === filterType.value)

  const filteredIds = new Set(filtered.map((n: any) => n.id))
  const filteredEdges = edges.filter((e: any) => filteredIds.has(e.source) && filteredIds.has(e.target))

  const option = {
    backgroundColor: 'transparent',
    series: [{
      type: 'graph',
      layout: 'force',
      data: filtered.map((n: any) => ({
        id: n.id,
        name: n.label,
        category: n.type === 'entity' ? 0 : 1,
        symbolSize: 30,
        label: { show: true, fontSize: 11 },
        tooltip: { formatter: `${n.label}\n${n.description || ''}` },
      })),
      links: filteredEdges.map((e: any) => ({
        source: e.source,
        target: e.target,
        lineStyle: { opacity: 0.4, width: 1 },
      })),
      categories: [
        { name: '实体', itemStyle: { color: '#409EFF' } },
        { name: '概念', itemStyle: { color: '#67C23A' } },
      ],
      force: { repulsion: 200, gravity: 0.1, edgeLength: [80, 150] },
      roam: true,
      draggable: true,
      emphasis: { focus: 'adjacency', lineStyle: { width: 3 } },
    }],
  }

  chart.setOption(option)
}

function initChart() {
  if (chartEl.value) {
    chart = echarts.init(chartEl.value)
    chart.on('click', (params: any) => {
      if (params.dataType === 'node' && params.data?.id) {
        const [type, name] = params.data.id.split(':')
        if (type && name) {
          router.push({ name: 'WikiPage', params: { kbId: kbId.value, pageType: type, name } })
        }
      }
    })
  }
}

function handleResize() {
  chart?.resize()
}

onMounted(() => {
  initChart()
  loadGraph()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
})

watch(kbId, loadGraph)
</script>

<style scoped>
.graph-view {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.graph-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--el-border-color);
  flex-shrink: 0;
}
.graph-title { font-size: 15px; font-weight: 600; }
.graph-canvas {
  flex: 1;
  width: 100%;
}
.legend { display: flex; align-items: center; margin-left: auto; font-size: 13px; }
.legend-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-right: 4px;
}
.legend-dot.entity { background: #409EFF; }
.legend-dot.concept { background: #67C23A; }
</style>
