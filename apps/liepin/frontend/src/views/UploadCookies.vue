<template>
    <el-row :gutter="20">
        <el-col :span="10">
            <el-form label-width="auto" style="max-width: 600px">
                <el-form-item label="上传 cookies 文件">
                    <el-upload class="upload-demo" drag action="http://localhost:11100/api/search_condition/cookiesFile"
                        :on-success="cookiesStore.handleCookiesUploadSuccess" :file-list="cookiesStore.cookiesFileList" multiple>
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
                <el-table-column label="操作" width="190">
                    <template #default="{ row }">
                        <el-button :type="row.selected ? 'success' : 'primary'" size="small"
                            @click="cookiesStore.toggleSelect(row)">
                            {{ row.selected ? '取消' : '选择' }}
                        </el-button>
                        <el-button type="danger" size="small" @click="confirmDelete(row.fileName)">
                            删除
                        </el-button>
                    </template>
                </el-table-column>
            </el-table>
        </el-col>

    </el-row>
</template>

<script lang="ts" setup>
import { onMounted } from 'vue'
import { ElMessageBox } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { useCookiesStore } from '../stores/cookiesStore'
const cookiesStore = useCookiesStore()

onMounted(() => {
    cookiesStore.loadCookiesInfo()
})

const confirmDelete = async (fileName: string) => {
    try {
        await ElMessageBox.confirm(
            `确认删除 Cookies 文件“${fileName}”吗？删除后无法恢复。`,
            '删除确认',
            {
                confirmButtonText: '删除',
                cancelButtonText: '取消',
                type: 'warning',
            }
        )
        await cookiesStore.deleteCookie(fileName)
    } catch (error: any) {
        if (error !== 'cancel' && error !== 'close') {
            console.error('删除 Cookies 文件失败:', error)
        }
    }
}
</script>
