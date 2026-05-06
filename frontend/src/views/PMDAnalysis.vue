<template>
  <div class="pmd-analysis">
    <div class="page-head">
      <div>
        <h1 class="page-title">{{ text.title }}</h1>
        <p class="page-subtitle">{{ text.subtitle }}</p>
      </div>
      <div v-if="result" class="head-actions">
        <el-button type="primary" @click="download(result.downloads.graph)">{{ text.downloadGraph }}</el-button>
        <el-button @click="download(result.downloads.counts_csv)">{{ text.downloadCsv }}</el-button>
        <el-button @click="download(result.downloads.radar_pdf)">{{ text.downloadPdf }}</el-button>
      </div>
    </div>

    <section class="section card-glass">
      <h2 class="section-title"><el-icon><Upload /></el-icon> {{ text.input }}</h2>
      <div class="mode-row">
        <el-radio-group v-model="mode">
          <el-radio-button value="single">{{ text.single }}</el-radio-button>
          <el-radio-button value="cross">{{ text.cross }}</el-radio-button>
        </el-radio-group>
        <el-select v-model="graphFormat" style="width: 140px">
          <el-option label="GraphML" value="graphml" />
          <el-option label="GEXF" value="gexf" />
        </el-select>
        <el-input-number v-model="roundVal" :min="4" :max="10" />
      </div>

      <div class="upload-row">
        <div class="upload-box" @click="inputA?.click()">
          <input ref="inputA" type="file" accept=".csv" hidden @change="onFileA" />
          <el-icon><Document /></el-icon>
          <span>{{ fileA?.name || text.sampleA }}</span>
        </div>
        <div v-if="mode === 'cross'" class="upload-box" @click="inputB?.click()">
          <input ref="inputB" type="file" accept=".csv" hidden @change="onFileB" />
          <el-icon><Document /></el-icon>
          <span>{{ fileB?.name || text.sampleB }}</span>
        </div>
      </div>

      <el-alert :title="text.note" type="info" show-icon :closable="false" class="note" />
      <el-button type="primary" size="large" :loading="processing" :disabled="!canRun" @click="run">
        {{ processing ? text.running : text.start }}
      </el-button>
    </section>

    <section v-if="result" class="section card-glass">
      <h2 class="section-title"><el-icon><Share /></el-icon> {{ text.result }}</h2>
      <div class="stats-row">
        <div class="stat-card"><span class="stat-val">{{ result.nodes }}</span><span class="stat-lbl">{{ text.nodes }}</span></div>
        <div class="stat-card"><span class="stat-val">{{ result.edges }}</span><span class="stat-lbl">{{ text.edges }}</span></div>
        <div class="stat-card"><span class="stat-val">{{ result.reaction_counts.length }}</span><span class="stat-lbl">{{ text.reactions }}</span></div>
      </div>

      <div class="plot-box">
        <img :src="'data:image/png;base64,' + result.radar_png" alt="PMD radar" />
      </div>

      <el-table :data="result.reaction_counts" class="dark-table" max-height="420">
        <el-table-column prop="Category" :label="text.category" min-width="160" />
        <el-table-column prop="Type" :label="text.type" width="80" />
        <el-table-column prop="Reaction" :label="text.reaction" min-width="120" />
        <el-table-column prop="Name" :label="text.name" min-width="200" />
        <el-table-column prop="Value" :label="text.value" width="100" />
      </el-table>
    </section>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api/index'
import { useI18n } from '../i18n'

const { lang } = useI18n()
const dict = {
  en: {
    title: 'PMD Analysis',
    subtitle: 'Build single-sample or cross-sample pairwise mass difference reaction networks and radar summaries.',
    input: 'Input Files',
    single: 'Single sample',
    cross: 'Cross sample',
    sampleA: 'Choose sample A CSV',
    sampleB: 'Choose sample B CSV',
    note: 'CSV must contain Molecular Formula or MolForm. Peak Height/Intensity is optional and will be used as node intensity.',
    start: 'Build PMD Network',
    running: 'Building...',
    result: 'PMD Result',
    nodes: 'Nodes',
    edges: 'Edges',
    reactions: 'Reactions',
    downloadGraph: 'Download Network',
    downloadCsv: 'Download CSV',
    downloadPdf: 'Download Radar PDF',
    category: 'Category',
    type: 'Type',
    reaction: 'Reaction',
    name: 'Name',
    value: 'Edges',
    success: 'PMD analysis complete',
    failed: 'PMD analysis failed',
  },
  zh: {
    title: 'PMD 分析',
    subtitle: '构建单样本或双样本 PMD 分子反应网络，并生成反应统计和雷达图。',
    input: '输入文件',
    single: '单样本',
    cross: '双样本',
    sampleA: '选择样品 A CSV',
    sampleB: '选择样品 B CSV',
    note: 'CSV 必须包含 Molecular Formula 或 MolForm。Peak Height/Intensity 可选，会作为节点强度。',
    start: '构建 PMD 网络',
    running: '构建中...',
    result: 'PMD 结果',
    nodes: '节点数',
    edges: '边数',
    reactions: '反应数',
    downloadGraph: '下载网络',
    downloadCsv: '下载 CSV',
    downloadPdf: '下载雷达图 PDF',
    category: '分类',
    type: '类型',
    reaction: '反应',
    name: '名称',
    value: '边数',
    success: 'PMD 分析完成',
    failed: 'PMD 分析失败',
  },
}
const text = computed(() => dict[lang.value] || dict.en)
const inputA = ref(null)
const inputB = ref(null)
const fileA = ref(null)
const fileB = ref(null)
const mode = ref('single')
const graphFormat = ref('graphml')
const roundVal = ref(8)
const processing = ref(false)
const result = ref(null)
const canRun = computed(() => !!fileA.value && (mode.value === 'single' || !!fileB.value) && !processing.value)

function onFileA(e) { fileA.value = e.target.files?.[0] || null }
function onFileB(e) { fileB.value = e.target.files?.[0] || null }
function download(url) { if (url) window.open(url, '_blank') }

async function run() {
  if (!canRun.value) return
  const fd = new FormData()
  fd.append('file_a', fileA.value)
  if (mode.value === 'cross' && fileB.value) fd.append('file_b', fileB.value)
  fd.append('mode', mode.value)
  fd.append('graph_format', graphFormat.value)
  fd.append('round_val', String(roundVal.value))
  processing.value = true
  result.value = null
  try {
    result.value = await api.post('/pmd/analyze', fd, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 1800000 })
    ElMessage.success(text.value.success)
  } catch (e) {
    ElMessage.error(`${text.value.failed}: ${e.message}`)
  } finally {
    processing.value = false
  }
}
</script>

<style lang="scss" scoped>
.pmd-analysis { max-width: 1400px; }
.page-head { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 20px; }
.page-title { font-size: 28px; font-weight: 700; margin-bottom: 4px; }
.page-subtitle { color: var(--text-secondary); margin: 0; font-size: 14px; }
.head-actions { display: flex; gap: 10px; flex-wrap: wrap; }
.section { padding: 24px; margin-bottom: 20px; }
.section-title { display: flex; align-items: center; gap: 8px; font-size: 18px; margin: 0 0 16px; }
.mode-row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 16px; }
.upload-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 16px; }
.upload-box { min-height: 140px; border: 2px dashed var(--border-color); border-radius: 8px; display: grid; place-items: center; gap: 8px; cursor: pointer; background: #0f172a; color: var(--text-secondary); text-align: center; padding: 18px; }
.upload-box:hover { border-color: var(--accent-blue); }
.upload-box .el-icon { font-size: 34px; color: var(--accent-blue); }
.note { margin-bottom: 16px; }
.stats-row { display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }
.stat-card { min-width: 120px; padding: 16px 20px; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 8px; text-align: center; }
.stat-val { display: block; font-size: 24px; font-weight: 700; color: #60a5fa; }
.stat-lbl { color: var(--text-secondary); font-size: 12px; }
.plot-box { background: white; border-radius: 8px; padding: 12px; margin-bottom: 18px; text-align: center; overflow: auto; }
.plot-box img { max-width: 100%; height: auto; }
</style>
