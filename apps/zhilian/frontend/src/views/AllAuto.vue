<template>
    <el-row :gutter="20">
        <el-col :span="10">
            <el-form :model="form" label-width="auto" style="max-width: 600px">
                <el-form-item label="启动流程">
                    <el-checkbox-group v-model="selectedProcess">
                        <el-checkbox label="上传高潜" value="uploadScreening" />
                        <el-checkbox label="初次会话" value="firstConversation" />
                        <el-checkbox label="二次会话" value="secondConversation" />
                        <el-checkbox label="自动回复" value="autoReply" />
                        <el-checkbox label="保存简历" value="saveResume" />
                    </el-checkbox-group>
                </el-form-item>
                <el-form-item label="发起会话模式" v-if="selectedProcess.includes('firstConversation')">
                    <el-radio-group v-model="conversationMode">
                        <el-radio value="single">按策略发起</el-radio>
                        <el-radio value="upload">按表格发起</el-radio>
                    </el-radio-group>
                </el-form-item>
                <el-form-item label="策略获取方式"
                    v-if="selectedProcess.includes('firstConversation') && conversationMode === 'single' || selectedProcess.includes('uploadScreening')">
                    <el-radio-group v-model="strategyMode">
                        <el-radio value="cloud">从云端选择</el-radio>
                        <el-radio value="upload">上传本地文件</el-radio>
                        <el-radio value="all">全部策略</el-radio>
                    </el-radio-group>
                </el-form-item>
                <el-form-item label="回复方式"
                    v-if="selectedProcess.includes('secondConversation') || selectedProcess.includes('autoReply') || selectedProcess.includes('saveResume')">
                    <el-radio-group v-model="replyMode">
                        <el-radio value="all">全部岗位回复</el-radio>
                        <el-radio value="single">单独岗位回复</el-radio>
                    </el-radio-group>
                </el-form-item>
                <el-form-item label="猎头账号"
                    v-if="
                        selectedProcess.includes('uploadScreening')
                        || (selectedProcess.includes('firstConversation') && conversationMode === 'single')
                        || (selectedProcess.includes('saveResume') && replyMode === 'single')
                        || ((selectedProcess.includes('secondConversation') || selectedProcess.includes('autoReply')) && replyMode === 'single')">
                    <div class="flex flex-wrap">
                        <div class="m-4">
                            <el-select v-model="hunterAccountValue" filterable remote reserve-keyword
                                placeholder="请输入姓名关键字" :remote-method="searchHunterAccounts"
                                :loading="hunterAccountLoading" :disabled="isHunterAccountDisabled"
                                @focus="handleHunterAccountFocus" style="width: 240px">
                                <el-option v-for="item in hunterAccountOptions" :key="item.value" :label="item.label"
                                    :value="item.value" />
                            </el-select>
                        </div>
                    </div>
                </el-form-item>

                <el-form-item label="岗位选择" v-if="selectedProcess.includes('uploadScreening')
                    || (selectedProcess.includes('firstConversation') && conversationMode === 'single')
                    || ((selectedProcess.includes('secondConversation')
                        || selectedProcess.includes('autoReply')
                        || selectedProcess.includes('saveResume')) && replyMode === 'single')">
                    <div class="flex flex-wrap">
                        <div class="m-4">
                            <el-select v-model="positionValue" filterable remote reserve-keyword placeholder="请输入岗位关键字"
                                :remote-method="searchPositions" :loading="positionLoading"
                                :disabled="isPositionDisabled" @focus="handlePositionFocus" style="width: 240px">
                                <el-option v-for="item in positionOptions" :key="item.value" :label="item.label"
                                    :value="item.value" />
                            </el-select>
                        </div>
                    </div>
                </el-form-item>

                <el-form-item label="策略选择" v-if="(selectedProcess.includes('uploadScreening')
                    || (selectedProcess.includes('firstConversation')) && conversationMode === 'single')
                    && strategyMode === 'cloud'">
                    <div class="flex flex-wrap">
                        <div class="m-4">
                            <el-select v-model="strategyValue" filterable remote reserve-keyword placeholder="请输入策略关键字"
                                :remote-method="searchStrategies" :loading="strategyLoading"
                                :disabled="isStrategyDisabled" @focus="handleStrategyFocus" style="width: 240px"
                                multiple>
                                <el-option v-for="item in strategyOptions" :key="item.value" :label="item.label"
                                    :value="item.value" />
                            </el-select>
                        </div>
                    </div>
                </el-form-item>


                <el-form-item label="限制发起会话数量" v-if="selectedProcess.includes('firstConversation')">
                    <el-input v-model="sessionLimitCount" style="width: 240px" placeholder="请输入限制数量" />
                </el-form-item>
                <el-form-item label="开始日期" v-if="selectedProcess.includes('saveResume')">
                    <el-date-picker v-model="startDate" type="date" placeholder="Pick a day"
                        value-format="YYYY-MM-DD HH:mm:ss" :disabled-date="disabledDate" />
                </el-form-item>

                <el-form-item label="结束日期" v-if="selectedProcess.includes('saveResume')">
                    <el-date-picker v-model="endDate" type="date" placeholder="Pick a day"
                        value-format="YYYY-MM-DD HH:mm:ss" :disabled-date="disabledDate" />
                </el-form-item>

                <el-form-item label="自动保存简历时间" v-if="selectedProcess.includes('saveResume')">
                    <el-time-picker v-model="saveResumeTime" placeholder="Arbitrary time"
                        value-format="YYYY-MM-DD HH:mm:ss" />
                </el-form-item>

                <!-- 上传 session 文件 -->
                <el-form-item label="上传 session 文件"
                    v-if="(selectedProcess.includes('uploadScreening') || selectedProcess.includes('firstConversation')) && strategyMode === 'upload'">
                    <el-upload class="upload-demo" drag action="/api/search_condition/sessionFile"
                        :on-success="handleSessionUploadSuccess" :file-list="sessionFileList">
                        <el-icon><upload-filled /></el-icon>
                        <div class="el-upload__text">
                            Drop file here or <em>click to upload</em>
                        </div>
                        <template #tip>
                            <div class="el-upload__tip">
                                支持 JSON 文件，大小限制根据后端接口
                            </div>
                        </template>
                    </el-upload>
                </el-form-item>

                <el-form-item label="上传 excel 文件" v-if="conversationMode === 'upload' && selectedProcess.includes('firstConversation')">
                    <el-upload class="upload-demo" drag action="/api/upload/excel"
                        :on-success="handleExcelUploadSuccess" :file-list="excelFileList">
                        <el-icon><upload-filled /></el-icon>
                        <div class="el-upload__text">
                            Drop file here or <em>click to upload</em>
                        </div>
                        <template #tip>
                            <div class="el-upload__tip">
                                支持 EXCEL 文件，大小限制根据后端接口
                            </div>
                            <div class="el-upload__tip">请查看.exe 路径下 save 文件夹中的 excel 作为运行结果</div>
                        </template>
                    </el-upload>
                </el-form-item>

                <!-- 表单提交按钮 -->
                <el-form-item>
                    <el-button type="primary" @click="onSubmit">开启全自动</el-button>
                </el-form-item>
            </el-form>
        </el-col>
        <el-col :span="12">
            <el-table :data="cookiesStore.cookiesRowData" :row-class-name="cookiesStore.rowClassName"
                :style="{ width: '700px' }" height="400">
                <!-- 原有列 -->
                <el-table-column v-for="col in cookiesStore.cookies_info_colums" :key="col.key" :label="col.title"
                    :width="col.width">
                    <template #default="{ row }">
                        {{ row[col.dataKey] }}
                    </template>
                </el-table-column>

                <!-- 操作列 -->
                <el-table-column label="操作" width="100">
                    <template #default="{ row }">
                        <el-button type="primary" size="small" @click="cookiesStore.toggleSelect(row)">
                            {{ row.selected ? '取消' : '选择' }}
                        </el-button>
                    </template>
                </el-table-column>
            </el-table>
        </el-col>
    </el-row>
</template>

<script lang="ts" setup>
import { ref, reactive, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useCookiesStore } from '../stores/cookiesStore'
import axios from 'axios'

const saveResumeTime = ref('')

const cookiesStore = useCookiesStore()
const excelFileList = ref([])
onMounted(() => {
    cookiesStore.loadCookiesInfo()
})

const startDate = ref('')
const endDate = ref('')

const disabledDate = (time: Date) => {
    return time.getTime() > Date.now()
}

// 默认发起 50个
const sessionLimitCount = ref<number>(50)

// 上传文件列表（显示在上传组件）
const replyMode = ref<'all' | 'single'>('all')  // 回复模式

// 表单数据，只存文件名
const form = reactive({
    sessionFileName: '',
    excel_name: "" as string
})

// 上传文件列表（显示在上传组件）
const sessionFileList = ref([])
const strategyMode = ref<'cloud' | 'upload' | 'all'>('cloud')  // 策略模式

const selectedProcess = ref<string[]>([])

const getSubmitSelectedProcess = () => {
    return selectedProcess.value.map((process) => {
        if (process === 'firstConversation' && conversationMode.value === 'upload') {
            return 'first_conversation_with_excel'
        }
        return process
    })
}

// 上传成功回调
const handleSessionUploadSuccess = (_response: any, file: any) => {
    form.sessionFileName = file.name
    ElMessage.success(`Session 文件上传成功: ${file.name}`)
}
const handleExcelUploadSuccess = (_response: any, file: any) => {
    form.excel_name = file.name
    ElMessage.success(`Excel 文件上传成功: ${file.name}`)
}


// 通用选项接口
interface SelectOption {
    value: string
    label: string
}

// 搜索框禁用状态控制
const isHunterAccountDisabled = ref(false)
const isPositionDisabled = ref(true)  // 初始禁用
const isStrategyDisabled = ref(true)  // 初始禁用
const conversationMode = ref<'single' | 'upload'>('single')
// 猎头账号选择相关变量和函数
const hunterAccountOptions = ref<SelectOption[]>([])
const hunterAccountValue = ref<string>('')
const hunterAccountLoading = ref(false)
const isHunterAccountLoaded = ref(false)
const selectedHunterId = ref<string>('')
let hunterAccountRequestId = 0  // 请求序列号，防止并发覆盖
let hunterAccountDebounceTimer: any = null  // 防抖定时器

const searchHunterAccounts = async (query: string) => {
    // 清除之前的防抖定时器
    if (hunterAccountDebounceTimer) {
        clearTimeout(hunterAccountDebounceTimer)
    }

    // 生成新的请求ID
    const currentRequestId = ++hunterAccountRequestId

    // 使用防抖：300ms 后才执行搜索
    hunterAccountDebounceTimer = setTimeout(async () => {
        await executeHunterAccountSearch(query, currentRequestId)
    }, 300)
}

const executeHunterAccountSearch = async (query: string, requestId: number) => {
    hunterAccountLoading.value = true
    try {
        const response = await axios.get(
            '/api/search_condition/searchAccounts',
            {
                params: { keyword: query }  // 空字符串会搜索所有
            }
        )

        // 只有当前请求是最新的才更新数据（防止旧请求覆盖新请求）
        if (requestId === hunterAccountRequestId) {
            hunterAccountOptions.value = response.data.map((item: any) => ({
                value: item.user_id.toString(),
                label: `${item.Name}-${item.user_id}`
            }))
        }
    } catch (e) {
        if (requestId === hunterAccountRequestId) {
            console.error('搜索猎头账号失败:', e)
            ElMessage.error('搜索失败, 请重试')
            hunterAccountOptions.value = []
        }
    } finally {
        if (requestId === hunterAccountRequestId) {
            hunterAccountLoading.value = false
        }
    }
}

// 猎头账号聚焦时加载所有数据
const handleHunterAccountFocus = () => {
    if (!isHunterAccountLoaded.value && hunterAccountOptions.value.length === 0) {
        isHunterAccountLoaded.value = true
        searchHunterAccounts('')  // 传空字符串加载所有数据
    }
}

// 监听猎头账号选择变化
watch(hunterAccountValue, (newValue) => {
    if (newValue) {
        isHunterAccountDisabled.value = true
        isPositionDisabled.value = false
    }
    selectedHunterId.value = newValue || ''
})

// 岗位选择相关变量和函数
const positionOptions = ref<SelectOption[]>([])
const positionValue = ref<string>('')
const positionLoading = ref(false)
const isPositionLoaded = ref(false)
const RawPositionList = ref<any[]>([])
const selectedPositionId = ref<string>('')
const selectedPositionName = ref<string>('')
let positionRequestId = 0  // 请求序列号
let positionDebounceTimer: any = null  // 防抖定时器

const searchPositions = async (query: string) => {
    // 清除之前的防抖定时器
    if (positionDebounceTimer) {
        clearTimeout(positionDebounceTimer)
    }

    // 生成新的请求ID
    const currentRequestId = ++positionRequestId

    // 使用防抖：300ms 后才执行搜索
    positionDebounceTimer = setTimeout(async () => {
        await executePositionSearch(query, currentRequestId)
    }, 300)
}

const executePositionSearch = async (query: string, requestId: number) => {
    positionLoading.value = true
    try {
        const hunterId = hunterAccountValue.value

        const response = await axios.get(
            '/api/search_condition/searchPositions',
            {
                params: {
                    keyword: query,  // 空字符串会搜索所有
                    hunterId: hunterId
                }
            }
        )

        // 只有当前请求是最新的才更新数据
        if (requestId === positionRequestId) {
            RawPositionList.value = response.data

            positionOptions.value = response.data.map((item: any) => ({
                value: item.position_id?.toString() || '',
                label: `${item.position_name}-${item.company_name}`
            }))
        }
    } catch (e) {
        if (requestId === positionRequestId) {
            console.error('搜索岗位失败:', e)
            ElMessage.error('搜索失败, 请重试')
            positionOptions.value = []
            RawPositionList.value = []
        }
    } finally {
        if (requestId === positionRequestId) {
            positionLoading.value = false
        }
    }
}

// 岗位聚焦时加载所有数据
const handlePositionFocus = () => {
    if (!isPositionLoaded.value && positionOptions.value.length === 0) {
        isPositionLoaded.value = true
        searchPositions('')  // 传空字符串加载所有数据
    }
}

// 监听岗位选择变化
watch(positionValue, (newValue) => {
    if (newValue) {
        isPositionDisabled.value = true
        isStrategyDisabled.value = false
    }
    selectedPositionId.value = newValue || ''

    const selected = RawPositionList.value.find((item: any) => item.position_id?.toString() === newValue)
    selectedPositionName.value = selected ? (selected.position_name || '') : ''
})

// 策略选择相关变量和函数
const strategyOptions = ref<SelectOption[]>([])
const strategyValue = ref<string[]>([])
const strategyLoading = ref(false)
const RawStrategyList = ref<any[]>([])
const isStrategyLoaded = ref(false)
let strategyRequestId = 0  // 请求序列号
let strategyDebounceTimer: any = null  // 防抖定时器

const searchStrategies = async (query: string) => {
    // 清除之前的防抖定时器
    if (strategyDebounceTimer) {
        clearTimeout(strategyDebounceTimer)
    }

    // 生成新的请求ID
    const currentRequestId = ++strategyRequestId

    // 使用防抖：300ms 后才执行搜索
    strategyDebounceTimer = setTimeout(async () => {
        await executeStrategySearch(query, currentRequestId)
    }, 300)
}

const executeStrategySearch = async (query: string, requestId: number) => {
    strategyLoading.value = true
    try {
        const positionId = positionValue.value

        const response = await axios.get(
            '/api/search_condition/searchStrategies',
            {
                params: {
                    keyword: query,  // 空字符串会搜索所有
                    positionId: positionId
                }
            }
        )

        // 只有当前请求是最新的才更新数据
        if (requestId === strategyRequestId) {
            RawStrategyList.value = response.data

            strategyOptions.value = response.data.map((item: any) => ({
                value: item.id.toString(),
                label: `${item.name}`
            }))
        }
    } catch (e) {
        if (requestId === strategyRequestId) {
            console.error('搜索策略失败:', e)
            ElMessage.error('搜索失败, 请重试')
            strategyOptions.value = []
            RawStrategyList.value = []
        }
    } finally {
        if (requestId === strategyRequestId) {
            strategyLoading.value = false
        }
    }
}

// 策略聚焦时加载所有数据
const handleStrategyFocus = () => {
    if (!isStrategyLoaded.value && strategyOptions.value.length === 0) {
        isStrategyLoaded.value = true
        searchStrategies('')  // 传空字符串加载所有数据
    }
}
// 获取选中策略的完整数据
const getSelectedStrategies = () => {
    if (!strategyValue.value || strategyValue.value.length === 0) return [];
    return RawStrategyList.value.filter(item =>
        strategyValue.value.includes(item.id.toString())
    );
}
const onSubmit = async () => {
    if (!selectedProcess.value || selectedProcess.value.length === 0) {
        ElMessage.error('请至少勾选一项流程')
        return
    }

    if (!cookiesStore.selectedCookies || cookiesStore.selectedCookies.length === 0) {
        ElMessage.error('选择 cookies')
        return
    }

    try {
        let payload: any = {
            selected_process: getSubmitSelectedProcess(),
            reply_mode: replyMode.value,
            hunter_id: hunterAccountValue.value,
            position_id: positionValue.value,
            position_name: selectedPositionName.value,
            limit_count: sessionLimitCount.value,
            start_time: startDate.value,
            end_time: endDate.value,
            save_resume_time: saveResumeTime.value,

            inject_session: {
                cookies_file_name_list: cookiesStore.selectedCookies,
                strategyMode: strategyMode.value,
            }
        }
        if (strategyMode.value === 'cloud') {
            const selectedStrategy = getSelectedStrategies()
            payload.inject_session.strategy_list = selectedStrategy
        } else if (strategyMode.value === 'upload') {
            payload.inject_session.sessionFileName = form.sessionFileName
        }
        if (conversationMode.value === 'upload'){
            payload.excel_name = form.excel_name
            payload.cookies_file_name_list = cookiesStore.selectedCookies
        }

        console.log('完整提交数据：', payload)

        const res = await axios.post(
            '/api/all_auto/',
            payload
        )
        ElMessage.success('自动化成功')
        console.log('后端响应：', res.data)
        document.title = '自动化成功'
    } catch (err) {
        console.error(err)
        const detail = axios.isAxiosError(err) ? err.response?.data?.detail : ''
        ElMessage.error(detail || '启动失败，请检查网络或接口')
        document.title = '自动化失败'
    }

}


</script>
