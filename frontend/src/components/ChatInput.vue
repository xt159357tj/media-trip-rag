<script setup>
import { ref } from 'vue'
import { useChatStore } from '../stores/chat'
import { uploadVideo } from '../api'

const store = useChatStore()

const text = ref('')
const videoFile = ref(null)
const videoPath = ref('')
const uploading = ref(false)
const uploadProgress = ref(0)

async function handleVideo(e) {
  const file = e.target.files[0]
  if (!file) return
  videoFile.value = file
  uploading.value = true
  uploadProgress.value = 0
  try {
    const { data } = await uploadVideo(file, (evt) => {
      uploadProgress.value = Math.round((evt.loaded / evt.total) * 100)
    })
    videoPath.value = data.data.file_path
  } catch {
    videoFile.value = null
  } finally {
    uploading.value = false
  }
}

function removeVideo() {
  videoFile.value = null
  videoPath.value = ''
}

function send() {
  const content = text.value.trim()
  if (!content && !videoPath.value) return
  if (store.streaming) return
  store.sendMessage(content || '请处理这个视频', videoPath.value)
  text.value = ''
  videoFile.value = null
  videoPath.value = ''
}

function onKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}
</script>

<template>
  <div class="input-area">
    <div class="input-row">
      <label class="upload-btn" title="上传视频">
        <input type="file" accept="video/*" hidden @change="handleVideo" :disabled="uploading" />
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
          <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/>
        </svg>
      </label>

      <textarea
        v-model="text"
        @keydown="onKeydown"
        placeholder="输入消息... (Enter 发送)"
        rows="1"
        :disabled="store.streaming"
      ></textarea>

      <button
        class="send-btn"
        @click="send"
        :disabled="(!text.trim() && !videoPath.value) || store.streaming"
      >
        {{ store.streaming ? '...' : '发送' }}
      </button>
    </div>

    <div class="video-preview" v-if="videoFile">
      <span v-if="uploading">上传中 {{ uploadProgress }}%</span>
      <span v-else>{{ videoFile.name }} 已就绪</span>
      <button @click="removeVideo">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.input-area {
  max-width: 720px; margin: 0 auto; width: 100%; padding: 0 24px 24px;
}
.input-row {
  display: flex; align-items: flex-end; gap: 8px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 8px 12px;
  box-shadow: var(--shadow-sm);
  transition: border-color .2s, box-shadow .2s;
}
.input-row:focus-within {
  border-color: var(--border-visible);
  box-shadow: var(--shadow);
}
.upload-btn {
  color: var(--text-tertiary); cursor: pointer; padding: 6px 4px;
  display: flex; align-items: center; transition: color .15s;
}
.upload-btn:hover { color: var(--text-secondary); }
textarea {
  flex: 1; background: none; border: none; outline: none;
  color: var(--text-primary); font-size: 14px; font-family: inherit;
  resize: none; max-height: 120px; padding: 6px 0; line-height: 1.5;
}
textarea::placeholder { color: var(--text-tertiary); }
.send-btn {
  background: var(--accent); color: #fff; border: none;
  border-radius: var(--radius); padding: 7px 18px;
  font-size: 13px; font-weight: 500; cursor: pointer;
  box-shadow: 0 1px 3px rgba(108, 92, 231, .3);
  transition: background .15s, box-shadow .15s; white-space: nowrap;
}
.send-btn:hover { background: var(--accent-hover); box-shadow: 0 2px 6px rgba(108, 92, 231, .4); }
.send-btn:disabled { opacity: .35; cursor: not-allowed; box-shadow: none; }
.video-preview {
  display: flex; align-items: center; gap: 8px; margin-top: 8px;
  padding: 6px 12px; background: var(--accent-dim); border-radius: var(--radius);
  color: var(--text-secondary); font-size: 12px;
}
.video-preview button {
  background: none; border: none; color: var(--text-tertiary);
  cursor: pointer; margin-left: auto; padding: 2px;
  display: flex; align-items: center;
}
.video-preview button:hover { color: var(--text-secondary); }
</style>
