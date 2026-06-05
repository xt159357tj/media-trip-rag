<script setup>
import { ref } from 'vue'
import { uploadDocument } from '../api'

const emit = defineEmits(['uploaded'])

const uploading = ref(false)
const progress = ref(0)
const message = ref('')

async function handleFile(e) {
  const file = e.target.files[0]
  if (!file) return
  uploading.value = true
  progress.value = 0
  message.value = ''
  try {
    const { data } = await uploadDocument(file, (evt) => {
      progress.value = Math.round((evt.loaded / evt.total) * 100)
    })
    if (data.code === 0) {
      message.value = '已添加'
      emit('uploaded')
    } else {
      message.value = data.message || '上传失败'
    }
  } catch (err) {
    message.value = '上传失败，请重试'
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="doc-upload">
    <label class="upload-zone">
      <input type="file" accept=".pdf,.docx,.doc,.txt,.md,.html,.htm" hidden @change="handleFile" :disabled="uploading" />
      <span v-if="uploading">上传中 {{ progress }}%</span>
      <span v-else>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12"/></svg>
        上传文档
      </span>
    </label>
    <span class="upload-msg" v-if="message" :class="{ err: message.includes('失败') }">{{ message }}</span>
  </div>
</template>

<style scoped>
.doc-upload { margin-top: 6px; }
.upload-zone {
  display: flex; align-items: center; justify-content: center; gap: 6px;
  padding: 10px; border: 1px solid var(--border); border-radius: var(--radius);
  cursor: pointer; color: var(--text-tertiary); font-size: 12px;
  transition: all .15s;
}
.upload-zone:hover { border-color: var(--border-visible); color: var(--text-secondary); }
.upload-zone svg { flex-shrink: 0; }
.upload-msg { display: block; margin-top: 4px; font-size: 11px; color: var(--success); }
.upload-msg.err { color: var(--danger); }
</style>
