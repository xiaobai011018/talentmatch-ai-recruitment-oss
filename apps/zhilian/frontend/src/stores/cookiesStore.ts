// src/stores/cookiesStore.ts
import { defineStore } from 'pinia'
import { ref,computed} from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'


interface CookieItem {
  fileName: string
  importTime: string
}

const LOCAL_STORAGE_KEY = 'selectedCookies'

export const useCookiesStore = defineStore('cookies', () => {
  const cookiesFileName = ref<string[]>([])
  const cookiesFileList = ref<any[]>([])
  const cookiesRowData = ref<any[]>([])
  const deletingFileName = ref('')


  const loadCookiesInfo = async () => {
    try {

      const res = await axios.get('/api/search_condition/cookiesList')
      const savedSelected: string[] = JSON.parse(localStorage.getItem(LOCAL_STORAGE_KEY) || '[]')
      cookiesRowData.value = res.data.map((item: any, index: number) => ({
        id: index + 1,
        fileName: item.fileName,
        importTime: item.importTime,
        selected: savedSelected.includes(item.fileName)
      }))

      // 每个 fileName 加入 cookiesFileName 队列
      cookiesFileName.value = [] // 先清空旧队列
      res.data.forEach((item: CookieItem)=> {
        cookiesFileName.value.push(item.fileName)
      })

      } catch (err) {
        ElMessage.error('加载 cookies 列表失败')
      }
    }

  const handleCookiesUploadSuccess = async (_response: any, file: any) => {
      cookiesFileName.value = [file.name]
      cookiesFileList.value = [file]

      // 先刷新表格
      await loadCookiesInfo()

      ElMessage.success(`Cookies 文件上传成功: ${file.name}`)
    }

  const cookies_info_colums = [
    {
      key: 'id',
      dataKey: 'id',
      title: 'ID',
      width: 100
    },
    {
      key: 'fileName',
      dataKey: 'fileName',
      title: 'Cookies 文件名',
      width: 220
    },
    {
      key: 'importTime',
      dataKey: 'importTime',
      title: '导入时间',
      width: 200
    }
  ]

  const saveSelected = () => {
    const selected = cookiesRowData.value
      .filter(r => r.selected)
      .map(r => r.fileName)
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(selected))
  }

  const toggleSelect = (row: any) => {
    row.selected = !row.selected
    saveSelected()
  }

  const deleteCookie = async (row: any) => {
    try {
      await ElMessageBox.confirm(
        `确认删除 Cookie 文件“${row.fileName}”吗？删除后无法恢复，请确认该 Cookie 未被正在运行的任务使用。`,
        '确认删除',
        {
          confirmButtonText: '确认删除',
          cancelButtonText: '取消',
          confirmButtonClass: 'el-button--danger',
          type: 'warning',
        }
      )
    } catch {
      return
    }

    deletingFileName.value = row.fileName
    try {
      await axios.delete('/api/search_condition/cookiesFile', {
        params: { fileName: row.fileName }
      })

      cookiesRowData.value = cookiesRowData.value.filter(item => item.fileName !== row.fileName)
      cookiesRowData.value.forEach((item, index) => {
        item.id = index + 1
      })
      cookiesFileName.value = cookiesFileName.value.filter(fileName => fileName !== row.fileName)
      cookiesFileList.value = cookiesFileList.value.filter(file => file.name !== row.fileName)
      saveSelected()
      ElMessage.success(`Cookie 文件已删除: ${row.fileName}`)
    } catch (err) {
      const detail = axios.isAxiosError(err) ? err.response?.data?.detail : ''
      ElMessage.error(detail || '删除 Cookie 文件失败')
    } finally {
      deletingFileName.value = ''
    }
  }

  const selectedCookies = computed(() => {
  return cookiesRowData.value
    .filter(r => r.selected)
    .map(r => r.fileName)
  })

  const rowClassName = (row: any) => {
    return row.selected ? 'row-selected' : ''
  }


  return {
    cookiesFileName,
    cookiesFileList,
    cookiesRowData,
    cookies_info_colums,
    selectedCookies,
    deletingFileName,
    toggleSelect,
    deleteCookie,
    loadCookiesInfo,
    handleCookiesUploadSuccess,
    rowClassName,
  }

})
