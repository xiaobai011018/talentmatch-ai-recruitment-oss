<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="brand">
        <h1 class="brand-title">MaiMai Helper</h1>
        <span class="brand-desc">脉脉招聘自动化</span>
      </div>
      <div class="header-status">
        <span class="status-dot" :class="is_manager_busy ? 'busy' : 'idle'"></span>
        <span class="status-text">{{ is_manager_busy ? '运行中' : '空闲' }}</span>
        <el-divider direction="vertical" />
        <span class="status-text">{{ is_auto_reply ? '自动回复开启' : '自动回复关闭' }}</span>
        <el-button type="danger" link @click="onExit">退出</el-button>
      </div>
    </header>

    <div class="app-body">
      <!-- 左侧：账号区（固定） -->
      <aside class="sidebar">
        <div class="sidebar-block">
          <h3 class="block-title">登录</h3>
          <el-upload drag multiple :before-upload="onCookiesBeforeUpload" class="upload-compact">
            <el-icon class="upload-icon-sm"><upload-filled /></el-icon>
            <span class="upload-label">上传 Cookies</span>
          </el-upload>
          <el-button size="small" class="w-full login-btn" @click="onLoginByChrome" :loading="is_manager_busy">
            Chrome 登录
          </el-button>
        </div>

        <div class="sidebar-block sidebar-grow">
          <div class="block-title-row">
            <h3 class="block-title">脉脉账号</h3>
            <span class="badge">{{ user_ids_selected.length }} 已选</span>
          </div>
          <div class="table-wrap">
            <el-table :data="users" height="100%" size="small" stripe @selection-change="onUserSelectionChange"
              empty-text="请先登录">
              <el-table-column type="selection" width="42" />
              <el-table-column prop="name" label="姓名" show-overflow-tooltip />
              <el-table-column prop="id" label="ID" width="88" show-overflow-tooltip />
            </el-table>
          </div>
        </div>

        <div class="sidebar-block">
          <h3 class="block-title">Excel 批量</h3>
          <el-upload drag action="http://127.0.0.1:23333/upload_excel" :on-success="upload_excel_handle_success"
            class="upload-compact">
            <el-icon class="upload-icon-sm"><upload-filled /></el-icon>
            <span class="upload-label">上传 Excel</span>
          </el-upload>
          <el-radio-group v-model="is_excel" size="small" class="excel-radio">
            <el-radio value="1">表格发起</el-radio>
            <el-radio value="2">策略发起</el-radio>
          </el-radio-group>
        </div>
      </aside>

      <!-- 右侧：Tab 工作区 -->
      <main class="workspace">
        <el-tabs v-model="activeTab" class="main-tabs">
          <!-- Tab 1: 一次激活 -->
          <el-tab-pane label="一次激活" name="first_contact">
            <div class="tab-content">
              <p class="tab-desc">按岗位/策略或 Excel 表格，向新候选人发起首次触达。请在左侧勾选脉脉账号；Excel 模式在左侧栏配置。</p>
              <el-form label-width="96px" class="main-form" @submit.prevent>
                <el-form-item label="猎头">
                  <el-select v-model="user_value" filterable remote reserve-keyword placeholder="搜索猎头"
                    :remote-method="search_user_list" :loading="user_loading" :disabled="is_user_disable"
                    @focus="handle_user_focus" class="w-full">
                    <el-option v-for="item in user_options" :key="item.value" :label="item.label" :value="item.value" />
                  </el-select>
                </el-form-item>
                <el-form-item label="岗位">
                  <el-select v-model="position_value" filterable remote reserve-keyword placeholder="搜索岗位"
                    :remote-method="search_position_list" :loading="position_loading" :disabled="is_position_disable"
                    @focus="handle_position_focus" class="w-full">
                    <el-option v-for="item in position_options" :key="item.value" :label="item.label"
                      :value="item.value" />
                  </el-select>
                </el-form-item>
                <el-form-item v-if="is_excel === '2'" label="策略">
                  <el-select v-model="strategy_value" filterable remote reserve-keyword placeholder="搜索策略（可多选）"
                    :remote-method="search_strategy_list" :loading="strategy_loading" :disabled="is_strategy_disable"
                    @focus="handle_strategy_focus" class="w-full" multiple collapse-tags collapse-tags-tooltip>
                    <el-option v-for="item in strategy_options" :key="item.value" :label="item.label"
                      :value="item.value" />
                  </el-select>
                </el-form-item>
                <el-form-item v-if="is_excel === '1'" label="发起方式">
                  <span class="field-hint">当前为左侧栏「表格发起」，将使用已上传的 Excel</span>
                </el-form-item>
                <el-form-item label="招呼语">
                  <el-input v-model="greet_text" type="textarea" :rows="3" resize="none"
                    placeholder="您好，请问最近是否在看新机会呢？" />
                </el-form-item>
                <el-form-item label="每账号上限">
                  <el-input-number v-model="limit_per_user" :step="10" :min="1" controls-position="right" />
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="onFirstContact" :loading="is_manager_busy">开始一次激活</el-button>
                </el-form-item>
              </el-form>
            </div>
          </el-tab-pane>

          <!-- Tab 2: 二次激活 -->
          <el-tab-pane label="二次激活" name="second_contact">
            <div class="tab-content">
              <p class="tab-desc">对已有会话、候选人尚未回复的会话发送二次触达。请在左侧勾选脉脉账号。</p>
              <el-form label-width="96px" class="main-form" @submit.prevent>
                <el-form-item label="回复方式">
                  <el-radio-group v-model="second_contact_mode">
                    <el-radio value="all">全部岗位回复</el-radio>
                    <el-radio value="single">单独岗位回复</el-radio>
                  </el-radio-group>
                </el-form-item>
                <template v-if="second_contact_mode === 'single'">
                  <el-form-item label="猎头">
                    <el-select v-model="second_contact_hunter_value" filterable remote reserve-keyword
                      placeholder="搜索猎头" :remote-method="search_second_contact_hunter"
                      :loading="second_contact_hunter_loading" @focus="handle_second_contact_hunter_focus"
                      class="w-full">
                      <el-option v-for="item in second_contact_hunter_options" :key="item.value" :label="item.label"
                        :value="item.value" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="岗位">
                    <el-select v-model="second_contact_position_value" filterable remote reserve-keyword
                      placeholder="搜索岗位" :remote-method="search_second_contact_position"
                      :loading="second_contact_position_loading" :disabled="!second_contact_hunter_value"
                      @focus="handle_second_contact_position_focus" class="w-full">
                      <el-option v-for="item in second_contact_position_options" :key="item.value"
                        :label="item.label" :value="item.value" />
                    </el-select>
                  </el-form-item>
                </template>
                <el-form-item>
                  <el-button type="primary" @click="onSecondContact" :loading="is_manager_busy">开启二次会话</el-button>
                </el-form-item>
              </el-form>
            </div>
          </el-tab-pane>

          <!-- Tab 3: 回复 -->
          <el-tab-pane label="消息回复" name="reply">
            <div class="tab-content">
              <p class="tab-desc">自动回复脉脉消息，或将队列中候选人上传人才库。</p>
              <div class="action-cards">
                <div class="action-card">
                  <h4>自动回复</h4>
                  <p>轮询未读消息并由 AI 回复，检测到联系方式后加入上传队列。</p>
                  <el-button :type="is_auto_reply ? 'warning' : 'primary'" @click="onAutoReply"
                    :loading="is_manager_busy && !is_auto_reply">
                    {{ is_auto_reply ? '停止自动回复' : '启动自动回复' }}
                  </el-button>
                </div>
                <div class="action-card">
                  <h4>上传队列简历</h4>
                  <p>处理自动回复已收集的候选人，上传 AnyHelper 意向库。</p>
                  <el-button @click="onUploadResume" :loading="is_manager_busy">开始上传</el-button>
                </div>
                <div class="action-card">
                  <h4>导出 Cookies</h4>
                  <p>将当前已登录账号的 Cookies 保存到本地。</p>
                  <el-button @click="onExportCookies" :loading="is_manager_busy">导出</el-button>
                </div>
              </div>
            </div>
          </el-tab-pane>

          <!-- Tab 3: 保存简历 -->
          <el-tab-pane label="保存简历" name="save">
            <div class="tab-content">
              <p class="tab-desc">按日期范围批量扫描历史会话，上传 AnyHelper（需先在左侧勾选账号）。</p>
              <el-form label-width="96px" class="main-form" @submit.prevent>
                <el-form-item label="开始日期">
                  <el-date-picker v-model="save_resume_start_date" type="date" placeholder="选择开始日期"
                    value-format="YYYY-MM-DD HH:mm:ss" :disabled-date="disabledFutureDate" class="w-full" />
                </el-form-item>
                <el-form-item label="结束日期">
                  <el-date-picker v-model="save_resume_end_date" type="date" placeholder="选择结束日期"
                    value-format="YYYY-MM-DD HH:mm:ss" :disabled-date="disabledFutureDate" class="w-full" />
                </el-form-item>
                <el-form-item label="岗位范围">
                  <el-radio-group v-model="save_resume_mode">
                    <el-radio value="all">全部在招岗位</el-radio>
                    <el-radio value="single">指定岗位</el-radio>
                  </el-radio-group>
                </el-form-item>
                <template v-if="save_resume_mode === 'single'">
                  <el-form-item label="猎头">
                    <el-select v-model="save_resume_hunter_value" filterable remote reserve-keyword
                      placeholder="搜索猎头" :remote-method="search_save_resume_hunter"
                      :loading="save_resume_hunter_loading" @focus="handle_save_resume_hunter_focus" class="w-full">
                      <el-option v-for="item in save_resume_hunter_options" :key="item.value" :label="item.label"
                        :value="item.value" />
                    </el-select>
                  </el-form-item>
                  <el-form-item label="目标岗位">
                    <el-select v-model="save_resume_position_value" filterable remote reserve-keyword
                      placeholder="搜索岗位" :remote-method="search_save_resume_position"
                      :loading="save_resume_position_loading" :disabled="!save_resume_hunter_value"
                      @focus="handle_save_resume_position_focus" class="w-full">
                      <el-option v-for="item in save_resume_position_options" :key="item.value" :label="item.label"
                        :value="item.value" />
                    </el-select>
                  </el-form-item>
                </template>
                <el-form-item>
                  <el-button type="primary" @click="onSaveResume" :loading="is_manager_busy">开启保存简历</el-button>
                </el-form-item>
              </el-form>
            </div>
          </el-tab-pane>

          <!-- Tab 4: 全流程 -->
          <el-tab-pane label="全流程" name="pipeline">
            <div class="tab-content">
              <p class="tab-desc">按顺序自动执行多个步骤，适合无人值守批量运行。</p>
              <el-form label-width="120px" class="main-form" @submit.prevent>
                <el-form-item label="执行步骤">
                  <el-checkbox-group v-model="auto_process_options" class="step-checks">
                    <el-checkbox label="一次激活"
                      :value="is_excel === '1' ? 'first_contact_with_excel' : 'first_contact'" />
                    <el-checkbox label="二次激活" value="second_contact" />
                    <el-checkbox label="自动回复" value="auto_reply" />
                    <el-checkbox label="上传队列简历" value="upload_resume" />
                    <el-checkbox label="保存简历" value="save_resume" />
                  </el-checkbox-group>
                </el-form-item>
                <el-form-item label="回复停止时间">
                  <el-time-picker v-model="auto_reply_stop_time" placeholder="自动回复停止" />
                </el-form-item>
                <el-form-item v-if="auto_process_options.includes('save_resume')" label="保存简历日期">
                  <div class="date-range">
                    <el-date-picker v-model="save_resume_start_date" type="date" placeholder="开始"
                      value-format="YYYY-MM-DD HH:mm:ss" :disabled-date="disabledFutureDate" />
                    <span class="date-sep">至</span>
                    <el-date-picker v-model="save_resume_end_date" type="date" placeholder="结束"
                      value-format="YYYY-MM-DD HH:mm:ss" :disabled-date="disabledFutureDate" />
                  </div>
                </el-form-item>
                <el-form-item v-if="auto_process_options.includes('save_resume')" label="保存简历启动">
                  <el-time-picker v-model="save_resume_run_time" placeholder="到点后停止回复并开始保存" />
                </el-form-item>
                <el-form-item v-if="auto_process_options.includes('save_resume')" label="保存岗位范围">
                  <el-radio-group v-model="save_resume_mode" size="small">
                    <el-radio value="all">全部</el-radio>
                    <el-radio value="single">指定</el-radio>
                  </el-radio-group>
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" size="large" @click="onAutoProcessAll" :loading="is_manager_busy">
                    启动全流程
                  </el-button>
                </el-form-item>
              </el-form>
            </div>
          </el-tab-pane>
        </el-tabs>
      </main>
    </div>
  </div>
</template>


<script setup>
import { ref, onMounted, nextTick } from 'vue';
import { ElMessage } from 'element-plus';
import axios from 'axios'
import { UploadFilled } from '@element-plus/icons-vue'

let excel_name = null
const upload_excel_handle_success = (response, file) => {
  excel_name = file.name
  ElMessage.success(`成功上传${excel_name}`)
}
const is_excel = ref("1")
const activeTab = ref('first_contact')



// 用户搜索
const user_value = ref('')
const user_loading = ref(false)
const user_options = ref([])
const is_user_loaded = ref(false)
const is_user_disable = ref(false)
let user_debounce_timer = null
let user_request_id = 0
const search_user_list = async (query) => {
  if (user_debounce_timer) {
    clearTimeout(user_debounce_timer)
  }
  const current_request_id = ++user_request_id
  user_debounce_timer = setTimeout(async () => {
    await execute_user_search(query, current_request_id)
  }, 300)
}
const execute_user_search = async (query, requestId) => {
  user_loading.value = true
  try {
    const response = await axios.get(
      'http://127.0.0.1:23333/ah_search/hunter',
      { params: { keyword: query } }
    )
    if (requestId === user_request_id) {
      user_options.value = response.data.map((item) => ({
        value: item.user_id.toString(),
        label: `${item.user_id}-${item.Name}`
      }))
    }
  } catch (e) {
    if (requestId === user_request_id) {
      console.error('搜索猎头账号失败:', e)
      ElMessage.error('搜索失败, 请重试')
      user_options.value = []
    }
  } finally {
    if (requestId === user_request_id) {
      user_loading.value = false
    }
  }
}
const handle_user_focus = () => {
  if (!is_user_loaded.value && user_options.value.length === 0) {
    is_user_loaded.value = true
    search_user_list('')
  }
}

const position_value = ref('')
const position_loading = ref(false)
const position_options = ref([])
const is_position_loaded = ref(false)
const is_position_disable = ref(false)
let position_debounce_timer = null
let position_request_id = 0
const search_position_list = async (query) => {
  if (position_debounce_timer) {
    clearTimeout(position_debounce_timer)
  }
  const current_request_id = ++position_request_id
  position_debounce_timer = setTimeout(async () => {
    await execute_position_search(query, current_request_id)
  }, 300)
}
const execute_position_search = async (query, request_id) => {
  position_loading.value = true
  try {
    const response = await axios.get(
      'http://127.0.0.1:23333/ah_search/position',
      {
        params: {
          hid: user_value.value,
          keyword: query
        }
      }
    )
    if (request_id === position_request_id) {
      position_options.value = response.data.map((item) => ({
        value: item.position_id.toString(),
        label: `${item.position_id}-${item.position_name}-${item.company_name}`
      }))
    }
  } catch (e) {
    if (request_id === position_request_id) {
      console.error('搜索岗位失败:', e)
      ElMessage.error('搜索失败, 请重试')
      position_options.value = []
    }
  } finally {
    if (request_id === position_request_id) {
      position_loading.value = false
    }
  }
}
const handle_position_focus = () => {
  if (!is_position_loaded.value && position_options.value.length === 0) {
    is_position_loaded.value = true
    search_position_list('')
  }
}

const strategy_value = ref([])
const strategy_loading = ref(false)
const strategy_options = ref([])
const is_strategy_loaded = ref(false)
const is_strategy_disable = ref(false)
const raw_strategy_list = ref([])
let strategy_debounce_timer = null
let strategy_request_id = 0
const search_strategy_list = async (query) => {
  if (strategy_debounce_timer) {
    clearTimeout(strategy_debounce_timer)
  }
  const current_request_id = ++strategy_request_id
  strategy_debounce_timer = setTimeout(async () => {
    await execute_strategy_search(query, current_request_id)
  }, 300)
}
const execute_strategy_search = async (query, request_id) => {
  strategy_loading.value = true
  try {
    const response = await axios.get(
      'http://127.0.0.1:23333/ah_search/strategy',
      {
        params: {
          pid: position_value.value,
          keyword: query
        }
      }
    )
    if (request_id === strategy_request_id) {
      raw_strategy_list.value = response.data
      strategy_options.value = response.data.map((item) => ({
        value: item.id.toString(),
        label: `${item.id}-${item.name}`
      }))
    }
  } catch (e) {
    if (request_id === strategy_request_id) {
      console.error('搜索策略失败:', e)
      ElMessage.error('搜索失败, 请重试')
      strategy_options.value = []
      raw_strategy_list.value = []
    }
  } finally {
    if (request_id === strategy_request_id) {
      strategy_loading.value = false
    }
  }
}
const handle_strategy_focus = () => {
  if (!is_strategy_loaded.value && strategy_options.value.length === 0) {
    is_strategy_loaded.value = true
    search_strategy_list('')
  }
}
const get_selected_strategies = () => {
  if (!strategy_value.value || strategy_value.value.length === 0) return ''
  return raw_strategy_list.value
    .filter(item => strategy_value.value.includes(item.id.toString()))
    .map(item => item.id)
    .join(',')
}

const users = ref([])
const user_ids_selected = ref([])
const greet_text = ref('')
const is_manager_busy = ref(false)
const limit_per_user = ref(50)
const is_auto_reply = ref(false)
const auto_process_options = ref([])
const auto_reply_stop_time = ref(null)
const save_resume_run_time = ref(null)
const save_resume_start_date = ref('')
const save_resume_end_date = ref('')
const save_resume_mode = ref('all')

const second_contact_mode = ref('all')
const second_contact_hunter_value = ref('')
const second_contact_hunter_loading = ref(false)
const second_contact_hunter_options = ref([])
const is_second_contact_hunter_loaded = ref(false)
let second_contact_hunter_debounce = null
let second_contact_hunter_request_id = 0

const second_contact_position_value = ref('')
const second_contact_position_loading = ref(false)
const second_contact_position_options = ref([])
const is_second_contact_position_loaded = ref(false)
let second_contact_position_debounce = null
let second_contact_position_request_id = 0

const save_resume_hunter_value = ref('')
const save_resume_hunter_loading = ref(false)
const save_resume_hunter_options = ref([])
const is_save_resume_hunter_loaded = ref(false)
let save_resume_hunter_debounce = null
let save_resume_hunter_request_id = 0

const save_resume_position_value = ref('')
const save_resume_position_loading = ref(false)
const save_resume_position_options = ref([])
const is_save_resume_position_loaded = ref(false)
let save_resume_position_debounce = null
let save_resume_position_request_id = 0

const disabledFutureDate = (time) => time.getTime() > Date.now()

const ensureUsersSelected = () => {
  if (user_ids_selected.value.length) return true
  ElMessage.warning('请先在左侧「脉脉账号」表格中勾选至少一个账号')
  return false
}

const validateSaveResumeParams = () => {
  if (!save_resume_start_date.value) {
    ElMessage.error('请选择开始日期')
    return false
  }
  if (!save_resume_end_date.value) {
    ElMessage.error('请选择结束日期')
    return false
  }
  if (save_resume_mode.value === 'single' && !save_resume_position_value.value) {
    ElMessage.error('指定岗位模式下请选择目标岗位')
    return false
  }
  if (!ensureUsersSelected()) return false
  return true
}

const buildSaveResumeQuery = () => {
  const params = new URLSearchParams({
    reply_mode: save_resume_mode.value,
    start_time: save_resume_start_date.value,
    end_time: save_resume_end_date.value,
    user_ids: user_ids_selected.value.join(','),
  })
  if (save_resume_mode.value === 'single') {
    params.set('position_id', save_resume_position_value.value)
  }
  return params
}

const search_save_resume_hunter = async (query) => {
  if (save_resume_hunter_debounce) clearTimeout(save_resume_hunter_debounce)
  const requestId = ++save_resume_hunter_request_id
  save_resume_hunter_debounce = setTimeout(async () => {
    save_resume_hunter_loading.value = true
    try {
      const response = await axios.get('http://127.0.0.1:23333/ah_search/hunter', { params: { keyword: query } })
      if (requestId === save_resume_hunter_request_id) {
        save_resume_hunter_options.value = response.data.map((item) => ({
          value: item.user_id.toString(),
          label: `${item.user_id}-${item.Name}`,
        }))
      }
    } catch (e) {
      if (requestId === save_resume_hunter_request_id) {
        ElMessage.error('搜索猎头账号失败')
        save_resume_hunter_options.value = []
      }
    } finally {
      if (requestId === save_resume_hunter_request_id) save_resume_hunter_loading.value = false
    }
  }, 300)
}

const handle_save_resume_hunter_focus = () => {
  if (!is_save_resume_hunter_loaded.value && !save_resume_hunter_options.value.length) {
    is_save_resume_hunter_loaded.value = true
    search_save_resume_hunter('')
  }
}

const search_save_resume_position = async (query) => {
  if (save_resume_position_debounce) clearTimeout(save_resume_position_debounce)
  const requestId = ++save_resume_position_request_id
  save_resume_position_debounce = setTimeout(async () => {
    save_resume_position_loading.value = true
    try {
      const response = await axios.get('http://127.0.0.1:23333/ah_search/position', {
        params: { hid: save_resume_hunter_value.value, keyword: query },
      })
      if (requestId === save_resume_position_request_id) {
        save_resume_position_options.value = response.data.map((item) => ({
          value: item.position_id.toString(),
          label: `${item.position_id}-${item.position_name}-${item.company_name}`,
        }))
      }
    } catch (e) {
      if (requestId === save_resume_position_request_id) {
        ElMessage.error('搜索岗位失败')
        save_resume_position_options.value = []
      }
    } finally {
      if (requestId === save_resume_position_request_id) save_resume_position_loading.value = false
    }
  }, 300)
}

const handle_save_resume_position_focus = () => {
  if (!is_save_resume_position_loaded.value && !save_resume_position_options.value.length) {
    is_save_resume_position_loaded.value = true
    search_save_resume_position('')
  }
}

const search_second_contact_hunter = async (query) => {
  if (second_contact_hunter_debounce) clearTimeout(second_contact_hunter_debounce)
  const requestId = ++second_contact_hunter_request_id
  second_contact_hunter_debounce = setTimeout(async () => {
    second_contact_hunter_loading.value = true
    try {
      const response = await axios.get('http://127.0.0.1:23333/ah_search/hunter', { params: { keyword: query } })
      if (requestId === second_contact_hunter_request_id) {
        second_contact_hunter_options.value = response.data.map((item) => ({
          value: item.user_id.toString(),
          label: `${item.user_id}-${item.Name}`,
        }))
      }
    } catch (e) {
      if (requestId === second_contact_hunter_request_id) {
        ElMessage.error('搜索猎头账号失败')
        second_contact_hunter_options.value = []
      }
    } finally {
      if (requestId === second_contact_hunter_request_id) second_contact_hunter_loading.value = false
    }
  }, 300)
}

const handle_second_contact_hunter_focus = () => {
  if (!is_second_contact_hunter_loaded.value && !second_contact_hunter_options.value.length) {
    is_second_contact_hunter_loaded.value = true
    search_second_contact_hunter('')
  }
}

const search_second_contact_position = async (query) => {
  if (second_contact_position_debounce) clearTimeout(second_contact_position_debounce)
  const requestId = ++second_contact_position_request_id
  second_contact_position_debounce = setTimeout(async () => {
    second_contact_position_loading.value = true
    try {
      const response = await axios.get('http://127.0.0.1:23333/ah_search/position', {
        params: { hid: second_contact_hunter_value.value, keyword: query },
      })
      if (requestId === second_contact_position_request_id) {
        second_contact_position_options.value = response.data.map((item) => ({
          value: item.position_id.toString(),
          label: `${item.position_id}-${item.position_name}-${item.company_name}`,
        }))
      }
    } catch (e) {
      if (requestId === second_contact_position_request_id) {
        ElMessage.error('搜索岗位失败')
        second_contact_position_options.value = []
      }
    } finally {
      if (requestId === second_contact_position_request_id) second_contact_position_loading.value = false
    }
  }, 300)
}

const handle_second_contact_position_focus = () => {
  if (!is_second_contact_position_loaded.value && !second_contact_position_options.value.length) {
    is_second_contact_position_loaded.value = true
    search_second_contact_position('')
  }
}

const validateSecondContactParams = () => {
  if (!ensureUsersSelected()) return false
  if (second_contact_mode.value === 'single' && !second_contact_position_value.value) {
    ElMessage.error('单独岗位回复请选择目标岗位')
    return false
  }
  return true
}

const onExit = () => {
  fetch('/shutdown')
}

const onUserSelectionChange = (rows) => {
  user_ids_selected.value = rows.map(obj => obj.id)
}

const onAutoProcessAll = async () => {
  if (!ensureUsersSelected()) return
  if (auto_process_options.value.includes('save_resume') && !validateSaveResumeParams()) return

  is_manager_busy.value = true

  if (greet_text.value == '')
    greet_text.value = '您好，请问最近是否在看新机会呢？'

  const options = [...auto_process_options.value]

  let res = null
  const baseParams = `greet_text=${encodeURIComponent(greet_text.value)}&limit_per_user=${limit_per_user.value}&options=${options.join(',')}&user_ids=${user_ids_selected.value.join()}`
  const autoReplyTs = auto_reply_stop_time.value ? auto_reply_stop_time.value.getTime() : ''
  const saveResumeTs = save_resume_run_time.value ? save_resume_run_time.value.getTime() : ''
  const saveResumeRange = options.includes('save_resume')
    ? `&save_resume_mode=${save_resume_mode.value}&save_resume_start_time=${encodeURIComponent(save_resume_start_date.value)}&save_resume_end_time=${encodeURIComponent(save_resume_end_date.value)}&save_resume_time=${saveResumeTs}&save_resume_position_id=${save_resume_position_value.value || ''}`
    : ''
  if (is_excel.value === '1') {
    res = await fetch(`/cmd_auto_process_all?pid=${position_value.value}&excel_name=${excel_name}&${baseParams}&auto_reply_stop_timestamp=${autoReplyTs}${saveResumeRange}`, {
      method: 'GET',
    })
  } else {
    res = await fetch(`/cmd_auto_process_all?pid=${position_value.value}&search_condition_ids=${get_selected_strategies()}&${baseParams}&auto_reply_stop_timestamp=${autoReplyTs}${saveResumeRange}`, {
      method: 'GET',
    })
  }

  let body = await res.json()
  if (body['succeed']) {
    ElMessage.success('successed')
  }
  else {
    ElMessage.error(body['data'])
  }

  is_manager_busy.value = false
}

const onLoginByChrome = async () => {
  is_manager_busy.value = true
  let res = await fetch('/login_by_chrome', { method: 'GET' })
  let body = await res.json()
  if (body['succeed']) {
    ElMessage.success('login successed')
    await nextTick()
    getUsers()
  }
  else {
    ElMessage.error(body['data'])
  }
  is_manager_busy.value = false
}

const onCookiesBeforeUpload = (file) => {
  let fileReader = new FileReader()
  fileReader.onloadend = async () => {
    let res = await fetch('/update_user', {
      method: 'POST',
      body: fileReader.result,
    })
    let body = await res.json()
    if (body['succeed']) {
      ElMessage.success(`${file.name} succeed`)
      await nextTick()
      getUsers()
    }
    else {
      ElMessage.error(file.name)
    }
  }
  fileReader.readAsArrayBuffer(file)
  return false
}

const getUsers = async () => {
  let res = await fetch('/get_users', { method: 'GET' })
  let body = await res.json()
  if (body['succeed']) {
    users.value = body['data']
  }
  else {
    ElMessage.error(body['data'])
  }
}

const onFirstContact = async () => {
  if (!ensureUsersSelected()) return
  is_manager_busy.value = true
  if (greet_text.value == '')
    greet_text.value = '您好，请问最近是否在看新机会呢？'
  let res = null
  if (is_excel.value === "1") {
    res = await fetch(`/cmd_first_contact_excel?excel_name=${excel_name}&&greet_text=${greet_text.value}&limit_per_user=${limit_per_user.value}&user_ids=${user_ids_selected.value.join()}`, {
      method: 'GET',
    })
  } else {
    res = await fetch(`/cmd_first_contact?pid=${position_value.value}&search_condition_ids=${get_selected_strategies()}&greet_text=${greet_text.value}&limit_per_user=${limit_per_user.value}&user_ids=${user_ids_selected.value.join()}`, {
      method: 'GET',
    })
  }
  let body = await res.json()
  if (body['succeed']) {
    ElMessage.success(`${body['data']['succ_count']}/${body['data']['search_total']} succeed`)
    for (let e in body['exceptions']) {
      ElMessage.warning(e)
    }
  }
  else {
    ElMessage.error(body['data'])
  }
  is_manager_busy.value = false
}

const getIsManagerBusy = async () => {
  let res = await fetch(`/is_locked`, { method: 'GET', })
  let body = await res.json()
  if (body['succeed']) {
    is_manager_busy.value = body['data']
  }
  else {
    ElMessage.error(body['data'])
  }
}

const onSecondContact = async () => {
  if (!validateSecondContactParams()) return
  is_manager_busy.value = true
  const params = new URLSearchParams({
    user_ids: user_ids_selected.value.join(','),
    reply_mode: second_contact_mode.value,
  })
  if (second_contact_mode.value === 'single') {
    params.set('position_id', second_contact_position_value.value)
  }
  let res = await fetch(`/cmd_second_contact?${params.toString()}`, { method: 'GET' })
  let body = await res.json()
  if (body['succeed']) {
    ElMessage.success(`succeed: ${JSON.stringify(body['data'])}`)
  }
  else {
    ElMessage.error(body['data'])
  }
  is_manager_busy.value = false
}

const getIsAutoReply = async () => {
  let res = await fetch(`/is_auto_reply`, { method: 'GET', })
  let body = await res.json()
  if (body['succeed']) {
    is_auto_reply.value = body['data']
  }
  else {
    ElMessage.error(body['data'])
  }
}

const onAutoReply = async () => {
  if (is_auto_reply.value) {
    is_auto_reply.value = false
    const res = await fetch(`/cmd_stop_auto_reply`, { method: 'GET' })
    const body = await res.json()
    if (body['succeed']) {
      ElMessage.success('已停止自动回复')
    } else {
      ElMessage.error(body['data'])
    }
    await getIsManagerBusy()
    await getIsAutoReply()
    return
  }

  if (!ensureUsersSelected()) return

  const res = await fetch(
    `/cmd_auto_reply?user_ids=${user_ids_selected.value.join(',')}`,
    { method: 'GET' },
  )
  const body = await res.json()
  if (body['succeed']) {
    is_auto_reply.value = true
    is_manager_busy.value = true
    ElMessage.success(body['data'] === '自动回复已在运行' ? body['data'] : '自动回复已在后台运行')
  } else {
    ElMessage.error(body['data'])
  }
}

const onUploadResume = async () => {
  is_manager_busy.value = true
  let res = await fetch(`/cmd_upload_resume`, { method: 'GET', })
  let body = await res.json()
  if (body['succeed']) {
    const stats = body['data'] || {}
    if ((stats['queued'] || 0) === 0) {
      ElMessage.info('当前待上传队列为空')
    } else {
      ElMessage.success(
        `队列${stats['queued']}位：成功${stats['succeeded']}，跳过${stats['skipped']}，` +
        `失败${stats['failed']}，剩余${stats['remaining']}`,
      )
    }
  }
  else {
    ElMessage.error(body['data'])
  }
  is_manager_busy.value = false
}

const onSaveResume = async () => {
  if (!validateSaveResumeParams()) return
  is_manager_busy.value = true
  try {
    const res = await fetch(`/cmd_save_resume?${buildSaveResumeQuery().toString()}`, { method: 'GET' })
    const body = await res.json()
    if (body['succeed']) {
      const data = body['data'] || {}
      ElMessage.success(`保存简历完成：成功 ${data.succ_count ?? 0} 条，跳过 ${data.skip_count ?? 0} 条`)
    } else {
      ElMessage.error(body['data'])
    }
  } catch (err) {
    ElMessage.error('保存简历发起失败')
  }
  is_manager_busy.value = false
}

const onExportCookies = async () => {
  is_manager_busy.value = true
  let res = await fetch(`/get_cookies`, { method: 'GET', })
  let body = await res.json()
  if (body['succeed']) {
    ElMessage.success(`succeed`)
  }
  else {
    ElMessage.error(body['data'])
  }
  is_manager_busy.value = false
}

onMounted(() => {
  getUsers()
  getIsManagerBusy()
  getIsAutoReply()
  setInterval(async () => {
    if (is_auto_reply.value) {
      await getIsAutoReply()
      await getIsManagerBusy()
      if (!is_auto_reply.value) {
        is_manager_busy.value = false
      }
    }
  }, 5000)
})
</script>

<style>
html,
body {
  margin: 0;
  padding: 0;
  background: #eef1f6;
}

#app {
  height: 100vh;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB',
    'Microsoft YaHei', sans-serif;
  -webkit-font-smoothing: antialiased;
  color: #1f2937;
  overflow: hidden;
}
</style>

<style scoped>
.app-shell {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f6f8;
}

.app-header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 52px;
  padding: 0 20px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
}

.brand {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.brand-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #111827;
}

.brand-desc {
  font-size: 12px;
  color: #9ca3af;
}

.header-status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #6b7280;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot.idle {
  background: #22c55e;
}

.status-dot.busy {
  background: #f59e0b;
}

.app-body {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow: hidden;
}

.sidebar {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 0;
  background: #fff;
  border-right: 1px solid #e5e7eb;
  padding: 16px 14px;
  overflow-y: auto;
}

.sidebar-block {
  padding-bottom: 16px;
  margin-bottom: 16px;
  border-bottom: 1px solid #f0f0f0;
}

.sidebar-block:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.sidebar-grow {
  flex: 1;
  min-height: 180px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.table-wrap {
  flex: 1;
  min-height: 0;
}

.login-btn {
  margin-top: 10px;
}

.block-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.block-title {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}

.block-title-row .block-title {
  margin-bottom: 0;
}

.badge {
  font-size: 11px;
  color: #6366f1;
  background: #eef2ff;
  padding: 2px 8px;
  border-radius: 10px;
}

.workspace {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: #fff;
  overflow: hidden;
}

.main-tabs {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.main-tabs :deep(.el-tabs__header) {
  margin: 0;
  padding: 0 24px;
  background: #fafafa;
  border-bottom: 1px solid #e5e7eb;
}

.main-tabs :deep(.el-tabs__content) {
  flex: 1;
  overflow-y: auto;
  padding: 0;
}

.main-tabs :deep(.el-tab-pane) {
  height: 100%;
}

.tab-content {
  max-width: 560px;
  padding: 24px 28px 32px;
}

.tab-desc {
  margin: 0 0 20px;
  font-size: 13px;
  line-height: 1.6;
  color: #6b7280;
}

.main-form :deep(.el-form-item) {
  margin-bottom: 18px;
}

.w-full {
  width: 100%;
}

.upload-compact :deep(.el-upload) {
  width: 100%;
}

.upload-compact :deep(.el-upload-dragger) {
  width: 100%;
  height: auto;
  padding: 14px 8px;
  border-radius: 8px;
  border-color: #e5e7eb;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.upload-compact :deep(.el-upload-dragger:hover) {
  border-color: #6366f1;
}

.upload-icon-sm {
  font-size: 22px;
  color: #6366f1;
}

.upload-label {
  font-size: 12px;
  color: #6b7280;
}

.excel-radio {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  margin-top: 10px;
}

.action-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 480px;
}

.action-card {
  padding: 16px 18px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #fafafa;
}

.action-card-single {
  max-width: 480px;
}

.field-hint {
  font-size: 13px;
  line-height: 1.5;
  color: #6b7280;
}

.action-card-single .field-hint {
  margin: 0 0 12px;
}

.action-card h4 {
  margin: 0 0 6px;
  font-size: 14px;
  font-weight: 600;
  color: #111827;
}

.action-card p {
  margin: 0 0 12px;
  font-size: 12px;
  line-height: 1.5;
  color: #6b7280;
}

.step-checks {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}

.date-range {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.date-sep {
  font-size: 13px;
  color: #9ca3af;
}
</style>
