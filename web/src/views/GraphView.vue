<template>
  <div class="graph-view">
    <div class="graph-toolbar">
      <span class="graph-title">知识图谱</span>
      <el-radio-group v-model="filterType" size="small" @change="updateGraph">
        <el-radio-button value="all">全部</el-radio-button>
        <el-radio-button value="entity">实体</el-radio-button>
        <el-radio-button value="concept">概念</el-radio-button>
        <el-radio-button value="source">原文</el-radio-button>
        <el-radio-button value="index">索引</el-radio-button>
      </el-radio-group>
      <el-select v-model="layoutName" size="small" style="width: 120px" @change="runLayout">
        <el-option label="力导向" value="cose" />
        <el-option label="环形" value="concentric" />
        <el-option label="圆形" value="circle" />
        <el-option label="网格" value="grid" />
      </el-select>
      <el-button size="small" @click="loadGraph">
        <el-icon><Refresh /></el-icon>
      </el-button>
      <div class="legend">
        <span class="legend-dot entity" />实体
        <span class="legend-dot concept" />概念
        <span class="legend-dot source" />原文
        <span class="legend-dot index" />索引
      </div>
    </div>

    <div ref="cyEl" class="graph-canvas" v-loading="loading" />

    <div v-if="hoveredNode" class="node-tooltip" :style="tooltipStyle">
      <div class="tooltip-name">{{ hoveredNode.label }}</div>
      <div class="tooltip-desc" v-if="hoveredNode.description">{{ hoveredNode.description }}</div>
      <div class="tooltip-hint">点击查看详情</div>
    </div>

    <el-empty v-if="!loading && !rawGraphData" description="图谱数据还未生成，请先运行流水线" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import cytoscape from 'cytoscape'
import { wikiApi } from '../api'

const route = useRoute()
const router = useRouter()
const cyEl = ref<HTMLElement | null>(null)
const loading = ref(false)
const filterType = ref('all')
const layoutName = ref('cose')
const rawGraphData = ref<any>(null)

const kbId = computed(() => route.params.kbId as string)

let cy: cytoscape.Core | null = null
const hoveredNode = ref<{ label: string; description?: string } | null>(null)
const tooltipStyle = ref<Record<string, string>>({})

// ── 颜色配置 ──
const COLORS = {
  entity: { bg: '#409EFF', border: '#337ECC', text: '#fff' },
  concept: { bg: '#67C23A', border: '#529D2C', text: '#fff' },
  source: { bg: '#9B59B6', border: '#7D3C98', text: '#fff' },
  index: { bg: '#E6A23C', border: '#CF9236', text: '#fff' },
  edge: '#c0c4cc',
  edgeHighlight: '#409EFF',
}

async function loadGraph() {
  if (!kbId.value) return
  loading.value = true
  try {
    const resp = await wikiApi.getGraph(kbId.value)
    rawGraphData.value = resp.data
    await nextTick()
    updateGraph()
  } catch (e) {
    rawGraphData.value = null
  } finally {
    loading.value = false
  }
}

function updateGraph() {
  if (!cy || !rawGraphData.value) return

  const { nodes, edges } = rawGraphData.value
  const filtered = filterType.value === 'all'
    ? nodes
    : nodes.filter((n: any) => n.type === filterType.value)

  const filteredIds = new Set(filtered.map((n: any) => n.id))
  const filteredEdges = edges.filter((e: any) => filteredIds.has(e.source) && filteredIds.has(e.target))

  // 转换为 cytoscape 格式
  const cyNodes = filtered.map((n: any) => ({
    group: 'nodes' as const,
    data: {
      id: n.id,
      label: n.label,
      type: n.type,
      category: n.category || 'other',
      description: n.description || '',
    },
  }))

  const cyEdges = filteredEdges.map((e: any, i: number) => ({
    group: 'edges' as const,
    data: {
      id: `e${i}`,
      source: e.source,
      target: e.target,
    },
  }))

  cy.elements().remove()
  cy.add([...cyNodes, ...cyEdges])
  runLayout()
}

function runLayout() {
  if (!cy) return

  const layoutConfigs: Record<string, any> = {
    cose: {
      name: 'cose',
      idealEdgeLength: 120,
      nodeOverlap: 20,
      refresh: 20,
      fit: true,
      padding: 40,
      randomize: false,
      componentSpacing: 60,
      nodeRepulsion: 4000,
      edgeElasticity: 100,
      nestingFactor: 5,
      gravity: 0.25,
      numIter: 1000,
      animate: true,
      animationDuration: 800,
    },
    concentric: {
      name: 'concentric',
      concentric: (node: any) => {
        const t = node.data('type')
        if (t === 'index') return 3
        if (t === 'entity' || t === 'concept') return 2
        return 1
      },
      levelWidth: () => 2,
      fit: true,
      padding: 40,
      animate: true,
      animationDuration: 600,
    },
    circle: {
      name: 'circle',
      fit: true,
      padding: 40,
      animate: true,
      animationDuration: 600,
    },
    grid: {
      name: 'grid',
      fit: true,
      padding: 40,
      animate: true,
      animationDuration: 600,
    },
  }

  cy.layout(layoutConfigs[layoutName.value] || layoutConfigs.cose).run()
}

function initCytoscape() {
  if (!cyEl.value) return

  cy = cytoscape({
    container: cyEl.value,
    style: [
      // 实体节点
      {
        selector: 'node[type="entity"]',
        style: {
          'background-color': COLORS.entity.bg,
          'border-color': COLORS.entity.border,
          'border-width': 2,
          'shape': 'round-rectangle',
          'width': 'label',
          'height': 40,
          'padding': '12px',
          'label': 'data(label)',
          'font-size': '13px',
          'font-weight': '600',
          'color': COLORS.entity.text,
          'text-valign': 'center',
          'text-halign': 'center',
          'text-wrap': 'ellipsis',
          'text-max-width': '120px',
          'overlay-padding': 4,
          'overlay-opacity': 0,
          'transition-property': 'background-color, border-color, width, height',
          'transition-duration': '0.2s',
        } as any,
      },
      // 概念节点
      {
        selector: 'node[type="concept"]',
        style: {
          'background-color': COLORS.concept.bg,
          'border-color': COLORS.concept.border,
          'border-width': 2,
          'shape': 'round-rectangle',
          'width': 'label',
          'height': 40,
          'padding': '12px',
          'label': 'data(label)',
          'font-size': '13px',
          'font-weight': '600',
          'color': COLORS.concept.text,
          'text-valign': 'center',
          'text-halign': 'center',
          'text-wrap': 'ellipsis',
          'text-max-width': '120px',
          'overlay-padding': 4,
          'overlay-opacity': 0,
          'transition-property': 'background-color, border-color, width, height',
          'transition-duration': '0.2s',
        } as any,
      },
      // 原文节点
      {
        selector: 'node[type="source"]',
        style: {
          'background-color': COLORS.source.bg,
          'border-color': COLORS.source.border,
          'border-width': 2,
          'shape': 'round-rectangle',
          'width': 'label',
          'height': 36,
          'padding': '10px',
          'label': 'data(label)',
          'font-size': '12px',
          'font-weight': '500',
          'color': COLORS.source.text,
          'text-valign': 'center',
          'text-halign': 'center',
          'text-wrap': 'ellipsis',
          'text-max-width': '100px',
          'overlay-padding': 4,
          'overlay-opacity': 0,
          'transition-property': 'background-color, border-color, width, height',
          'transition-duration': '0.2s',
        } as any,
      },
      // 索引节点
      {
        selector: 'node[type="index"]',
        style: {
          'background-color': COLORS.index.bg,
          'border-color': COLORS.index.border,
          'border-width': 3,
          'shape': 'round-rectangle',
          'width': 'label',
          'height': 44,
          'padding': '14px',
          'label': 'data(label)',
          'font-size': '14px',
          'font-weight': '700',
          'color': COLORS.index.text,
          'text-valign': 'center',
          'text-halign': 'center',
          'overlay-padding': 4,
          'overlay-opacity': 0,
          'transition-property': 'background-color, border-color, width, height',
          'transition-duration': '0.2s',
        } as any,
      },
      // 边
      {
        selector: 'edge',
        style: {
          'width': 1.5,
          'line-color': COLORS.edge,
          'target-arrow-color': COLORS.edge,
          'target-arrow-shape': 'triangle',
          'arrow-scale': 0.8,
          'curve-style': 'bezier',
          'opacity': 0.5,
          'transition-property': 'line-color, opacity, width',
          'transition-duration': '0.2s',
        } as any,
      },
      // hover 高亮
      {
        selector: 'node:active',
        style: {
          'overlay-opacity': 0.1,
        } as any,
      },
      // 选中状态
      {
        selector: '.highlighted',
        style: {
          'background-color': '#E6A23C',
          'border-color': '#D4910A',
          'z-index': 10,
        } as any,
      },
      {
        selector: 'edge.highlighted',
        style: {
          'line-color': COLORS.edgeHighlight,
          'target-arrow-color': COLORS.edgeHighlight,
          'opacity': 1,
          'width': 2.5,
        } as any,
      },
      // 非高亮（淡化）
      {
        selector: '.faded',
        style: {
          'opacity': 0.15,
        } as any,
      },
    ],
    layout: { name: 'preset' },
    minZoom: 0.3,
    maxZoom: 3,
    wheelSensitivity: 0.3,
  })

  // Hover 效果
  cy.on('mouseover', 'node', (e) => {
    const node = e.target
    node.addClass('highlighted')
    node.connectedEdges().addClass('highlighted')
    node.neighborhood('node').addClass('highlighted')
    // 淡化其他元素
    cy!.elements().not(node).not(node.connectedEdges()).not(node.neighborhood('node')).addClass('faded')

    const pos = node.renderedPosition()
    hoveredNode.value = {
      label: node.data('label'),
      description: node.data('description'),
    }
    tooltipStyle.value = {
      left: `${pos.x + 20}px`,
      top: `${pos.y - 20}px`,
    }
  })

  cy.on('mouseout', 'node', (e) => {
    cy!.elements().removeClass('highlighted').removeClass('faded')
    hoveredNode.value = null
  })

  // 点击导航
  cy.on('tap', 'node', (e) => {
    const node = e.target
    const id = node.data('id')
    const type = node.data('type')
    if (type === 'index') {
      router.push({ name: 'Wiki', params: { kbId: kbId.value } })
    } else {
      const [_, name] = id.split(':')
      if (type && name) {
        router.push({ name: 'WikiPage', params: { kbId: kbId.value, pageType: type, name } })
      }
    }
  })
}

function handleResize() {
  cy?.resize()
}

onMounted(() => {
  initCytoscape()
  loadGraph()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  cy?.destroy()
})

watch(kbId, loadGraph)
</script>

<style scoped>
.graph-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  position: relative;
}
.graph-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--el-border-color);
  flex-shrink: 0;
  background: var(--el-bg-color);
}
.graph-title { font-size: 15px; font-weight: 600; }
.graph-canvas {
  flex: 1;
  width: 100%;
  background: var(--el-fill-color-blank);
}
.legend { display: flex; align-items: center; margin-left: auto; font-size: 13px; gap: 12px; }
.legend-dot {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}
.legend-dot::before {
  content: '';
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 3px;
}
.legend-dot.entity::before { background: #409EFF; }
.legend-dot.concept::before { background: #67C23A; }
.legend-dot.source::before { background: #9B59B6; }
.legend-dot.index::before { background: #E6A23C; }

.node-tooltip {
  position: absolute;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 10px 14px;
  max-width: 260px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.12);
  pointer-events: none;
  z-index: 100;
}
.tooltip-name {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 4px;
}
.tooltip-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}
.tooltip-hint {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
  margin-top: 6px;
}
</style>
