<template>
  <el-config-provider :locale="zhCn">
    <div class="app-layout">
      <aside class="sidebar">
        <div class="logo">
          <div class="logo-icon">
            <svg viewBox="0 0 32 32" fill="none">
              <circle cx="16" cy="16" r="14" stroke="url(#g)" stroke-width="2" />
              <path d="M8 20 L12 12 L16 18 L20 10 L24 16" stroke="url(#g)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
              <defs><linearGradient id="g" x1="0" y1="0" x2="32" y2="32"><stop stop-color="#3b82f6" /><stop offset="1" stop-color="#06b6d4" /></linearGradient></defs>
            </svg>
          </div>
          <span class="logo-text">FT-ICR MS</span>
        </div>
        <el-menu
          :default-active="activeMenu"
          :router="true"
          class="sidebar-menu"
          background-color="transparent"
          text-color="#94a3b8"
          active-text-color="#3b82f6"
        >
          <el-menu-item index="/">
            <el-icon><Odometer /></el-icon>
            <span>仪表盘</span>
          </el-menu-item>
          <el-menu-item index="/analysis">
            <el-icon><DataAnalysis /></el-icon>
            <span>新建分析</span>
          </el-menu-item>
          <el-menu-item index="/data-analysis">
            <el-icon><TrendCharts /></el-icon>
            <span>数据分析</span>
          </el-menu-item>
          <el-menu-item index="/batch-processing">
            <el-icon><FolderOpened /></el-icon>
            <span>批量处理</span>
          </el-menu-item>
          <el-menu-item index="/ml-analysis">
            <el-icon><Cpu /></el-icon>
            <span>机器学习</span>
          </el-menu-item>
          <el-menu-item index="/source-database">
            <el-icon><Files /></el-icon>
            <span>数据库创建</span>
          </el-menu-item>
          <el-menu-item index="/history">
            <el-icon><Clock /></el-icon>
            <span>历史记录</span>
          </el-menu-item>
        </el-menu>
        <div class="sidebar-footer">
          <span class="version">v1.0.0</span>
        </div>
      </aside>
      <main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </el-config-provider>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

const route = useRoute()
const activeMenu = computed(() => {
  if (route.path.startsWith('/task')) return '/history'
  return route.path
})
</script>

<style lang="scss" scoped>
.app-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  width: 220px;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px 20px 16px;
  border-bottom: 1px solid var(--border-color);
}

.logo-icon {
  width: 32px;
  height: 32px;
  svg { width: 100%; height: 100%; }
}

.logo-text {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 1px;
  background: var(--accent-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.sidebar-menu {
  flex: 1;
  padding: 8px;
  border: none !important;
  .el-menu-item {
    border-radius: var(--radius-md);
    margin-bottom: 4px;
    height: 44px;
    line-height: 44px;
    &:hover { background: rgba(59, 130, 246, 0.08) !important; }
    &.is-active {
      background: rgba(59, 130, 246, 0.12) !important;
      color: var(--accent-blue) !important;
      &::before {
        content: '';
        position: absolute;
        left: 0;
        top: 50%;
        transform: translateY(-50%);
        width: 3px;
        height: 20px;
        background: var(--accent-gradient);
        border-radius: 2px;
      }
    }
    .el-icon { margin-right: 8px; }
  }
}

.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid var(--border-color);
  .version {
    font-size: 12px;
    color: var(--text-muted);
  }
}

.main-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px 28px;
  background:
    radial-gradient(ellipse at 70% 10%, rgba(59, 130, 246, 0.03) 0%, transparent 40%),
    var(--bg-primary);
}
</style>
