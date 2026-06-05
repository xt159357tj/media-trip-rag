<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '../stores/chat'
import { listDocuments, deleteDocument } from '../api'
import DocUpload from './DocUpload.vue'

const store = useChatStore()
const router = useRouter()
const collapsed = ref(false)
const kbDocs = ref([])

async function fetchKbDocs() {
  try {
    const { data } = await listDocuments()
    if (data.code === 0) {
      kbDocs.value = data.data.documents || []
    }
  } catch { /* ignore */ }
}

async function removeKbDoc(sourceName) {
  try {
    await deleteDocument(sourceName)
    kbDocs.value = kbDocs.value.filter(d => d.source !== sourceName)
  } catch { /* ignore */ }
}

function logout() {
  store.clearUser()
  router.push('/login')
}

onMounted(fetchKbDocs)
</script>

<template>
  <aside class="sidebar" :class="{ collapsed }">
    <div class="sidebar-top">
      <!-- Toggle -->
      <button class="toggle-btn" @click="collapsed = !collapsed" :title="collapsed ? '展开' : '收起'">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
          <path v-if="!collapsed" d="M15 18l-6-6 6-6"/>
          <path v-else d="M9 18l6-6-6-6"/>
        </svg>
      </button>

      <template v-if="!collapsed">
        <!-- New chat -->
        <button class="new-chat-btn" @click="store.newChat()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
            <path d="M12 5v14M5 12h14"/>
          </svg>
          新建对话
        </button>

        <!-- Sessions -->
        <div class="section">
          <p class="section-label">会话</p>
          <div class="session-list" v-if="store.sessions.length > 0">
            <div
              v-for="s in store.sessions" :key="s.session_id"
              class="session-item"
              :class="{ active: s.session_id === store.currentSessionId }"
              @click="store.loadSession(s.session_id)"
            >
              <span class="session-text">{{ s.preview || s.session_id }}</span>
              <button class="item-del" @click.stop="store.removeSession(s.session_id)" title="删除">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M18 6L6 18M6 6l12 12"/></svg>
              </button>
            </div>
          </div>
          <p class="empty" v-else>暂无会话</p>
        </div>

        <!-- Divider -->
        <div class="section-divider"></div>

        <!-- Knowledge base -->
        <div class="section">
          <p class="section-label">知识库</p>
          <DocUpload @uploaded="fetchKbDocs" />
          <div class="kb-list" v-if="kbDocs.length > 0">
            <div class="kb-item" v-for="doc in kbDocs" :key="doc.source">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6"/></svg>
              <span class="kb-name" :title="doc.source">{{ doc.source }}</span>
              <button class="item-del" @click="removeKbDoc(doc.source)" title="删除">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M18 6L6 18M6 6l12 12"/></svg>
              </button>
            </div>
          </div>
          <p class="empty" v-else>暂无文档</p>
        </div>
      </template>
    </div>

    <!-- User -->
    <div class="user-bar" v-if="!collapsed">
      <div class="avatar">{{ (store.uname || 'U')[0].toUpperCase() }}</div>
      <span class="uname">{{ store.uname }}</span>
      <button class="logout-btn" @click="logout" title="退出">退出</button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 260px; min-width: 260px;
  background: var(--bg-surface);
  border-right: 1px solid var(--border);
  display: flex; flex-direction: column;
  transition: width .2s ease, min-width .2s ease;
}
.sidebar.collapsed {
  width: 44px; min-width: 44px;
}
.sidebar-top {
  flex: 1; overflow-y: auto; padding: 16px 12px;
}
.toggle-btn {
  display: flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; background: var(--bg-elevated);
  border: 1px solid var(--border); border-radius: var(--radius);
  color: var(--text-tertiary); cursor: pointer; margin-bottom: 14px;
  box-shadow: var(--shadow-sm); transition: all .15s;
}
.toggle-btn:hover { border-color: var(--border-visible); color: var(--text-secondary); }

.new-chat-btn {
  display: flex; align-items: center; gap: 6px;
  width: 100%; padding: 8px 10px; margin-bottom: 18px;
  border: 1px solid var(--border); border-radius: var(--radius);
  background: var(--bg-elevated); color: var(--text-secondary);
  font-size: 13px; font-family: inherit; cursor: pointer;
  box-shadow: var(--shadow-sm); transition: all .15s;
}
.new-chat-btn:hover { border-color: var(--accent); color: var(--accent); box-shadow: var(--shadow); }

.section { margin-bottom: 16px; }
.section-label {
  font-size: 10px; font-weight: 500; text-transform: uppercase;
  letter-spacing: .04em; color: var(--text-tertiary);
  margin-bottom: 10px; padding: 0 4px;
}

/* ── Divider ── */
.section-divider {
  height: 1px;
  background: var(--border);
  margin: 0 2px 18px;
}

/* ── Sessions ── */
.session-list { max-height: 200px; overflow-y: auto; }
.session-item {
  display: flex; align-items: center; padding: 7px 8px;
  border-radius: var(--radius); cursor: pointer; margin-bottom: 2px;
  transition: background .1s;
}
.session-item:hover { background: var(--bg-hover); }
.session-item.active { background: var(--accent-dim); }
.session-text {
  flex: 1; color: var(--text-secondary); font-size: 12px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.session-item.active .session-text { color: var(--accent-hover); }

/* ── KB ── */
.kb-list { max-height: 130px; overflow-y: auto; }
.kb-item {
  display: flex; align-items: center; gap: 6px; padding: 5px 6px;
  border-radius: var(--radius); transition: background .1s;
  color: var(--text-tertiary);
}
.kb-item:hover { background: var(--bg-hover); }
.kb-name {
  color: var(--text-tertiary); font-size: 12px; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; flex: 1;
}
.kb-item:hover .kb-name { color: var(--text-secondary); }

/* ── Delete button ── */
.item-del {
  background: none; border: none; color: transparent; cursor: pointer;
  padding: 2px; display: flex; align-items: center;
  flex-shrink: 0; transition: color .1s;
}
.session-item:hover .item-del,
.kb-item:hover .item-del { color: var(--text-tertiary); }
.item-del:hover { color: var(--danger) !important; }

.empty {
  color: var(--text-tertiary); font-size: 12px; text-align: center;
  padding: 12px 0; opacity: .6;
}

/* ── User bar ── */
.user-bar {
  display: flex; align-items: center; gap: 8px; padding: 12px;
  border-top: 1px solid var(--border);
  background: var(--bg-elevated);
}
.avatar {
  width: 28px; height: 28px; border-radius: 50%;
  background: var(--accent-dim); color: var(--accent);
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 600; flex-shrink: 0;
}
.uname { color: var(--text-secondary); font-size: 13px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.logout-btn {
  background: none; border: none; color: var(--text-tertiary);
  font-size: 12px; font-family: inherit; cursor: pointer;
}
.logout-btn:hover { color: var(--text-secondary); }
</style>
