<template>
  <div class="batch-processing">
    <div class="page-head">
      <div>
        <h1 class="page-title">批量处理</h1>
        <p class="page-subtitle">批量上传常规分析 CSV，统一生成 Van Krevelen 图、PDF 和加权平均指标表。</p>
      </div>
      <div v-if="result?.success" class="head-actions">
        <el-button type="primary" @click="download(result.pdf_zip_url)">
          <el-icon><Document /></el-icon> 下载全部 PDF
        </el-button>
        <el-button @click="download(result.weighted_excel_url)">
          <el-icon><Download /></el-icon> 下载加权平均 Excel
        </el-button>
      </div>
    </div>

    <section class="section card-glass">
      <h2 class="section-title"><el-icon><Upload /></el-icon> 上传常规分析 CSV</h2>
      <el-upload
        v-model:file-list="fileList"
        class="batch-upload"
        drag
        multiple
        accept=".csv"
        :auto-upload="false"
        :disabled="processing"
      >
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖拽多个 CSV 到这里，或点击选择文件</div>
        <template #tip>
          <div class="upload-tip">
            支持常规分析导出的结果 CSV，也支持少量缺失派生列的常规 CSV；系统会自动补齐指标并按常规过滤规则处理。
          </div>
        </template>
      </el-upload>
      <div class="element-panel">
        <div>
          <h3>元素分类参与元素</h3>
          <p>基础类别始终包含 C/H/O；勾选的元素会参与 VK 图例分类。比如勾选 P 后，含磷分子会进入 CHOP、CHONP、CHOPS、CHONPS 等类别。</p>
        </div>
        <el-checkbox-group v-model="selectedElements" :disabled="processing">
          <el-checkbox-button v-for="elem in elementOptions" :key="elem" :label="elem" :value="elem" />
        </el-checkbox-group>
      </div>
      <div class="color-panel">
        <div class="color-head">
          <h3>元素类别颜色</h3>
          <p>网页预览和导出的 PDF 会使用同一套颜色。含 P 的 CHOP、CHONP、CHOPS、CHONPS 也可以单独设置。</p>
        </div>
        <div class="color-grid">
          <div v-for="cat in visibleColorCategories" :key="cat" class="color-item">
            <span class="swatch" :style="{ background: vkColors[cat] }"></span>
            <span class="color-label">{{ cat }}</span>
            <el-color-picker v-model="vkColors[cat]" size="small" :disabled="processing" />
          </div>
        </div>
      </div>
      <div v-if="fileList.length" class="label-panel">
        <div class="color-head">
          <h3>图标签</h3>
          <p>每个文件可单独设置一个显示在 VK 图左上角的标签。留空则图中不显示标签。</p>
        </div>
        <div class="label-list">
          <div v-for="file in fileList" :key="file.uid" class="label-row">
            <span class="file-name">{{ file.name }}</span>
            <el-input
              v-model="file.figureLabel"
              placeholder="例如 S1、O1、汛期-上游"
              clearable
              :disabled="processing"
            />
          </div>
        </div>
      </div>
      <div class="upload-actions">
        <el-button type="primary" size="large" :loading="processing" :disabled="!fileList.length" @click="runBatch">
          开始批量处理
        </el-button>
        <el-button :disabled="processing || !fileList.length" @click="fileList = []">清空列表</el-button>
      </div>
    </section>

    <section v-if="result" class="section card-glass">
      <div class="result-title-row">
        <h2 class="section-title">处理结果</h2>
        <div class="summary">
          <el-tag type="success" effect="dark">成功 {{ result.success }}</el-tag>
          <el-tag v-if="result.failed" type="danger" effect="dark">失败 {{ result.failed }}</el-tag>
          <el-tag type="info" effect="plain">总计 {{ result.total }}</el-tag>
        </div>
      </div>

      <div class="result-grid">
        <article v-for="item in result.items" :key="item.id || item.filename" class="result-card">
          <div class="item-head">
            <div>
              <h3>{{ item.filename }}</h3>
              <p v-if="item.status === 'success'">{{ item.rows }} 个分子 | 分配率 {{ formatRate(item.assignment_rate) }}%</p>
              <p v-else class="error-text">{{ item.error }}</p>
            </div>
            <el-tag :type="item.status === 'success' ? 'success' : 'danger'" effect="dark">
              {{ item.status === 'success' ? '成功' : '失败' }}
            </el-tag>
          </div>
          <div v-if="item.status === 'success'" class="vk-box">
            <img :src="item.preview_url" :alt="item.filename + ' VK 图'" />
          </div>
          <div v-if="item.status === 'success'" class="item-actions">
            <el-button size="small" type="primary" @click="download(item.pdf_url)">
              <el-icon><Document /></el-icon> PDF
            </el-button>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api/index'

const fileList = ref([])
const processing = ref(false)
const result = ref(null)
const elementOptions = ['N', 'S', 'P', 'Cl']
const selectedElements = ref(['N', 'S'])
const vkColors = reactive({
  CHO: '#ffa07a',
  CHON: '#4169e1',
  CHOS: '#dc143c',
  CHONS: '#48d1cc',
  CHOP: '#7c3aed',
  CHONP: '#2563eb',
  CHOPS: '#059669',
  CHONPS: '#6d28d9',
  CHOCl: '#ffa500',
  CHONCl: '#4682b4',
  CHOSCl: '#8b0000',
  CHONSCl: '#008080',
  Other: '#a9a9a9',
})
const baseColorCategories = ['CHO', 'CHON', 'CHOS', 'CHONS']
const pColorCategories = ['CHOP', 'CHONP', 'CHOPS', 'CHONPS']
const clColorCategories = ['CHOCl', 'CHONCl', 'CHOSCl', 'CHONSCl']
const visibleColorCategories = computed(() => {
  const cats = [...baseColorCategories]
  if (selectedElements.value.includes('P')) cats.push(...pColorCategories)
  if (selectedElements.value.includes('Cl')) cats.push(...clColorCategories)
  cats.push('Other')
  return cats
})

function download(url) {
  if (!url) return
  window.open(url, '_blank')
}

function colorString() {
  return Object.entries(vkColors).map(([cat, color]) => `${cat}:${color}`).join(',')
}

function formatRate(rate) {
  return Number(rate || 0).toFixed(2)
}

async function runBatch() {
  if (!fileList.value.length) {
    ElMessage.warning('请先选择 CSV 文件')
    return
  }
  const form = new FormData()
  for (const item of fileList.value) {
    if (item.raw) form.append('files', item.raw, item.name)
  }
  form.append('elements', selectedElements.value.join(','))
  form.append('custom_colors', colorString())
  form.append('labeljson', JSON.stringify(fileList.value.map(item => item.figureLabel || '')))
  processing.value = true
  result.value = null
  try {
    const data = await api.post('/batch/regular-analysis', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 900000,
    })
    result.value = data
    if (data.success) {
      ElMessage.success(`批量处理完成：成功 ${data.success} 个，失败 ${data.failed} 个`)
    } else {
      ElMessage.error('没有文件处理成功，请检查 CSV 格式')
    }
  } catch (e) {
    ElMessage.error('批量处理失败: ' + (e.message || '未知错误'))
  } finally {
    processing.value = false
  }
}
</script>

<style lang="scss" scoped>
.batch-processing { max-width: 1400px; }
.page-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 20px;
}
.page-title { font-size: 28px; font-weight: 700; margin-bottom: 4px; }
.page-subtitle { color: var(--text-secondary); margin: 0; font-size: 14px; }
.head-actions { display: flex; gap: 10px; flex-wrap: wrap; }
.section { margin-bottom: 22px; padding: 22px; }
.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  margin: 0 0 16px;
}
.batch-upload {
  :deep(.el-upload-dragger) {
    background: #111827;
    border: 1px dashed #2563eb;
    border-radius: 8px;
    padding: 34px 20px;
  }
  :deep(.el-upload__text) { color: #dbeafe; font-size: 15px; }
  :deep(.el-upload-list__item-name) { color: var(--text-primary); }
}
.upload-icon { font-size: 42px; color: #3b82f6; margin-bottom: 8px; }
.upload-tip { color: var(--text-secondary); font-size: 13px; margin-top: 8px; }
.element-panel {
  margin-top: 18px;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  padding: 14px 16px;
  border: 1px solid #24466f;
  background: #0f172a;
  border-radius: 8px;
  h3 { margin: 0 0 4px; font-size: 15px; color: var(--text-primary); }
  p { margin: 0; color: var(--text-secondary); font-size: 13px; line-height: 1.5; }
}
.color-panel {
  margin-top: 14px;
  padding: 14px 16px;
  border: 1px solid #24466f;
  background: #0f172a;
  border-radius: 8px;
}
.color-head {
  margin-bottom: 12px;
  h3 { margin: 0 0 4px; font-size: 15px; color: var(--text-primary); }
  p { margin: 0; color: var(--text-secondary); font-size: 13px; line-height: 1.5; }
}
.color-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 10px;
}
.color-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid #1e3a5f;
  border-radius: 8px;
  background: #111827;
}
.swatch {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.7);
  flex: 0 0 auto;
}
.color-label {
  flex: 1;
  color: var(--text-primary);
  font-size: 13px;
  font-family: 'Times New Roman', serif;
}
.label-panel {
  margin-top: 14px;
  padding: 14px 16px;
  border: 1px solid #24466f;
  background: #0f172a;
  border-radius: 8px;
}
.label-list { display: grid; gap: 10px; }
.label-row {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(260px, 2fr);
  gap: 12px;
  align-items: center;
}
.file-name {
  color: var(--text-primary);
  font-size: 13px;
  word-break: break-all;
}
.upload-actions { margin-top: 18px; display: flex; gap: 12px; }
.result-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.summary { display: flex; gap: 8px; flex-wrap: wrap; }
.result-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
  gap: 18px;
}
.result-card {
  border: 1px solid #24466f;
  background: #111827;
  border-radius: 8px;
  padding: 16px;
}
.item-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  h3 { margin: 0 0 4px; font-size: 15px; color: var(--text-primary); word-break: break-all; }
  p { margin: 0; color: var(--text-secondary); font-size: 13px; }
}
.error-text { color: #fca5a5 !important; }
.vk-box {
  background: white;
  border-radius: 6px;
  overflow: hidden;
  min-height: 280px;
  display: flex;
  align-items: center;
  justify-content: center;
  img { width: 100%; display: block; }
}
.item-actions { margin-top: 12px; display: flex; justify-content: flex-end; }
@media (max-width: 900px) {
  .page-head, .result-title-row { flex-direction: column; align-items: stretch; }
  .element-panel { flex-direction: column; align-items: flex-start; }
  .label-row { grid-template-columns: 1fr; }
  .result-grid { grid-template-columns: 1fr; }
}
</style>
