import { computed, ref } from 'vue'

const saved = localStorage.getItem('fticrms_theme')
const theme = ref(saved === 'light' ? 'light' : 'dark')

function applyTheme(value) {
  const normalized = value === 'light' ? 'light' : 'dark'
  theme.value = normalized
  localStorage.setItem('fticrms_theme', normalized)
  document.documentElement.dataset.theme = normalized
  document.documentElement.classList.toggle('dark', normalized === 'dark')
}

applyTheme(theme.value)

export function useTheme() {
  const isDark = computed(() => theme.value === 'dark')
  const toggleTheme = () => applyTheme(isDark.value ? 'light' : 'dark')
  return { theme, isDark, setTheme: applyTheme, toggleTheme }
}
