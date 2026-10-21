<template>
    <el-row :gutter="20">
        <el-col :span="10">
            <el-form :model="form" label-width="auto" style="max-width: 600px">

                <el-form-item label="回复方式">
                    <el-radio-group v-model="replyMode">
                        <el-radio value="all">全部岗位回复</el-radio>
                        <el-radio value="single">单独岗位回复</el-radio>
                    </el-radio-group>
                </el-form-item>

                <!-- 猎头账号选择（保持原逻辑） -->
                <el-form-item label="猎头账号" v-if="replyMode === 'single'">
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

                <el-form-item label="岗位选择" v-if="replyMode === 'single'">
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

                <!-- 表单提交按钮 -->
                <el-form-item>
                    <el-button type="primary" @click="onSubmit">开启二次会话</el-button>
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
import axios from 'axios'
import { useCookiesStore } from '../stores/cookiesStore'

const cookiesStore = useCookiesStore()

onMounted(() => {
    cookiesStore.loadCookiesInfo()
})


// 表单数据，只存文件名
const form = reactive({
    sessionFileName: ''
})

// 上传文件列表（显示在上传组件）
const replyMode = ref<'all' | 'single'>('all')  // 回复模式


// 通用选项接口
interface SelectOption {
    value: string
    label: string
}

// 搜索框禁用状态控制
const isHunterAccountDisabled = ref(false)
const isPositionDisabled = ref(true)  // 初始禁用

// 猎头账号选择相关变量和函数
const hunterAccountOptions = ref<SelectOption[]>([])
const hunterAccountValue = ref<string>('')
const hunterAccountLoading = ref(false)
const isHunterAccountLoaded = ref(false)
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
    }
    selectedPositionId.value = newValue || ''

    const selected = RawPositionList.value.find((item: any) => item.position_id?.toString() === newValue)
    selectedPositionName.value = selected ? (selected.position_name || '') : ''
})

// 表单提交
const onSubmit = async () => {
    if (replyMode.value === 'single') {
        if (!hunterAccountValue.value) {
            ElMessage.error('请选择猎头账号')
            return
        }
        if (!positionValue.value) {
            ElMessage.error('请选择岗位')
            return
        }
    }
    if (!cookiesStore.selectedCookies || cookiesStore.selectedCookies.length === 0) {
        ElMessage.error('选择 cookies')
        return
    }

    try {
        let payload: any = {
            position_id: selectedPositionId.value,
            cookies_file_name_list: cookiesStore.selectedCookies,
            reply_mode: replyMode.value
        };

        console.log('完整提交数据：', payload)

        const res = await axios.post(
            '/api/conversation/start_second_conversation',
            payload
        )
        ElMessage.success('二次会话成功')
        console.log('后端响应：', res.data)
        document.title = '二次会话成功'
    } catch (err) {
        console.error(err)
        ElMessage.error('二次会话发起错误')
        document.title = '二次会话发起错误'
    }
}
</script>
