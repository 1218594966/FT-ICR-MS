<template>
  <div class="new-analysis">
    <h1 class="page-title">{{ pageText.title }}</h1>
    <p class="page-subtitle">{{ pageText.subtitle }}</p>

    <!-- Step 1: File Upload -->
    <section class="section card-glass">
      <h2 class="section-title"><el-icon><Upload /></el-icon> 数据文件上传</h2>

      <div class="upload-tabs">
        <div :class="['tab-btn', { active: uploadMode === 'folder' }]" @click="uploadMode = 'folder'">
          <el-icon><FolderOpened /></el-icon> 文件夹上传
        </div>
        <div :class="['tab-btn', { active: uploadMode === 'zip' }]" @click="uploadMode = 'zip'">
          <el-icon><Document /></el-icon> ZIP 上传
        </div>
      </div>

      <!-- Folder upload mode -->
      <div v-if="uploadMode === 'folder'" class="upload-dropzone" @click="triggerFolderInput" @dragover.prevent @drop.prevent="handleFolderDrop">
        <input ref="folderInputRef" type="file" webkitdirectory mozdirectory multiple style="display:none" @change="handleFolderSelect" />
        <el-icon class="upload-icon"><FolderOpened /></el-icon>
        <div class="upload-text">点击选择 <strong>.d 文件夹</strong>，支持多次选择添加多个文件</div>
        <div class="upload-tip">直接选择 Bruker .d 文件夹，可添加多个后按顺序分析</div>
      </div>

      <!-- ZIP upload mode -->
      <div v-else class="upload-dropzone" @click="triggerZipInput" @dragover.prevent @drop.prevent="handleZipDrop">
        <input ref="zipInputRef" type="file" accept=".zip" multiple style="display:none" @change="handleZipSelect" />
        <el-icon class="upload-icon"><Document /></el-icon>
        <div class="upload-text">点击选择 <strong>.zip 文件</strong>，支持多选</div>
        <div class="upload-tip">将 .d 文件夹压缩为 .zip 后上传</div>
      </div>

      <!-- Upload progress -->
      <div v-if="uploading" class="upload-progress">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>正在上传 {{ uploadProgress }}% ...</span>
        <el-progress :percentage="uploadProgress" :stroke-width="4" :show-text="false" style="flex:1" />
      </div>

      <!-- Uploaded files list -->
      <div v-if="uploadedFiles.length" class="upload-list">
        <div v-for="(f, i) in uploadedFiles" :key="i" class="upload-success">
          <el-icon color="#10b981"><CircleCheck /></el-icon>
          <span class="success-name">{{ f.filename }}</span>
          <span class="success-size" v-if="f.size">{{ formatSize(f.size) }}</span>
          <span class="success-size" v-if="f.file_count">{{ f.file_count }} 个文件</span>
          <el-tag v-if="f.taskStatus" :type="f.taskStatus === 'success' ? 'success' : f.taskStatus === 'running' ? 'warning' : 'info'" size="small" effect="dark" style="margin-left:8px">
            {{ { success: '成功', running: '运行中', failed: '失败', pending: '等待中' }[f.taskStatus] || f.taskStatus }}
          </el-tag>
          <el-button text type="danger" size="small" @click="removeUpload(i)" style="margin-left:auto">
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>
    </section>

    <!-- Step 2: Parameters -->
    <section class="section card-glass">
      <h2 class="section-title"><el-icon><Setting /></el-icon> 分析参数配置</h2>

      <el-collapse v-model="activePanels">
        <!-- Peak Detection -->
        <el-collapse-item title="峰检测参数" name="peak">
          <div class="param-grid">
            <div class="param-item">
              <label>峰最小突出度 (%)</label>
              <el-input-number v-model="params.peak_detection.peak_min_prominence_percent" :min="0" :max="1" :step="0.001" :precision="3" />
            </div>
          </div>
        </el-collapse-item>

        <!-- Calibration -->
        <el-collapse-item title="校准参数" name="calibration">
          <div class="param-grid">
            <div class="param-item">
              <label>m/z 范围</label>
              <div class="range-inputs">
                <el-input-number v-model="params.calibration.min_noise_mz" :min="0" :max="10000" />
                <span>~</span>
                <el-input-number v-model="params.calibration.max_noise_mz" :min="0" :max="10000" />
              </div>
            </div>
            <div class="param-item">
              <label>ppm 误差范围</label>
              <div class="range-inputs">
                <el-input-number v-model="params.calibration.min_calib_ppm_error" :min="-10" :max="10" :step="0.1" />
                <span>~</span>
                <el-input-number v-model="params.calibration.max_calib_ppm_error" :min="-10" :max="10" :step="0.1" />
              </div>
            </div>
          </div>
        </el-collapse-item>

        <!-- Preliminary Search -->
        <el-collapse-item title="初步分子式搜索参数" name="prelim">
          <div class="param-grid">
            <div class="param-item" v-for="elem in ['C', 'H', 'O']" :key="'pre_'+elem">
              <label>{{ elem }} 原子范围</label>
              <div class="range-inputs">
                <el-input-number v-model="params.preliminary_search.used_atoms[elem][0]" :min="0" :max="200" size="small" />
                <span>~</span>
                <el-input-number v-model="params.preliminary_search.used_atoms[elem][1]" :min="0" :max="200" size="small" />
              </div>
            </div>
            <div class="param-item">
              <label>ppm 误差范围</label>
              <div class="range-inputs">
                <el-input-number v-model="params.preliminary_search.min_ppm_error" :min="-50" :max="0" :step="0.5" />
                <span>~</span>
                <el-input-number v-model="params.preliminary_search.max_ppm_error" :min="0" :max="50" :step="0.5" />
              </div>
            </div>
          </div>
        </el-collapse-item>

        <!-- Full Search -->
        <el-collapse-item title="完整分子式搜索参数" name="full">
          <div class="param-grid">
            <div class="param-item" v-for="elem in allElements" :key="'full_'+elem">
              <label>{{ elem }} 原子范围</label>
              <div class="range-inputs">
                <el-input-number v-model="params.full_search.used_atoms[elem][0]" :min="0" :max="200" size="small" />
                <span>~</span>
                <el-input-number v-model="params.full_search.used_atoms[elem][1]" :min="0" :max="200" size="small" />
              </div>
            </div>
            <div class="param-item">
              <label>ppm 误差范围</label>
              <div class="range-inputs">
                <el-input-number v-model="params.full_search.min_ppm_error" :min="-50" :max="0" :step="0.1" />
                <span>~</span>
                <el-input-number v-model="params.full_search.max_ppm_error" :min="0" :max="50" :step="0.1" />
              </div>
            </div>
            <div class="param-item">
              <label>H/C 范围</label>
              <div class="range-inputs">
                <el-input-number v-model="params.full_search.min_hc" :min="0" :max="5" :step="0.05" />
                <span>~</span>
                <el-input-number v-model="params.full_search.max_hc" :min="0" :max="5" :step="0.05" />
              </div>
            </div>
            <div class="param-item">
              <label>O/C 范围</label>
              <div class="range-inputs">
                <el-input-number v-model="params.full_search.min_oc" :min="0" :max="5" :step="0.05" />
                <span>~</span>
                <el-input-number v-model="params.full_search.max_oc" :min="0" :max="5" :step="0.05" />
              </div>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>

      <div class="param-actions">
        <el-button @click="resetParams">
          <el-icon><RefreshLeft /></el-icon> 恢复默认参数
        </el-button>
        <el-button type="primary" size="large" :disabled="!uploadedFiles.length || running" @click="startAnalysis">
          <el-icon v-if="!running"><CaretRight /></el-icon>
          <el-icon v-else class="is-loading"><Loading /></el-icon>
          {{ running ? '分析中...' : '开始分析' }}
        </el-button>
      </div>
    </section>

    <!-- Step 3: Progress -->
    <transition name="slide">
      <section v-if="running || taskResult" class="section card-glass">
        <h2 class="section-title"><el-icon><TrendCharts /></el-icon> 分析进度</h2>
        <div class="progress-section">
          <el-progress
            :percentage="progress"
            :stroke-width="12"
            :color="progressColors"
            :format="(p) => p.toFixed(0) + '%'"
          />
          <div class="step-info">
            <span v-if="running" class="current-step">
              <el-icon class="is-loading"><Loading /></el-icon>
              {{ currentStepName }} ...
            </span>
            <span v-else-if="taskResult?.status === 'success'" class="step-done">
              <el-icon color="#10b981"><CircleCheck /></el-icon> 分析完成
            </span>
            <span v-else-if="taskResult?.status === 'failed'" class="step-fail">
              <el-icon color="#ef4444"><CircleClose /></el-icon> 分析失败
            </span>
          </div>
          <div class="step-timeline" v-if="stepNames.length">
            <div
              v-for="(name, i) in stepNames"
              :key="i"
              class="timeline-item"
              :class="{ active: currentStep === i + 1, done: currentStep > i + 1 }"
            >
              <div class="timeline-dot" />
              <span>{{ name }}</span>
            </div>
          </div>
        </div>
      </section>
    </transition>

    <!-- Step 4: Results Preview -->
    <transition name="slide">
      <section v-if="taskResult?.status === 'success'" class="section card-glass">
        <h2 class="section-title"><el-icon><DataLine /></el-icon> 分析结果预览</h2>

        <div class="result-summary">
          <div class="summary-item" v-for="item in summaryItems" :key="item.label">
            <span class="summary-value">{{ item.value }}</span>
            <span class="summary-label">{{ item.label }}</span>
          </div>
        </div>

        <el-tabs v-model="activeChart" type="border-card">
          <el-tab-pane label="质谱图" name="spectrum">
            <div ref="spectrumChart" class="chart-container" />
          </el-tab-pane>
          <el-tab-pane label="m/z vs ppm 误差" name="error">
            <div ref="errorChart" class="chart-container" />
          </el-tab-pane>
          <el-tab-pane label="化合物分类" name="classification">
            <div ref="classChart" class="chart-container" />
          </el-tab-pane>
        </el-tabs>

        <div class="result-actions">
          <el-button type="primary" size="large" @click="exportCSV">
            <el-icon><Download /></el-icon> 导出 CSV
          </el-button>
          <el-button size="large" @click="$router.push(`/task/${taskId}`)">
            <el-icon><View /></el-icon> 查看完整报告
          </el-button>
        </div>
      </section>
    </transition>
  </div>
</template>

<script setup>
import { computed, ref, reactive, onUnmounted, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { uploadDataFile, uploadFolder, startAnalysis as apiStart, getTaskStatus, getChartData, getExportUrl } from '../api/analysis'
import { useI18n } from '../i18n'

const { lang } = useI18n()
const pageText = computed(() => lang.value === 'zh'
  ? { title: '新建分析', subtitle: '上传 FT-ICR MS 数据文件，配置分析参数，一键开始分析' }
  : { title: 'New Analysis', subtitle: 'Upload FT-ICR MS data, configure parameters, and start analysis.' })

const allElements = ['C', 'H', 'O', 'N', 'S', 'P', 'Cl']
const stepNames = [
  '峰检测', 'Kendrick 过滤', '初步搜索', '质量校准',
  '完整搜索', '指标计算', '氮规则', '化合物分类', '加权平均',
]
const activePanels = ref(['peak', 'full'])
const uploadMode = ref('folder')
const folderInputRef = ref(null)
const zipInputRef = ref(null)
const uploadedFiles = ref([])
const uploading = ref(false)
const uploadProgress = ref(0)
const running = ref(false)
const progress = ref(0)
const currentStep = ref(0)
const currentStepName = ref('')
const taskId = ref(null)
const taskResult = ref(null)
const activeChart = ref('spectrum')
const spectrumChart = ref(null)
const errorChart = ref(null)
const classChart = ref(null)

const progressColors = [
  { color: '#3b82f6', percentage: 30 },
  { color: '#06b6d4', percentage: 60 },
  { color: '#10b981', percentage: 100 },
]

const params = reactive({
  peak_detection: { threshold_method: 'log', noise_threshold_log_nsigma: 6, peak_min_prominence_percent: 0.01 },
  kendrick_filter: { kendrick_rounding_method: 'ceil' },
  calibration: { min_noise_mz: 100, max_noise_mz: 999, min_picking_mz: 100, max_picking_mz: 999, max_calib_ppm_error: 1, min_calib_ppm_error: -1, calib_pol_order: 2 },
  preliminary_search: {
    used_atoms: { C: [4, 50], H: [4, 120], O: [1, 50], N: [0, 0], S: [0, 0], P: [0, 0], Cl: [0, 0] },
    min_ppm_error: -5, max_ppm_error: 5, is_protonated: true, is_radical: false, is_adduct: true,
  },
  full_search: {
    used_atoms: { C: [4, 50], H: [4, 120], O: [1, 50], N: [0, 5], S: [0, 3], P: [0, 0], Cl: [0, 0] },
    min_ppm_error: -1, max_ppm_error: 1, is_protonated: true, is_radical: false, is_adduct: false,
    min_hc: 0.3, max_hc: 2.25, min_oc: 0.0, max_oc: 1.2,
  },
})

let polling = null

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}

function triggerFolderInput() {
  folderInputRef.value?.click()
}
function triggerZipInput() {
  zipInputRef.value?.click()
}

function removeUpload(i) { uploadedFiles.value.splice(i, 1) }

async function handleFolderSelect(e) {
  const files = e.target.files
  if (!files || !files.length) return
  await doFolderUpload(files)
  e.target.value = ''
}

function handleFolderDrop(e) { ElMessage.info('请点击按钮选择 .d 文件夹') }

async function doFolderUpload(files) {
  uploading.value = true
  uploadProgress.value = 0
  try {
    const progressTimer = setInterval(() => { if (uploadProgress.value < 90) uploadProgress.value += 10 }, 300)
    const res = await uploadFolder(files)
    clearInterval(progressTimer)
    uploadProgress.value = 100
    uploadedFiles.value.push(res)
    ElMessage.success(`上传成功: ${res.filename} (${res.file_count} 个文件)`)
  } catch (e) { ElMessage.error('上传失败: ' + e.message) }
  finally { uploading.value = false }
}

async function handleZipSelect(e) {
  const files = e.target.files
  if (!files) return
  for (const file of files) { await doZipUpload(file) }
  e.target.value = ''
}

function handleZipDrop(e) {
  const files = e.dataTransfer?.files
  if (!files) return
  for (const file of files) {
    if (!file.name.endsWith('.zip')) { ElMessage.warning(`${file.name} 不是 .zip 文件`); continue }
    doZipUpload(file)
  }
}

async function doZipUpload(file) {
  uploading.value = true
  uploadProgress.value = 0
  try {
    const progressTimer = setInterval(() => { if (uploadProgress.value < 90) uploadProgress.value += 10 }, 300)
    const res = await uploadDataFile(file)
    clearInterval(progressTimer)
    uploadProgress.value = 100
    uploadedFiles.value.push(res)
    ElMessage.success(`上传成功: ${res.filename}`)
  } catch (e) { ElMessage.error('上传失败: ' + e.message) }
  finally { uploading.value = false }
}

function resetParams() {
  Object.assign(params, {
    peak_detection: { threshold_method: 'log', noise_threshold_log_nsigma: 6, peak_min_prominence_percent: 0.01 },
    kendrick_filter: { kendrick_rounding_method: 'ceil' },
    calibration: { min_noise_mz: 100, max_noise_mz: 999, min_picking_mz: 100, max_picking_mz: 999, max_calib_ppm_error: 1, min_calib_ppm_error: -1, calib_pol_order: 2 },
    preliminary_search: {
      used_atoms: { C: [4, 50], H: [4, 120], O: [1, 50], N: [0, 0], S: [0, 0], P: [0, 0], Cl: [0, 0] },
      min_ppm_error: -5, max_ppm_error: 5, is_protonated: true, is_radical: false, is_adduct: true,
    },
    full_search: {
      used_atoms: { C: [4, 50], H: [4, 120], O: [1, 50], N: [0, 5], S: [0, 3], P: [0, 0], Cl: [0, 0] },
      min_ppm_error: -1, max_ppm_error: 1, is_protonated: true, is_radical: false, is_adduct: false,
      min_hc: 0.3, max_hc: 2.25, min_oc: 0.0, max_oc: 1.2,
    },
  })
  ElMessage.info('参数已恢复默认值')
}

async function startAnalysis() {
  if (!uploadedFiles.value.length) return ElMessage.warning('请先上传数据文件')
  running.value = true
  taskResult.value = null

  for (let i = 0; i < uploadedFiles.value.length; i++) {
    const f = uploadedFiles.value[i]
    progress.value = 0
    currentStep.value = 0
    currentStepName.value = ''
    f.taskStatus = 'running'

    try {
      const res = await apiStart(f.task_id, f.file_path, f.filename, params)
      f.taskId = res.id
      taskId.value = res.id

      await new Promise((resolve, reject) => {
        const poll = setInterval(async () => {
          try {
            const status = await getTaskStatus(res.id)
            progress.value = status.progress || 0
            currentStepName.value = mapStepName(status.current_step)
            const stepIdx = stepNames.indexOf(currentStepName.value)
            currentStep.value = stepIdx >= 0 ? stepIdx + 1 : currentStep.value
            f.taskStatus = status.status

            if (status.status === 'success') {
              clearInterval(poll)
              taskResult.value = status
              await loadResults(res.id)
              ElMessage.success(`[${i + 1}/${uploadedFiles.value.length}] ${f.filename} 分析完成！`)
              resolve()
            } else if (status.status === 'failed') {
              clearInterval(poll)
              taskResult.value = status
              ElMessage.error(`${f.filename} 分析失败: ${status.error_message || '未知错误'}`)
              resolve()
            }
          } catch {}
        }, 1500)
      })
    } catch (e) {
      f.taskStatus = 'failed'
      ElMessage.error(`${f.filename} 启动失败: ${e.message}`)
    }
  }
  running.value = false
}

function mapStepName(step) {
  const map = {
    peak_detection: '峰检测', kendrick_filter: 'Kendrick 过滤', preliminary_search: '初步搜索',
    calibration: '质量校准', full_search: '完整搜索', indices_calc: '指标计算',
    nitrogen_rule: '氮规则', classification: '化合物分类', weighted_avg: '加权平均',
  }
  return map[step] || step
}

const summaryItems = ref([])

async function loadResults(tid) {
  try {
    const [spectrum, error, classification, weighted] = await Promise.all([
      getChartData(tid, 'spectrum'),
      getChartData(tid, 'error'),
      getChartData(tid, 'classification'),
      getChartData(tid, 'weighted'),
    ])

    const detail = await getChartData(tid, 'error')
    const totalPeaks = detail.mz?.length || 0

    summaryItems.value = [
      { label: '总峰数', value: totalPeaks },
      { label: '化合物类别数', value: Object.keys(classification).length },
      { label: '分析耗时', value: '-' },
    ]

    await nextTick()
    renderSpectrum(spectrum)
    renderError(error)
    renderClassification(classification)

    watch(activeChart, async (val) => {
      await nextTick()
      if (val === 'spectrum') renderSpectrum(spectrum)
      else if (val === 'error') renderError(error)
      else if (val === 'classification') renderClassification(classification)
    })
  } catch (e) {
    console.error('Load results error:', e)
  }
}

function renderSpectrum(data) {
  if (!spectrumChart.value || !data.mz?.length) return
  const chart = echarts.init(spectrumChart.value)
  const sampled = data.mz.length > 5000 ? sampleData(data.mz, data.abundance, 5000) : data
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'value', name: 'm/z', axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { color: '#1e3a5f' } } },
    yAxis: { type: 'value', name: 'Abundance', axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { color: '#1e3a5f' } } },
    series: [{
      type: 'line', data: sampled.mz.map((m, i) => [m, sampled.abundance[i]]),
      lineStyle: { color: '#3b82f6', width: 1 }, symbol: 'none', large: true,
    }],
    grid: { left: 60, right: 20, top: 30, bottom: 40 },
  })
}

function renderError(data) {
  if (!errorChart.value || !data.mz?.length) return
  const chart = echarts.init(errorChart.value)
  const sampled = data.mz.length > 5000 ? sampleData(data.mz, data.ppm_error, 5000) : data
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item', formatter: (p) => `m/z: ${p.value[0].toFixed(4)}<br/>ppm: ${p.value[1].toFixed(3)}` },
    xAxis: { type: 'value', name: 'm/z', axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { color: '#1e3a5f' } } },
    yAxis: { type: 'value', name: 'Error (ppm)', axisLabel: { color: '#94a3b8' }, splitLine: { lineStyle: { color: '#1e3a5f' } } },
    series: [{
      type: 'scatter', data: sampled.mz.map((m, i) => [m, sampled.ppm_error[i]]),
      symbolSize: 3, itemStyle: { color: '#06b6d4' }, large: true,
    }],
    grid: { left: 60, right: 20, top: 30, bottom: 40 },
  })
}

function renderClassification(data) {
  if (!classChart.value || !Object.keys(data).length) return
  const chart = echarts.init(classChart.value)
  const colors = ['#3b82f6', '#06b6d4', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444', '#ec4899', '#64748b']
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { orient: 'vertical', right: 10, top: 'center', textStyle: { color: '#94a3b8' } },
    series: [{
      type: 'pie', radius: ['40%', '70%'], center: ['40%', '50%'],
      itemStyle: { borderRadius: 6, borderColor: '#1a2332', borderWidth: 2 },
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold', color: '#e2e8f0' } },
      data: Object.entries(data).map(([name, value], i) => ({ name, value, itemStyle: { color: colors[i % colors.length] } })),
    }],
  })
}

function sampleData(x, y, n) {
  const step = Math.max(1, Math.floor(x.length / n))
  const sx = [], sy = []
  for (let i = 0; i < x.length; i += step) { sx.push(x[i]); sy.push(y[i]) }
  return { mz: sx, abundance: sy, ppm_error: sy }
}

function exportCSV() {
  if (!taskId.value) return
  window.open(getExportUrl(taskId.value), '_blank')
}

onUnmounted(() => {
  if (polling) clearInterval(polling)
})
</script>

<style lang="scss" scoped>
.new-analysis { max-width: 1200px; }
.page-title { font-size: 28px; font-weight: 700; margin-bottom: 4px; }
.page-subtitle { color: var(--text-secondary); margin-bottom: 24px; font-size: 14px; }
.section {
  padding: 24px;
  margin-bottom: 20px;
}
.section-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  .el-icon { color: var(--accent-blue); }
}
.upload-tabs {
  display: flex; gap: 0; margin-bottom: 16px;
  border: 1px solid var(--border-color); border-radius: var(--radius-md); overflow: hidden;
  width: fit-content;
}
.tab-btn {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 20px; font-size: 13px; cursor: pointer;
  background: var(--bg-secondary); color: var(--text-secondary);
  border-right: 1px solid var(--border-color);
  transition: all 0.2s;
  &:last-child { border-right: none; }
  &:hover { color: var(--text-primary); }
  &.active {
    background: rgba(59, 130, 246, 0.12);
    color: var(--accent-blue);
  }
}
.upload-dropzone {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 48px 24px; border: 2px dashed var(--border-color); border-radius: var(--radius-md);
  background: var(--bg-secondary); cursor: pointer; transition: all 0.3s;
  &:hover { border-color: var(--accent-blue); background: rgba(59, 130, 246, 0.04); }
}
.upload-icon { font-size: 48px; color: var(--text-muted); margin-bottom: 12px; }
.upload-text { color: var(--text-secondary); font-size: 14px; text-align: center;
  strong { color: var(--accent-blue); }
}
.upload-tip { color: var(--text-muted); font-size: 12px; margin-top: 8px; }
.upload-progress {
  display: flex; align-items: center; gap: 10px;
  margin-top: 12px; padding: 10px 14px;
  background: rgba(59, 130, 246, 0.06); border-radius: var(--radius-sm);
  color: var(--accent-blue); font-size: 13px;
}
.upload-list { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.upload-success {
  display: flex; align-items: center; gap: 8px;
  margin-top: 12px; padding: 10px 14px;
  background: rgba(16, 185, 129, 0.08); border-radius: var(--radius-sm);
  color: var(--accent-green); font-size: 14px;
}
.success-name { font-weight: 600; }
.success-size { color: var(--text-muted); font-size: 12px; }

.param-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
}
.param-item {
  label {
    display: block; font-size: 13px; color: var(--text-secondary);
    margin-bottom: 6px;
  }
}
.range-inputs {
  display: flex; align-items: center; gap: 8px;
  span { color: var(--text-muted); }
}
.checkbox-group {
  display: flex; gap: 16px;
  .el-checkbox { color: var(--text-primary); }
}
.param-actions {
  display: flex; justify-content: space-between; align-items: center;
  margin-top: 20px; padding-top: 16px;
  border-top: 1px solid var(--border-color);
}

.progress-section { text-align: center; }
.current-step {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  margin-top: 12px; color: var(--accent-blue); font-size: 14px;
}
.step-done, .step-fail {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  margin-top: 12px; font-size: 14px;
}
.step-done { color: var(--accent-green); }
.step-fail { color: var(--accent-red); }
.step-timeline {
  display: flex; justify-content: center; gap: 4px;
  margin-top: 20px; flex-wrap: wrap;
}
.timeline-item {
  display: flex; align-items: center; gap: 4px;
  font-size: 12px; color: var(--text-muted);
  padding: 4px 10px; border-radius: 20px;
  background: var(--bg-secondary);
  &.active { color: var(--accent-blue); background: rgba(59, 130, 246, 0.12); }
  &.done { color: var(--accent-green); background: rgba(16, 185, 129, 0.08); }
}
.timeline-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--text-muted);
  .active & { background: var(--accent-blue); }
  .done & { background: var(--accent-green); }
}

.result-summary {
  display: flex; gap: 20px; margin-bottom: 20px; flex-wrap: wrap;
}
.summary-item {
  padding: 16px 24px; background: var(--bg-secondary);
  border-radius: var(--radius-md); text-align: center;
  border: 1px solid var(--border-color);
}
.summary-value {
  display: block; font-size: 24px; font-weight: 700;
  background: var(--accent-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.summary-label { font-size: 12px; color: var(--text-secondary); margin-top: 4px; }

.chart-container { width: 100%; height: 400px; }
.result-actions {
  display: flex; gap: 12px; margin-top: 20px; justify-content: center;
}

:deep(.el-collapse) { border: none; }
:deep(.el-collapse-item__header) {
  background: var(--bg-secondary); color: var(--text-primary);
  border-color: var(--border-color); padding: 0 12px;
  border-radius: var(--radius-sm); margin-bottom: 2px;
}
:deep(.el-collapse-item__content) { padding: 16px 0; }
:deep(.el-collapse-item__wrap) { background: transparent; border: none; }
:deep(.el-tabs__item) { color: var(--text-secondary); }
:deep(.el-tabs__item.is-active) { color: var(--accent-blue); }
:deep(.el-tabs__content) { padding: 16px 0; }
:deep(.el-tabs) { background: transparent; --el-tabs-header-height: 40px; }
</style>
