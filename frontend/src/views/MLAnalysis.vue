<template>
  <div class="ml-analysis">
    <h1 class="page-title">{{ text.title }}</h1>
    <p class="page-subtitle">{{ text.subtitle }}</p>

    <section class="section card-glass">
      <h2 class="section-title"><el-icon><Document /></el-icon> {{ text.selectData }}</h2>

      <div class="source-row">
        <el-select
          v-model="selectedTaskId"
          filterable
          clearable
          :placeholder="text.historyPlaceholder"
          class="history-select"
          @change="onHistorySelected"
        >
          <el-option v-for="item in dprFiles" :key="item.id" :label="item.filename" :value="item.id" />
        </el-select>
        <el-button @click="loadDprFiles" :loading="loadingFiles">{{ text.refresh }}</el-button>
      </div>

      <el-divider>{{ text.orUpload }}</el-divider>

      <div class="upload-box" :class="{ disabled: !!selectedTaskId }" @click="triggerInput">
        <input ref="fileInput" type="file" accept=".csv" style="display:none" @change="onFile" />
        <el-icon><Upload /></el-icon>
        <span>{{ selectedFileLabel }}</span>
      </div>

      <div v-if="file || selectedTaskId || loadingClasses" class="class-controls">
        <div v-if="loadingClasses" class="class-loading">{{ text.loadingClasses }}</div>
        <div v-else-if="!classOptions.length" class="class-loading">
          <p>{{ classLoadMessage }}</p>
          <el-button v-if="file || selectedTaskId" size="small" type="primary" @click="inspectClasses">
            {{ text.readClasses }}
          </el-button>
        </div>

        <template v-else>
          <div class="control-block">
            <span class="control-label">{{ text.modelMode }}</span>
            <div class="mode-buttons">
              <el-button
                size="large"
                :type="classificationMode === 'binary' ? 'primary' : 'default'"
                :disabled="classOptions.length < 2"
                @click="selectMode('binary')"
              >
                {{ text.binary }}
              </el-button>
              <el-button
                size="large"
                :type="classificationMode === 'three' ? 'primary' : 'default'"
                :disabled="classOptions.length < 3"
                @click="selectMode('three')"
              >
                {{ text.threeClass }}
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
            <span class="control-label">{{ text.shapTarget }}</span>
            <el-select v-model="shapClass" :placeholder="text.selectClass" :disabled="!selectedClasses.length">
              <el-option v-for="label in selectedClasses" :key="label" :label="label" :value="label" />
            </el-select>
            <p>{{ text.shapHint }}</p>
          </div>

          <div class="control-block shap-target">
            <span class="control-label">{{ text.shapDataset }}</span>
            <el-select v-model="shapDataset">
              <el-option :label="text.trainSet" value="train" />
              <el-option :label="text.testSet" value="test" />
              <el-option :label="text.allData" value="all" />
            </el-select>
            <p>{{ text.datasetHint }}</p>
          </div>
        </template>
      </div>

      <el-button type="primary" :disabled="!canAnalyze" @click="runAnalysis" class="run-button">
        <el-icon v-if="!processing"><CaretRight /></el-icon>
        <el-icon v-else class="is-loading"><Loading /></el-icon>
        {{ analyzeButtonText }}
      </el-button>
    </section>

    <section v-if="result" class="section card-glass">
      <h2 class="section-title"><el-icon><DataAnalysis /></el-icon> {{ text.results }}</h2>

      <div class="stats-row">
        <div class="stat-card">
          <span class="stat-val">{{ result.accuracy_test }}</span>
          <span class="stat-lbl">{{ text.testAccuracy }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-val">{{ result.accuracy_train }}</span>
          <span class="stat-lbl">{{ text.trainAccuracy }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-val">{{ Object.keys(result.label_mapping).length }}</span>
          <span class="stat-lbl">{{ text.classCount }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-val">{{ result.row_count }}</span>
          <span class="stat-lbl">{{ text.rows }}</span>
        </div>
      </div>

      <div v-if="result.source_name" class="info-block">
        <h3>{{ text.source }}</h3>
        <el-tag type="success" class="tag-item">{{ result.source_name }}</el-tag>
      </div>

      <div class="info-block">
        <h3>{{ text.labelMapping }}</h3>
        <el-tag v-for="(val, key) in result.label_mapping" :key="key" class="tag-item">
          {{ key }} -> {{ val }}
        </el-tag>
        <el-tag type="warning" class="tag-item">{{ text.shapPositive }}: {{ result.shap_target_class }}</el-tag>
        <el-tag type="warning" class="tag-item">{{ text.shapRows }}: {{ result.shap_dataset_label }} ({{ result.shap_row_count }})</el-tag>
      </div>

      <div class="info-block">
        <h3>{{ text.modelParams }}</h3>
        <el-tag v-for="(val, key) in result.best_params" :key="key" type="info" class="tag-item">
          {{ key }}: {{ val }}
        </el-tag>
      </div>

      <el-tabs type="border-card" class="result-tabs">
        <el-tab-pane :label="text.testReport">
          <pre class="report-text">{{ result.report_test }}</pre>
        </el-tab-pane>
        <el-tab-pane :label="text.trainReport">
          <pre class="report-text">{{ result.report_train }}</pre>
        </el-tab-pane>
      </el-tabs>

      <div class="plots-section">
        <h3>{{ text.plots }}</h3>
        <div class="plot-grid">
          <div v-if="result.plots.correlation" class="plot-item">
            <h4>{{ text.correlation }}</h4>
            <img :src="'data:image/png;base64,' + result.plots.correlation" alt="Correlation Matrix" />
          </div>
          <div v-if="result.plots.confusion" class="plot-item">
            <h4>{{ text.confusion }}</h4>
            <img :src="'data:image/png;base64,' + result.plots.confusion" alt="Confusion Matrix" />
          </div>
          <div v-if="result.plots.shap" class="plot-item">
            <h4>{{ text.shapPlot }}</h4>
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
import { useI18n } from '../i18n'

const { lang } = useI18n()

const dictionary = {
  en: {
    title: 'Machine Learning SHAP Analysis',
    subtitle: 'Choose a DPR result file from Data Analysis, or upload a CSV, then run XGBoost classification and SHAP interpretation.',
    selectData: 'Select Data File',
    historyPlaceholder: 'Choose a DPR result from history',
    refresh: 'Refresh',
    orUpload: 'Or upload local CSV',
    uploadHint: 'Choose CSV file with MolForm, Col1, Col2, NewCol columns',
    historySelected: 'History DPR file selected. Clear the selection above to upload a local CSV.',
    loadingClasses: 'Reading classes from NewCol...',
    readClasses: 'Read Classes',
    noClasses: 'No usable classes were found in NewCol.',
    readClassesHint: 'File selected, but NewCol classes have not been loaded yet. Click Read Classes.',
    emptyHint: 'Select a history DPR file or upload a CSV. Binary/three-class options will appear here.',
    modelMode: 'Model mode',
    binary: 'Binary',
    threeClass: 'Three-class',
    chooseBinary: 'Choose 2 classes for binary classification',
    chooseThree: 'Choose 3 classes for three-class classification',
    chooseMode: 'Choose binary or three-class mode first',
    shapTarget: 'Positive SHAP target class',
    selectClass: 'Select class',
    shapHint: 'Positive SHAP values push the model toward the selected class; negative values push it away from that class.',
    shapDataset: 'SHAP explanation dataset',
    trainSet: 'Train set',
    testSet: 'Test set',
    allData: 'All data',
    datasetHint: 'The model is trained on the train split. This option only controls which rows are explained by SHAP.',
    start: 'Start Analysis',
    processing: 'Analyzing...',
    reading: 'Reading classes...',
    chooseModeButton: 'Choose binary or three-class mode first',
    results: 'Analysis Results',
    testAccuracy: 'Test accuracy',
    trainAccuracy: 'Train accuracy',
    classCount: 'Classes',
    rows: 'Rows',
    source: 'Data Source',
    labelMapping: 'Label Mapping',
    shapPositive: 'SHAP positive class',
    shapRows: 'SHAP rows',
    modelParams: 'Model Parameters',
    testReport: 'Test Report',
    trainReport: 'Train Report',
    plots: 'Plots',
    correlation: 'Feature Correlation Matrix',
    confusion: 'Confusion Matrix',
    shapPlot: 'SHAP Beeswarm',
    loadFailed: 'Failed to load DPR files',
    inspectFailed: 'Failed to read classes',
    complete: 'Analysis complete',
    failed: 'Analysis failed',
  },
  zh: {
    title: '机器学习 SHAP 分析',
    subtitle: '选择数据分析生成的 DPR 结果文件，或上传 CSV，进行 XGBoost 分类和 SHAP 特征解释。',
    selectData: '选择数据文件',
    historyPlaceholder: '选择历史记录中的 DPR 结果',
    refresh: '刷新',
    orUpload: '或上传本地 CSV',
    uploadHint: '选择包含 MolForm、Col1、Col2、NewCol 列的 CSV 文件',
    historySelected: '已选择历史 DPR 文件；清空上方选择后可上传本地 CSV。',
    loadingClasses: '正在读取 NewCol 中的类别...',
    readClasses: '读取类别',
    noClasses: '没有在 NewCol 中读取到可用于建模的类别。',
    readClassesHint: '已选择文件，但还没有读取到 NewCol 类别。请点击读取类别。',
    emptyHint: '请先选择历史 DPR 文件或上传 CSV，系统会在这里显示二分类/三分类选项。',
    modelMode: '建模方式',
    binary: '二分类',
    threeClass: '三分类',
    chooseBinary: '选择参与二分类的 2 个类别',
    chooseThree: '选择参与三分类的 3 个类别',
    chooseMode: '请先选择二分类或三分类',
    shapTarget: 'SHAP 正向解释类别',
    selectClass: '选择类别',
    shapHint: 'SHAP 值为正表示特征把模型推向当前类别；为负表示远离该类别。',
    shapDataset: 'SHAP 计算数据集',
    trainSet: '训练集',
    testSet: '测试集',
    allData: '全部数据',
    datasetHint: '模型仍使用训练集训练；这里仅选择 SHAP 图解释训练集、测试集还是全部数据。',
    start: '开始分析',
    processing: '分析中...',
    reading: '读取类别中...',
    chooseModeButton: '请先选择二分类或三分类',
    results: '分析结果',
    testAccuracy: '测试集准确率',
    trainAccuracy: '训练集准确率',
    classCount: '分类数',
    rows: '数据行数',
    source: '数据来源',
    labelMapping: '标签编码映射',
    shapPositive: 'SHAP 正向类别',
    shapRows: 'SHAP 数据行数',
    modelParams: '模型参数',
    testReport: '测试集分类报告',
    trainReport: '训练集分类报告',
    plots: '可视化图表',
    correlation: '特征相关性矩阵',
    confusion: '混淆矩阵',
    shapPlot: 'SHAP 蜂群图',
    loadFailed: '加载 DPR 文件失败',
    inspectFailed: '读取类别失败',
    complete: '分析完成',
    failed: '分析失败',
  },
}

const text = computed(() => dictionary[lang.value] || dictionary.en)
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

const requiredClassCount = computed(() => classificationMode.value === 'binary' ? 2 : classificationMode.value === 'three' ? 3 : 0)
const canAnalyze = computed(() => {
  const hasSource = !!file.value || !!selectedTaskId.value
  const required = requiredClassCount.value
  return hasSource && required > 0 && selectedClasses.value.length === required && !!shapClass.value && !processing.value && !loadingClasses.value
})
const classSelectLabel = computed(() => {
  if (classificationMode.value === 'binary') return text.value.chooseBinary
  if (classificationMode.value === 'three') return text.value.chooseThree
  return text.value.chooseMode
})
const analyzeButtonText = computed(() => {
  if (processing.value) return text.value.processing
  if (loadingClasses.value) return text.value.reading
  if ((file.value || selectedTaskId.value) && !classificationMode.value) return text.value.chooseModeButton
  return text.value.start
})
const classLoadMessage = computed(() => {
  if (classLoadError.value) return classLoadError.value
  if (file.value || selectedTaskId.value) return text.value.readClassesHint
  return text.value.emptyHint
})
const selectedFileLabel = computed(() => {
  if (selectedTaskId.value) return text.value.historySelected
  return file.value?.name || text.value.uploadHint
})

function triggerInput() {
  if (!selectedTaskId.value) fileInput.value?.click()
}

function onFile(e) {
  file.value = e.target.files?.[0]
  if (file.value) {
    selectedTaskId.value = ''
    inspectClasses()
  }
}

async function loadDprFiles() {
  loadingFiles.value = true
  try {
    const res = await api.get('/ml/dpr-files')
    dprFiles.value = res.files || []
    if (selectedTaskId.value) applyCachedClasses()
  } catch (e) {
    ElMessage.error(`${text.value.loadFailed}: ${e.message}`)
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
      res = await api.post('/ml/inspect', fd, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 1800000 })
    }
    applyClassOptions(res.classes || [])
    if (!classOptions.value.length && selectedTaskId.value && applyCachedClasses()) return
    if (!classOptions.value.length) classLoadError.value = text.value.noClasses
  } catch (e) {
    classLoadError.value = `${text.value.inspectFailed}: ${e.message}`
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
    const fd = new FormData()
    fd.append('selected_classes', JSON.stringify(selectedClasses.value))
    fd.append('shap_class', shapClass.value)
    fd.append('shap_dataset', shapDataset.value)
    let res
    if (selectedTaskId.value) {
      res = await api.post(`/ml/analyze-task/${selectedTaskId.value}`, fd, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 1800000 })
    } else {
      fd.append('file', file.value)
      res = await api.post('/ml/analyze', fd, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 1800000 })
    }
    result.value = res
    ElMessage.success(text.value.complete)
  } catch (e) {
    ElMessage.error(`${text.value.failed}: ${e.message}`)
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
.ml-analysis { max-width: 1280px; }
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
.class-loading { grid-column: 1 / -1; color: var(--text-secondary); display: flex; align-items: center; gap: 12px; flex-wrap: wrap; p { margin: 0; } }
.mode-buttons { display: grid; grid-template-columns: 1fr; gap: 10px; }
.mode-buttons :deep(.el-button) { width: 100%; min-height: 44px; margin-left: 0; font-weight: 700; border-color: #3b82f6; }
.shap-target p { color: var(--text-secondary); font-size: 12px; line-height: 1.5; margin: 0; }
.run-button { margin-top: 12px; }
.stats-row { display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }
.stat-card { padding: 16px 24px; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: var(--radius-lg); text-align: center; min-width: 120px; }
.stat-val { display: block; font-size: 24px; font-weight: 700; background: var(--accent-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.stat-lbl { color: var(--text-secondary); font-size: 12px; }
.info-block { margin: 18px 0; h3 { font-size: 14px; margin-bottom: 10px; color: var(--text-secondary); } }
.tag-item { margin-right: 8px; margin-bottom: 8px; }
.result-tabs { margin: 20px 0; }
.report-text { background: var(--bg-secondary); padding: 16px; border-radius: var(--radius-md); overflow-x: auto; color: var(--text-primary); font-family: 'Courier New', monospace; font-size: 12px; }
.plots-section h3 { margin-bottom: 16px; }
.plot-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 20px; }
.plot-item { background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: var(--radius-lg); padding: 16px; h4 { margin-bottom: 12px; font-size: 14px; color: var(--text-secondary); } img { width: 100%; height: auto; border-radius: var(--radius-md); background: white; } }
@media (max-width: 1100px) {
  .class-controls { grid-template-columns: 1fr; }
  .plot-grid { grid-template-columns: 1fr; }
}
</style>
