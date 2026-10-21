import { createRouter, createWebHashHistory } from 'vue-router'
import SessionPage from '@/views/SessionPage.vue'
import FirstConversation from '../views/FirstConversation.vue'
import OtherPage from '@/views/OtherPage.vue'
import AutoReply from '../views/AutoReply.vue'
import SecondConversation from '../views/SecondConversation.vue'
import SaveResume from '../views/SaveResume.vue'
import UploadCookies from '../views/UploadCookies.vue'
import AllAuto from '../views/AllAuto.vue'

const routes = [
  { path: '/', redirect: '/cookies' },
  { path: '/cookies', component: UploadCookies },
  { path: '/session', component: SessionPage },
  { path: '/firstConversation', component: FirstConversation },
  { path: '/secondConversation', component: SecondConversation },
  { path: '/autoReply', component: AutoReply },
  { path: '/saveResume', component: SaveResume },
  { path: '/allAuto', component: AllAuto },
  { path: '/other', component: OtherPage }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router
