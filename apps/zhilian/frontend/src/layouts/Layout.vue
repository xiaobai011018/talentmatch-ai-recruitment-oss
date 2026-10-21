<template>
  <el-container class="common-layout">
    <el-header>
      <span>招聘平台全自动</span>
      <el-button class="theme-toggle-btn" @click="toggleTheme" :icon="isDark ? 'Sunny' : 'Moon'" circle size="small" />
    </el-header>
    <el-container>
      <el-aside width="200px">
        <el-menu :default-active="activeMenu" router>
          <el-menu-item index="/cookies">上传 cookies</el-menu-item>
          <el-menu-item index="/session">上传高潜功能</el-menu-item>
          <el-menu-item index="/firstConversation">初次会话功能</el-menu-item>
          <el-menu-item index="/secondConversation">二次会话功能</el-menu-item>
          <el-menu-item index="/autoReply">自动回复功能</el-menu-item>
          <el-menu-item index="/saveResume">保存简历功能</el-menu-item>
          <el-menu-item index='/allAuto'>全自动</el-menu-item>
          <el-menu-item index="/other">其他功能</el-menu-item>
        </el-menu>
      </el-aside>
      <el-main>
        <keep-alive>
          <router-view />
        </keep-alive>
      </el-main>
    </el-container>
  </el-container>
</template>

<script lang="ts">
import { defineComponent, ref, computed } from 'vue'

export default defineComponent({
  setup() {
    const activeMenu = ref('/cookies')

    // 检查当前是否为暗黑主题
    const isDark = computed(() => {
      return document.documentElement.classList.contains('dark')
    })

    // 主题切换方法
    const toggleTheme = () => {
      if ((window as any).toggleTheme) {
        (window as any).toggleTheme()
      }
    }

    return {
      activeMenu,
      isDark,
      toggleTheme
    }
  }
})
</script>
