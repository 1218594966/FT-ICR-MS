import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue'),
    meta: { title: '仪表盘' },
  },
  {
    path: '/analysis',
    name: 'NewAnalysis',
    component: () => import('../views/NewAnalysis.vue'),
    meta: { title: '新建分析' },
  },
  {
    path: '/data-analysis',
    name: 'DataAnalysis',
    component: () => import('../views/DataAnalysis.vue'),
    meta: { title: '数据分析' },
  },
  {
    path: '/batch-processing',
    name: 'BatchProcessing',
    component: () => import('../views/BatchProcessing.vue'),
    meta: { title: '批量处理' },
  },
  {
    path: '/ml-analysis',
    name: 'MLAnalysis',
    component: () => import('../views/MLAnalysis.vue'),
    meta: { title: '机器学习分析' },
  },
  {
    path: '/source-database',
    name: 'SourceDatabase',
    component: () => import('../views/SourceDatabase.vue'),
    meta: { title: '数据库创建' },
  },
  {
    path: '/task/:id',
    name: 'TaskDetail',
    component: () => import('../views/TaskDetail.vue'),
    meta: { title: '任务详情' },
  },
  {
    path: '/history',
    name: 'History',
    component: () => import('../views/History.vue'),
    meta: { title: '历史记录' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  document.title = `${to.meta.title || 'FT-ICR MS'} - FT-ICR MS 分析平台`
})

export default router
