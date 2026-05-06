import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Dashboard', component: () => import('../views/Dashboard.vue'), meta: { titleKey: 'dashboard' } },
  { path: '/analysis', name: 'NewAnalysis', component: () => import('../views/NewAnalysis.vue'), meta: { titleKey: 'newAnalysis' } },
  { path: '/data-analysis', name: 'DataAnalysis', component: () => import('../views/DataAnalysis.vue'), meta: { titleKey: 'dataAnalysis' } },
  { path: '/batch-processing', name: 'BatchProcessing', component: () => import('../views/BatchProcessing.vue'), meta: { titleKey: 'batchProcessing' } },
  { path: '/ml-analysis', name: 'MLAnalysis', component: () => import('../views/MLAnalysis.vue'), meta: { titleKey: 'mlAnalysis' } },
  { path: '/source-database', name: 'SourceDatabase', component: () => import('../views/SourceDatabase.vue'), meta: { titleKey: 'sourceDatabase' } },
  { path: '/task/:id', name: 'TaskDetail', component: () => import('../views/TaskDetail.vue'), meta: { titleKey: 'taskDetail' } },
  { path: '/history', name: 'History', component: () => import('../views/History.vue'), meta: { titleKey: 'history' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
