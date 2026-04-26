<template>
  <div class="topo-container">
    <div class="topo-controls">
      <el-tag v-if="loading" type="info" size="small">加载中...</el-tag>
      <el-tag v-else :type="nodes.length > 0 ? 'success' : 'info'" size="small">
        {{ nodes.length }} 节点 / {{ links.length }} 链路
      </el-tag>
      <el-button size="small" text @click="refreshData" :disabled="loading">
        <el-icon><Refresh /></el-icon>
      </el-button>
    </div>
    <div ref="chartRef" class="topo-chart" v-loading="loading"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { api } from '@/stores'
import * as echarts from 'echarts'

const chartRef = ref(null)
const loading = ref(false)
const nodes = ref([])
const links = ref([])
let chart = null

function buildGraph(raw) {
  const graphNodes = []
  const graphLinks = []

  // dedup by id
  const seen = new Set()
  for (const n of raw.nodes || []) {
    if (!seen.has(n.id)) {
      seen.add(n.id)
      graphNodes.push({
        id: n.id,
        name: n.name || n.ip || n.id,
        category: n.group || 'device',
        symbolSize: n.symbolSize || 25,
        itemStyle: n.online === false ? { color: '#F56C6C' } : undefined,
        label: { show: true, fontSize: 10, color: n.online === false ? '#F56C6C' : '#ccc' },
      })
    }
  }

  for (const l of raw.links || []) {
    graphLinks.push({
      source: l.source,
      target: l.target,
      lineStyle: {
        color: l.type === 'offline' ? '#555' : (l.state === 'up' ? '#409EFF' : '#888'),
        width: l.type === 'internal' ? 2 : 1,
        curveness: 0.3,
        opacity: l.type === 'offline' ? 0.3 : 0.8,
      },
    })
  }

  return { nodes: graphNodes, links: graphLinks }
}

function initChart() {
  if (!chartRef.value) return
  if (chart) chart.dispose()

  chart = echarts.init(chartRef.value, null, { renderer: 'canvas' })

  const categories = [
    { name: 'router', itemStyle: { color: '#409EFF' } },
    { name: 'interface', itemStyle: { color: '#67C23A' } },
    { name: 'device', itemStyle: { color: '#E6A23C' } },
    { name: 'offline', itemStyle: { color: '#F56C6C' } },
  ]

  const option = {
    title: { show: false },
    tooltip: { trigger: 'item', formatter: '{b}' },
    legend: {
      data: categories.map(c => c.name),
      textStyle: { color: '#999' },
      bottom: 0,
      left: 'center',
    },
    series: [{
      type: 'graph',
      layout: 'force',
      force: {
        repulsion: 300,
        edgeLength: [80, 200],
        layoutAnimation: true,
        friction: 0.2,
      },
      roam: true,
      draggable: true,
      data: graphData.value.nodes,
      links: graphData.value.links,
      categories,
      label: { show: true, position: 'bottom', fontSize: 10 },
      edgeSymbol: ['none', 'arrow'],
      edgeSymbolSize: [0, 8],
      lineStyle: { color: 'source', opacity: 0.6, width: 1.5 },
      emphasis: {
        focus: 'adjacency',
        lineStyle: { width: 3 },
      },
    }],
  }

  chart.setOption(option)
  chart.on('click', function (params) {
    if (params.dataType === 'node') {
      const node = params.data
      let info = `节点: ${node.name}\n类型: ${node.category}`
      if (node.itemStyle?.color === '#F56C6C') info += '\n状态: 离线'
      ElMessage.info(info)
    }
  })
}

const graphData = ref({ nodes: [], links: [] })

async function refreshData() {
  loading.value = true
  try {
    const res = await api.get('/topology/full')
    nodes.value = res.data.nodes || []
    links.value = res.data.links || []
    graphData.value = buildGraph(res.data)
    nextTick(() => {
      if (chart) {
        chart.setOption({
          series: [{ data: graphData.value.nodes, links: graphData.value.links }],
        })
      } else {
        initChart()
      }
    })
  } catch (e) {
    ElMessage.error('获取拓扑数据失败')
  }
  loading.value = false
}

function handleResize() {
  chart?.resize()
}

onMounted(() => {
  nextTick(() => {
    initChart()
    refreshData()
  })
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
})
</script>

<style scoped>
.topo-container {
  background: #141414;
  border: 1px solid #222;
  border-radius: 8px;
  overflow: hidden;
}
.topo-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid #222;
}
.topo-chart {
  width: 100%;
  height: 400px;
}
</style>
