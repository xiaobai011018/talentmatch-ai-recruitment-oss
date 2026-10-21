// src/stores/cookiesStore.ts
import { defineStore } from 'pinia'
import { ref,computed} from 'vue'
import { ElMessage } from 'element-plus'
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


  const loadCookiesInfo = async () => {
    try {

      const res = await axios.get('http://localhost:11100/api/search_condition/cookiesList')
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

  const deleteCookie = async (fileName: string) => {
    try {
      await axios.delete('http://localhost:11100/api/search_condition/cookiesFile', {
        params: { fileName }
      })

      const savedSelected: string[] = JSON.parse(localStorage.getItem(LOCAL_STORAGE_KEY) || '[]')
      localStorage.setItem(
        LOCAL_STORAGE_KEY,
        JSON.stringify(savedSelected.filter(item => item !== fileName))
      )

      await loadCookiesInfo()
      ElMessage.success(`Cookies 文件已删除: ${fileName}`)
    } catch (err) {
      ElMessage.error(`删除 Cookies 文件失败: ${fileName}`)
      throw err
    }
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
    toggleSelect,
    loadCookiesInfo,
    handleCookiesUploadSuccess,
    deleteCookie,
    rowClassName,
  }

})
