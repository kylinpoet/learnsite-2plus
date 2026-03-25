import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import { initializeTheme } from './composables/useTheme'
import './styles/base.css'

initializeTheme()

createApp(App).use(router).use(ElementPlus).mount('#app')
