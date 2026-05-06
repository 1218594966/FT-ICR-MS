<template>
  <div class="task-detail" v-loading="loading">
    <div class="header-row">
      <div>
        <h1 class="page-title">{{ task?.filename || pageText.title }}</h1>
        <p class="page-subtitle">
          <el-tag :type="statusType" effect="dark" size="small">{{ statusLabel }}</el-tag>
          <el-tag v-if="task?.task_type === 'dpr'" type="warning" effect="plain" size="small">DPR 对比</el-tag>
          <el-tag v-else type="info" effect="plain" size="small">常规分析</el-tag>
          <span v-if="task?.created_at" class="time-text">创建于 {{ formatTime(task.created_at) }}</span>
        </p>
      </div>
      <div class="header-actions">
        <el-button v-if="task?.status === 'success'" type="primary" @click="exportCSV">
          <el-icon><Download /></el-icon> 导出 CSV
        </el-button>
        <el-button v-if="task?.status === 'success' && task?.task_type !== 'dpr'" @click="exportWeightedCSV">
          <el-icon><Download /></el-icon> 加权平均表
        </el-button>
        <el-button type="danger" plain @click="handleDelete">
          <el-icon><Delete /></el-icon> 删除
        </el-button>
      </div>
    </div>

    <!-- Running Progress -->
    <section v-if="task?.status === 'running' || task?.status === 'pending'" class="section card-glass">
      <h2 class="section-title"><el-icon class="is-loading"><Loading /></el-icon> 分析进行中</h2>
      <el-progress :percentage="task?.progress || 0" :stroke-width="14" :color="progressColors" :format="(p) => p.toFixed(0) + '%'" />
      <div class="current-step">
        <span v-if="task?.current_step">当前步骤: {{ mapStepName(task.current_step) }}</span>
        <span v-else>等待中...</span>
      </div>
      <div class="step-timeline" v-if="task?.task_type !== 'dpr'">
        <div v-for="(name, i) in stepNames" :key="i" class="timeline-item" :class="{ active: isCurrentStep(i), done: isDoneStep(i) }">
          <div class="timeline-dot" /><span>{{ name }}</span>
        </div>
      </div>
    </section>

    <!-- Summary Stats (only for regular analysis) -->
    <div class="stats-row" v-if="task?.status === 'success' && task?.task_type !== 'dpr'">
      <div class="stat-card" v-for="s in summaryStats" :key="s.label">
        <span class="stat-val">{{ s.value }}</span>
        <span class="stat-lbl">{{ s.label }}</span>
      </div>
    </div>

    <!-- DPR Result Table -->
    <section v-if="task?.status === 'success' && task?.task_type === 'dpr'" class="section card-glass">
      <h2 class="section-title"><el-icon><Grid /></el-icon> DPR 对比结果 (前20行)</h2>
      <el-table :data="dprTableData.slice(0, 20)" class="dark-table" stripe max-height="600">
        <el-table-column prop="MolForm" label="分子式" min-width="150" />
        <el-table-column prop="Col1" label="样本1" width="80" align="center" />
        <el-table-column prop="Col2" label="样本2" width="80" align="center" />
        <el-table-column prop="NewCol" label="DPR分类" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.NewCol === 'R' ? 'success' : row.NewCol === 'D' ? 'danger' : 'primary'" size="small">
              {{ row.NewCol === 'R' ? 'R (残留)' : row.NewCol === 'D' ? 'D (消失)' : row.NewCol === 'P' ? 'P (新增)' : '-' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="H/C" label="H/C" width="90" align="center">
          <template #default="{ row }">{{ (row['H/C'] || 0).toFixed(3) }}</template>
        </el-table-column>
        <el-table-column prop="O/C" label="O/C" width="90" align="center">
          <template #default="{ row }">{{ (row['O/C'] || 0).toFixed(3) }}</template>
        </el-table-column>
      </el-table>
      <div v-if="dprTableData.length > 20" class="table-tip">
        <el-text type="info" size="small">共 {{ dprTableData.length }} 条，仅显示前20条。下载完整CSV获取全部数据。</el-text>
      </div>
    </section>

    <!-- Charts (only for regular analysis) -->
    <section v-if="task?.status === 'success' && task?.task_type !== 'dpr'" class="section card-glass">
      <div class="chart-toolbar">
        <el-select v-model="chartFont" size="small" style="width:120px" @change="rerenderChart">
          <el-option label="Times New Roman" value="Times New Roman" />
          <el-option label="Arial" value="Arial" />
          <el-option label="SimSun" value="SimSun" />
        </el-select>
        <el-input-number v-model="chartFontSize" :min="8" :max="24" size="small" style="width:100px" @change="rerenderChart" />
        <span class="toolbar-label">字体大小</span>
        <el-divider direction="vertical" />
        <el-button size="small" type="primary" @click="exportChartPDF"><el-icon><Document /></el-icon> PDF</el-button>
        <el-button size="small" @click="exportChartTIF"><el-icon><Picture /></el-icon> TIF</el-button>
      </div>

      <!-- VK custom params -->
      <div v-if="activeTab === 'vankrevelen'" class="vk-params">
        <el-input-number v-model="vkParams.ocMin" :min="0" :max="2" :step="0.1" size="small" controls-position="right" />
        <span>≤ O/C ≤</span>
        <el-input-number v-model="vkParams.ocMax" :min="0" :max="2" :step="0.1" size="small" controls-position="right" />
        <el-divider direction="vertical" />
        <el-input-number v-model="vkParams.hcMin" :min="0" :max="3" :step="0.1" size="small" controls-position="right" />
        <span>≤ H/C ≤</span>
        <el-input-number v-model="vkParams.hcMax" :min="0" :max="3" :step="0.1" size="small" controls-position="right" />
        <el-divider direction="vertical" />
        <span>散点大小</span>
        <el-input-number v-model="vkParams.dotSize" :min="1" :max="100" :step="1" size="small" controls-position="right" style="width:80px" />
        <el-divider direction="vertical" />
        <el-checkbox v-model="vkParams.showLabels">类别标签</el-checkbox>
        <el-checkbox v-model="vkParams.showBoundaries">边界框</el-checkbox>
        <el-button size="small" type="primary" @click="rerenderChart">更新</el-button>
      </div>

      <!-- Color customization for VK -->
      <div v-if="activeTab === 'vankrevelen'" class="vk-colors">
        <span class="toolbar-label">元素分类颜色:</span>
        <div v-for="(color, cat) in vkColors" :key="cat" class="color-item">
          <span class="color-label">{{ cat }}</span>
          <el-color-picker v-model="vkColors[cat]" size="small" @change="onColorChange" />
        </div>
      </div>

      <el-tabs v-model="activeTab" type="border-card" class="detail-tabs">
        <el-tab-pane label="质谱图" name="spectrum"><div ref="spectrumRef" class="chart-box" /></el-tab-pane>
        <el-tab-pane label="初步搜索误差" name="preliminary"><div ref="preliminaryRef" class="chart-box" /></el-tab-pane>
        <el-tab-pane label="Van Krevelen" name="vankrevelen">
          <div ref="vankrevelenRef" class="chart-box vk-preview">
            <img v-if="vkPreviewUrl" :src="vkPreviewUrl" alt="Van Krevelen" />
          </div>
        </el-tab-pane>
        <el-tab-pane label="化合物分类" name="class"><div ref="classRef" class="chart-box" /></el-tab-pane>
        <el-tab-pane label="加权平均指标" name="weighted"><div ref="weightedRef" class="chart-box" /></el-tab-pane>
      </el-tabs>
    </section>

    <!-- Steps Detail (only for regular analysis) -->
    <section v-if="task?.result?.steps && task?.task_type !== 'dpr'" class="section card-glass">
      <h2 class="section-title">各步骤详情</h2>
      <el-timeline>
        <el-timeline-item v-for="(step, key) in task.result.steps" :key="key" :type="step.status === 'success' ? 'success' : 'danger'" :timestamp="step.time ? step.time + 's' : ''" placement="top">
          <h4>{{ mapStepName(key) }}</h4>
          <p v-if="step.status === 'success'" class="step-data">{{ formatStepData(step.data) }}</p>
          <p v-else class="step-error">{{ step.error }}</p>
        </el-timeline-item>
      </el-timeline>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import { getTaskDetail, getTaskStatus, getChartData, getExportUrl, getVKPdfUrl, getVKSvgUrl, getVKTifUrl, getChartPdfUrl, getChartTifUrl, deleteTask } from '../api/analysis'
import api from '../api/index'
import { useI18n } from '../i18n'

const route = useRoute()
const router = useRouter()
const { lang } = useI18n()
const pageText = computed(() => lang.value === 'zh' ? { title: '任务详情' } : { title: 'Task Detail' })
const taskId = route.params.id

const task = ref(null)
const loading = ref(true)
const activeTab = ref('spectrum')
const chartFont = ref('Times New Roman')
const chartFontSize = ref(12)

const spectrumRef = ref(null)
const preliminaryRef = ref(null)
const vankrevelenRef = ref(null)
const classRef = ref(null)
const weightedRef = ref(null)

const vkParams = reactive({ ocMin: 0, ocMax: 1.2, hcMin: 0.25, hcMax: 2.5, dotSize: 15, showLabels: true, showBoundaries: true })
const vkColors = reactive({
  CHO: '#ffa07a', CHON: '#4169e1', CHOS: '#dc143c', CHONS: '#48d1cc',
  CHOP: '#a9a9a9', CHONP: '#a9a9a9', CHOPS: '#a9a9a9', CHONPS: '#a9a9a9',
  CHOCl: '#ffa500', CHONCl: '#4682b4', CHOSCl: '#8b0000', CHONSCl: '#008080', Other: '#a9a9a9',
})

let polling = null
let chartData = {}
let currentChart = null

const stepNames = ['峰检测', 'Kendrick 过滤', '初步搜索', '质量校准', '完整搜索', '指标计算', '氮规则', '化合物分类', '加权平均']
const stepKeys = ['peak_detection', 'kendrick_filter', 'preliminary_search', 'calibration', 'full_search', 'indices_calc', 'nitrogen_rule', 'classification', 'weighted_avg']
const progressColors = [{ color: '#3b82f6', percentage: 30 }, { color: '#06b6d4', percentage: 60 }, { color: '#10b981', percentage: 100 }]

const statusType = computed(() => ({ success: 'success', running: 'warning', failed: 'danger', pending: 'info' })[task.value?.status] || 'info')
const statusLabel = computed(() => ({ success: '成功', running: '运行中', failed: '失败', pending: '等待中' })[task.value?.status] || '-')

const isDprTask = computed(() => task.value?.task_type === 'dpr')

const dprTableData = ref([])
const dprRawData = ref(null)
const vkPreviewUrl = computed(() => {
  if (task.value?.status !== 'success' || task.value?.task_type === 'dpr') return ''
  return getVKSvgUrl(taskId, getVKParams())
})

const weightedAvgs = computed(() => task.value?.result?.steps?.weighted_avg?.data?.weighted_averages || null)
const weightedTableData = computed(() => {
  if (!weightedAvgs.value) return []
  return Object.entries(weightedAvgs.value).map(([k, v]) => ({ metric: k.replace('_w', ''), value: typeof v === 'number' ? v : 0 }))
})
const summaryStats = computed(() => {
  if (!task.value?.result?.steps) return []
  const fs = task.value.result.steps.full_search?.data
  const items = []
  if (fs) { items.push({ label: '总峰数', value: fs.total_peaks }, { label: '已分配', value: fs.assigned_peaks }, { label: '分配率', value: fs.assignment_rate + '%' }) }
  items.push({ label: '总耗时', value: (task.value.result.total_time || 0).toFixed(1) + 's' })
  return items
})

function formatTime(t) { return t ? new Date(t).toLocaleString('zh-CN') : '-' }
function mapStepName(key) { return { peak_detection: '峰检测', kendrick_filter: 'Kendrick 过滤', preliminary_search: '初步搜索', calibration: '质量校准', full_search: '完整搜索', indices_calc: '指标计算', nitrogen_rule: '氮规则', classification: '化合物分类', weighted_avg: '加权平均' }[key] || key }
function isCurrentStep(i) { return task.value?.current_step === stepKeys[i] }
function isDoneStep(i) { return stepKeys.indexOf(task.value?.current_step) > i }
function formatStepData(data) {
  if (!data) return ''
  const p = []
  if (data.total_peaks !== undefined) p.push(`总峰: ${data.total_peaks}`)
  if (data.filtered_peaks !== undefined) p.push(`过滤后: ${data.filtered_peaks}`)
  if (data.assigned_peaks !== undefined) p.push(`已分配: ${data.assigned_peaks}`)
  if (data.remaining_peaks !== undefined) p.push(`剩余: ${data.remaining_peaks}`)
  if (data.type_counts) p.push(`分类: ${Object.keys(data.type_counts).length} 类`)
  return p.join(' | ')
}

function exportCSV() {
  window.open(getExportUrl(taskId), '_blank')
}

function exportWeightedCSV() {
  if (!weightedAvgs.value) return
  const rows = [['指标', '加权平均值']]
  Object.entries(weightedAvgs.value).forEach(([k, v]) => { rows.push([k.replace('_w', ''), typeof v === 'number' ? v.toFixed(6) : '']) })
  const csv = rows.map(r => r.join(',')).join('\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `${taskId}_weighted_averages.csv`
  a.click()
}

async function handleDelete() {
  try { await ElMessageBox.confirm('确定删除此任务？', '确认', { type: 'warning' }); await deleteTask(taskId); router.push('/history') } catch {}
}

function startPolling() {
  polling = setInterval(async () => {
    try {
      const s = await getTaskStatus(taskId)
      if (task.value) Object.assign(task.value, s)
      if (s.status === 'success' || s.status === 'failed') { stopPolling(); await loadFullDetail() }
    } catch {}
  }, 2000)
}
function stopPolling() { if (polling) { clearInterval(polling); polling = null } }

async function loadFullDetail() {
  try {
    task.value = await getTaskDetail(taskId)
    if (task.value?.status === 'success') {
      if (task.value?.task_type === 'dpr') {
        // Load DPR data
        await loadDprData()
      } else {
        // Load regular analysis charts
        const [spectrum, preliminary, vankrevelen, classification, weighted] = await Promise.all([
          getChartData(taskId, 'spectrum'), getChartData(taskId, 'preliminary'),
          getChartData(taskId, 'vankrevelen'), getChartData(taskId, 'classification'), getChartData(taskId, 'weighted'),
        ])
        chartData = { spectrum, preliminary, vankrevelen, classification, weighted }
        await nextTick(); renderChart(activeTab.value)
      }
    }
  } catch (e) { ElMessage.error('加载失败: ' + e.message) }
}

async function loadDprData() {
  try {
    // Get the final CSV file from result
    const finalFile = task.value?.result?.final_file
    const sessionId = task.value?.id
    if (!finalFile || !sessionId) return
    
    const res = await api.get(`/data-analysis/dpr-data/${sessionId}/${finalFile}`)
    dprRawData.value = res
    
    // Convert to table data
    const tableData = []
    const scatter = res.scatter || {}
    for (const cat of ['Resistant', 'Disappearance', 'Product']) {
      const data = scatter[cat] || { molform: [], oc_raw: [], hc_raw: [] }
      for (let i = 0; i < (data.molform || []).length; i++) {
        tableData.push({
          MolForm: data.molform[i],
          Col1: cat === 'Disappearance' ? 1 : cat === 'Resistant' ? 1 : 0,
          Col2: cat === 'Product' ? 1 : cat === 'Resistant' ? 1 : 0,
          NewCol: cat === 'Disappearance' ? 'D' : cat === 'Resistant' ? 'R' : 'P',
          category: cat,
          'H/C': data.hc_raw[i],
          'O/C': data.oc_raw[i],
        })
      }
    }
    dprTableData.value = tableData
  } catch (e) {
    console.error('Failed to load DPR data:', e)
  }
}

function rerenderChart() { renderChart(activeTab.value) }

// Van Krevelen element classification (matching Python classify_formula exactly)
function classifyElem(row) {
  const elems = new Set()
  for (const e of ['C', 'H', 'O', 'N', 'S', 'P']) { if (row[e] > 0) elems.add(e) }
  const cats = { 'CHONPS': new Set(['C','H','O','N','P','S']), 'CHOPS': new Set(['C','H','O','P','S']),
    'CHONP': new Set(['C','H','O','N','P']), 'CHONS': new Set(['C','H','O','N','S']),
    'CHOP': new Set(['C','H','O','P']), 'CHOS': new Set(['C','H','O','S']),
    'CHON': new Set(['C','H','O','N']), 'CHO': new Set(['C','H','O']) }
  for (const [name, combo] of Object.entries(cats)) {
    if (combo.size === elems.size && [...combo].every(e => elems.has(e))) return name
  }
  return 'Other'
}

function buildVKOption() {
  const d = chartData.vankrevelen
  if (!d || !d.oc?.length) return null
  const font = chartFont.value, fs = chartFontSize.value

  // Group by element category
  const grouped = {}
  d.oc.forEach((oc, i) => {
    const cat = d.elem_category[i] || 'Other'
    if (!grouped[cat]) grouped[cat] = []
    grouped[cat].push([oc, d.hc[i]])
  })

  // Category boundary boxes (matching Python exactly)
  const boundaries = {
    Lipid: { oc: [0, 0.3], hc: [1.5, 2.0] },
    'Peptide-like': { oc: [0.3, 0.67], hc: [1.5, 2.2] },
    Carbohydrate: { oc: [0.67, 1.2], hc: [1.5, 2.5] },
    'Unsaturated hydrocarbon': { oc: [0, 0.1], hc: [0.67, 1.5] },
    Lignin: { oc: [0.1, 0.67], hc: [0.67, 1.5] },
    'Condensed aromatics': { oc: [0, 0.67], hc: [0.3, 0.67] },
    Tannin: { oc: [0.67, 1.2], hc: [0.5, 1.5] },
  }

  // Build markLine data for boundary boxes (matching matplotlib style: black dotted lines)
  const markLineData = vkParams.showBoundaries ? Object.entries(boundaries).flatMap(([name, { oc, hc }]) => [
    // Bottom line
    { coord: [oc[0], hc[0]], symbol: 'none', lineStyle: { type: 'dotted', color: 'black', width: 1 } },
    { coord: [oc[1], hc[0]], symbol: 'none', lineStyle: { type: 'dotted', color: 'black', width: 1 } },
    // Top line
    { coord: [oc[0], hc[1]], symbol: 'none', lineStyle: { type: 'dotted', color: 'black', width: 1 } },
    { coord: [oc[1], hc[1]], symbol: 'none', lineStyle: { type: 'dotted', color: 'black', width: 1 } },
    // Left line
    { coord: [oc[0], hc[0]], symbol: 'none', lineStyle: { type: 'dotted', color: 'black', width: 1 } },
    { coord: [oc[0], hc[1]], symbol: 'none', lineStyle: { type: 'dotted', color: 'black', width: 1 } },
    // Right line
    { coord: [oc[1], hc[0]], symbol: 'none', lineStyle: { type: 'dotted', color: 'black', width: 1 } },
    { coord: [oc[1], hc[1]], symbol: 'none', lineStyle: { type: 'dotted', color: 'black', width: 1 } },
  ]) : []

  // Build scatter series per element category (matching matplotlib style)
  const series = Object.entries(grouped).map(([cat, data]) => ({
    name: cat, type: 'scatter', data, symbolSize: vkParams.dotSize,
    itemStyle: { 
      color: vkColors[cat] || '#999', 
      opacity: 0.5,
      borderColor: 'white',
      borderWidth: 0.5
    },
  }))

  // Add boundary labels as markPoint if showLabels is true
  if (vkParams.showLabels && vkParams.showBoundaries) {
    const labelData = Object.entries(boundaries).map(([name, { oc, hc }]) => {
      const lx = (oc[0] + oc[1]) / 2
      const ly = (hc[0] + hc[1]) / 2
      let label = name
      let rotation = 0
      if (name === 'Unsaturated hydrocarbon') {
        rotation = 90
      }
      return {
        coord: [lx, ly],
        value: label,
        symbol: 'none',
        label: {
          show: true,
          formatter: label,
          fontFamily: font,
          fontSize: fs - 2,
          color: 'black',
          rotate: rotation
        }
      }
    })
    if (series.length > 0) {
      series[0].markPoint = { data: labelData, silent: true }
    }
  }

  // Add boundary markLine to first series
  if (series.length > 0 && markLineData.length > 0) {
    series[0].markLine = { silent: true, data: markLineData }
  }

  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item', formatter: p => p.componentType === 'series' ? `O/C: ${p.value[0].toFixed(3)}<br/>H/C: ${p.value[1].toFixed(3)}<br/>${p.seriesName}` : '' },
    legend: { 
      show: true, 
      top: 5, 
      right: 10, 
      textStyle: { color: '#94a3b8', fontFamily: font, fontSize: fs },
      itemStyle: { borderColor: 'white', borderWidth: 0.5 }
    },
    xAxis: { 
      type: 'value', 
      name: 'O/C', 
      min: vkParams.ocMin, 
      max: vkParams.ocMax, 
      nameTextStyle: { fontFamily: font, fontSize: fs, fontWeight: 'bold' }, 
      axisLabel: { color: '#94a3b8', fontFamily: font, fontSize: fs }, 
      splitLine: { lineStyle: { color: '#1e3a5f' } },
      axisLine: { lineStyle: { color: 'black' } }
    },
    yAxis: { 
      type: 'value', 
      name: 'H/C', 
      min: vkParams.hcMin, 
      max: vkParams.hcMax, 
      nameTextStyle: { fontFamily: font, fontSize: fs, fontWeight: 'bold' }, 
      axisLabel: { color: '#94a3b8', fontFamily: font, fontSize: fs }, 
      splitLine: { lineStyle: { color: '#1e3a5f' } },
      axisLine: { lineStyle: { color: 'black' } }
    },
    series,
    grid: { left: 80, right: 120, top: 40, bottom: 50 },
  }
}

function getChartOption(type) {
  const font = chartFont.value, fs = chartFontSize.value
  const axSty = { axisLabel: { color: '#94a3b8', fontFamily: font, fontSize: fs }, splitLine: { lineStyle: { color: '#1e3a5f' } } }

  if (type === 'spectrum' && chartData.spectrum) {
    const d = chartData.spectrum
    return { backgroundColor: 'transparent', tooltip: { trigger: 'axis' }, xAxis: { type: 'value', name: 'm/z', nameTextStyle: { fontFamily: font, fontSize: fs }, ...axSty }, yAxis: { type: 'value', name: 'Abundance', nameTextStyle: { fontFamily: font, fontSize: fs }, ...axSty }, series: [{ type: 'line', data: d.mz.map((m, i) => [m, d.abundance[i]]), lineStyle: { color: '#3b82f6', width: 1 }, symbol: 'none', large: true }], grid: { left: 80, right: 30, top: 40, bottom: 50 } }
  }
  if (type === 'preliminary' && chartData.preliminary) {
    const d = chartData.preliminary
    return { backgroundColor: 'transparent', tooltip: { trigger: 'item', formatter: p => `m/z: ${p.value[0].toFixed(4)}<br/>ppm: ${p.value[1].toFixed(3)}` }, xAxis: { type: 'value', name: 'm/z', nameTextStyle: { fontFamily: font, fontSize: fs }, ...axSty }, yAxis: { type: 'value', name: 'Error (ppm)', nameTextStyle: { fontFamily: font, fontSize: fs }, ...axSty }, series: [{ type: 'scatter', data: d.mz.map((m, i) => [m, d.ppm_error[i]]), symbolSize: 4, itemStyle: { color: '#f59e0b' }, large: true }], grid: { left: 80, right: 30, top: 40, bottom: 50 } }
  }
  if (type === 'vankrevelen') return buildVKOption()
  if (type === 'class' && chartData.classification) {
    const colors = ['#3b82f6', '#06b6d4', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444', '#ec4899', '#64748b']
    return { backgroundColor: 'transparent', tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' }, legend: { orient: 'vertical', right: 10, top: 'center', textStyle: { color: '#94a3b8', fontFamily: font, fontSize: fs } }, series: [{ type: 'pie', radius: ['40%', '70%'], center: ['40%', '50%'], itemStyle: { borderRadius: 6, borderColor: '#1a2332', borderWidth: 2 }, label: { show: false }, emphasis: { label: { show: true, fontSize: fs + 2, fontWeight: 'bold', color: '#e2e8f0', fontFamily: font } }, data: Object.entries(chartData.classification).map(([name, value], i) => ({ name, value, itemStyle: { color: colors[i % colors.length] } })) }] }
  }
  if (type === 'weighted' && chartData.weighted) {
    const d = chartData.weighted, keys = Object.keys(d)
    return { backgroundColor: 'transparent', tooltip: { trigger: 'axis' }, xAxis: { type: 'category', data: keys.map(k => k.replace('_w', '')), axisLabel: { color: '#94a3b8', fontFamily: font, fontSize: fs, rotate: 30 } }, yAxis: { type: 'value', ...axSty }, series: [{ type: 'bar', data: keys.map(k => d[k]), itemStyle: { color: '#3b82f6', borderRadius: [4, 4, 0, 0] }, label: { show: true, position: 'top', formatter: p => p.value.toFixed(4), fontFamily: font, fontSize: fs - 2, color: '#94a3b8' } }], grid: { left: 80, right: 30, top: 40, bottom: 80 } }
  }
  return null
}

function renderChart(type) {
  if (type === 'vankrevelen') {
    if (currentChart) currentChart.dispose()
    currentChart = null
    return
  }
  const refs = { spectrum: spectrumRef, preliminary: preliminaryRef, vankrevelen: vankrevelenRef, class: classRef, weighted: weightedRef }
  const el = refs[type]; if (!el.value) return
  if (currentChart) currentChart.dispose()
  currentChart = echarts.init(el.value)
  const opt = getChartOption(type); if (opt) currentChart.setOption(opt)
}

function onColorChange() {
  rerenderChart()
}

function getCustomColorsString() {
  // Convert vkColors to format: "CHO:#ff0000,CHON:#00ff00,..."
  return Object.entries(vkColors).map(([cat, color]) => `${cat}:${color}`).join(',')
}

function getVKParams() {
  return { 
    font_size: chartFontSize.value, 
    scale: 1.0, 
    oc_min: vkParams.ocMin, 
    oc_max: vkParams.ocMax, 
    hc_min: vkParams.hcMin, 
    hc_max: vkParams.hcMax, 
    dot_size: vkParams.dotSize, 
    show_labels: vkParams.showLabels ? 1 : 0,
    show_boundaries: vkParams.showBoundaries ? 1 : 0,
    panel_label: '',
    custom_colors: getCustomColorsString()
  }
}

function exportChartPDF() {
  if (activeTab.value === 'vankrevelen') {
    window.open(getVKPdfUrl(taskId, getVKParams()), '_blank')
    return
  }
  if (!currentChart) return
  currentChart.resize()
  window.open(getChartPdfUrl(taskId, activeTab.value, { font_size: chartFontSize.value, scale: 1.0 }), '_blank')
}

function exportChartTIF() {
  if (activeTab.value === 'vankrevelen') {
    window.open(getVKTifUrl(taskId, getVKParams()), '_blank')
    return
  }
  if (!currentChart) return
  currentChart.resize()
  window.open(getChartTifUrl(taskId, activeTab.value, { font_size: chartFontSize.value, scale: 1.0 }), '_blank')
}

watch(activeTab, async v => { await nextTick(); renderChart(v) })

onMounted(async () => {
  try {
    task.value = await getTaskDetail(taskId)
    if (task.value?.status === 'running' || task.value?.status === 'pending') startPolling()
    else if (task.value?.status === 'success') await loadFullDetail()
  } catch (e) { ElMessage.error('加载失败: ' + e.message) }
  finally { loading.value = false }
})
onUnmounted(() => stopPolling())
</script>

<style lang="scss" scoped>
.task-detail { max-width: 1200px; }
.header-row { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-title { font-size: 24px; font-weight: 700; margin-bottom: 8px; }
.page-subtitle { display: flex; align-items: center; gap: 12px; }
.time-text { color: var(--text-muted); font-size: 13px; }
.header-actions { display: flex; gap: 8px; }
.current-step { text-align: center; margin-top: 14px; color: var(--accent-blue); font-size: 14px; display: flex; align-items: center; justify-content: center; gap: 8px; }
.step-timeline { display: flex; justify-content: center; gap: 4px; margin-top: 16px; flex-wrap: wrap; }
.timeline-item { display: flex; align-items: center; gap: 4px; font-size: 12px; color: var(--text-muted); padding: 4px 10px; border-radius: 20px; background: var(--bg-secondary); &.active { color: var(--accent-blue); background: rgba(59, 130, 246, 0.12); } &.done { color: var(--accent-green); background: rgba(16, 185, 129, 0.08); } }
.timeline-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--text-muted); .active & { background: var(--accent-blue); } .done & { background: var(--accent-green); } }
.stats-row { display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }
.stat-card { padding: 16px 24px; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-lg); text-align: center; min-width: 120px; }
.stat-val { display: block; font-size: 24px; font-weight: 700; background: var(--accent-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.stat-lbl { font-size: 12px; color: var(--text-secondary); }
.section { padding: 24px; margin-bottom: 20px; }
.section-title { font-size: 16px; font-weight: 600; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
.chart-toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.toolbar-label { font-size: 12px; color: var(--text-muted); }
.vk-params { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; padding: 10px 14px; background: var(--bg-secondary); border-radius: var(--radius-sm); font-size: 13px; color: var(--text-secondary); flex-wrap: wrap; }
.vk-colors { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; padding: 8px 14px; background: var(--bg-secondary); border-radius: var(--radius-sm); flex-wrap: wrap; }
.color-item { display: flex; align-items: center; gap: 4px; }
.color-label { font-size: 11px; color: var(--text-muted); min-width: 50px; }
.detail-tabs { margin-bottom: 0; }
.chart-box { width: 100%; height: 450px; }
.vk-preview {
  height: auto;
  min-height: 450px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: white;
}
.vk-preview img {
  width: 100%;
  max-height: 760px;
  object-fit: contain;
}
.step-data { color: var(--text-secondary); font-size: 13px; }
.step-error { color: var(--accent-red); font-size: 13px; }
.dark-table {
  --el-table-bg-color: #1e293b;
  --el-table-tr-bg-color: #1e293b;
  --el-table-row-hover-bg-color: #2d3a4f;
  --el-table-header-bg-color: #0f172a;
  --el-table-border-color: #334155;
  --el-table-text-color: #e2e8f0;
  --el-table-header-text-color: #94a3b8;
  --el-table-expanded-cell-bg-color: #1e293b;
}
.dark-table :deep(.el-table__row--striped td.el-table__cell) {
  background-color: #253347 !important;
}
.dark-table :deep(.el-table__row:hover > td.el-table__cell) {
  background-color: #2d3a4f !important;
}
:deep(.el-tabs__item) { color: var(--text-secondary); }
:deep(.el-tabs__item.is-active) { color: var(--accent-blue); }
:deep(.el-tabs) { background: transparent; }
.table-tip { margin-top: 12px; text-align: center; }
</style>
