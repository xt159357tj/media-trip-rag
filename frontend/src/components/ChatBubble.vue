<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import { useChatStore } from '../stores/chat'
import VideoPlayer from './VideoPlayer.vue'

const props = defineProps({
  message: { type: Object, required: true },
  isLast: { type: Boolean, default: false },
})

const store = useChatStore()

const displayContent = computed(() => {
  if (props.isLast && props.message.role === 'assistant' && store.streaming) {
    return store.streamingContent
  }
  return props.message.content
})

const renderedContent = computed(() => {
  const raw = displayContent.value
  if (props.message.role === 'user' || !raw) return ''
  try {
    return marked.parse(raw, { breaks: true })
  } catch {
    return '<pre>' + raw.replace(/&/g,'&amp;').replace(/</g,'&lt;') + '</pre>'
  }
})
</script>

<template>
  <div class="bubble-row" :class="message.role">
    <!-- Assistant avatar (left) -->
    <div class="avatar" v-if="message.role === 'assistant'">AI</div>

    <!-- Message body -->
    <div class="bubble" :class="message.role">
      <template v-if="message.role === 'user'">
        <p v-if="message.filePath" class="file-tag">{{ message.filePath }}</p>
        <p>{{ message.content }}</p>
      </template>
      <template v-else>
        <div class="streaming-status" v-if="isLast && store.currentStatus && store.streaming">
          <span class="pulse"></span>
          {{ store.currentStatus }}
        </div>
        <div class="markdown-body" v-html="renderedContent"></div>
        <span v-if="isLast && !displayContent && store.streaming" class="cursor-blink">|</span>
        <VideoPlayer v-if="message.videoUrl" :url="message.videoUrl" />
      </template>
    </div>

    <!-- User avatar (right) -->
    <div class="avatar user-avatar" v-if="message.role === 'user'">U</div>
  </div>
</template>

<style scoped>
.bubble-row {
  display: flex; align-items: flex-start; gap: 10px;
  margin-bottom: 24px;
}
.bubble-row.user { justify-content: flex-end; }
.bubble-row.assistant { justify-content: flex-start; }

/* ── Avatar ── */
.avatar {
  width: 30px; height: 30px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 600; flex-shrink: 0;
  color: var(--text-secondary);
  background: var(--bg-elevated);
  border: 1px solid var(--border);
}
.user-avatar {
  background: var(--accent-dim);
  color: var(--accent);
  border-color: transparent;
}

/* ── Bubbles ── */
.bubble {
  max-width: 68%; font-size: 14px; line-height: 1.65;
  padding: 10px 14px;
}
.bubble.user {
  background: var(--accent-dim); color: var(--text-primary);
  border-radius: 14px 14px 4px 14px;
  box-shadow: var(--shadow-sm);
  border: 1px solid rgba(108, 92, 231, 0.1);
}
.bubble.assistant {
  background: var(--bg-surface);
  color: var(--text-primary);
  border-radius: 14px 14px 14px 4px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border);
}
.bubble p { margin: 0; }
.file-tag { font-size: 11px; color: var(--text-tertiary); margin-bottom: 4px; }

/* ── Streaming ── */
.streaming-status {
  display: flex; align-items: center; gap: 7px;
  color: var(--text-tertiary); font-size: 12px; padding: 2px 0 8px;
}
.pulse {
  width: 5px; height: 5px; border-radius: 50%; background: var(--accent);
  animation: pulse 1.4s infinite;
}
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: .25; } }
.cursor-blink { color: var(--accent); animation: blink 1s infinite; margin-left: 1px; }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }

/* ── Markdown ── */
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  color: var(--text-primary); margin: 14px 0 6px; font-weight: 500;
  letter-spacing: -.01em;
}
.markdown-body :deep(h1) { font-size: 18px; }
.markdown-body :deep(h2) { font-size: 15px; }
.markdown-body :deep(h3) { font-size: 14px; }
.markdown-body :deep(p) { margin: 0 0 6px; }
.markdown-body :deep(ul), .markdown-body :deep(ol) { margin: 4px 0; padding-left: 18px; }
.markdown-body :deep(li) { margin-bottom: 2px; }
.markdown-body :deep(code) {
  background: var(--bg-elevated); padding: 2px 5px; border-radius: 3px;
  font-size: 13px; color: var(--accent);
}
.markdown-body :deep(pre) {
  background: var(--bg-elevated); padding: 12px 14px; border-radius: var(--radius);
  overflow-x: auto; border: 1px solid var(--border);
}
.markdown-body :deep(pre code) { background: none; padding: 0; color: var(--text-primary); }
.markdown-body :deep(blockquote) {
  border-left: 2px solid var(--accent); padding-left: 12px;
  margin: 8px 0; color: var(--text-secondary);
}
.markdown-body :deep(a) { color: var(--accent); }
.markdown-body :deep(table) { border-collapse: collapse; width: 100%; font-size: 13px; }
.markdown-body :deep(th), .markdown-body :deep(td) {
  border: 1px solid var(--border); padding: 6px 10px; text-align: left;
}
.markdown-body :deep(th) { background: var(--bg-elevated); font-weight: 500; }
.markdown-body :deep(strong) { color: var(--text-primary); font-weight: 500; }
.markdown-body :deep(hr) { border: none; border-top: 1px solid var(--border); margin: 16px 0; }
</style>
