<template>
  <section class="page" data-module="opinion">
    <header class="page-head">
      <div>
        <h2>客户反馈受理</h2>
        <p class="page-desc">围绕反馈编号、委托单位、反馈类型做筛选，完成反馈的受理、处理结论登记与关闭。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="exportRows">导出客户反馈清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>反馈编号</span>
        <input v-model="filters.keyword" placeholder="按反馈编号检索" />
      </label>
      <label class="filter-item">
        <span>反馈状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <!-- 列表读取失败：明确是接口问题，并保留重试入口与当前过滤条件 -->
    <div v-if="loadState === 'error'" class="state-banner error-state-block">
      <div>
        <strong>反馈记录加载失败</strong>
        <p>{{ loadError }}</p>
        <p class="filter-keep">当前过滤条件仍保留：{{ filterSummary || '全部状态、不限反馈编号' }}</p>
      </div>
      <button class="btn primary" type="button" :disabled="loading" @click="reload">
        {{ loading ? '加载中…' : '重新加载' }}
      </button>
    </div>

    <template v-else>
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in columns" :key="column">{{ column }}</th>
            <th>可执行动作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="String(row.id)">
            <td v-for="column in columns" :key="column">{{ displayValue(row, column) }}</td>
            <td class="row-actions">
              <button class="link" type="button" @click="openDetail(row)">查看详情</button>
              <button v-if="canAccept(row)" class="link" type="button" @click="runRowAction('受理反馈', row)">
                受理反馈
              </button>
              <button v-if="canProcess(row)" class="link" type="button" @click="openProcess(row)">
                处理完成
              </button>
              <button v-if="canClose(row)" class="link" type="button" @click="runRowAction('关闭反馈', row)">
                关闭反馈
              </button>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- 空态：明确是“没有数据”而不是接口失败，并保留当前过滤条件 -->
      <div v-if="!loading && !rows.length" class="state-banner empty-state-block">
        <strong>暂无待受理记录</strong>
        <p>当前过滤条件下没有匹配的客户反馈记录，并非加载失败。</p>
        <p class="filter-keep">过滤条件：{{ filterSummary }}</p>
        <div class="state-actions">
          <button class="btn" type="button" @click="resetFilters">清空条件查看全部</button>
          <button class="btn ghost" type="button" @click="reload">重新查询</button>
        </div>
      </div>

      <div v-if="loading && !rows.length" class="state-banner empty-state-block">
        <span>反馈记录加载中…</span>
      </div>
    </template>

    <footer class="page-foot">
      <span>共 {{ total }} 条客户反馈记录</span>
      <span v-if="successMessage" class="success-text">{{ successMessage }}</span>
      <!-- 行内动作失败：给出原因与重试入口，不卡死页面 -->
      <span v-if="actionError" class="error-text">
        {{ actionError.message }}
        <button class="link" type="button" @click="retryRowAction">重试</button>
      </span>
    </footer>

    <!-- 详情弹窗：反馈结论与列表、处理弹窗取同一份字段口径 -->
    <div v-if="detailVisible" class="modal-mask" @click.self="closeDetail">
      <div class="modal-card" role="dialog" aria-modal="true" aria-label="反馈详情">
        <header class="modal-head">
          <h3>反馈详情 · {{ detailRow?.['反馈编号'] }}</h3>
          <button class="link" type="button" @click="closeDetail">关闭</button>
        </header>
        <dl v-if="detailRow" class="detail-grid">
          <template v-for="column in detailFields" :key="column">
            <dt>{{ column }}</dt>
            <dd>{{ displayValue(detailRow, column) }}</dd>
          </template>
        </dl>
        <footer class="modal-foot">
          <button class="btn" type="button" @click="closeDetail">知道了</button>
          <button v-if="detailRow && canProcess(detailRow)" class="btn primary" type="button" @click="openProcessFromDetail">
            填写处理结果
          </button>
        </footer>
      </div>
    </div>

    <!-- 处理弹窗 -->
    <div v-if="processVisible" class="modal-mask" @click.self="onProcessMaskClick">
      <div class="modal-card" role="dialog" aria-modal="true" aria-label="处理反馈">
        <header class="modal-head">
          <h3>处理反馈 · {{ processRow?.['反馈编号'] }}</h3>
          <button class="link" type="button" :disabled="processSubmitting" @click="cancelProcess">关闭</button>
        </header>
        <div v-if="processRow" class="process-body">
          <p class="process-summary">
            {{ processRow['委托单位'] }} · {{ processRow['反馈类型'] }} · 当前状态：{{ processStatusText }}
          </p>
          <label class="filter-item">
            <span>处理人员</span>
            <input v-model="processForm['处理人员']" placeholder="请填写处理人员姓名" />
          </label>
          <label class="filter-item">
            <span>处理结果（反馈结论）</span>
            <textarea
              v-model="processForm['处理结果']"
              rows="4"
              placeholder="请填写处理结果，提交后将作为反馈结论在列表与详情中展示"
            ></textarea>
          </label>
          <!-- 处理结果为空：明确说明原因，而不是静默退回 -->
          <p v-if="processFormError" class="error-text">{{ processFormError }}</p>
          <!-- 提交失败：给出后端原因，保留已填内容，提供重试；按钮不会卡死 -->
          <div v-if="processSubmitError" class="state-banner error-state-block inline">
            <div>
              <strong>提交失败</strong>
              <p>{{ processSubmitError }}</p>
              <p class="filter-keep">已填写的处理人员与处理结果已保留，可直接重试。</p>
            </div>
            <button class="btn primary" type="button" :disabled="processSubmitting" @click="submitProcess">
              {{ processSubmitting ? '提交中…' : '重试提交' }}
            </button>
          </div>
        </div>
        <footer class="modal-foot">
          <button class="btn" type="button" :disabled="processSubmitting" @click="cancelProcess">取消</button>
          <button class="btn primary" type="button" :disabled="processSubmitting" @click="submitProcess">
            {{ processSubmitting ? '提交中…' : '提交处理结果' }}
          </button>
        </footer>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = {
  id: number
  status?: string
  pending?: boolean
  abnormal?: boolean
  [field: string]: string | number | boolean | null | undefined
}

const ENDPOINT = '/api/opinion'
const columns = ['反馈编号', '委托单位', '反馈类型', '反馈内容', '处理人员', '处理结果', '反馈日期', '反馈状态']
const detailFields = columns
const statuses = ['待受理', '处理中', '已处理', '已关闭']
const stats = [
  { label: '待受理反馈', value: 0 },
  { label: '处理中反馈', value: 0 },
  { label: '已关闭反馈', value: 0 },
]
const NOT_YET = '待处理'

const rows = ref<Row[]>([])
const total = ref(0)
const loading = ref(false)
const loadState = ref<'idle' | 'loading' | 'success' | 'error'>('idle')
const loadError = ref('')
const successMessage = ref('')
// 受理页默认看待受理队列；筛选条件在加载失败与空态时都保留。
const filters = reactive<{ keyword: string; status: string }>({ keyword: '', status: '待受理' })

const filterSummary = computed(() => {
  const parts: string[] = []
  if (filters.keyword.trim()) parts.push(`反馈编号包含「${filters.keyword.trim()}」`)
  parts.push(`状态为「${filters.status || '全部'}」`)
  return parts.join('，')
})

// 行内动作（受理/关闭）失败后的重试上下文
const actionError = ref<{ message: string; action: string; row: Row } | null>(null)

// 详情弹窗
const detailVisible = ref(false)
const detailRow = ref<Row | null>(null)

// 处理弹窗
const processVisible = ref(false)
const processRow = ref<Row | null>(null)
const processForm = reactive<{ '处理人员': string; '处理结果': string }>({ '处理人员': '', '处理结果': '' })
const processSubmitting = ref(false)
const processFormError = ref('')
const processSubmitError = ref('')

const processStatusText = computed(() => (processRow.value ? statusText(processRow.value) : ''))

function displayValue(row: Row, column: string): string {
  const value = row[column]
  if (column === '处理结果') {
    // 列表、详情、处理弹窗共用这一口径，保证三处反馈结论一致
    return str(value) || NOT_YET
  }
  if (column === '反馈状态') {
    return statusText(row)
  }
  return str(value) || '—'
}

function statusText(row: Row): string {
  return str(row['反馈状态']) || str(row.status) || '待受理'
}

function str(value: unknown): string {
  if (value === null || value === undefined) return ''
  return String(value).trim()
}

function canAccept(row: Row): boolean {
  return statusText(row) === '待受理'
}

function canProcess(row: Row): boolean {
  const status = statusText(row)
  return status === '待受理' || status === '处理中'
}

function canClose(row: Row): boolean {
  return statusText(row) === '处理中' || statusText(row) === '已处理'
}

function resetFilters() {
  filters.keyword = ''
  filters.status = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function parseActionError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown; message?: unknown }
    const message = str(payload.message) || str(payload.detail)
    if (message) return message
  } catch {
    // 响应体不是 JSON 时退回通用提示
  }
  return fallback
}

async function reload() {
  loadState.value = 'loading'
  loadError.value = ''
  loading.value = true
  const query = new URLSearchParams()
  if (filters.keyword.trim()) query.set('keyword', filters.keyword.trim())
  if (filters.status) query.set('status', filters.status)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error(await parseActionError(response, '反馈记录列表读取失败，请稍后重试'))
    }
    const payload = (await response.json()) as { items?: Row[]; total?: number }
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    loadState.value = 'success'
  } catch (error) {
    // 失败时不清空已有数据与过滤条件，让用户能分辨“无数据”和“接口失败”
    loadError.value = error instanceof Error ? error.message : '客户反馈列表读取失败'
    loadState.value = 'error'
  } finally {
    loading.value = false
  }
}

function upsertRow(updated: Row) {
  // 按反馈记录 id 合并：重试成功也不会重复显示同一条记录
  const index = rows.value.findIndex((item) => item.id === updated.id)
  if (index >= 0) {
    rows.value.splice(index, 1, { ...rows.value[index], ...updated })
  } else {
    rows.value.unshift(updated)
  }
  total.value = rows.value.length
}

function flashSuccess(message: string) {
  successMessage.value = message
  window.setTimeout(() => {
    if (successMessage.value === message) successMessage.value = ''
  }, 4000)
}

async function postAction(action: string, row: Row, extra: Record<string, string> = {}): Promise<boolean> {
  const response = await request(`${ENDPOINT}/${row.id}/actions`, {
    method: 'POST',
    body: JSON.stringify({ values: { action, ...extra } }),
  })
  const payload = (await response.json().catch(() => null)) as
    | { ok?: boolean; message?: string; detail?: string; entry?: Row }
    | null
  if (!response.ok || !payload || payload.ok === false) {
    throw new Error(payload?.message || payload?.detail || '客户反馈动作未生效，请稍后重试')
  }
  if (payload.entry) upsertRow(payload.entry)
  flashSuccess(payload.message || `反馈记录已${action}`)
  return true
}

async function runRowAction(action: string, row: Row) {
  actionError.value = null
  try {
    await postAction(action, row)
    await reload()
  } catch (error) {
    actionError.value = {
      message: error instanceof Error ? error.message : '客户反馈操作失败',
      action,
      row,
    }
  }
}

async function retryRowAction() {
  if (!actionError.value) return
  const { action, row } = actionError.value
  await runRowAction(action, row)
}

async function fetchDetail(row: Row): Promise<Row> {
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (response.ok) {
      const payload = (await response.json()) as Row
      return { ...row, ...payload }
    }
  } catch {
    // 明细接口失败时退回列表数据，不阻断查看
  }
  return row
}

async function openDetail(row: Row) {
  detailRow.value = row
  detailVisible.value = true
  detailRow.value = await fetchDetail(row)
}

function closeDetail() {
  detailVisible.value = false
  detailRow.value = null
}

async function openProcess(row: Row) {
  processRow.value = row
  processForm['处理人员'] = str(row['处理人员'])
  processForm['处理结果'] = str(row['处理结果'])
  processFormError.value = ''
  processSubmitError.value = ''
  processVisible.value = true
  processRow.value = await fetchDetail(row)
  processForm['处理人员'] = processForm['处理人员'] || str(processRow.value['处理人员'])
  processForm['处理结果'] = processForm['处理结果'] || str(processRow.value['处理结果'])
}

function openProcessFromDetail() {
  if (!detailRow.value) return
  const row = detailRow.value
  closeDetail()
  void openProcess(row)
}

function cancelProcess() {
  if (processSubmitting.value) return
  processVisible.value = false
  processRow.value = null
  processFormError.value = ''
  processSubmitError.value = ''
}

function onProcessMaskClick() {
  if (!processSubmitting.value) cancelProcess()
}

async function submitProcess() {
  if (!processRow.value) return
  processFormError.value = ''
  processSubmitError.value = ''
  if (!processForm['处理结果'].trim()) {
    processFormError.value = '处理结果不能为空，请填写本次反馈的处理结论后再提交。'
    return
  }
  if (!processForm['处理人员'].trim()) {
    processFormError.value = '处理人员不能为空，请填写负责处理本次反馈的人员姓名。'
    return
  }
  processSubmitting.value = true
  const row = processRow.value
  try {
    // 同一反馈编号重复提交由后端幂等兜底：已处理时只返回当前结论，不产生新记录
    await postAction('处理完成', row, {
      '处理人员': processForm['处理人员'].trim(),
      '处理结果': processForm['处理结果'].trim(),
    })
    processVisible.value = false
    processRow.value = null
    await reload()
  } catch (error) {
    // 失败后按钮恢复可点，保留表单内容，用户可直接重试
    processSubmitError.value = error instanceof Error ? error.message : '处理结果提交失败，请稍后重试'
  } finally {
    processSubmitting.value = false
  }
}

onMounted(reload)
</script>

<style scoped>
.state-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px 20px;
  margin-top: 10px;
}
.state-banner p { margin: 4px 0 0; font-size: 13px; color: var(--muted); }
.state-banner .filter-keep { font-size: 12px; }
.state-banner.inline { margin: 8px 0; }
.empty-state-block { flex-direction: column; align-items: flex-start; }
.state-actions { display: flex; gap: 8px; margin-top: 10px; }
.error-state-block { border-color: #f0a8a0; background: #fef3f2; }
.error-state-block p { color: #b42318; }
.success-text { color: #067647; }
.filter-item select,
.filter-item textarea,
.filter-item input {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 13px;
  min-width: 160px;
}
.filter-item textarea { width: 100%; min-width: 0; resize: vertical; }
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}
.modal-card {
  width: 640px;
  max-width: calc(100vw - 40px);
  max-height: calc(100vh - 60px);
  overflow: auto;
  background: #fff;
  border-radius: 10px;
  padding: 18px 20px;
}
.modal-head { display: flex; justify-content: space-between; align-items: center; }
.modal-head h3 { margin: 0; font-size: 16px; }
.modal-foot { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
.detail-grid {
  display: grid;
  grid-template-columns: 110px 1fr;
  gap: 6px 12px;
  margin: 14px 0 0;
  font-size: 13px;
}
.detail-grid dt { color: var(--muted); }
.detail-grid dd { margin: 0; }
.process-body { display: flex; flex-direction: column; gap: 10px; margin-top: 12px; }
.process-body .filter-item { display: flex; flex-direction: column; gap: 4px; }
.process-body .filter-item span { font-size: 12px; color: var(--muted); }
.process-body .filter-item input,
.process-body .filter-item textarea { width: 100%; min-width: 0; }
.process-summary { margin: 0; font-size: 13px; color: var(--muted); }
</style>
