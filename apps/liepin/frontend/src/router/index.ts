import { createRouter, createWebHashHistory } from 'vue-router'
import AutoReply from '../views/AutoReply.vue'
import SecondConversation from '../views/SecondConversation.vue'
import SaveResume from '../views/SaveResume.vue'
import UploadCookies from '../views/UploadCookies.vue'
import AllAuto from '../views/AllAuto.vue'
import FirstConversation from '../views/FirstConversation.vue'
import UploadScreeningResume from '../views/UploadScreeningResume.vue'

const routes = [
  { path: '/', redirect: '/cookies' },
  { path: '/cookies', component: UploadCookies },
  { path: '/uploadScreeningResume', component: UploadScreeningResume },
  { path: '/firstConversation', component: FirstConversation},
  { path: '/secondConversation', component: SecondConversation},
  { path: '/autoReply', component: AutoReply },
  { path: '/saveResume', component: SaveResume },
  { path: '/allAuto', component: AllAuto }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router
