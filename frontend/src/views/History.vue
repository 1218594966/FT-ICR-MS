<template>
  <div class="history">
    <h1 class="page-title">{{ pageText.title }}</h1>
    <p class="page-subtitle">{{ pageText.subtitle }}</p>

    <div class="filter-bar">
      <el-select v-model="typeFilter" :placeholder="text.taskType" clearable style="width: 160px" @change="loadData">
        <el-option :label="text.allTypes" value="" />
        <el-option :label="text.regularAnalysis" value="analysis" />
        <el-option :label="text.dprAnalysis" value="dpr" />
      </el-select>
      <el-select v-model="statusFilter" :placeholder="text.statusFilter" clearable style="width: 140px" @change="loadData">
        <el-option :label="text.allStatuses" value="" />
        <el-option :label="text.success" value="success" />
        <el-option :label="text.running" value="running" />
        <el-option :label="text.failed" value="failed" />
        <el-option :label="text.pending" value="pending" />
      </el-select>
      <el-input v-model="keyword" :placeholder="text.searchFilename" clearable prefix-icon="Search" style="width: 260px" @clear="loadData" @keyup.enter="loadData" />
      <div class="filter-spacer"></div>
      <input ref="importInput" class="hidden-file-input" type="file" accept=".csv" @change="handleImportCsv" />
      <el-button type="primary" :loading="importing" @click="triggerImport">
        <el-icon><Upload /></el-icon> {{ text.importCsv }}
      </el-button>
    </div>

    <el-table :data="tasks" class="dark-table" v-loading="loading" @row-click="goDetail" stripe>
      <el-table-column prop="filename" :label="text.filename" min-width="220" show-overflow-tooltip />
      <el-table-column :label="text.type" width="120">
        <template #default="{ row }">
          <el-tag :type="row.task_type === 'dpr' ? 'warning' : 'info'" size="small" effect="plain">
            {{ row.task_type === 'dpr' ? text.dprCompare : text.regularAnalysis }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="status" :label="text.status" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small" effect="dark">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="progress" :label="text.progress" width="130">
        <template #default="{ row }">
          <el-progress :percentage="row.progress || 0" :stroke-width="6" :color="'#3b82f6'" />
        </template>
      </el-table-column>
      <el-table-column prop="current_step" :label="text.currentStep" width="130">
        <template #default="{ row }">{{ row.current_step || '-' }}</template>
      </el-table-column>
      <el-table-column prop="created_at" :label="text.createdAt" width="180">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column :label="text.actions" width="280" fixed="right">
        <template #default="{ row }">
          <el-button type="success" plain size="small" @click.stop="handleExport(row)" v-if="row.status === 'success'">
            <el-icon><Download /></el-icon> {{ text.exportCsv }}
          </el-button>
          <el-button class="rename-btn" type="primary" size="small" @click.stop="handleRename(row)">
            <el-icon><Edit /></el-icon> {{ text.rename }}
          </el-button>
          <el-button type="danger" plain size="small" @click.stop="handleDelete(row)">
            <el-icon><Delete /></el-icon> {{ text.delete }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Rename Dialog -->
    <el-dialog v-model="renameDialogVisible" :title="text.rename" width="400">
      <el-input v-model="newFilename" :placeholder="text.filenamePlaceholder" @keyup.enter="confirmRename" />
      <template #footer>
        <el-button @click="renameDialogVisible = false">{{ text.cancel }}</el-button>
        <el-button type="primary" @click="confirmRename">{{ text.confirm }}</el-button>
      </template>
    </el-dialog>

    <div class="pagination-wrap">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadData"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getHistory, deleteTask, getExportUrl } from '../api/analysis'
import api from '../api/index'
import { useI18n } from '../i18n'

const router = useRouter()
const { lang } = useI18n()
const pageText = computed(() => lang.value === 'zh'
  ? { title: '历史记录', subtitle: '查看和管理所有分析任务。' }
  : { title: 'History', subtitle: 'View and manage all analysis tasks.' })
const text = computed(() => lang.value === 'zh' ? {
  taskType: '任务类型',
  allTypes: '全部类型',
  regularAnalysis: '常规分析',
  dprAnalysis: 'DPR 对比分析',
  dprCompare: 'DPR 对比',
  statusFilter: '状态筛选',
  allStatuses: '全部状态',
  success: '成功',
  running: '运行中',
  failed: '失败',
  pending: '等待中',
  searchFilename: '搜索文件名...',
  importCsv: '导入常规分析 CSV',
  filename: '文件名',
  type: '类型',
  status: '状态',
  progress: '进度',
  currentStep: '当前步骤',
  createdAt: '创建时间',
  actions: '操作',
  exportCsv: '导出 CSV',
  rename: '重命名',
  delete: '删除',
  filenamePlaceholder: '请输入新文件名',
  cancel: '取消',
  confirm: '确定',
  filenameRequired: '文件名不能为空',
  renameSuccess: '重命名成功',
  renameFailed: '重命名失败',
  importComplete: '导入完成，已生成',
  regularRows: '条常规分析结果',
  importFailed: '导入失败',
  deleteConfirmTitle: '确认',
  deleteConfirm: '确定删除任务',
  deleted: '已删除',
  locale: 'zh-CN',
  unknown: '未知错误',
} : {
  taskType: 'Task Type',
  allTypes: 'All Types',
  regularAnalysis: 'Regular Analysis',
  dprAnalysis: 'DPR Comparison',
  dprCompare: 'DPR Compare',
  statusFilter: 'Status',
  allStatuses: 'All Statuses',
  success: 'Success',
  running: 'Running',
  failed: 'Failed',
  pending: 'Pending',
  searchFilename: 'Search filename...',
  importCsv: 'Import Regular CSV',
  filename: 'Filename',
  type: 'Type',
  status: 'Status',
  progress: 'Progress',
  currentStep: 'Current Step',
  createdAt: 'Created At',
  actions: 'Actions',
  exportCsv: 'Export CSV',
  rename: 'Rename',
  delete: 'Delete',
  filenamePlaceholder: 'Enter a new filename',
  cancel: 'Cancel',
  confirm: 'Confirm',
  filenameRequired: 'Filename cannot be empty',
  renameSuccess: 'Renamed successfully',
  renameFailed: 'Rename failed',
  importComplete: 'Import complete. Generated',
  regularRows: 'regular-analysis rows',
  importFailed: 'Import failed',
  deleteConfirmTitle: 'Confirm',
  deleteConfirm: 'Delete task',
  deleted: 'Deleted',
  locale: 'en-US',
  unknown: 'Unknown error',
})
const tasks = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const keyword = ref('')
const statusFilter = ref('')
const typeFilter = ref('')
const renameDialogVisible = ref(false)
const newFilename = ref('')
const currentTask = ref(null)
const importInput = ref(null)
const importing = ref(false)

function statusType(s) {
  return { success: 'success', running: 'warning', failed: 'danger', pending: 'info' }[s] || 'info'
}
function statusLabel(s) {
  return { success: text.value.success, running: text.value.running, failed: text.value.failed, pending: text.value.pending }[s] || s
}
function formatTime(t) { return t ? new Date(t).toLocaleString(text.value.locale) : '-' }
function goDetail(row) { router.push(`/task/${row.id}`) }

function handleExport(row) {
  window.open(getExportUrl(row.id), '_blank')
}

function handleRename(row) {
  currentTask.value = row
  newFilename.value = row.filename
  renameDialogVisible.value = true
}

async function confirmRename() {
  if (!newFilename.value.trim()) {
    ElMessage.warning(text.value.filenameRequired)
    return
  }
  try {
    await api.put(`/history/${currentTask.value.id}/rename`, { filename: newFilename.value.trim() })
    ElMessage.success(text.value.renameSuccess)
    renameDialogVisible.value = false
    loadData()
  } catch (e) {
    ElMessage.error(`${text.value.renameFailed}: ` + (e.response?.data?.detail || e.message))
  }
}

async function loadData() {
  loading.value = true
  try {
    const res = await getHistory({ 
      page: page.value, 
      page_size: pageSize.value, 
      status: statusFilter.value || undefined, 
      keyword: keyword.value || undefined,
      task_type: typeFilter.value || undefined
    })
    tasks.value = res.tasks || []
    total.value = res.total || 0
  } catch {} finally { loading.value = false }
}

function triggerImport() {
  importInput.value?.click()
}

async function handleImportCsv(event) {
  const file = event.target.files?.[0]
  if (!file) return
  importing.value = true
  const form = new FormData()
  form.append('file', file)
  try {
    const res = await api.post('/history/import-analysis-csv', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 600000,
    })
    typeFilter.value = 'analysis'
    statusFilter.value = 'success'
    page.value = 1
    await loadData()
    ElMessage.success(`${text.value.importComplete} ${res.rows || 0} ${text.value.regularRows}`)
  } catch (e) {
    ElMessage.error(`${text.value.importFailed}: ` + (e.message || text.value.unknown))
  } finally {
    importing.value = false
    event.target.value = ''
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`${text.value.deleteConfirm} "${row.filename}"?`, text.value.deleteConfirmTitle, { type: 'warning' })
    await deleteTask(row.id)
    ElMessage.success(text.value.deleted)
    loadData()
  } catch {}
}

onMounted(loadData)
</script>

<style lang="scss" scoped>
.history { max-width: 1200px; }
.page-title { font-size: 28px; font-weight: 700; margin-bottom: 4px; }
.page-subtitle { color: var(--text-secondary); margin-bottom: 20px; font-size: 14px; }
.filter-bar { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; flex-wrap: wrap; }
.filter-spacer { flex: 1; min-width: 16px; }
.hidden-file-input { display: none; }
.dark-table {
  --el-table-bg-color: #1e293b;
  --el-table-tr-bg-color: #1e293b;
  --el-table-row-hover-bg-color: #2d3a4f;
  --el-table-header-bg-color: #0f172a;
  --el-table-border-color: #334155;
  --el-table-text-color: #e2e8f0;
  --el-table-header-text-color: #94a3b8;
  --el-table-expanded-cell-bg-color: #1e293b;
  border-radius: var(--radius-lg); overflow: hidden; cursor: pointer;
}
.dark-table :deep(.el-table__row--striped td.el-table__cell) {
  background-color: #253347 !important;
}
.dark-table :deep(.el-table__row:hover > td.el-table__cell) {
  background-color: #2d3a4f !important;
}
.pagination-wrap { display: flex; justify-content: center; margin-top: 20px; }
:deep(.el-pagination) { --el-pagination-bg-color: transparent; --el-pagination-text-color: var(--text-secondary); --el-pagination-button-bg-color: var(--bg-card); }
.rename-btn {
  background: #2563eb !important;
  border-color: #60a5fa !important;
  color: #fff !important;
  font-weight: 600;
}
.rename-btn:hover {
  background: #1d4ed8 !important;
  border-color: #93c5fd !important;
  color: #fff !important;
}
</style>
