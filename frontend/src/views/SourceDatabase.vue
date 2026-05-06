<template>
  <div class="source-database">
    <h1 class="page-title">数据库创建</h1>
    <p class="page-subtitle">把任意数量的 CSV 文件归入一个标签，合并所有分子式和 Peak Height 强度，形成可复用的分子数据库。</p>

    <section class="section card-glass">
      <h2 class="section-title"><el-icon><Files /></el-icon> 创建或追加分子数据库</h2>
      <div class="form-grid">
        <div class="field">
          <span>写入方式</span>
          <el-radio-group v-model="writeMode">
            <el-radio-button value="new">新建/按标签写入</el-radio-button>
            <el-radio-button value="append">追加到已有数据库</el-radio-button>
          </el-radio-group>
        </div>
        <div v-if="writeMode === 'new'" class="field">
          <span>标签/数据库名称</span>
          <el-input v-model="databaseName" placeholder="例如：再生水、污水、上游背景" />
        </div>
        <div v-else class="field">
          <span>已有数据库</span>
          <el-select v-model="selectedDatabaseId" filterable placeholder="选择要追加的数据库">
            <el-option v-for="db in databases" :key="db.id" :label="db.name" :value="db.id" />
          </el-select>
        </div>
        <div class="field full">
          <span>备注</span>
          <el-input v-model="description" placeholder="可填写来源说明、采样批次或点位信息" />
        </div>
      </div>

      <div class="upload-box" @click="triggerBuildInput">
        <input ref="buildInput" type="file" accept=".csv" multiple style="display:none" @change="onBuildFiles" />
        <el-icon><Upload /></el-icon>
        <strong>选择任意数量 CSV 文件</strong>
        <span>{{ buildFileLabel }}</span>
      </div>
      <div v-if="buildFiles.length" class="file-list">
        <el-tag v-for="file in buildFiles" :key="file.name" effect="plain">{{ file.name }}</el-tag>
      </div>
      <div class="actions">
        <el-button type="primary" :disabled="!canBuild || building" @click="buildDatabase">
          <el-icon v-if="!building"><CaretRight /></el-icon>
          <el-icon v-else class="is-loading"><Loading /></el-icon>
          {{ building ? '写入中...' : '创建/更新数据库' }}
        </el-button>
        <el-button @click="loadDatabases">刷新数据库列表</el-button>
      </div>
    </section>

    <section class="section card-glass">
      <h2 class="section-title"><el-icon><DataBoard /></el-icon> 已有分子数据库</h2>
      <el-table :data="databases" v-loading="loadingDatabases" class="db-table">
        <el-table-column prop="name" label="标签/数据库" min-width="180" />
        <el-table-column prop="formula_count" label="分子数" width="110" />
        <el-table-column prop="file_count" label="来源文件数" width="120" />
        <el-table-column prop="updated_at" label="更新时间" width="190">
          <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="来源文件" min-width="260">
          <template #default="{ row }">
            <div class="source-files">
              <el-tag v-for="file in row.files.slice(0, 4)" :key="file.filename" size="small" effect="plain">
                {{ file.filename }} ({{ file.formula_count }})
              </el-tag>
              <span v-if="row.files.length > 4" class="muted">+{{ row.files.length - 4 }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="210">
          <template #default="{ row }">
            <div class="operation-buttons">
              <el-button size="small" @click="downloadDatabase(row)">下载 CSV</el-button>
              <el-button size="small" type="danger" plain @click="deleteDatabase(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="section card-glass">
      <h2 class="section-title"><el-icon><Connection /></el-icon> 样品与数据库对比</h2>
      <div class="compare-row">
        <el-select v-model="compareDatabaseId" filterable placeholder="选择用于对比的数据库">
          <el-option v-for="db in databases" :key="db.id" :label="`${db.name} (${db.formula_count})`" :value="db.id" />
        </el-select>
        <div class="sample-picker" :class="{ selected: compareFile }" @click="triggerCompareInput">
          <input ref="compareInput" type="file" accept=".csv" style="display:none" @change="onCompareFile" />
          <el-icon><UploadFilled /></el-icon>
          <div>
            <strong>{{ compareFile?.name || '点击选择待对比样品 CSV' }}</strong>
            <span>需要包含 Molecular Formula 或 MolForm；Peak Height 会保留到导出结果中</span>
          </div>
        </div>
        <el-button type="primary" :disabled="!compareDatabaseId || !compareFile || comparing" @click="compareDatabase">
          {{ comparing ? '对比中...' : '开始对比' }}
        </el-button>
      </div>
    </section>

    <section class="section card-glass">
      <h2 class="section-title"><el-icon><TrendCharts /></el-icon> 两文件 DPR 与数据库对比</h2>
      <div class="dpr-row">
        <el-select v-model="dprDatabaseId" filterable placeholder="选择来源数据库">
          <el-option v-for="db in databases" :key="db.id" :label="`${db.name} (${db.formula_count})`" :value="db.id" />
        </el-select>
        <div class="sample-picker" :class="{ selected: dprUpstreamFile }" @click="triggerDprInput('upstream')">
          <input ref="dprUpstreamInput" type="file" accept=".csv" style="display:none" @change="onDprFile('upstream', $event)" />
          <el-icon><UploadFilled /></el-icon>
          <div>
            <strong>{{ dprUpstreamFile?.name || '点击选择上游/前点位 CSV' }}</strong>
            <span>用于和下游文件共同定义 D/P/R</span>
          </div>
        </div>
        <div class="sample-picker" :class="{ selected: dprDownstreamFile }" @click="triggerDprInput('downstream')">
          <input ref="dprDownstreamInput" type="file" accept=".csv" style="display:none" @change="onDprFile('downstream', $event)" />
          <el-icon><UploadFilled /></el-icon>
          <div>
            <strong>{{ dprDownstreamFile?.name || '点击选择下游/后点位 CSV' }}</strong>
            <span>D=上游有下游无，P=下游有上游无，R=两者都有</span>
          </div>
        </div>
      </div>
      <div class="actions">
        <el-checkbox v-model="dprRemoveCore">移除核心分子</el-checkbox>
        <el-button type="primary" :disabled="!canRunDpr || dprRunning" @click="runDprDatabase">
          {{ dprRunning ? '分析中...' : '开始 DPR 数据库对比' }}
        </el-button>
      </div>
    </section>

    <section v-if="buildResult" class="section card-glass">
      <h2 class="section-title"><el-icon><CircleCheck /></el-icon> 最近一次写入结果</h2>
      <div class="stats-row">
        <div class="stat-card">
          <span class="stat-val">{{ buildResult.database.formula_count }}</span>
          <span class="stat-lbl">{{ buildResult.database.name }} 分子数</span>
        </div>
        <div class="stat-card">
          <span class="stat-val">{{ buildResult.database.file_count }}</span>
          <span class="stat-lbl">累计来源文件</span>
        </div>
      </div>
      <el-table :data="buildResult.uploaded" size="small">
        <el-table-column prop="filename" label="文件" />
        <el-table-column prop="formula_count" label="文件内分子数" width="140" />
        <el-table-column prop="new_unique_count" label="新增唯一分子" width="140" />
        <el-table-column prop="total_intensity" label="总强度" width="140" />
      </el-table>
    </section>

    <section v-if="compareResult" class="section card-glass">
      <h2 class="section-title"><el-icon><TrendCharts /></el-icon> 对比结果</h2>
      <div class="stats-row">
        <div class="stat-card">
          <span class="stat-val">{{ compareResult.summary.overlap_count }}</span>
          <span class="stat-lbl">Overlap 命中分子</span>
        </div>
        <div class="stat-card">
          <span class="stat-val">{{ compareResult.summary.query_overlap_rate.toFixed(2) }}%</span>
          <span class="stat-lbl">样品命中率</span>
        </div>
      </div>

      <div class="download-row">
        <el-button @click="downloadBase64(compareResult.downloads.overlap_csv_base64, 'overlap.csv')">下载 Overlap</el-button>
        <el-button @click="downloadBase64(compareResult.downloads.sample_only_csv_base64, 'sample_only.csv')">下载 Sample only</el-button>
        <el-button @click="downloadBase64(compareResult.downloads.database_only_csv_base64, 'database_only.csv')">下载 Database only</el-button>
      </div>

      <div class="result-grid compare-result-grid">
        <div class="info-panel">
          <h3>各来源文件相似度</h3>
          <el-table :data="compareResult.source_file_similarity" size="small">
            <el-table-column prop="filename" label="来源文件" min-width="180" show-overflow-tooltip />
            <el-table-column prop="overlap" label="命中" width="80" />
            <el-table-column prop="sample_coverage" label="样品覆盖率" width="120">
              <template #default="{ row }">{{ row.sample_coverage.toFixed(2) }}%</template>
            </el-table-column>
          </el-table>
        </div>
        <div class="info-panel">
          <h3>元素类别分布</h3>
          <el-table :data="compareResult.element_class_distribution" size="small" max-height="280">
            <el-table-column prop="class" label="类别" width="90" />
            <el-table-column prop="overlap" label="Overlap" />
            <el-table-column prop="sample_only" label="Sample only" />
            <el-table-column prop="database_only" label="Database only" />
          </el-table>
        </div>
      </div>

      <div class="plot-and-advice">
        <div class="plot-item">
          <h3>样品与数据库分子集合关系</h3>
          <img :src="plotSrc(compareResult.plots.comparison)" alt="comparison plot" />
        </div>
        <div class="suggestions">
          <h3>分析建议</h3>
          <p v-for="item in analysisSuggestions" :key="item">{{ item }}</p>
          <p>还可以把多个标签数据库同时与同一样品比较，做“来源贡献排序”；如果后续每个样品都有环境变量，可以把命中率和元素类别比例作为特征进入机器学习。</p>
        </div>
      </div>
    </section>

    <section v-if="dprResult" class="section card-glass">
      <h2 class="section-title"><el-icon><DataAnalysis /></el-icon> DPR 数据库对比结果</h2>
      <div class="stats-row">
        <div class="stat-card">
          <span class="stat-val">{{ dprResult.fate_counts.D }}</span>
          <span class="stat-lbl">D 消失组</span>
        </div>
        <div class="stat-card">
          <span class="stat-val">{{ dprResult.fate_counts.P }}</span>
          <span class="stat-lbl">P 产生组</span>
        </div>
        <div class="stat-card">
          <span class="stat-val">{{ dprResult.fate_counts.R }}</span>
          <span class="stat-lbl">R 背景组</span>
        </div>
        <div class="stat-card">
          <span class="stat-val">{{ dprResult.core_removed }}</span>
          <span class="stat-lbl">移除核心分子</span>
        </div>
      </div>

      <div class="download-row">
        <el-button @click="downloadBase64(dprResult.downloads.D_csv_base64, 'D_disappearance.csv')">下载 D</el-button>
        <el-button @click="downloadBase64(dprResult.downloads.P_csv_base64, 'P_product.csv')">下载 P</el-button>
        <el-button @click="downloadBase64(dprResult.downloads.R_csv_base64, 'R_resistant.csv')">下载 R</el-button>
      </div>

      <div class="result-grid">
        <div class="info-panel">
          <h3>D/P/R 在数据库中的存在率</h3>
          <el-table :data="dprPresenceRows" size="small">
            <el-table-column prop="group" label="组别" width="90" />
            <el-table-column prop="inSource" label="存在于数据库" />
            <el-table-column prop="notInSource" label="不在数据库" />
            <el-table-column prop="rate" label="存在率" />
          </el-table>
        </div>
        <div class="info-panel">
          <h3>卡方检验</h3>
          <el-table :data="dprTestRows" size="small">
            <el-table-column prop="name" label="比较" />
            <el-table-column prop="p" label="P-value" />
            <el-table-column prop="result" label="结论" />
          </el-table>
        </div>
      </div>

      <div class="plot-grid">
        <div class="plot-item">
          <h3>3x2 总体热图</h3>
          <img :src="plotSrc(dprResult.plots.overall_3x2)" alt="DPR 3x2 heatmap" />
          <div class="plot-downloads">
            <el-button size="small" @click="downloadImageBase64(dprResult.plots.overall_3x2, 'DPR_3x2_heatmap.png')">下载 PNG</el-button>
            <el-button v-if="dprResult.plot_pdfs?.overall_3x2" size="small" @click="downloadPdfBase64(dprResult.plot_pdfs.overall_3x2, 'DPR_3x2_heatmap.pdf')">下载 PDF</el-button>
          </div>
        </div>
        <div class="plot-item">
          <h3>D vs R</h3>
          <img :src="plotSrc(dprResult.plots.d_vs_r)" alt="D vs R heatmap" />
          <div class="plot-downloads">
            <el-button size="small" @click="downloadImageBase64(dprResult.plots.d_vs_r, 'D_vs_R_heatmap.png')">下载 PNG</el-button>
            <el-button v-if="dprResult.plot_pdfs?.d_vs_r" size="small" @click="downloadPdfBase64(dprResult.plot_pdfs.d_vs_r, 'D_vs_R_heatmap.pdf')">下载 PDF</el-button>
          </div>
        </div>
        <div class="plot-item">
          <h3>P vs D</h3>
          <img :src="plotSrc(dprResult.plots.p_vs_d)" alt="P vs D heatmap" />
          <div class="plot-downloads">
            <el-button size="small" @click="downloadImageBase64(dprResult.plots.p_vs_d, 'P_vs_D_heatmap.png')">下载 PNG</el-button>
            <el-button v-if="dprResult.plot_pdfs?.p_vs_d" size="small" @click="downloadPdfBase64(dprResult.plot_pdfs.p_vs_d, 'P_vs_D_heatmap.pdf')">下载 PDF</el-button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api/index'

const buildInput = ref(null)
const compareInput = ref(null)
const dprUpstreamInput = ref(null)
const dprDownstreamInput = ref(null)
const databases = ref([])
const loadingDatabases = ref(false)
const writeMode = ref('new')
const selectedDatabaseId = ref('')
const compareDatabaseId = ref('')
const databaseName = ref('再生水')
const description = ref('')
const buildFiles = ref([])
const compareFile = ref(null)
const dprDatabaseId = ref('')
const dprUpstreamFile = ref(null)
const dprDownstreamFile = ref(null)
const dprRemoveCore = ref(true)
const building = ref(false)
const comparing = ref(false)
const dprRunning = ref(false)
const buildResult = ref(null)
const compareResult = ref(null)
const dprResult = ref(null)
const analysisSuggestions = [
  '优先查看样品命中率和命中分子的元素类别分布，先判断样品是否明显接近某个来源数据库。',
  '多个来源数据库之间建议批量计算样品命中率，并输出来源排序表，用于判断样品更接近哪类来源。',
  '建议把 overlap、sample only、database only 分别导出，再进入 VK、DBE、NOSC 和机器学习模块比较类别差异。',
]

const buildFileLabel = computed(() => {
  if (!buildFiles.value.length) return '可一次选择 1 个或多个 CSV，列名支持 Molecular Formula / MolForm / Peak Height'
  return `已选择 ${buildFiles.value.length} 个文件`
})

const canBuild = computed(() => {
  if (!buildFiles.value.length) return false
  if (writeMode.value === 'append') return !!selectedDatabaseId.value
  return !!databaseName.value.trim()
})

const canRunDpr = computed(() => !!dprDatabaseId.value && !!dprUpstreamFile.value && !!dprDownstreamFile.value)

const dprPresenceRows = computed(() => {
  if (!dprResult.value) return []
  return ['D', 'P', 'R'].map((key) => {
    const row = dprResult.value.presence[key]
    return {
      group: key,
      inSource: row.in_source,
      notInSource: row.not_in_source,
      rate: `${row.presence_rate.toFixed(2)}%`,
    }
  })
})

const dprTestRows = computed(() => {
  if (!dprResult.value) return []
  const labels = { overall_3x2: 'D/P/R 总体', p_vs_d: 'P vs D', d_vs_r: 'D vs R' }
  return Object.entries(dprResult.value.tests).map(([key, test]) => {
    const p = test.p_value
    return {
      name: labels[key] || key,
      p: p == null ? 'N/A' : p.toFixed(5),
      result: p == null ? '无法检验' : (p < 0.05 ? '显著' : '不显著'),
    }
  })
})

function triggerBuildInput() { buildInput.value?.click() }
function triggerCompareInput() { compareInput.value?.click() }
function triggerDprInput(which) {
  if (which === 'upstream') dprUpstreamInput.value?.click()
  else dprDownstreamInput.value?.click()
}
function onBuildFiles(event) { buildFiles.value = Array.from(event.target.files || []) }
function onCompareFile(event) { compareFile.value = event.target.files?.[0] || null }
function onDprFile(which, event) {
  const file = event.target.files?.[0] || null
  if (which === 'upstream') dprUpstreamFile.value = file
  else dprDownstreamFile.value = file
}
function formatTime(t) { return t ? new Date(t).toLocaleString('zh-CN') : '-' }
function plotSrc(base64) { return `data:image/png;base64,${base64}` }

async function loadDatabases() {
  loadingDatabases.value = true
  try {
    const res = await api.get('/source-db/databases')
    databases.value = res.databases || []
    if (!compareDatabaseId.value && databases.value.length) compareDatabaseId.value = databases.value[0].id
    if (!dprDatabaseId.value && databases.value.length) dprDatabaseId.value = databases.value[0].id
  } catch (e) {
    ElMessage.error('加载数据库失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loadingDatabases.value = false
  }
}

async function buildDatabase() {
  if (!canBuild.value) return
  building.value = true
  buildResult.value = null
  try {
    const fd = new FormData()
    buildFiles.value.forEach((file) => fd.append('files', file))
    if (writeMode.value === 'append') fd.append('database_id', selectedDatabaseId.value)
    else fd.append('name', databaseName.value.trim())
    fd.append('description', description.value || '')
    buildResult.value = await api.post('/source-db/databases', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 600000,
    })
    ElMessage.success('数据库已更新')
    buildFiles.value = []
    await loadDatabases()
  } catch (e) {
    ElMessage.error('写入失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    building.value = false
  }
}

async function compareDatabase() {
  if (!compareDatabaseId.value || !compareFile.value) return
  comparing.value = true
  compareResult.value = null
  try {
    const fd = new FormData()
    fd.append('database_id', compareDatabaseId.value)
    fd.append('query_file', compareFile.value)
    compareResult.value = await api.post('/source-db/compare', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 600000,
    })
    ElMessage.success('对比完成')
  } catch (e) {
    ElMessage.error('对比失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    comparing.value = false
  }
}

async function runDprDatabase() {
  if (!canRunDpr.value) return
  dprRunning.value = true
  dprResult.value = null
  try {
    const fd = new FormData()
    fd.append('database_id', dprDatabaseId.value)
    fd.append('upstream_file', dprUpstreamFile.value)
    fd.append('downstream_file', dprDownstreamFile.value)
    fd.append('remove_core', dprRemoveCore.value ? 'true' : 'false')
    dprResult.value = await api.post('/source-db/compare-dpr', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 600000,
    })
    ElMessage.success('DPR 数据库对比完成')
  } catch (e) {
    ElMessage.error('DPR 对比失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    dprRunning.value = false
  }
}

function downloadDatabase(row) {
  window.open(`/api/source-db/databases/${row.id}/download`, '_blank')
}

async function deleteDatabase(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除数据库“${row.name}”？该操作不可恢复。`,
      '确认删除',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        confirmButtonClass: 'el-button--danger',
      },
    )
    await api.delete(`/source-db/databases/${row.id}`)
    if (selectedDatabaseId.value === row.id) selectedDatabaseId.value = ''
    if (compareDatabaseId.value === row.id) compareDatabaseId.value = ''
    if (dprDatabaseId.value === row.id) dprDatabaseId.value = ''
    ElMessage.success('数据库已删除')
    await loadDatabases()
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error('删除失败: ' + (e.response?.data?.detail || e.message))
  }
}

function downloadBase64(base64, filename) {
  const link = document.createElement('a')
  link.href = `data:text/csv;base64,${base64}`
  link.download = filename
  link.click()
}

function downloadImageBase64(base64, filename) {
  const link = document.createElement('a')
  link.href = `data:image/png;base64,${base64}`
  link.download = filename
  link.click()
}

function downloadPdfBase64(base64, filename) {
  const link = document.createElement('a')
  link.href = `data:application/pdf;base64,${base64}`
  link.download = filename
  link.click()
}

onMounted(loadDatabases)
</script>

<style lang="scss" scoped>
.source-database { max-width: 1280px; }
.page-title { font-size: 28px; font-weight: 700; margin-bottom: 4px; }
.page-subtitle { color: var(--text-secondary); margin-bottom: 24px; font-size: 14px; }
.section { padding: 24px; margin-bottom: 20px; }
.section-title { font-size: 16px; font-weight: 600; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; .el-icon { color: var(--accent-blue); } }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(260px, 1fr)); gap: 16px; margin-bottom: 18px; }
.field { display: flex; flex-direction: column; gap: 8px; span { color: var(--text-secondary); font-size: 13px; } }
.field.full { grid-column: 1 / -1; }
.upload-box {
  min-height: 150px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px;
  padding: 22px; border: 2px dashed var(--border-color); border-radius: var(--radius-md);
  background: var(--bg-secondary); cursor: pointer; transition: all 0.2s; margin-bottom: 12px;
  &:hover { border-color: var(--accent-blue); background: rgba(59, 130, 246, 0.05); }
  .el-icon { font-size: 34px; color: var(--text-muted); }
  strong { color: var(--text-primary); }
  span { color: var(--text-secondary); font-size: 13px; text-align: center; }
}
.file-list, .source-files { display: flex; gap: 8px; flex-wrap: wrap; }
.operation-buttons { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.actions, .download-row { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }
.db-table { border-radius: var(--radius-md); overflow: hidden; }
.compare-row { display: grid; grid-template-columns: minmax(260px, 360px) 1fr auto; gap: 12px; align-items: stretch; }
.dpr-row { display: grid; grid-template-columns: minmax(220px, 320px) 1fr 1fr; gap: 12px; align-items: stretch; }
.sample-picker {
  min-height: 74px; display: flex; align-items: center; gap: 12px; padding: 12px 14px;
  border: 2px solid #3b82f6; border-radius: var(--radius-md); cursor: pointer;
  color: var(--text-primary); background: rgba(59, 130, 246, 0.12);
  box-shadow: inset 0 0 0 1px rgba(147, 197, 253, 0.35);
  .el-icon { font-size: 28px; color: #60a5fa; flex-shrink: 0; }
  strong { display: block; color: #e5f0ff; font-size: 14px; margin-bottom: 4px; }
  span { display: block; color: #a7bedc; font-size: 12px; line-height: 1.4; }
  &:hover { background: rgba(59, 130, 246, 0.18); border-color: #60a5fa; }
  &.selected { border-color: #22c55e; background: rgba(34, 197, 94, 0.12); }
}
.stats-row { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 16px; }
.stat-card {
  min-width: 150px; padding: 16px 20px; text-align: center;
  background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-md);
}
.stat-val { display: block; font-size: 23px; font-weight: 700; color: var(--accent-blue); }
.stat-lbl { display: block; margin-top: 4px; font-size: 12px; color: var(--text-secondary); }
.result-grid { display: grid; grid-template-columns: minmax(360px, 0.95fr) minmax(420px, 1.05fr); gap: 16px; margin-top: 16px; align-items: start; }
.compare-result-grid { grid-template-columns: minmax(320px, 420px) minmax(520px, 1fr); }
.info-panel, .plot-item, .suggestions {
  background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 16px;
  align-self: start;
}
h3 { font-size: 15px; margin-bottom: 12px; }
.plot-and-advice { display: grid; grid-template-columns: minmax(360px, 1fr) minmax(320px, 0.9fr); gap: 16px; margin-top: 16px; }
.plot-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; margin-top: 16px; }
.plot-item img { width: 100%; height: auto; background: #fff; border-radius: var(--radius-sm); margin-bottom: 10px; }
.plot-downloads { display: flex; gap: 8px; flex-wrap: wrap; }
.suggestions { color: var(--text-secondary); line-height: 1.7; p { margin-bottom: 10px; } }
.muted { color: var(--text-muted); font-size: 12px; }
@media (max-width: 900px) {
  .form-grid, .compare-row, .dpr-row, .result-grid, .plot-and-advice { grid-template-columns: 1fr; }
}
</style>
