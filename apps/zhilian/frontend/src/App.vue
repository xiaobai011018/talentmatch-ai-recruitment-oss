<template>
  <div :class="{ 'dark': isDark }">
    <Layout />
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, onMounted } from 'vue'
import Layout from './layouts/Layout.vue'
import { useCookiesStore } from './stores/cookiesStore'

export default defineComponent({
  components: { Layout },
  setup() {
    const isDark = ref(false)
    
    // 从localStorage读取主题设置
    onMounted(() => {
      const savedTheme = localStorage.getItem('theme')
      if (savedTheme === 'dark') {
        isDark.value = true
        document.documentElement.classList.add('dark')
      }
      const cookiesStore = useCookiesStore()
      cookiesStore.loadCookiesInfo()
    })
    
    // 提供全局主题切换方法
    const toggleTheme = () => {
      isDark.value = !isDark.value
      if (isDark.value) {
        document.documentElement.classList.add('dark')
        localStorage.setItem('theme', 'dark')
      } else {
        document.documentElement.classList.remove('dark')
        localStorage.setItem('theme', 'light')
      }
    }
    
    // 将toggleTheme方法挂载到全局，供子组件使用
    ;(window as any).toggleTheme = toggleTheme
    
    return {
      isDark
    }
  }
})
</script>
