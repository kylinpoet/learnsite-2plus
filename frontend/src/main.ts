import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { initializeTheme } from './composables/useTheme'
import './styles/base.css'

initializeTheme()

createApp(App).use(router).mount('#app')
