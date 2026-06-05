<script setup>
import { ref, watch, nextTick } from 'vue'
import { useChatStore } from '../stores/chat'
import ChatBubble from './ChatBubble.vue'

const store = useChatStore()
const container = ref(null)

watch(
  () => store.messages.length,
  async () => { await nextTick(); scrollBottom() },
)
watch(
  () => store.messages[store.messages.length - 1]?.content,
  async () => { await nextTick(); scrollBottom() },
)

function scrollBottom() {
  if (container.value) {
    container.value.scrollTop = container.value.scrollHeight
  }
}
</script>

<template>
  <div class="chat-area" ref="container">
    <div class="messages" v-if="store.messages.length > 0">
      <ChatBubble
        v-for="(msg, i) in store.messages" :key="i"
        :message="msg" :is-last="i === store.messages.length - 1"
      />
    </div>
    <div class="empty-state" v-else>
      <div class="empty-logo">
        <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
          <rect width="40" height="40" rx="10" fill="var(--accent-dim)"/>
          <path d="M12 20L18 26L28 14" stroke="var(--accent)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <h2>Media Trip RAG</h2>
      <p>视频字幕 · 出行规划 · 知识库检索 · 智能问答</p>
    </div>
  </div>
</template>

<style scoped>
.chat-area {
  flex: 1; overflow-y: auto; padding: 32px 24px;
  scroll-behavior: smooth;
}
.messages { max-width: 720px; margin: 0 auto; }
.empty-state {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; height: 100%; text-align: center;
  padding-bottom: 60px;
}
.empty-logo { margin-bottom: 20px; opacity: .6; }
.empty-state h2 {
  font-size: 20px; font-weight: 500; color: var(--text-primary);
  margin: 0 0 6px; letter-spacing: -.01em;
}
.empty-state p {
  color: var(--text-tertiary); font-size: 13px;
}
</style>
