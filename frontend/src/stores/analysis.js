import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getDefaultParams, getTaskStatus } from '../api/analysis'

export const useAnalysisStore = defineStore('analysis', () => {
  const defaultParams = ref(null)
  const currentTask = ref(null)
  const polling = ref(null)

  async function fetchDefaults() {
    if (!defaultParams.value) {
      defaultParams.value = await getDefaultParams()
    }
    return defaultParams.value
  }

  function startPolling(taskId, onUpdate) {
    stopPolling()
    polling.value = setInterval(async () => {
      try {
        const status = await getTaskStatus(taskId)
        currentTask.value = status
        if (onUpdate) onUpdate(status)
        if (status.status === 'success' || status.status === 'failed') {
          stopPolling()
        }
      } catch {
        // ignore polling errors
      }
    }, 1500)
  }

  function stopPolling() {
    if (polling.value) {
      clearInterval(polling.value)
      polling.value = null
    }
  }

  return { defaultParams, currentTask, fetchDefaults, startPolling, stopPolling }
})
