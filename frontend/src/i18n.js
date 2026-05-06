import { computed, ref } from 'vue'

const saved = localStorage.getItem('fticrms_lang')
const lang = ref(saved === 'zh' ? 'zh' : 'en')

const messages = {
  en: {
    appTitle: 'FT-ICR MS Web Platform',
    dashboard: 'Dashboard',
    newAnalysis: 'New Analysis',
    dataAnalysis: 'Data Analysis',
    batchProcessing: 'Batch Processing',
    mlAnalysis: 'Machine Learning',
    sourceDatabase: 'Molecular Database',
    pmdAnalysis: 'PMD Analysis',
    history: 'History',
    taskDetail: 'Task Detail',
    language: 'Language',
    english: 'English',
    chinese: '中文',
  },
  zh: {
    appTitle: 'FT-ICR MS 分析平台',
    dashboard: '仪表盘',
    newAnalysis: '新建分析',
    dataAnalysis: '数据分析',
    batchProcessing: '批量处理',
    mlAnalysis: '机器学习',
    sourceDatabase: '分子数据库',
    pmdAnalysis: 'PMD 分析',
    history: '历史记录',
    taskDetail: '任务详情',
    language: '语言',
    english: 'English',
    chinese: '中文',
  },
}

export function useI18n() {
  const t = (key) => messages[lang.value]?.[key] || messages.en[key] || key
  const setLang = (value) => {
    lang.value = value === 'zh' ? 'zh' : 'en'
    localStorage.setItem('fticrms_lang', lang.value)
    document.documentElement.lang = lang.value === 'zh' ? 'zh-CN' : 'en'
  }
  const currentMessages = computed(() => messages[lang.value] || messages.en)
  return { lang, t, setLang, messages: currentMessages }
}
