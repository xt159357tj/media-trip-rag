<script setup>
const props = defineProps({ url: { type: String, required: true } })

async function downloadVideo() {
  try {
    const resp = await fetch(props.url)
    const blob = await resp.blob()
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = props.url.split('/').pop() || 'video.mp4'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(a.href)
  } catch {
    window.open(props.url, '_blank')
  }
}
</script>

<template>
  <div class="inline-player">
    <div class="player-header">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polygon points="5 3 19 12 5 21 5 3"/>
      </svg>
      <span>视频已生成</span>
    </div>
    <video :src="url" controls class="player-video"></video>
    <div class="player-actions">
      <button @click="downloadVideo">下载</button>
    </div>
  </div>
</template>

<style scoped>
.inline-player {
  margin-top: 12px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  max-width: 560px;
}
.player-header {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 14px; color: var(--text-secondary); font-size: 12px;
  border-bottom: 1px solid var(--border);
}
.player-video {
  width: 100%; max-height: 360px; background: #000; display: block;
}
.player-actions {
  display: flex; gap: 8px; padding: 8px 14px; justify-content: flex-end;
}
.player-actions button {
  background: none; border: 1px solid var(--border-visible);
  color: var(--text-secondary); padding: 4px 12px;
  border-radius: var(--radius); font-size: 12px;
  cursor: pointer; transition: all .15s;
}
.player-actions button:hover {
  border-color: var(--accent); color: var(--accent);
}
</style>
