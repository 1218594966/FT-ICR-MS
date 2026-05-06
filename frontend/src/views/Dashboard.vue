<template>
  <div class="dashboard">
    <h1 class="page-title">仪表盘</h1>
    <p class="page-subtitle">FT-ICR MS 数据分析平台概览</p>

    <div class="stats-grid">
      <div class="stat-card" v-for="s in stats" :key="s.label">
        <div class="stat-icon" :style="{ background: s.bg }">
          <el-icon :size="24"><component :is="s.icon" /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-value">{{ s.value }}</span>
          <span class="stat-label">{{ s.label }}</span>
        </div>
      </div>
    </div>

    <div class="quick-actions">
      <h2 class="section-title">快速操作</h2>
      <div class="action-cards">
        <div class="action-card card-glass" @click="$router.push('/analysis')">
          <el-icon :size="36" color="#3b82f6"><Upload /></el-icon>
          <h3>新建分析</h3>
          <p>上传 .d 数据文件，配置参数，开始分析</p>
        </div>
        <div class="action-card card-glass" @click="$router.push('/history')">
          <el-icon :size="36" color="#06b6d4"><Document /></el-icon>
          <h3>历史记录</h3>
          <p>查看、对比和管理历史分析结果</p>
        </div>
      </div>
    </div>

    <div class="recent-section" v-if="recentTasks.length">
      <h2 class="section-title">最近任务</h2>
      <el-table :data="recentTasks" class="dark-table" @row-click="goDetail">
        <el-table-column prop="filename" label="文件名" min-width="200" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small" effect="dark">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="120">
          <template #default="{ row }">
            <el-progress :percentage="row.progress" :stroke-width="6" :color="'#3b82f6'" />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getHistory } from '../api/analysis'

const router = useRouter()
const recentTasks = ref([])
const stats = ref([
  { label: '总任务数', value: 0, icon: 'Tickets', bg: 'linear-gradient(135deg, #3b82f6, #06b6d4)' },
  { label: '成功任务', value: 0, icon: 'CircleCheck', bg: 'linear-gradient(135deg, #10b981, #06b6d4)' },
  { label: '运行中', value: 0, icon: 'Loading', bg: 'linear-gradient(135deg, #f59e0b, #ef4444)' },
  { label: '失败任务', value: 0, icon: 'CircleClose', bg: 'linear-gradient(135deg, #ef4444, #8b5cf6)' },
])

function statusType(s) {
  return { success: 'success', running: 'warning', failed: 'danger', pending: 'info' }[s] || 'info'
}
function statusLabel(s) {
  return { success: '成功', running: '运行中', failed: '失败', pending: '等待中' }[s] || s
}
function formatTime(t) {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN')
}
function goDetail(row) {
  router.push(`/task/${row.id}`)
}

onMounted(async () => {
  try {
    const data = await getHistory({ page: 1, page_size: 50 })
    recentTasks.value = data.tasks || []
    stats.value[0].value = data.total || 0
    stats.value[1].value = data.tasks.filter(t => t.status === 'success').length
    stats.value[2].value = data.tasks.filter(t => t.status === 'running' || t.status === 'pending').length
    stats.value[3].value = data.tasks.filter(t => t.status === 'failed').length
  } catch {}
})
</script>

<style lang="scss" scoped>
.dashboard { max-width: 1200px; }
.page-title {
  font-size: 28px;
  font-weight: 700;
  margin-bottom: 4px;
}
.page-subtitle {
  color: var(--text-secondary);
  margin-bottom: 28px;
  font-size: 14px;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
  margin-bottom: 32px;
}
.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  transition: all 0.3s;
  &:hover { border-color: var(--accent-blue); box-shadow: var(--shadow-glow); }
}
.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}
.stat-info {
  display: flex;
  flex-direction: column;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
}
.stat-label {
  font-size: 13px;
  color: var(--text-secondary);
}
.section-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 16px;
}
.action-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
  margin-bottom: 32px;
}
.action-card {
  padding: 28px;
  cursor: pointer;
  text-align: center;
  h3 { margin: 12px 0 8px; font-size: 16px; }
  p { color: var(--text-secondary); font-size: 13px; }
}
.dark-table {
  --el-table-bg-color: var(--bg-card);
  --el-table-tr-bg-color: var(--bg-card);
  --el-table-header-bg-color: var(--bg-secondary);
  --el-table-row-hover-bg-color: var(--bg-card-hover);
  --el-table-border-color: var(--border-color);
  --el-table-text-color: var(--text-primary);
  --el-table-header-text-color: var(--text-secondary);
  border-radius: var(--radius-lg);
  overflow: hidden;
  cursor: pointer;
}
</style>
