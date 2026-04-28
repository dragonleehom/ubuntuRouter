import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  const theme = ref(localStorage.getItem('ubunturouter-theme') || 'dark')

  function setTheme(name) {
    theme.value = name
    localStorage.setItem('ubunturouter-theme', name)
    applyTheme(name)
  }

  function toggleTheme() {
    setTheme(theme.value === 'dark' ? 'light' : 'dark')
  }

  function applyTheme(name) {
    document.documentElement.setAttribute('data-theme', name)
  }

  // Initialize on first load
  applyTheme(theme.value)

  return { theme, setTheme, toggleTheme }
})
