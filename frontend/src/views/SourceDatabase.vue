<template>
  <div class="source-database">
    <h1 class="page-title">{{ pageText.title }}</h1>
    <p class="page-subtitle">{{ pageText.subtitle }}</p>

    <section class="section card-glass">
      <h2 class="section-title"><el-icon><Files /></el-icon> {{ text.createOrAppend }}</h2>
      <div class="form-grid">
        <div class="field">
          <span>{{ text.writeMode }}</span>
          <el-radio-group v-model="writeMode">
            <el-radio-button value="new">{{ text.writeNew }}</el-radio-button>
            <el-radio-button value="append">{{ text.writeAppend }}</el-radio-button>
          </el-radio-group>
        </div>
        <div v-if="writeMode === 'new'" class="field">
          <span>{{ text.dbName }}</span>
          <el-input v-model="databaseName" :placeholder="text.dbNamePlaceholder" />
        </div>
        <div v-else class="field">
          <span>{{ text.existingDb }}</span>
          <el-select v-model="selectedDatabaseId" filterable :placeholder="text.chooseAppendDb">
            <el-option v-for="db in databases" :key="db.id" :label="db.name" :value="db.id" />
          </el-select>
        </div>
        <div class="field full">
          <span>{{ text.description }}</span>
          <el-input v-model="description" :placeholder="text.descriptionPlaceholder" />
        </div>
      </div>

      <div class="upload-box" @click="triggerBuildInput">
        <input ref="buildInput" type="file" accept=".csv" multiple style="display:none" @change="onBuildFiles" />
        <el-icon><Upload /></el-icon>
        <strong>{{ text.chooseAnyCsv }}</strong>
        <span>{{ buildFileLabel }}</span>
      </div>
      <div v-if="buildFiles.length" class="file-list">
        <el-tag v-for="file in buildFiles" :key="file.name" effect="plain">{{ file.name }}</el-tag>
      </div>
      <div class="actions">
        <el-button type="primary" :disabled="!canBuild || building" @click="buildDatabase">
          <el-icon v-if="!building"><CaretRight /></el-icon>
          <el-icon v-else class="is-loading"><Loading /></el-icon>
          {{ building ? text.writing : text.createUpdateDb }}
        </el-button>
        <el-button @click="loadDatabases">{{ text.refreshDbs }}</el-button>
      </div>
    </section>

    <section class="section card-glass">
      <h2 class="section-title"><el-icon><DataBoard /></el-icon> {{ text.existingDatabases }}</h2>
      <el-table :data="databases" v-loading="loadingDatabases" class="db-table">
        <el-table-column prop="name" :label="text.dbLabel" min-width="180" />
        <el-table-column prop="formula_count" :label="text.formulaCount" width="110" />
        <el-table-column prop="file_count" :label="text.sourceFileCount" width="120" />
        <el-table-column prop="updated_at" :label="text.updatedAt" width="190">
          <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column :label="text.sourceFiles" min-width="260">
          <template #default="{ row }">
            <div class="source-files">
              <el-tag v-for="file in row.files.slice(0, 4)" :key="file.filename" size="small" effect="plain">
                {{ file.filename }} ({{ file.formula_count }})
              </el-tag>
              <span v-if="row.files.length > 4" class="muted">+{{ row.files.length - 4 }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="text.actions" width="210">
          <template #default="{ row }">
            <div class="operation-buttons">
              <el-button size="small" @click="downloadDatabase(row)">{{ text.downloadCsv }}</el-button>
              <el-button size="small" type="danger" plain @click="deleteDatabase(row)">{{ text.delete }}</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="section card-glass">
      <h2 class="section-title"><el-icon><Connection /></el-icon> {{ text.sampleDbCompare }}</h2>
      <div class="compare-row">
        <el-select v-model="compareDatabaseId" filterable :placeholder="text.chooseCompareDb">
          <el-option v-for="db in databases" :key="db.id" :label="`${db.name} (${db.formula_count})`" :value="db.id" />
        </el-select>
        <div class="sample-picker" :class="{ selected: compareFile }" @click="triggerCompareInput">
          <input ref="compareInput" type="file" accept=".csv" style="display:none" @change="onCompareFile" />
          <el-icon><UploadFilled /></el-icon>
          <div>
            <strong>{{ compareFile?.name || text.chooseCompareCsv }}</strong>
            <span>{{ text.compareCsvHelp }}</span>
          </div>
        </div>
        <el-button type="primary" :disabled="!compareDatabaseId || !compareFile || comparing" @click="compareDatabase">
          {{ comparing ? text.comparing : text.startCompare }}
        </el-button>
      </div>
    </section>

    <section class="section card-glass">
      <h2 class="section-title"><el-icon><TrendCharts /></el-icon> {{ text.twoFileDprCompare }}</h2>
      <div class="dpr-row">
        <el-select v-model="dprDatabaseId" filterable :placeholder="text.chooseSourceDb">
          <el-option v-for="db in databases" :key="db.id" :label="`${db.name} (${db.formula_count})`" :value="db.id" />
        </el-select>
        <div class="sample-picker" :class="{ selected: dprUpstreamFile }" @click="triggerDprInput('upstream')">
          <input ref="dprUpstreamInput" type="file" accept=".csv" style="display:none" @change="onDprFile('upstream', $event)" />
          <el-icon><UploadFilled /></el-icon>
          <div>
            <strong>{{ dprUpstreamFile?.name || text.chooseUpstream }}</strong>
            <span>{{ text.upstreamHelp }}</span>
          </div>
        </div>
        <div class="sample-picker" :class="{ selected: dprDownstreamFile }" @click="triggerDprInput('downstream')">
          <input ref="dprDownstreamInput" type="file" accept=".csv" style="display:none" @change="onDprFile('downstream', $event)" />
          <el-icon><UploadFilled /></el-icon>
          <div>
            <strong>{{ dprDownstreamFile?.name || text.chooseDownstream }}</strong>
            <span>{{ text.downstreamHelp }}</span>
          </div>
        </div>
      </div>
      <div class="actions">
        <el-checkbox v-model="dprRemoveCore">{{ text.removeCore }}</el-checkbox>
        <el-button type="primary" :disabled="!canRunDpr || dprRunning" @click="runDprDatabase">
          {{ dprRunning ? text.analyzing : text.startDprCompare }}
        </el-button>
      </div>
    </section>

    <section v-if="buildResult" class="section card-glass">
      <h2 class="section-title"><el-icon><CircleCheck /></el-icon> {{ text.lastWriteResult }}</h2>
      <div class="stats-row">
        <div class="stat-card">
          <span class="stat-val">{{ buildResult.database.formula_count }}</span>
          <span class="stat-lbl">{{ buildResult.database.name }} {{ text.formulaCount }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-val">{{ buildResult.database.file_count }}</span>
          <span class="stat-lbl">{{ text.totalSourceFiles }}</span>
        </div>
      </div>
      <el-table :data="buildResult.uploaded" size="small">
        <el-table-column prop="filename" :label="text.file" />
        <el-table-column prop="formula_count" :label="text.formulasInFile" width="140" />
        <el-table-column prop="new_unique_count" :label="text.newUnique" width="140" />
        <el-table-column prop="total_intensity" :label="text.totalIntensity" width="140" />
      </el-table>
    </section>

    <section v-if="compareResult" class="section card-glass">
      <h2 class="section-title"><el-icon><TrendCharts /></el-icon> {{ text.compareResult }}</h2>
      <div class="stats-row">
        <div class="stat-card">
          <span class="stat-val">{{ compareResult.summary.overlap_count }}</span>
          <span class="stat-lbl">Overlap {{ text.hitFormulas }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-val">{{ compareResult.summary.query_overlap_rate.toFixed(2) }}%</span>
          <span class="stat-lbl">{{ text.sampleHitRate }}</span>
        </div>
      </div>

      <div class="download-row">
        <el-button @click="downloadBase64(compareResult.downloads.overlap_csv_base64, 'overlap.csv')">{{ text.download }} Overlap</el-button>
        <el-button @click="downloadBase64(compareResult.downloads.sample_only_csv_base64, 'sample_only.csv')">{{ text.download }} Sample only</el-button>
        <el-button @click="downloadBase64(compareResult.downloads.database_only_csv_base64, 'database_only.csv')">{{ text.download }} Database only</el-button>
      </div>

      <div class="result-grid compare-result-grid">
        <div class="info-panel">
          <h3>{{ text.sourceSimilarity }}</h3>
          <el-table :data="compareResult.source_file_similarity" size="small">
            <el-table-column prop="filename" :label="text.sourceFile" min-width="180" show-overflow-tooltip />
            <el-table-column prop="overlap" :label="text.hit" width="80" />
            <el-table-column prop="sample_coverage" :label="text.sampleCoverage" width="120">
              <template #default="{ row }">{{ row.sample_coverage.toFixed(2) }}%</template>
            </el-table-column>
          </el-table>
        </div>
        <div class="info-panel">
          <h3>{{ text.elementDistribution }}</h3>
          <el-table :data="compareResult.element_class_distribution" size="small" max-height="280">
            <el-table-column prop="class" :label="text.class" width="90" />
            <el-table-column prop="overlap" label="Overlap" />
            <el-table-column prop="sample_only" label="Sample only" />
            <el-table-column prop="database_only" label="Database only" />
          </el-table>
        </div>
      </div>

      <div class="plot-and-advice">
        <div class="plot-item">
          <h3>{{ text.sampleDbSetRelation }}</h3>
          <img :src="plotSrc(compareResult.plots.comparison)" alt="comparison plot" />
        </div>
        <div class="suggestions">
          <h3>{{ text.analysisAdvice }}</h3>
          <p v-for="item in analysisSuggestions" :key="item">{{ item }}</p>
          <p>{{ text.extraAdvice }}</p>
        </div>
      </div>
    </section>

    <section v-if="dprResult" class="section card-glass">
      <h2 class="section-title"><el-icon><DataAnalysis /></el-icon> {{ text.dprDbResult }}</h2>
      <div class="stats-row">
        <div class="stat-card">
          <span class="stat-val">{{ dprResult.fate_counts.D }}</span>
          <span class="stat-lbl">D {{ text.disappearedGroup }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-val">{{ dprResult.fate_counts.P }}</span>
          <span class="stat-lbl">P {{ text.producedGroup }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-val">{{ dprResult.fate_counts.R }}</span>
          <span class="stat-lbl">R {{ text.resistantGroup }}</span>
        </div>
        <div class="stat-card">
          <span class="stat-val">{{ dprResult.core_removed }}</span>
          <span class="stat-lbl">{{ text.coreRemoved }}</span>
        </div>
      </div>

      <div class="download-row">
        <el-button @click="downloadBase64(dprResult.downloads.D_csv_base64, 'D_disappearance.csv')">{{ text.download }} D</el-button>
        <el-button @click="downloadBase64(dprResult.downloads.P_csv_base64, 'P_product.csv')">{{ text.download }} P</el-button>
        <el-button @click="downloadBase64(dprResult.downloads.R_csv_base64, 'R_resistant.csv')">{{ text.download }} R</el-button>
      </div>

      <div class="result-grid">
        <div class="info-panel">
          <h3>{{ text.dprPresence }}</h3>
          <el-table :data="dprPresenceRows" size="small">
            <el-table-column prop="group" :label="text.group" width="90" />
            <el-table-column prop="inSource" :label="text.inDatabase" />
            <el-table-column prop="notInSource" :label="text.notInDatabase" />
            <el-table-column prop="rate" :label="text.presenceRate" />
          </el-table>
        </div>
        <div class="info-panel">
          <h3>{{ text.chiSquare }}</h3>
          <el-table :data="dprTestRows" size="small">
            <el-table-column prop="name" :label="text.comparison" />
            <el-table-column prop="p" label="P-value" />
            <el-table-column prop="result" :label="text.conclusion" />
          </el-table>
        </div>
      </div>

      <div class="plot-grid">
        <div class="plot-item">
          <h3>{{ text.overallHeatmap }}</h3>
          <img :src="plotSrc(dprResult.plots.overall_3x2)" alt="DPR 3x2 heatmap" />
          <div class="plot-downloads">
            <el-button size="small" @click="downloadImageBase64(dprResult.plots.overall_3x2, 'DPR_3x2_heatmap.png')">{{ text.download }} PNG</el-button>
            <el-button v-if="dprResult.plot_pdfs?.overall_3x2" size="small" @click="downloadPdfBase64(dprResult.plot_pdfs.overall_3x2, 'DPR_3x2_heatmap.pdf')">{{ text.download }} PDF</el-button>
          </div>
        </div>
        <div class="plot-item">
          <h3>D vs R</h3>
          <img :src="plotSrc(dprResult.plots.d_vs_r)" alt="D vs R heatmap" />
          <div class="plot-downloads">
            <el-button size="small" @click="downloadImageBase64(dprResult.plots.d_vs_r, 'D_vs_R_heatmap.png')">{{ text.download }} PNG</el-button>
            <el-button v-if="dprResult.plot_pdfs?.d_vs_r" size="small" @click="downloadPdfBase64(dprResult.plot_pdfs.d_vs_r, 'D_vs_R_heatmap.pdf')">{{ text.download }} PDF</el-button>
          </div>
        </div>
        <div class="plot-item">
          <h3>P vs D</h3>
          <img :src="plotSrc(dprResult.plots.p_vs_d)" alt="P vs D heatmap" />
          <div class="plot-downloads">
            <el-button size="small" @click="downloadImageBase64(dprResult.plots.p_vs_d, 'P_vs_D_heatmap.png')">{{ text.download }} PNG</el-button>
            <el-button v-if="dprResult.plot_pdfs?.p_vs_d" size="small" @click="downloadPdfBase64(dprResult.plot_pdfs.p_vs_d, 'P_vs_D_heatmap.pdf')">{{ text.download }} PDF</el-button>
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
import { useI18n } from '../i18n'

const { lang } = useI18n()
const pageText = computed(() => lang.value === 'zh'
  ? { title: '分子数据库', subtitle: '把任意数量的 CSV 文件归入一个标签，合并所有分子式和 Peak Height 强度，形成可复用的分子数据库。' }
  : { title: 'Molecular Database', subtitle: 'Merge any number of CSV files into a reusable molecular database with formulas and Peak Height intensities.' })
const text = computed(() => lang.value === 'zh' ? {
  createOrAppend: '创建或追加分子数据库',
  writeMode: '写入方式',
  writeNew: '新建/按标签写入',
  writeAppend: '追加到已有数据库',
  dbName: '标签/数据库名称',
  dbNamePlaceholder: '例如：再生水、污水、上游背景',
  existingDb: '已有数据库',
  chooseAppendDb: '选择要追加的数据库',
  description: '备注',
  descriptionPlaceholder: '可填写来源说明、采样批次或点位信息',
  chooseAnyCsv: '选择任意数量 CSV 文件',
  emptyBuildFiles: '可一次选择 1 个或多个 CSV，列名支持 Molecular Formula / MolForm / Peak Height',
  selectedFiles: '已选择',
  files: '个文件',
  writing: '写入中...',
  createUpdateDb: '创建/更新数据库',
  refreshDbs: '刷新数据库列表',
  existingDatabases: '已有分子数据库',
  dbLabel: '标签/数据库',
  formulaCount: '分子数',
  sourceFileCount: '来源文件数',
  updatedAt: '更新时间',
  sourceFiles: '来源文件',
  actions: '操作',
  downloadCsv: '下载 CSV',
  delete: '删除',
  sampleDbCompare: '样品与数据库对比',
  chooseCompareDb: '选择用于对比的数据库',
  chooseCompareCsv: '点击选择待对比样品 CSV',
  compareCsvHelp: '需要包含 Molecular Formula 或 MolForm；Peak Height 会保留到导出结果中',
  comparing: '对比中...',
  startCompare: '开始对比',
  twoFileDprCompare: '两文件 DPR 与数据库对比',
  chooseSourceDb: '选择来源数据库',
  chooseUpstream: '点击选择上游/前点位 CSV',
  upstreamHelp: '用于和下游文件共同定义 D/P/R',
  chooseDownstream: '点击选择下游/后点位 CSV',
  downstreamHelp: 'D=上游有下游无，P=下游有上游无，R=两者都有',
  removeCore: '移除核心分子',
  analyzing: '分析中...',
  startDprCompare: '开始 DPR 数据库对比',
  lastWriteResult: '最近一次写入结果',
  totalSourceFiles: '累计来源文件',
  file: '文件',
  formulasInFile: '文件内分子数',
  newUnique: '新增唯一分子',
  totalIntensity: '总强度',
  compareResult: '对比结果',
  hitFormulas: '命中分子',
  sampleHitRate: '样品命中率',
  download: '下载',
  sourceSimilarity: '各来源文件相似度',
  sourceFile: '来源文件',
  hit: '命中',
  sampleCoverage: '样品覆盖率',
  elementDistribution: '元素类别分布',
  class: '类别',
  sampleDbSetRelation: '样品与数据库分子集合关系',
  analysisAdvice: '分析建议',
  extraAdvice: '还可以把多个标签数据库同时与同一样品比较，做“来源贡献排序”；如果后续每个样品都有环境变量，可以把命中率和元素类别比例作为特征进入机器学习。',
  advice: [
    '优先查看样品命中率和命中分子的元素类别分布，先判断样品是否明显接近某个来源数据库。',
    '多个来源数据库之间建议批量计算样品命中率，并输出来源排序表，用于判断样品更接近哪类来源。',
    '建议把 overlap、sample only、database only 分别导出，再进入 VK、DBE、NOSC 和机器学习模块比较类别差异。',
  ],
  dprDbResult: 'DPR 数据库对比结果',
  disappearedGroup: '消失组',
  producedGroup: '产生组',
  resistantGroup: '背景组',
  coreRemoved: '移除核心分子',
  dprPresence: 'D/P/R 在数据库中的存在率',
  group: '组别',
  inDatabase: '存在于数据库',
  notInDatabase: '不在数据库',
  presenceRate: '存在率',
  chiSquare: '卡方检验',
  comparison: '比较',
  conclusion: '结论',
  overallHeatmap: '3x2 总体热图',
  overallLabel: 'D/P/R 总体',
  unavailable: '无法检验',
  significant: '显著',
  notSignificant: '不显著',
  loadDbFailed: '加载数据库失败',
  dbUpdated: '数据库已更新',
  writeFailed: '写入失败',
  compareComplete: '对比完成',
  compareFailed: '对比失败',
  dprComplete: 'DPR 数据库对比完成',
  dprFailed: 'DPR 对比失败',
  deleteDbConfirm: '确定删除数据库',
  deleteDbSuffix: '该操作不可恢复。',
  deleteConfirmTitle: '确认删除',
  cancel: '取消',
  dbDeleted: '数据库已删除',
  deleteFailed: '删除失败',
  locale: 'zh-CN',
} : {
  createOrAppend: 'Create or Append Molecular Database',
  writeMode: 'Write mode',
  writeNew: 'Create / write by label',
  writeAppend: 'Append to existing database',
  dbName: 'Label / database name',
  dbNamePlaceholder: 'Example: reclaimed water, wastewater, upstream background',
  existingDb: 'Existing database',
  chooseAppendDb: 'Choose a database to append to',
  description: 'Description',
  descriptionPlaceholder: 'Source notes, sampling batch, or site information',
  chooseAnyCsv: 'Choose any number of CSV files',
  emptyBuildFiles: 'Choose one or more CSV files. Column names can be Molecular Formula / MolForm / Peak Height.',
  selectedFiles: 'Selected',
  files: 'files',
  writing: 'Writing...',
  createUpdateDb: 'Create / Update Database',
  refreshDbs: 'Refresh Databases',
  existingDatabases: 'Existing Molecular Databases',
  dbLabel: 'Label / Database',
  formulaCount: 'Formula Count',
  sourceFileCount: 'Source Files',
  updatedAt: 'Updated At',
  sourceFiles: 'Source Files',
  actions: 'Actions',
  downloadCsv: 'Download CSV',
  delete: 'Delete',
  sampleDbCompare: 'Sample vs Database Comparison',
  chooseCompareDb: 'Choose a database for comparison',
  chooseCompareCsv: 'Click to choose sample CSV',
  compareCsvHelp: 'Requires Molecular Formula or MolForm. Peak Height is retained in exported results.',
  comparing: 'Comparing...',
  startCompare: 'Start Comparison',
  twoFileDprCompare: 'Two-File DPR vs Database Comparison',
  chooseSourceDb: 'Choose source database',
  chooseUpstream: 'Click to choose upstream / earlier-site CSV',
  upstreamHelp: 'Used with the downstream file to define D/P/R',
  chooseDownstream: 'Click to choose downstream / later-site CSV',
  downstreamHelp: 'D=upstream only, P=downstream only, R=present in both',
  removeCore: 'Remove core molecules',
  analyzing: 'Analyzing...',
  startDprCompare: 'Start DPR Database Comparison',
  lastWriteResult: 'Latest Write Result',
  totalSourceFiles: 'Total Source Files',
  file: 'File',
  formulasInFile: 'Formulas in File',
  newUnique: 'New Unique Formulas',
  totalIntensity: 'Total Intensity',
  compareResult: 'Comparison Results',
  hitFormulas: 'hit formulas',
  sampleHitRate: 'Sample Hit Rate',
  download: 'Download',
  sourceSimilarity: 'Source File Similarity',
  sourceFile: 'Source File',
  hit: 'Hits',
  sampleCoverage: 'Sample Coverage',
  elementDistribution: 'Element Class Distribution',
  class: 'Class',
  sampleDbSetRelation: 'Sample and Database Formula Sets',
  analysisAdvice: 'Analysis Advice',
  extraAdvice: 'You can also compare multiple labeled databases against the same sample to rank source contribution. If environmental variables are available later, use hit rates and element class proportions as machine-learning features.',
  advice: [
    'Check the sample hit rate and the element distribution of hit formulas first to judge whether the sample is close to a source database.',
    'For multiple source databases, batch-compute sample hit rates and export a source-ranking table.',
    'Export overlap, sample only, and database only sets, then compare them in VK, DBE, NOSC, and machine-learning modules.',
  ],
  dprDbResult: 'DPR Database Comparison Results',
  disappearedGroup: 'Disappeared group',
  producedGroup: 'Produced group',
  resistantGroup: 'Resistant group',
  coreRemoved: 'Core molecules removed',
  dprPresence: 'D/P/R Presence Rate in Database',
  group: 'Group',
  inDatabase: 'In Database',
  notInDatabase: 'Not in Database',
  presenceRate: 'Presence Rate',
  chiSquare: 'Chi-Square Tests',
  comparison: 'Comparison',
  conclusion: 'Conclusion',
  overallHeatmap: 'Overall 3x2 Heatmap',
  overallLabel: 'Overall D/P/R',
  unavailable: 'Unavailable',
  significant: 'Significant',
  notSignificant: 'Not significant',
  loadDbFailed: 'Failed to load databases',
  dbUpdated: 'Database updated',
  writeFailed: 'Write failed',
  compareComplete: 'Comparison complete',
  compareFailed: 'Comparison failed',
  dprComplete: 'DPR database comparison complete',
  dprFailed: 'DPR comparison failed',
  deleteDbConfirm: 'Delete database',
  deleteDbSuffix: 'This cannot be undone.',
  deleteConfirmTitle: 'Confirm Delete',
  cancel: 'Cancel',
  dbDeleted: 'Database deleted',
  deleteFailed: 'Delete failed',
  locale: 'en-US',
})
const buildInput = ref(null)
const compareInput = ref(null)
const dprUpstreamInput = ref(null)
const dprDownstreamInput = ref(null)
const databases = ref([])
const loadingDatabases = ref(false)
const writeMode = ref('new')
const selectedDatabaseId = ref('')
const compareDatabaseId = ref('')
const databaseName = ref(lang.value === 'zh' ? '再生水' : 'Reclaimed Water')
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
const analysisSuggestions = computed(() => text.value.advice)

const buildFileLabel = computed(() => {
  if (!buildFiles.value.length) return text.value.emptyBuildFiles
  return `${text.value.selectedFiles} ${buildFiles.value.length} ${text.value.files}`
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
  const labels = { overall_3x2: text.value.overallLabel, p_vs_d: 'P vs D', d_vs_r: 'D vs R' }
  return Object.entries(dprResult.value.tests).map(([key, test]) => {
    const p = test.p_value
    return {
      name: labels[key] || key,
      p: p == null ? 'N/A' : p.toFixed(5),
      result: p == null ? text.value.unavailable : (p < 0.05 ? text.value.significant : text.value.notSignificant),
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
function formatTime(t) { return t ? new Date(t).toLocaleString(text.value.locale) : '-' }
function plotSrc(base64) { return `data:image/png;base64,${base64}` }

async function loadDatabases() {
  loadingDatabases.value = true
  try {
    const res = await api.get('/source-db/databases')
    databases.value = res.databases || []
    if (!compareDatabaseId.value && databases.value.length) compareDatabaseId.value = databases.value[0].id
    if (!dprDatabaseId.value && databases.value.length) dprDatabaseId.value = databases.value[0].id
  } catch (e) {
    ElMessage.error(`${text.value.loadDbFailed}: ` + (e.response?.data?.detail || e.message))
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
    ElMessage.success(text.value.dbUpdated)
    buildFiles.value = []
    await loadDatabases()
  } catch (e) {
    ElMessage.error(`${text.value.writeFailed}: ` + (e.response?.data?.detail || e.message))
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
    ElMessage.success(text.value.compareComplete)
  } catch (e) {
    ElMessage.error(`${text.value.compareFailed}: ` + (e.response?.data?.detail || e.message))
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
    ElMessage.success(text.value.dprComplete)
  } catch (e) {
    ElMessage.error(`${text.value.dprFailed}: ` + (e.response?.data?.detail || e.message))
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
      `${text.value.deleteDbConfirm} "${row.name}"? ${text.value.deleteDbSuffix}`,
      text.value.deleteConfirmTitle,
      {
        type: 'warning',
        confirmButtonText: text.value.delete,
        cancelButtonText: text.value.cancel,
        confirmButtonClass: 'el-button--danger',
      },
    )
    await api.delete(`/source-db/databases/${row.id}`)
    if (selectedDatabaseId.value === row.id) selectedDatabaseId.value = ''
    if (compareDatabaseId.value === row.id) compareDatabaseId.value = ''
    if (dprDatabaseId.value === row.id) dprDatabaseId.value = ''
    ElMessage.success(text.value.dbDeleted)
    await loadDatabases()
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error(`${text.value.deleteFailed}: ` + (e.response?.data?.detail || e.message))
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
