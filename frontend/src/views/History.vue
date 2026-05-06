<template>
  <div class="history">
    <h1 class="page-title">历史记录</h1>
    <p class="page-subtitle">查看和管理所有分析任务</p>

    <div class="filter-bar">
      <el-select v-model="typeFilter" placeholder="任务类型" clearable style="width: 160px" @change="loadData">
        <el-option label="全部类型" value="" />
        <el-option label="常规分析" value="analysis" />
        <el-option label="DPR 对比分析" value="dpr" />
      </el-select>
      <el-select v-model="statusFilter" placeholder="状态筛选" clearable style="width: 140px" @change="loadData">
        <el-option label="全部状态" value="" />
        <el-option label="成功" value="success" />
        <el-option label="运行中" value="running" />
        <el-option label="失败" value="failed" />
        <el-option label="等待中" value="pending" />
      </el-select>
      <el-input v-model="keyword" placeholder="搜索文件名..." clearable prefix-icon="Search" style="width: 260px" @clear="loadData" @keyup.enter="loadData" />
      <div class="filter-spacer"></div>
      <input ref="importInput" class="hidden-file-input" type="file" accept=".csv" @change="handleImportCsv" />
      <el-button type="primary" :loading="importing" @click="triggerImport">
        <el-icon><Upload /></el-icon> 导入常规分析CSV
      </el-button>
    </div>

    <el-table :data="tasks" class="dark-table" v-loading="loading" @row-click="goDetail" stripe>
      <el-table-column prop="filename" label="文件名" min-width="220" show-overflow-tooltip />
      <el-table-column label="类型" width="120">
        <template #default="{ row }">
          <el-tag :type="row.task_type === 'dpr' ? 'warning' : 'info'" size="small" effect="plain">
            {{ row.task_type === 'dpr' ? 'DPR 对比' : '常规分析' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small" effect="dark">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="progress" label="进度" width="130">
        <template #default="{ row }">
          <el-progress :percentage="row.progress || 0" :stroke-width="6" :color="'#3b82f6'" />
        </template>
      </el-table-column>
      <el-table-column prop="current_step" label="当前步骤" width="130">
        <template #default="{ row }">{{ row.current_step || '-' }}</template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button type="success" plain size="small" @click.stop="handleExport(row)" v-if="row.status === 'success'">
            <el-icon><Download /></el-icon> 导出CSV
          </el-button>
          <el-button class="rename-btn" type="primary" size="small" @click.stop="handleRename(row)">
            <el-icon><Edit /></el-icon> 重命名
          </el-button>
          <el-button type="danger" plain size="small" @click.stop="handleDelete(row)">
            <el-icon><Delete /></el-icon> 删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Rename Dialog -->
    <el-dialog v-model="renameDialogVisible" title="重命名" width="400">
      <el-input v-model="newFilename" placeholder="请输入新文件名" @keyup.enter="confirmRename" />
      <template #footer>
        <el-button @click="renameDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmRename">确定</el-button>
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
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getHistory, deleteTask, getExportUrl } from '../api/analysis'
import api from '../api/index'

const router = useRouter()
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
  return { success: '成功', running: '运行中', failed: '失败', pending: '等待中' }[s] || s
}
function formatTime(t) { return t ? new Date(t).toLocaleString('zh-CN') : '-' }
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
    ElMessage.warning('文件名不能为空')
    return
  }
  try {
    await api.put(`/history/${currentTask.value.id}/rename`, { filename: newFilename.value.trim() })
    ElMessage.success('重命名成功')
    renameDialogVisible.value = false
    loadData()
  } catch (e) {
    ElMessage.error('重命名失败: ' + (e.response?.data?.detail || e.message))
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
    ElMessage.success(`导入完成，已生成 ${res.rows || 0} 条常规分析结果`)
  } catch (e) {
    ElMessage.error('导入失败: ' + (e.message || '未知错误'))
  } finally {
    importing.value = false
    event.target.value = ''
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除任务 "${row.filename}"？`, '确认', { type: 'warning' })
    await deleteTask(row.id)
    ElMessage.success('已删除')
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
