import { defineStore } from 'pinia'
import { ref } from 'vue'
import zhCN from '../locales/zh-CN'
import en from '../locales/en'

const messages = { 'zh-CN': zhCN, 'en': en }

export const useLocaleStore = defineStore('locale', () => {
  const locale = ref(localStorage.getItem('ubunturouter-locale') || 'zh-CN')

  function setLocale(lang) {
    locale.value = lang
    localStorage.setItem('ubunturouter-locale', lang)
  }

  function t(key) {
    return messages[locale.value]?.[key] ?? messages['zh-CN']?.[key] ?? key
  }

  return { locale, setLocale, t }
})
