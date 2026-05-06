<template>
  <div class="ml-analysis">
    <h1 class="page-title">机器学习 SHAP 分析</h1>
    <p class="page-subtitle">选择数据分析生成的 DPR 完整结果文件，或上传 CSV，进行 XGBoost 分类和 SHAP 特征重要性分析</p>

    <!-- Data Source Section -->
    <section class="section card-glass">
      <h2 class="section-title"><el-icon><Document /></el-icon> 选择数据文件</h2>

      <div class="source-row">
        <el-select
          v-model="selectedTaskId"
          filterable
          clearable
          placeholder="选择数据分析历史记录中的 DPR 完整结果"
          class="history-select"
          @change="onHistorySelected"
        >
          <el-option
            v-for="item in dprFiles"
            :key="item.id"
            :label="item.filename"
            :value="item.id"
          />
        </el-select>
        <el-button @click="loadDprFiles" :loading="loadingFiles">刷新</el-button>
      </div>

      <el-divider>或上传本地 CSV</el-divider>

      <div class="upload-box" :class="{ disabled: !!selectedTaskId }" @click="triggerInput">
        <input ref="fileInput" type="file" accept=".csv" style="display:none" @change="onFile" />
        <el-icon><Upload /></el-icon>
        <span>{{ selectedFileLabel }}</span>
      </div>

      <div v-if="file || selectedTaskId || loadingClasses" class="class-controls">
        <div v-if="loadingClasses" class="class-loading">正在读取 NewCol 中的类别...</div>
        <div v-else-if="!classOptions.length" class="class-loading">
          <p>{{ classLoadMessage }}</p>
          <el-button v-if="file || selectedTaskId" size="small" type="primary" @click="inspectClasses">读取类别</el-button>
        </div>
        <template v-else>
        <div class="control-block">
          <span class="control-label">建模方式</span>
          <div class="mode-buttons">
            <el-button
              size="large"
              :type="classificationMode === 'binary' ? 'primary' : 'default'"
              :disabled="classOptions.length < 2"
              @click="selectMode('binary')"
            >
              二分类
            </el-button>
            <el-button
              size="large"
              :type="classificationMode === 'three' ? 'primary' : 'default'"
              :disabled="classOptions.length < 3"
              @click="selectMode('three')"
            >
              三分类
            </el-button>
          </div>
        </div>
        <div class="control-block">
          <span class="control-label">{{ classSelectLabel }}</span>
          <el-checkbox-group v-model="selectedClasses" @change="onSelectedClassesChange">
            <el-checkbox
              v-for="item in classOptions"
              :key="item.label"
              :value="item.label"
              :disabled="!classificationMode"
              border
            >
              {{ item.label }} ({{ item.count }})
            </el-checkbox>
          </el-checkbox-group>
        </div>
        <div class="control-block shap-target">
          <span class="control-label">SHAP 正向解释类别</span>
          <el-select v-model="shapClass" placeholder="选择类别" :disabled="!selectedClasses.length">
            <el-option v-for="label in selectedClasses" :key="label" :label="label" :value="label" />
          </el-select>
          <p>SHAP 值为正表示特征把模型推向当前选择的类别；为负表示远离该类别。</p>
        </div>
        <div class="control-block shap-target">
          <span class="control-label">SHAP 计算数据集</span>
          <el-select v-model="shapDataset">
            <el-option label="训练集" value="train" />
            <el-option label="测试集" value="test" />
            <el-option label="全部数据" value="all" />
          </el-select>
          <p>模型仍使用训练集训练；这里选择 SHAP 图解释训练集、测试集还是全部数据。</p>
        </div>
        </template>
      </div>

      <el-button type="primary" :disabled="!canAnalyze" @click="runAnalysis" style="margin-top:12px">
        <el-icon v-if="!processing"><CaretRight /></el-icon>
        <el-icon v-else class="is-loading"><Loading /></el-icon>
        {{ analyzeButtonText }}
      </el-button>
    </section>

    <!-- Results Section -->
    <section v-if="result" class="section card-glass">
      <h2 class="section-title"><el-icon><DataAnalysis /></el-icon> 分析结果</h2>
      
      <!-- Summary Stats -->
      <div class="stats-row">
        <div class="stat-card">
          <span class="stat-val">{{ result.accuracy_test }}</span>
          <span class="stat-lbl">测试集准确率</span>
        </div>
        <div class="stat-card">
          <span class="stat-val">{{ result.accuracy_train }}</span>
          <span class="stat-lbl">训练集准确率</span>
        </div>
        <div class="stat-card">
          <span class="stat-val">{{ Object.keys(result.label_mapping).length }}</span>
          <span class="stat-lbl">分类数</span>
        </div>
        <div class="stat-card">
          <span class="stat-val">{{ result.row_count }}</span>
          <span class="stat-lbl">数据行数</span>
        </div>
      </div>

      <div v-if="result.source_name" class="info-block">
        <h3>数据来源</h3>
        <el-tag type="success" class="tag-item">{{ result.source_name }}</el-tag>
      </div>

      <!-- Label Mapping -->
      <div class="info-block">
        <h3>标签编码映射</h3>
        <el-tag v-for="(val, key) in result.label_mapping" :key="key" class="tag-item">
          {{ key }} → {{ val }}
        </el-tag>
        <el-tag type="warning" class="tag-item">SHAP 正向类别: {{ result.shap_target_class }}</el-tag>
        <el-tag type="warning" class="tag-item">SHAP 数据集: {{ result.shap_dataset_label }} ({{ result.shap_row_count }} 行)</el-tag>
      </div>

      <!-- Best Parameters -->
      <div class="info-block">
        <h3>最佳参数</h3>
        <el-tag v-for="(val, key) in result.best_params" :key="key" type="info" class="tag-item">
          {{ key }}: {{ val }}
        </el-tag>
      </div>

      <!-- Classification Reports -->
      <el-tabs type="border-card" class="result-tabs">
        <el-tab-pane label="测试集分类报告">
          <pre class="report-text">{{ result.report_test }}</pre>
        </el-tab-pane>
        <el-tab-pane label="训练集分类报告">
          <pre class="report-text">{{ result.report_train }}</pre>
        </el-tab-pane>
      </el-tabs>

      <!-- Plots -->
      <div class="plots-section">
        <h3>可视化图表</h3>
        <div class="plot-grid">
          <div v-if="result.plots.correlation" class="plot-item">
            <h4>特征相关性矩阵</h4>
            <img :src="'data:image/png;base64,' + result.plots.correlation" alt="Correlation Matrix" />
          </div>
          <div v-if="result.plots.confusion" class="plot-item">
            <h4>混淆矩阵</h4>
            <img :src="'data:image/png;base64,' + result.plots.confusion" alt="Confusion Matrix" />
          </div>
          <div v-if="result.plots.shap" class="plot-item">
            <h4>SHAP 蜂群图</h4>
            <img :src="'data:image/png;base64,' + result.plots.shap" alt="SHAP Beeswarm" />
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api/index'

const fileInput = ref(null)
const file = ref(null)
const selectedTaskId = ref('')
const dprFiles = ref([])
const loadingFiles = ref(false)
const loadingClasses = ref(false)
const processing = ref(false)
const result = ref(null)
const classOptions = ref([])
const classificationMode = ref('')
const selectedClasses = ref([])
const shapClass = ref('')
const shapDataset = ref('train')
const classLoadError = ref('')

const requiredClassCount = computed(() => {
  if (classificationMode.value === 'binary') return 2
  if (classificationMode.value === 'three') return 3
  return 0
})

const canAnalyze = computed(() => {
  const hasSource = !!file.value || !!selectedTaskId.value
  const required = requiredClassCount.value
  return hasSource && required > 0 && selectedClasses.value.length === required && !!shapClass.value && !processing.value && !loadingClasses.value
})

const classSelectLabel = computed(() => {
  if (classificationMode.value === 'binary') return '选择参与二分类的 2 个类别'
  if (classificationMode.value === 'three') return '选择参与三分类的 3 个类别'
  return '请先选择二分类或三分类'
})

const analyzeButtonText = computed(() => {
  if (processing.value) return '分析中...'
  if (loadingClasses.value) return '读取类别中...'
  if ((file.value || selectedTaskId.value) && !classificationMode.value) return '请先选择二分类或三分类'
  return '开始分析'
})

const classLoadMessage = computed(() => {
  if (classLoadError.value) return classLoadError.value
  if (file.value || selectedTaskId.value) return '已选择文件，但还没有读取到 NewCol 类别。请点击“读取类别”。'
  return '请先选择历史 DPR 文件或上传 CSV，系统会在这里显示二分类/三分类选项。'
})

const selectedFileLabel = computed(() => {
  if (selectedTaskId.value) return '已选择历史 DPR 文件；清空上方选择后可上传本地 CSV'
  return file.value?.name || '选择 CSV 文件 (含 MolForm, Col1, Col2, NewCol 列)'
})

function triggerInput() {
  if (selectedTaskId.value) return
  fileInput.value?.click()
}

function onFile(e) {
  file.value = e.target.files?.[0]
  if (file.value) {
    selectedTaskId.value = ''
    inspectClasses()
  }
}

function formatTime(t) {
  return t ? new Date(t).toLocaleString('zh-CN') : '-'
}

async function loadDprFiles() {
  loadingFiles.value = true
  try {
    const res = await api.get('/ml/dpr-files')
    dprFiles.value = res.files || []
    if (selectedTaskId.value) applyCachedClasses()
  } catch (e) {
    ElMessage.error('加载历史 DPR 文件失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loadingFiles.value = false
  }
}

function resetClassSelection() {
  classOptions.value = []
  classificationMode.value = ''
  selectedClasses.value = []
  shapClass.value = ''
  classLoadError.value = ''
}

function applyClassOptions(classes) {
  classOptions.value = classes || []
  classificationMode.value = ''
  selectedClasses.value = []
  shapClass.value = ''
}

function applyCachedClasses() {
  const selected = dprFiles.value.find((item) => item.id === selectedTaskId.value)
  if (selected?.classes?.length) {
    result.value = null
    file.value = null
    resetClassSelection()
    applyClassOptions(selected.classes)
    return true
  }
  return false
}

function onHistorySelected() {
  if (!selectedTaskId.value) {
    if (!file.value) resetClassSelection()
    return
  }
  if (!applyCachedClasses()) inspectClasses()
}

function selectMode(mode) {
  classificationMode.value = mode
  const required = requiredClassCount.value
  selectedClasses.value = classOptions.value.slice(0, required).map((item) => item.label)
  shapClass.value = selectedClasses.value[selectedClasses.value.length - 1] || ''
}

function onSelectedClassesChange() {
  const required = requiredClassCount.value
  if (required && selectedClasses.value.length > required) selectedClasses.value = selectedClasses.value.slice(0, required)
  if (!selectedClasses.value.includes(shapClass.value)) {
    shapClass.value = selectedClasses.value[selectedClasses.value.length - 1] || ''
  }
}

async function inspectClasses() {
  result.value = null
  if (selectedTaskId.value && applyCachedClasses()) return
  resetClassSelection()
  if (!file.value && !selectedTaskId.value) return
  loadingClasses.value = true
  try {
    let res
    if (selectedTaskId.value) {
      res = await api.get(`/ml/inspect-task/${selectedTaskId.value}`)
    } else {
      const fd = new FormData()
      fd.append('file', file.value)
      res = await api.post('/ml/inspect', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 600000,
      })
    }
    applyClassOptions(res.classes || [])
    if (!classOptions.value.length && selectedTaskId.value && applyCachedClasses()) return
    if (!classOptions.value.length) classLoadError.value = '没有在 NewCol 中读取到可用于建模的类别。'
  } catch (e) {
    classLoadError.value = '读取类别失败: ' + (e.response?.data?.detail || e.message)
    ElMessage.error(classLoadError.value)
  } finally {
    loadingClasses.value = false
  }
}

async function runAnalysis() {
  if (!canAnalyze.value) return
  
  processing.value = true
  result.value = null
  
  try {
    let res
    const fd = new FormData()
    fd.append('selected_classes', JSON.stringify(selectedClasses.value))
    fd.append('shap_class', shapClass.value)
    fd.append('shap_dataset', shapDataset.value)
    if (selectedTaskId.value) {
      res = await api.post(`/ml/analyze-task/${selectedTaskId.value}`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 600000,
      })
    } else {
      fd.append('file', file.value)
      res = await api.post('/ml/analyze', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 600000
      })
    }
    
    result.value = res
    ElMessage.success('分析完成')
  } catch (e) {
    ElMessage.error('分析失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    processing.value = false
  }
}

watch(selectedTaskId, (value) => {
  if (value) {
    file.value = null
    if (!applyCachedClasses()) inspectClasses()
  } else if (!file.value) {
    resetClassSelection()
  }
})

onMounted(loadDprFiles)
</script>

<style lang="scss" scoped>
.ml-analysis { max-width: 1200px; }
.page-title { font-size: 28px; font-weight: 700; margin-bottom: 4px; }
.page-subtitle { color: var(--text-secondary); margin-bottom: 20px; font-size: 14px; }
.section { padding: 24px; margin-bottom: 20px; }
.section-title { font-size: 16px; font-weight: 600; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
.source-row { display: flex; gap: 12px; align-items: center; margin-bottom: 16px; }
.history-select { flex: 1; min-width: 280px; }
.upload-box {
  border: 2px dashed var(--border-color);
  border-radius: var(--radius-lg);
  padding: 40px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  &:hover { border-color: var(--accent-blue); background: rgba(59, 130, 246, 0.05); }
  &.disabled { cursor: not-allowed; opacity: 0.65; }
  .el-icon { font-size: 48px; color: var(--text-muted); margin-bottom: 12px; }
  span { display: block; color: var(--text-secondary); }
}
.class-controls {
  display: grid;
  grid-template-columns: minmax(180px, 240px) minmax(320px, 1fr) minmax(240px, 320px) minmax(240px, 320px);
  gap: 16px;
  margin-top: 16px;
  padding: 16px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
}
.control-block { display: flex; flex-direction: column; gap: 10px; }
.control-label { color: var(--text-primary); font-size: 13px; font-weight: 600; }
.class-loading {
  grid-column: 1 / -1;
  color: var(--text-secondary);
  padding: 8px 0;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  p { margin: 0; }
}
.mode-buttons { display: grid; grid-template-columns: 1fr; gap: 10px; }
.mode-buttons :deep(.el-button) {
  width: 100%;
  min-height: 44px;
  margin-left: 0;
  font-weight: 700;
  border-color: #3b82f6;
}
.mode-buttons :deep(.el-button--primary) {
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.25);
}
.shap-target p { color: var(--text-secondary); font-size: 12px; line-height: 1.5; margin: 0; }
.stats-row { display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }
.stat-card {
  padding: 16px 24px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  text-align: center;
  min-width: 120px;
}
.stat-val {
  display: block;
  font-size: 24px;
  font-weight: 700;
  background: var(--accent-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.stat-lbl { font-size: 12px; color: var(--text-secondary); }
.info-block { margin-bottom: 20px; h3 { font-size: 14px; margin-bottom: 8px; } }
.tag-item { margin-right: 8px; margin-bottom: 8px; }
.result-tabs { margin-bottom: 20px; }
.report-text {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  color: var(--text-primary);
}
.plots-section {
  h3 { font-size: 16px; margin-bottom: 16px; }
}
.plot-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 20px;
}
.plot-item {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 16px;
  h4 { font-size: 14px; margin-bottom: 12px; color: var(--text-secondary); }
  img { width: 100%; height: auto; border-radius: var(--radius-sm); }
}
@media (max-width: 900px) {
  .source-row, .class-controls { grid-template-columns: 1fr; flex-direction: column; align-items: stretch; }
}
</style>
