<template>
  <section class="page" data-module="opinion">
    <header class="page-head">
      <div>
        <h2>客户反馈受理</h2>
        <p class="page-desc">围绕反馈编号、委托单位、反馈类型、反馈内容对待受理记录做筛选、受理与处理结论登记。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记反馈记录</button>
        <button class="btn" type="button" @click="exportRows">导出客户反馈清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card stat-clickable" @click="applyStatus(item.status)">
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
        <span>委托单位</span>
        <input v-model="filters.client" placeholder="按委托单位检索" />
      </label>
      <label class="filter-item">
        <span>反馈类型</span>
        <input v-model="filters.category" placeholder="按反馈类型检索" />
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

    <div v-if="notice" class="notice-bar" :class="`notice-${notice.kind}`">
      <span>{{ notice.text }}</span>
      <button v-if="notice.retry" class="link" type="button" @click="notice.retry">{{ notice.retryLabel }}</button>
      <button class="link" type="button" @click="notice = null">关闭</button>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="loading">
          <td :colspan="columns.length + 1" class="empty-state">反馈记录加载中…</td>
        </tr>
        <tr v-else-if="loadError">
          <td :colspan="columns.length + 1" class="empty-state state-error">
            <p class="state-title">反馈记录加载失败</p>
            <p class="state-desc">原因：{{ loadError }}</p>
            <button class="btn primary" type="button" @click="reload">重新加载</button>
          </td>
        </tr>
        <tr v-else-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">
            <p class="state-title">{{ emptyText.title }}</p>
            <p class="state-desc">{{ emptyText.desc }}</p>
            <p v-if="activeFilterText" class="state-desc">当前过滤条件：{{ activeFilterText }}，条件已保留，可直接调整后重新查询。</p>
            <button v-if="hasActiveFilter" class="btn" type="button" @click="resetFilters">清空过滤条件</button>
          </td>
        </tr>
        <template v-else>
          <tr v-for="row in rows" :key="String(row.id)">
            <td v-for="column in columns" :key="column">
              <template v-if="column === '处理结果'">{{ conclusionOf(row) }}</template>
              <template v-else-if="column === '反馈状态'">
                <span class="status-tag">{{ statusOf(row) }}</span>
              </template>
              <template v-else>{{ row[column] ?? '—' }}</template>
            </td>
            <td class="row-actions">
              <button
                v-for="action in actionsFor(row)"
                :key="action.key"
                class="link"
                type="button"
                :disabled="pendingActionKey === actionKey(row, action.key)"
                @click="runAction(action.key, row)"
              >
                {{ pendingActionKey === actionKey(row, action.key) ? '提交中…' : action.label }}
              </button>
            </td>
          </tr>
        </template>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条客户反馈记录</span>
      <span v-if="loading" class="muted-text">正在同步最新数据…</span>
    </footer>

    <!-- 反馈详情：处理结果与受理列表、处理弹窗共用同一套结论口径 -->
    <div v-if="detail" class="modal-mask" @click.self="detail = null">
      <div class="modal" role="dialog" aria-modal="true" aria-label="反馈详情">
        <header class="modal-head">
          <h3>反馈详情</h3>
          <button class="link" type="button" @click="detail = null">关闭</button>
        </header>
        <div v-if="detail.loading" class="modal-body muted-text">反馈明细加载中…</div>
        <div v-else-if="detail.error" class="modal-body">
          <p class="error-text">反馈明细加载失败，原因：{{ detail.error }}</p>
          <button class="btn primary" type="button" @click="loadDetail(detail.id)">重试加载</button>
        </div>
        <dl v-else class="detail-grid">
          <template v-for="column in columns" :key="column">
            <dt>{{ column }}</dt>
            <dd v-if="column === '处理结果'">{{ conclusionOf(detail.row) }}</dd>
            <dd v-else-if="column === '反馈状态'">{{ statusOf(detail.row) }}</dd>
            <dd v-else>{{ detail.row[column] ?? '—' }}</dd>
          </template>
        </dl>
      </div>
    </div>

    <!-- 处理弹窗：填写处理人员与处理结果；失败说明原因并允许原地重试 -->
    <div v-if="handle" class="modal-mask" @click.self="closeHandle">
      <div class="modal" role="dialog" aria-modal="true" aria-label="填写处理结果">
        <header class="modal-head">
          <h3>填写处理结果</h3>
          <button class="link" type="button" :disabled="handle.submitting" @click="closeHandle">关闭</button>
        </header>
        <div class="modal-body">
          <dl class="detail-grid readonly">
            <dt>反馈编号</dt><dd>{{ handle.row['反馈编号'] }}</dd>
            <dt>委托单位</dt><dd>{{ handle.row['委托单位'] }}</dd>
            <dt>反馈类型</dt><dd>{{ handle.row['反馈类型'] }}</dd>
            <dt>反馈内容</dt><dd>{{ handle.row['反馈内容'] ?? '—' }}</dd>
            <dt>当前结论</dt><dd>{{ conclusionOf(handle.row) }}</dd>
          </dl>
          <form class="modal-form" @submit.prevent="submitHandle">
            <label class="form-item">
              <span>处理人员 <em>*</em></span>
              <input v-model="handle.handler" placeholder="请填写处理人员" :disabled="handle.submitting" />
            </label>
            <label class="form-item">
              <span>处理结果 <em>*</em></span>
              <textarea v-model="handle.result" rows="4" placeholder="请填写处理结果（必填，提交后作为反馈结论）" :disabled="handle.submitting"></textarea>
            </label>
            <p v-if="handle.formError" class="error-text">{{ handle.formError }}</p>
            <p v-if="handle.submitError" class="error-text">提交失败，原因：{{ handle.submitError }}</p>
            <div class="modal-actions">
              <button class="btn" type="button" :disabled="handle.submitting" @click="closeHandle">取消</button>
              <button class="btn primary" type="submit" :disabled="handle.submitting">
                {{ handle.submitting ? '提交中…' : (handle.submitError ? '重试提交' : '提交处理结果') }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- 登记弹窗：反馈编号重复提交只生效一次 -->
    <div v-if="create" class="modal-mask" @click.self="closeCreate">
      <div class="modal" role="dialog" aria-modal="true" aria-label="登记反馈记录">
        <header class="modal-head">
          <h3>登记反馈记录</h3>
          <button class="link" type="button" :disabled="create.submitting" @click="closeCreate">关闭</button>
        </header>
        <div class="modal-body">
          <form class="modal-form" @submit.prevent="submitCreate">
            <label class="form-item">
              <span>反馈编号 <em>*</em></span>
              <input v-model="create.form['反馈编号']" placeholder="如 OPIN-0009" :disabled="create.submitting" />
            </label>
            <label class="form-item">
              <span>委托单位 <em>*</em></span>
              <input v-model="create.form['委托单位']" placeholder="请填写委托单位" :disabled="create.submitting" />
            </label>
            <label class="form-item">
              <span>反馈类型 <em>*</em></span>
              <input v-model="create.form['反馈类型']" placeholder="如 投诉 / 咨询 / 改进建议" :disabled="create.submitting" />
            </label>
            <label class="form-item">
              <span>反馈内容</span>
              <textarea v-model="create.form['反馈内容']" rows="3" placeholder="可补充客户反馈的具体内容" :disabled="create.submitting"></textarea>
            </label>
            <p v-if="create.formError" class="error-text">{{ create.formError }}</p>
            <p v-if="create.submitError" class="error-text">提交失败，原因：{{ create.submitError }}</p>
            <div class="modal-actions">
              <button class="btn" type="button" :disabled="create.submitting" @click="closeCreate">取消</button>
              <button class="btn primary" type="submit" :disabled="create.submitting">
                {{ create.submitting ? '提交中…' : (create.submitError ? '重试提交' : '提交登记') }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/opinion'
const columns = ['反馈编号', '委托单位', '反馈类型', '反馈内容', '处理人员', '处理结果', '反馈日期', '反馈状态']
const statuses = ['待受理', '处理中', '已处理', '已关闭']
const emptyStats = [
  { label: '待受理反馈', value: 0, status: '待受理' },
  { label: '处理中反馈', value: 0, status: '处理中' },
  { label: '已关闭反馈', value: 0, status: '已关闭' },
]

const rows = ref<Row[]>([])
const total = ref(0)
const loading = ref(false)
const loadError = ref('')
const filters = reactive({ keyword: '', client: '', category: '', status: '待受理' })
const stats = ref(emptyStats.map((item) => ({ ...item })))

interface Notice {
  kind: 'success' | 'error' | 'info'
  text: string
  retry?: () => void
  retryLabel?: string
}
const notice = ref<Notice | null>(null)

/** 反馈结论的唯一口径：受理列表、详情、处理弹窗都从这里取值，避免三处结论不一致。 */
function conclusionOf(row: Row): string {
  const result = String(row['处理结果'] ?? '').trim()
  if (result) return result
  const status = statusOf(row)
  if (status === '待受理') return '待受理，暂无处理结论'
  if (status === '处理中') return '处理中，尚未填写处理结论'
  if (status === '已关闭') return '已关闭，未填写处理结论'
  return '未填写处理结论'
}

function statusOf(row: Row): string {
  return String(row['反馈状态'] ?? row.status ?? '').trim()
}

const hasActiveFilter = computed(() =>
  Boolean(filters.keyword.trim() || filters.client.trim() || filters.category.trim() || filters.status),
)

const activeFilterText = computed(() => {
  const parts: string[] = []
  if (filters.keyword.trim()) parts.push(`反馈编号含「${filters.keyword.trim()}」`)
  if (filters.client.trim()) parts.push(`委托单位含「${filters.client.trim()}」`)
  if (filters.category.trim()) parts.push(`反馈类型含「${filters.category.trim()}」`)
  if (filters.status) parts.push(`反馈状态为「${filters.status}」`)
  return parts.join('、')
})

const emptyText = computed(() => {
  // 受理页面默认看待受理：没有记录时要明确说“暂无待受理记录”，不能留白让人误以为接口失败。
  if (!hasActiveFilter.value || filters.status === '待受理') {
    return {
      title: '暂无待受理记录',
      desc: hasActiveFilter.value
        ? '当前过滤条件下没有待受理的客户反馈记录，过滤条件已保留。'
        : '当前没有需要受理的客户反馈记录。新反馈登记后会出现在这里。',
    }
  }
  const target = filters.status
  return {
    title: `暂无「${target}」状态的反馈记录`,
    desc: '当前过滤条件下没有匹配的客户反馈记录，过滤条件已保留，可调整后重新查询。',
  }
})

function resetFilters() {
  filters.keyword = ''
  filters.client = ''
  filters.category = ''
  filters.status = ''
  notice.value = null
  void reload()
}

function applyStatus(status: string) {
  filters.status = status
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function buildQuery(): string {
  const params: Record<string, string> = {}
  if (filters.keyword.trim()) params.keyword = filters.keyword.trim()
  if (filters.client.trim()) params.client = filters.client.trim()
  if (filters.category.trim()) params.category = filters.category.trim()
  if (filters.status) params.status = filters.status
  return new URLSearchParams(params).toString()
}

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string; message?: string }
    return payload.message || payload.detail || fallback
  } catch {
    return fallback
  }
}

async function reload() {
  loading.value = true
  loadError.value = ''
  try {
    const response = await request(`${ENDPOINT}?${buildQuery()}`)
    if (!response.ok) {
      throw new Error(await readError(response, `接口返回 ${response.status}`))
    }
    const payload = (await response.json()) as { items?: Row[]; total?: number }
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    rows.value = []
    loadError.value = error instanceof Error ? error.message : '反馈记录列表读取失败'
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    const results = await Promise.all(
      ['待受理', '处理中', '已关闭'].map(async (status) => {
        const response = await request(`${ENDPOINT}?status=${encodeURIComponent(status)}&size=1`)
        if (!response.ok) return 0
        const payload = (await response.json()) as { total?: number }
        return payload.total ?? 0
      }),
    )
    stats.value = [
      { label: '待受理反馈', value: results[0], status: '待受理' },
      { label: '处理中反馈', value: results[1], status: '处理中' },
      { label: '已关闭反馈', value: results[2], status: '已关闭' },
    ]
  } catch {
    // 统计只是辅助信息，加载失败不打断受理操作
  }
}

interface RowAction {
  key: string
  label: string
}

function actionsFor(row: Row): RowAction[] {
  const status = statusOf(row)
  if (status === '待受理') {
    return [
      { key: '受理反馈', label: '受理反馈' },
      { key: '关闭反馈', label: '关闭反馈' },
      { key: 'detail', label: '查看详情' },
    ]
  }
  if (status === '处理中') {
    return [
      { key: 'handle', label: '填写处理结果' },
      { key: '关闭反馈', label: '关闭反馈' },
      { key: 'detail', label: '查看详情' },
    ]
  }
  return [{ key: 'detail', label: '查看详情' }]
}

function actionKey(row: Row, key: string): string {
  return `${row.id}:${key}`
}

const pendingActionKey = ref('')

async function runAction(key: string, row: Row) {
  if (key === 'detail') {
    void loadDetail(Number(row.id))
    return
  }
  if (key === 'handle') {
    openHandle(row)
    return
  }
  notice.value = null
  const keyOf = actionKey(row, key)
  pendingActionKey.value = keyOf
  try {
    const result = await postAction(Number(row.id), { action: key })
    if (!result.ok) throw new Error(result.message)
    notice.value = { kind: 'success', text: result.message }
    await Promise.all([reload(), loadStats()])
  } catch (error) {
    const reason = error instanceof Error ? error.message : '客户反馈操作失败'
    // 失败后按钮恢复可点，并保留同一条记录上的重试入口
    notice.value = {
      kind: 'error',
      text: `${row['反馈编号']} ${key}失败：${reason}`,
      retryLabel: '重试',
      retry: () => runAction(key, row),
    }
  } finally {
    if (pendingActionKey.value === keyOf) pendingActionKey.value = ''
  }
}

interface ActionResponse {
  ok: boolean
  message: string
  entry: Row | null
}

async function postAction(entryId: number, values: Record<string, string>): Promise<ActionResponse> {
  const response = await request(`${ENDPOINT}/${entryId}/actions`, {
    method: 'POST',
    body: JSON.stringify({ values }),
  })
  if (!response.ok) {
    throw new Error(await readError(response, `接口返回 ${response.status}`))
  }
  return (await response.json()) as ActionResponse
}

/* ---------------- 详情弹窗 ---------------- */

interface DetailState {
  id: number
  row: Row
  loading: boolean
  error: string
}
const detail = ref<DetailState | null>(null)

async function loadDetail(entryId: number) {
  const state: DetailState = detail.value ?? { id: entryId, row: {}, loading: true, error: '' }
  state.id = entryId
  state.loading = true
  state.error = ''
  detail.value = state
  try {
    const response = await request(`${ENDPOINT}/${entryId}`)
    if (!response.ok) {
      throw new Error(await readError(response, `接口返回 ${response.status}`))
    }
    state.row = (await response.json()) as Row
  } catch (error) {
    state.error = error instanceof Error ? error.message : '反馈明细读取失败'
  } finally {
    state.loading = false
  }
}

/* ---------------- 处理弹窗 ---------------- */

interface HandleState {
  row: Row
  handler: string
  result: string
  submitting: boolean
  formError: string
  submitError: string
}
const handle = ref<HandleState | null>(null)

function openHandle(row: Row) {
  notice.value = null
  handle.value = {
    row,
    handler: String(row['处理人员'] ?? ''),
    result: String(row['处理结果'] ?? ''),
    submitting: false,
    formError: '',
    submitError: '',
  }
}

function closeHandle() {
  if (handle.value?.submitting) return
  handle.value = null
}

async function submitHandle() {
  if (!handle.value) return
  const state = handle.value
  const missing: string[] = []
  if (!state.handler.trim()) missing.push('处理人员')
  if (!state.result.trim()) missing.push('处理结果')
  if (missing.length) {
    // 必填项缺失要说明原因，不能静默退回
    state.formError = `${missing.join('、')}不能为空，请补充后重新提交`
    return
  }
  state.formError = ''
  state.submitting = true
  state.submitError = ''
  try {
    const result = await postAction(Number(state.row.id), {
      action: '处理完成',
      处理人员: state.handler.trim(),
      处理结果: state.result.trim(),
    })
    if (!result.ok) throw new Error(result.message)
    handle.value = null
    notice.value = { kind: 'success', text: result.message }
    // 成功后以服务端返回为准刷新列表：按 id 覆盖，绝不会重复追加同一条反馈编号
    await Promise.all([reload(), loadStats()])
  } catch (error) {
    // 失败保留已填写内容与错误原因，按钮变为“重试提交”，可直接原地重试
    state.submitError = error instanceof Error ? error.message : '处理结果提交失败'
  } finally {
    state.submitting = false
  }
}

/* ---------------- 登记弹窗 ---------------- */

type CreateForm = Record<'反馈编号' | '委托单位' | '反馈类型' | '反馈内容', string>

interface CreateState {
  form: CreateForm
  submitting: boolean
  formError: string
  submitError: string
}
const create = ref<CreateState | null>(null)

function openCreate() {
  notice.value = null
  create.value = {
    form: { 反馈编号: '', 委托单位: '', 反馈类型: '', 反馈内容: '' },
    submitting: false,
    formError: '',
    submitError: '',
  }
}

function closeCreate() {
  if (create.value?.submitting) return
  create.value = null
}

async function submitCreate() {
  if (!create.value) return
  const state = create.value
  const missing = ['反馈编号', '委托单位', '反馈类型'].filter(
    (field) => !state.form[field as keyof CreateForm].trim(),
  )
  if (missing.length) {
    state.formError = `缺少必填字段：${missing.join('、')}，请补充后重新提交`
    return
  }
  state.formError = ''
  state.submitting = true
  state.submitError = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: state.form }),
    })
    if (!response.ok) {
      throw new Error(await readError(response, `接口返回 ${response.status}`))
    }
    const result = (await response.json()) as ActionResponse
    if (!result.ok) throw new Error(result.message)
    create.value = null
    notice.value = { kind: 'info', text: result.message }
    filters.keyword = ''
    filters.client = ''
    filters.category = ''
    filters.status = '待受理'
    await Promise.all([reload(), loadStats()])
  } catch (error) {
    state.submitError = error instanceof Error ? error.message : '反馈记录登记失败'
  } finally {
    state.submitting = false
  }
}

onMounted(() => {
  void reload()
  void loadStats()
})
</script>
