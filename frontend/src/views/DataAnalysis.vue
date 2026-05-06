<template>
  <div class="data-analysis">
    <h1 class="page-title">{{ pageText.title }}</h1>
    <p class="page-subtitle">{{ pageText.subtitle }}</p>

    <!-- Step 1: Upload CSVs -->
    <section class="section card-glass">
      <h2 class="section-title"><el-icon><Upload /></el-icon> 上传 CSV 文件</h2>
      <div class="upload-row">
        <div class="upload-box" @click="triggerInput(1)">
          <input ref="input1" type="file" accept=".csv" style="display:none" @change="onFile(1, $event)" />
          <el-icon><Document /></el-icon>
          <span>{{ file1?.name || '选择文件 1 (S1.csv)' }}</span>
        </div>
        <div class="upload-box" @click="triggerInput(2)">
          <input ref="input2" type="file" accept=".csv" style="display:none" @change="onFile(2, $event)" />
          <el-icon><Document /></el-icon>
          <span>{{ file2?.name || '选择文件 2 (S8.csv)' }}</span>
        </div>
      </div>
      <el-button type="primary" :disabled="!file1 || !file2 || processing" @click="processFiles" style="margin-top:12px">
        <el-icon v-if="!processing"><CaretRight /></el-icon>
        <el-icon v-else class="is-loading"><Loading /></el-icon>
        {{ processing ? '处理中...' : '开始处理' }}
      </el-button>
    </section>

    <!-- Step 2: Results -->
    <section v-if="result" class="section card-glass">
      <h2 class="section-title"><el-icon><CircleCheck /></el-icon> 处理结果</h2>
      <div class="result-info">
        <span>原始矩阵: {{ result.raw_matrix_shape[0] }} × {{ result.raw_matrix_shape[1] }}</span>
        <span>归一化矩阵: {{ result.binary_matrix_shape[0] }} × {{ result.binary_matrix_shape[1] }}</span>
        <span>计算指标: {{ result.columns?.filter(c => !['MolForm','Col1','Col2'].includes(c)).join(', ') }}</span>
      </div>
      <div class="download-row">
        <el-button type="primary" @click="downloadFinal"><el-icon><Download /></el-icon> 下载完整结果 CSV</el-button>
        <el-button @click="goToTaskDetail"><el-icon><View /></el-icon> 查看详情 (历史记录)</el-button>
      </div>
    </section>

    <!-- Step 3: DPR Chart -->
    <section class="section card-glass">
      <h2 class="section-title"><el-icon><DataLine /></el-icon> DPR Van Krevelen 图</h2>
      <div class="dpr-controls">
        <div class="dpr-upload" @click="triggerDprInput">
          <input ref="dprInput" type="file" accept=".csv" style="display:none" @change="onDprFile" />
          <el-button size="small"><el-icon><Upload /></el-icon> 上传转置 CSV</el-button>
        </div>
        <span v-if="dprFilename" class="dpr-filename">{{ dprFilename }}</span>
        <el-divider direction="vertical" />
        <span>显示类别:</span>
        <el-select v-model="dprCategory" size="small" style="width:160px">
          <el-option label="全部" value="all" />
          <el-option label="Disappearance" value="Disappearance" />
          <el-option label="Resistant" value="Resistant" />
          <el-option label="Product" value="Product" />
        </el-select>
        <el-divider direction="vertical" />
        <span>散点大小</span>
        <el-input-number v-model="dprDotSize" :min="1" :max="100" size="small" controls-position="right" style="width:80px" />
        <el-divider direction="vertical" />
        <el-select v-model="dprFont" size="small" style="width:120px">
          <el-option label="Times New Roman" value="Times New Roman" />
          <el-option label="Arial" value="Arial" />
        </el-select>
        <el-input-number v-model="dprFontSize" :min="8" :max="24" size="small" controls-position="right" style="width:80px" />
        <span class="toolbar-label">字体</span>
        <el-divider direction="vertical" />
        <el-input v-model="dprPanelLabel" size="small" style="width:80px" placeholder="标签" />
        <el-divider direction="vertical" />
        <el-button size="small" type="primary" @click="exportDpr('pdf')"><el-icon><Document /></el-icon> PDF</el-button>
        <el-button size="small" @click="exportDpr('tif')"><el-icon><Picture /></el-icon> TIF</el-button>
      </div>
      <div class="chart-box dpr-preview">
        <img v-if="dprPreviewUrl" :src="dprPreviewUrl" alt="DPR Van Krevelen" />
        <el-empty v-else description="请先处理或上传 DPR CSV" />
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api/index'
import { useI18n } from '../i18n'

const router = useRouter()
const { lang } = useI18n()
const pageText = computed(() => lang.value === 'zh'
  ? { title: '数据分析', subtitle: '上传两个 CSV 文件，生成 DPR 分类结果和 DPR Van Krevelen 图。' }
  : { title: 'Data Analysis', subtitle: 'Upload two CSV files to generate DPR classes and DPR Van Krevelen plots.' })
const input1 = ref(null)
const input2 = ref(null)
const dprInput = ref(null)
const file1 = ref(null)
const file2 = ref(null)
const processing = ref(false)
const result = ref(null)
const dprSessionId = ref(null)
const dprFilename = ref(null)
const dprCategory = ref('all')
const dprDotSize = ref(6)
const dprFont = ref('Times New Roman')
const dprFontSize = ref(12)
const dprPanelLabel = ref('')

const dprParams = computed(() => new URLSearchParams({
  category: dprCategory.value,
  font_size: dprFontSize.value,
  scale: '1.0',
  panel_label: dprPanelLabel.value,
  dot_size: dprDotSize.value,
  font_family: dprFont.value,
}).toString())

const dprPreviewUrl = computed(() => {
  if (!dprSessionId.value || !dprFilename.value) return ''
  return `/api/data-analysis/export-svg/${encodeURIComponent(dprSessionId.value)}/${encodeURIComponent(dprFilename.value)}?${dprParams.value}`
})

function triggerInput(n) { (n === 1 ? input1 : input2).value?.click() }
function triggerDprInput() { dprInput.value?.click() }
function onFile(n, e) { if (n === 1) file1.value = e.target.files[0]; else file2.value = e.target.files[0] }

function goToTaskDetail() {
  if (result.value?.task_id) {
    router.push(`/task/${result.value.task_id}`)
  }
}

async function processFiles() {
  if (!file1.value || !file2.value) return
  processing.value = true
  try {
    const fd = new FormData()
    fd.append('file1', file1.value)
    fd.append('file2', file2.value)
    const res = await api.post('/data-analysis/process', fd, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 600000 })
    result.value = res
    dprSessionId.value = res.session_id
    dprFilename.value = res.final_file
    ElMessage.success('处理完成，已自动计算指标')
  } catch (e) {
    ElMessage.error('处理失败: ' + (e.response?.data?.detail || e.message))
  } finally { processing.value = false }
}

function downloadFinal() {
  if (!result.value) return
  window.open(`/api/data-analysis/download/${result.value.session_id}/${result.value.final_file}`, '_blank')
}

async function onDprFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  try {
    const fd = new FormData()
    fd.append('file', file)
    const res = await api.post('/data-analysis/upload-dpr-csv', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    dprSessionId.value = res.session_id
    dprFilename.value = res.filename
  } catch (e) { ElMessage.error('上传失败: ' + (e.response?.data?.detail || e.message)) }
}

function exportDpr(format) {
  if (!dprSessionId.value || !dprFilename.value) { ElMessage.warning('请先加载数据'); return }
  window.open(`/api/data-analysis/export-${format}/${encodeURIComponent(dprSessionId.value)}/${encodeURIComponent(dprFilename.value)}?${dprParams.value}`, '_blank')
}
</script>

<style lang="scss" scoped>
.data-analysis { max-width: 1200px; }
.page-title { font-size: 28px; font-weight: 700; margin-bottom: 4px; }
.page-subtitle { color: var(--text-secondary); margin-bottom: 24px; font-size: 14px; }
.section { padding: 24px; margin-bottom: 20px; }
.section-title { font-size: 16px; font-weight: 600; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; .el-icon { color: var(--accent-blue); } }
.upload-row { display: flex; gap: 16px; }
.upload-box {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px;
  padding: 28px; border: 2px dashed var(--border-color); border-radius: var(--radius-md);
  background: var(--bg-secondary); cursor: pointer; transition: all 0.3s;
  &:hover { border-color: var(--accent-blue); }
  .el-icon { font-size: 32px; color: var(--text-muted); }
  span { color: var(--text-secondary); font-size: 13px; }
}
.result-info { display: flex; gap: 20px; margin-bottom: 12px; color: var(--text-secondary); font-size: 14px; }
.download-row { display: flex; gap: 12px; }
.dpr-controls { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.dpr-filename { font-size: 12px; color: var(--accent-green); }
.toolbar-label { font-size: 12px; color: var(--text-muted); }
.chart-box { width: 100%; min-height: 500px; }
.dpr-preview { display: flex; align-items: center; justify-content: center; background: white; overflow: auto; }
.dpr-preview img { width: 100%; max-height: 760px; object-fit: contain; }
:deep(.el-card) { background: var(--bg-card); border-color: var(--border-color); }
</style>
