import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import router from './router'
import App from './App.vue'
import './assets/theme-dark.css'
import './assets/theme-light-glass.css'
import { useThemeStore } from '@/stores/theme'
import { useLocaleStore } from './stores/locale'

const app = createApp(App)

// 注册所有 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus)

// 全局 $t 方法 — 用于中英文切换
app.config.globalProperties.$t = (key) => {
  const store = useLocaleStore()
  return store.t(key)
}

app.mount('#app')

// Initialize theme after mount (applies data-theme attribute)
const themeStore = useThemeStore()
