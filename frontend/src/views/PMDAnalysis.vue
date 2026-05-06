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
        <div class="round-control">
          <span>{{ text.roundDecimals }}</span>
          <el-tooltip :content="text.roundHelp" placement="top">
            <el-input-number v-model="roundVal" :min="4" :max="10" controls-position="right" />
          </el-tooltip>
        </div>
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

      <div class="reaction-panel">
        <div class="panel-head">
          <div>
            <h3>{{ text.reactionSettings }}</h3>
            <p>{{ text.reactionHelp }}</p>
          </div>
          <div class="reaction-actions">
            <el-button size="small" @click="addReaction">{{ text.addReaction }}</el-button>
            <el-button size="small" @click="resetReactions">{{ text.resetDefault }}</el-button>
          </div>
        </div>
        <el-table :data="reactions" size="small" max-height="360" class="reaction-table">
          <el-table-column :label="text.enabled" width="72" align="center">
            <template #default="{ row }">
              <el-checkbox v-model="row.enabled" />
            </template>
          </el-table-column>
          <el-table-column :label="text.category" min-width="160">
            <template #default="{ row }">
              <el-input v-model="row.category" size="small" />
            </template>
          </el-table-column>
          <el-table-column :label="text.type" width="90">
            <template #default="{ row }">
              <el-select v-model="row.type" size="small">
                <el-option label="+" value="+" />
                <el-option label="-" value="-" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column :label="text.reaction" min-width="120">
            <template #default="{ row }">
              <el-input v-model="row.formula" size="small" placeholder="CO2" />
            </template>
          </el-table-column>
          <el-table-column :label="text.name" min-width="200">
            <template #default="{ row }">
              <el-input v-model="row.name" size="small" />
            </template>
          </el-table-column>
          <el-table-column :label="text.color" width="100">
            <template #default="{ row }">
              <el-color-picker v-model="row.color" size="small" />
            </template>
          </el-table-column>
          <el-table-column :label="text.actions" width="90">
            <template #default="{ $index }">
              <el-button text type="danger" size="small" @click="removeReaction($index)">{{ text.delete }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

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
    roundDecimals: 'Mass decimals',
    roundHelp: 'Number of decimals used when matching mass differences. 8 means formulas are matched after rounding exact masses to 8 decimal places.',
    reactionSettings: 'Reaction Settings',
    reactionHelp: 'Default reactions are preloaded. You can enable, disable, edit, delete, or add reactions such as +CO, -CO, +O, -CH2.',
    enabled: 'Enabled',
    color: 'Color',
    actions: 'Actions',
    addReaction: 'Add Reaction',
    resetDefault: 'Reset Defaults',
    delete: 'Delete',
    category: 'Category',
    type: 'Type',
    reaction: 'Reaction',
    name: 'Name',
    value: 'Edges',
    success: 'PMD analysis complete',
    failed: 'PMD analysis failed',
    needReaction: 'Enable at least one valid reaction',
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
    roundDecimals: '质量匹配小数位',
    roundHelp: '用于匹配质量差的小数位数。8 表示把精确质量四舍五入到 8 位小数后匹配反应差值。',
    reactionSettings: '反应设置',
    reactionHelp: '默认反应已预置；你可以启用、停用、编辑、删除或新增 +CO、-CO、+O、-CH2 这类反应。',
    enabled: '启用',
    color: '颜色',
    actions: '操作',
    addReaction: '新增反应',
    resetDefault: '恢复默认',
    delete: '删除',
    category: '分类',
    type: '类型',
    reaction: '反应',
    name: '名称',
    value: '边数',
    success: 'PMD 分析完成',
    failed: 'PMD 分析失败',
    needReaction: '请至少启用一个有效反应',
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
const defaultReactions = [
  { category: 'Carboxylic acid', type: '-', formula: 'CO', name: 'Loss of CO', color: '#ef4444', enabled: true },
  { category: 'Carboxylic acid', type: '-', formula: 'CO2', name: 'Decarboxylation', color: '#ef4444', enabled: true },
  { category: 'Carboxylic acid', type: '-', formula: 'CH2O', name: 'Loss of formaldehyde', color: '#ef4444', enabled: true },
  { category: 'Oxygen addition', type: '+', formula: 'O', name: 'Hydroxylation', color: '#2563eb', enabled: true },
  { category: 'Oxygen addition', type: '+', formula: 'O2', name: 'Two-hydroxylation', color: '#2563eb', enabled: true },
  { category: 'Oxygen addition', type: '+', formula: 'O3', name: 'Tri-hydroxylation', color: '#2563eb', enabled: true },
  { category: 'Oxygen addition', type: '+', formula: 'H2O', name: 'Hydration', color: '#2563eb', enabled: true },
  { category: 'Oxygen addition', type: '+', formula: 'H2O2', name: 'Di-hydroxylation', color: '#2563eb', enabled: true },
  { category: 'Other reactions', type: '-', formula: 'H2O', name: 'Dehydration', color: '#10b981', enabled: true },
  { category: 'Other reactions', type: '+', formula: 'H2', name: 'Hydrogenation', color: '#10b981', enabled: true },
  { category: 'Other reactions', type: '-', formula: 'H2', name: 'Dehydrogenation', color: '#10b981', enabled: true },
  { category: 'Sulfate', type: '-', formula: 'S', name: 'Remove S', color: '#9333ea', enabled: true },
  { category: 'Sulfate', type: '-', formula: 'SO', name: 'Remove SO', color: '#9333ea', enabled: true },
  { category: 'Sulfate', type: '-', formula: 'SO2', name: 'Remove SO2', color: '#9333ea', enabled: true },
  { category: 'Sulfate', type: '-', formula: 'SO3', name: 'Remove SO3', color: '#9333ea', enabled: true },
  { category: 'Amine', type: '-', formula: 'NH3', name: 'Ammonia elimination', color: '#f59e0b', enabled: true },
  { category: 'Amine', type: '-', formula: 'NH', name: 'Deamination', color: '#f59e0b', enabled: true },
  { category: 'Dealkyl', type: '-', formula: 'CH2', name: 'Demethylation', color: '#64748b', enabled: true },
  { category: 'Dealkyl', type: '-', formula: 'C2H2', name: 'Dealkylation', color: '#64748b', enabled: true },
  { category: 'Dealkyl', type: '-', formula: 'C2H4', name: 'Deethylation', color: '#64748b', enabled: true },
  { category: 'Dealkyl', type: '-', formula: 'C3H6', name: 'Deisopropyl', color: '#64748b', enabled: true },
]
const reactions = ref(defaultReactions.map((item) => ({ ...item })))
const activeReactions = computed(() => reactions.value
  .filter((row) => row.enabled && row.formula?.trim())
  .map((row) => ({
    category: row.category || 'Custom',
    type: row.type || '+',
    formula: row.formula.trim(),
    name: row.name || row.formula.trim(),
    color: row.color || '#2563eb',
  })))
const canRun = computed(() => !!fileA.value && (mode.value === 'single' || !!fileB.value) && activeReactions.value.length > 0 && !processing.value)

function onFileA(e) { fileA.value = e.target.files?.[0] || null }
function onFileB(e) { fileB.value = e.target.files?.[0] || null }
function download(url) { if (url) window.open(url, '_blank') }
function resetReactions() { reactions.value = defaultReactions.map((item) => ({ ...item })) }
function addReaction() {
  reactions.value.push({ category: 'Custom', type: '+', formula: 'CO', name: 'Custom reaction', color: '#2563eb', enabled: true })
}
function removeReaction(index) { reactions.value.splice(index, 1) }

async function run() {
  if (!canRun.value) return
  if (!activeReactions.value.length) {
    ElMessage.warning(text.value.needReaction)
    return
  }
  const fd = new FormData()
  fd.append('file_a', fileA.value)
  if (mode.value === 'cross' && fileB.value) fd.append('file_b', fileB.value)
  fd.append('mode', mode.value)
  fd.append('graph_format', graphFormat.value)
  fd.append('round_val', String(roundVal.value))
  fd.append('custom_reactions', JSON.stringify(activeReactions.value))
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
.round-control { display: flex; align-items: center; gap: 8px; color: var(--text-secondary); font-size: 13px; }
.upload-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 16px; }
.upload-box { min-height: 140px; border: 2px dashed var(--border-color); border-radius: 8px; display: grid; place-items: center; gap: 8px; cursor: pointer; background: #0f172a; color: var(--text-secondary); text-align: center; padding: 18px; }
.upload-box:hover { border-color: var(--accent-blue); }
.upload-box .el-icon { font-size: 34px; color: var(--accent-blue); }
.note { margin-bottom: 16px; }
.reaction-panel { margin: 14px 0 18px; padding: 14px; border: 1px solid #24466f; background: #0f172a; border-radius: 8px; }
.panel-head { display: flex; justify-content: space-between; gap: 14px; align-items: flex-start; margin-bottom: 12px; }
.panel-head h3 { margin: 0 0 4px; font-size: 15px; color: var(--text-primary); }
.panel-head p { margin: 0; color: var(--text-secondary); font-size: 13px; line-height: 1.5; }
.reaction-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.reaction-table { --el-table-bg-color: #111827; --el-table-tr-bg-color: #111827; --el-table-header-bg-color: #0f172a; --el-table-border-color: #334155; --el-table-text-color: #e2e8f0; --el-table-header-text-color: #94a3b8; }
.stats-row { display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }
.stat-card { min-width: 120px; padding: 16px 20px; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 8px; text-align: center; }
.stat-val { display: block; font-size: 24px; font-weight: 700; color: #60a5fa; }
.stat-lbl { color: var(--text-secondary); font-size: 12px; }
.plot-box { background: white; border-radius: 8px; padding: 12px; margin-bottom: 18px; text-align: center; overflow: auto; }
.plot-box img { max-width: 100%; height: auto; }
</style>
