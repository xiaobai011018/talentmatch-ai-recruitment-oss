import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import './assets/style.css'

// 创建 Vue 应用实例
const app = createApp(App)

// 使用路由
app.use(router)

// 使用 ElementPlus
app.use(ElementPlus)

app.use(createPinia())

// 挂载到页面
app.mount('#app')
