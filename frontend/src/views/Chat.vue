<script setup>
import { onMounted } from 'vue'
import { useChatStore } from '../stores/chat'
import Sidebar from '../components/Sidebar.vue'
import ChatArea from '../components/ChatArea.vue'
import ChatInput from '../components/ChatInput.vue'

const store = useChatStore()

onMounted(() => {
  store.fetchSessions()
})
</script>

<template>
  <div class="chat-layout">
    <Sidebar />
    <div class="main-panel">
      <ChatArea />
      <ChatInput />
    </div>
  </div>
</template>

<style scoped>
.chat-layout {
  display: flex; height: 100vh; overflow: hidden;
}
.main-panel {
  flex: 1; display: flex; flex-direction: column; min-width: 0;
  background: var(--bg-primary);
}
</style>
