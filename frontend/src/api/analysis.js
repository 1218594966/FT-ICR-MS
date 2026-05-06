import api from './index'

export function uploadDataFile(file) {
  const fd = new FormData()
  fd.append('file', file)
  return api.post('/upload/data', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 600000,
  })
}

export function uploadFolder(files) {
  const fd = new FormData()
  for (const f of files) {
    fd.append('files', f, f.webkitRelativePath || f.name)
  }
  return api.post('/upload/folder', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 600000,
  })
}

export function startAnalysis(taskId, filePath, filename, params) {
  return api.post('/analysis/start', { params }, {
    params: { file_path: filePath, filename },
  })
}

export function getTaskStatus(taskId) {
  return api.get(`/analysis/${taskId}/status`)
}

export function getTaskDetail(taskId) {
  return api.get(`/analysis/${taskId}`)
}

export function deleteTask(taskId) {
  return api.delete(`/analysis/${taskId}`)
}

export function getResultData(taskId) {
  return api.get(`/results/${taskId}/data`)
}

export function getChartData(taskId, chartType) {
  return api.get(`/results/${taskId}/chart/${chartType}`)
}

export function getExportUrl(taskId) {
  return `/api/results/${taskId}/export`
}

export function getVKPdfUrl(taskId, params = {}) {
  const qs = new URLSearchParams(params).toString()
  return `/api/export/${taskId}/vankrevelen/pdf${qs ? '?' + qs : ''}`
}

export function getVKSvgUrl(taskId, params = {}) {
  const qs = new URLSearchParams(params).toString()
  return `/api/export/${taskId}/vankrevelen/svg${qs ? '?' + qs : ''}`
}

export function getVKTifUrl(taskId, params = {}) {
  const qs = new URLSearchParams(params).toString()
  return `/api/export/${taskId}/vankrevelen/tif${qs ? '?' + qs : ''}`
}

export function getChartPdfUrl(taskId, chartType, params = {}) {
  const qs = new URLSearchParams(params).toString()
  return `/api/export/${taskId}/${chartType}/pdf${qs ? '?' + qs : ''}`
}

export function getChartTifUrl(taskId, chartType, params = {}) {
  const qs = new URLSearchParams(params).toString()
  return `/api/export/${taskId}/${chartType}/tif${qs ? '?' + qs : ''}`
}

export function getHistory(params = {}) {
  return api.get('/history', { params })
}

export function getDefaultParams() {
  return api.get('/config/defaults')
}
