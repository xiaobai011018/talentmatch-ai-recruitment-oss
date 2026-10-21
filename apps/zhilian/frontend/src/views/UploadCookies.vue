<template>
    <el-row :gutter="20">
        <el-col :span="10">
            <el-form label-width="auto" style="max-width: 600px">
                <el-form-item label="上传 cookies 文件">
                    <el-upload class="upload-demo" drag action="/api/search_condition/cookiesFile"
                        :on-success="cookiesStore.handleCookiesUploadSuccess" :file-list="cookiesStore.cookiesFileList">
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
            </el-form>
        </el-col>

        <el-col :span="12">
            <div class="selection-summary">
                已选择 <strong>{{ cookiesStore.selectedCookies.length }}</strong> 个 Cookie
            </div>
            <el-table :data="cookiesStore.cookiesRowData" :row-class-name="cookiesStore.rowClassName" :style="{ width: '700px' }"
                height="400">
                <!-- 原有列 -->
                <el-table-column v-for="col in cookiesStore.cookies_info_colums" :key="col.key" :label="col.title"
                    :width="col.width">
                    <template #default="{ row }">
                        {{ row[col.dataKey] }}
                    </template>
                </el-table-column>

                <!-- 操作列 -->
                <el-table-column label="操作" width="180">
                    <template #default="{ row }">
                        <div class="action-buttons">
                            <el-button :type="row.selected ? 'success' : 'primary'" size="small"
                                @click="cookiesStore.toggleSelect(row)">
                                {{ row.selected ? '已选（取消）' : '选择' }}
                            </el-button>
                            <el-button type="danger" size="small" plain
                                :loading="cookiesStore.deletingFileName === row.fileName"
                                @click="cookiesStore.deleteCookie(row)">
                                删除
                            </el-button>
                        </div>
                    </template>
                </el-table-column>
            </el-table>
        </el-col>

    </el-row>
</template>

<script lang="ts" setup>
import { onMounted } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import { useCookiesStore } from '../stores/cookiesStore'
const cookiesStore = useCookiesStore()

onMounted(() => {
    cookiesStore.loadCookiesInfo()
})
</script>

<style scoped>
.selection-summary {
    margin-bottom: 10px;
    color: var(--el-text-color-regular);
}

.action-buttons {
    display: flex;
    align-items: center;
    gap: 8px;
}

.action-buttons .el-button + .el-button {
    margin-left: 0;
}

:deep(.el-table .row-selected > td.el-table__cell) {
    background-color: var(--el-color-primary-light-9) !important;
}

:deep(.el-table .row-selected > td.el-table__cell:first-child) {
    box-shadow: inset 4px 0 0 var(--el-color-primary);
}
</style>
