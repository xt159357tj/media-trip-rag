import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import * as api from '../api'

export const useChatStore = defineStore('chat', () => {
  const sessions = ref([])
  const currentSessionId = ref(null)
  const messages = ref([])
  const streaming = ref(false)
  const streamingContent = ref('')
  const currentStatus = ref('')
  const videoUrl = ref(null)

  const uid = ref(localStorage.getItem('uid') || '')
  const uname = ref(localStorage.getItem('uname') || '')

  function setUser(newUid, newUname) {
    localStorage.setItem('uid', newUid)
    localStorage.setItem('uname', newUname)
    uid.value = newUid
    uname.value = newUname
  }

  function clearUser() {
    localStorage.removeItem('uid')
    localStorage.removeItem('uname')
    uid.value = ''
    uname.value = ''
    newChat()
  }

  async function fetchSessions() {
    try {
      const { data } = await api.getSessions()
      sessions.value = data.data.sessions || []
    } catch { /* ignore */ }
  }

  function newChat() {
    currentSessionId.value = null
    messages.value = []
    streamingContent.value = ''
    videoUrl.value = null
    currentStatus.value = ''
  }

  async function loadSession(sessionId) {
    try {
      const { data } = await api.getSession(sessionId)
      const history = data.data.history || []
      currentSessionId.value = sessionId
      const msgs = []
      for (const turn of history) {
        for (const m of turn.user || []) {
          if (m.type === 'text') msgs.push({ role: 'user', content: m.content })
          if (m.type === 'file') msgs.push({ role: 'user', content: '[视频]', filePath: m.file_path })
        }
        for (const m of turn.assistant || []) {
          if (m.type === 'text') msgs.push({ role: 'assistant', content: m.content })
          if (m.type === 'file') {
            msgs.push({ role: 'assistant', content: '视频已生成', filePath: m.file_path, videoUrl: m.file_path })
            videoUrl.value = m.file_path
          }
        }
      }
      messages.value = msgs
    } catch { /* ignore */ }
  }

  async function removeSession(sessionId) {
    try {
      await api.deleteSession(sessionId)
      sessions.value = sessions.value.filter((s) => s.session_id !== sessionId)
      if (currentSessionId.value === sessionId) newChat()
    } catch { /* ignore */ }
  }

  function sendMessage(userInput, videoPath) {
    if (streaming.value) return

    const userMsg = { role: 'user', content: userInput }
    if (videoPath) userMsg.filePath = videoPath

    messages.value.push(userMsg)
    messages.value.push({ role: 'assistant', content: '' })

    streaming.value = true
    streamingContent.value = ''
    currentStatus.value = ''

    const payload = {
      uid: uid.value,
      session_id: currentSessionId.value || undefined,
      user_input: userInput,
      original_video_path: videoPath || '',
    }

    fetch('http://127.0.0.1:8000/api/process', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then((response) => {
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        function pump() {
          reader.read().then(({ done, value }) => {
            if (done) {
              streaming.value = false
              currentStatus.value = ''
              return
            }
            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split('\n')
            buffer = lines.pop() || ''

            for (const line of lines) {
              if (!line.startsWith('data: ')) continue
              const raw = line.slice(6)
              if (raw === '[DONE]') continue

              try {
                const event = JSON.parse(raw)
                if (event.type === 'status') {
                  currentStatus.value = event.content
                } else if (event.type === 'answer') {
                  streamingContent.value += event.content
                } else if (event.type === 'done') {
                  const last = messages.value[messages.value.length - 1]
                  if (event.content && !streamingContent.value) {
                    last.content = event.content
                  } else {
                    last.content = streamingContent.value
                  }
                  currentSessionId.value = event.session_id
                  streamingContent.value = ''
                  streaming.value = false
                  if (event.video_url) {
                    last.videoUrl = event.video_url
                    videoUrl.value = event.video_url
                  }
                  fetchSessions()
                } else if (event.type === 'error') {
                  streamingContent.value = `错误: ${event.content}`
                }
              } catch { /* malformed JSON, skip */ }
            }
            pump()
          })
        }
        pump()
      })
      .catch(() => {
        messages.value[messages.value.length - 1].content = '请求失败，请检查后端服务是否运行。'
        streamingContent.value = ''
        streaming.value = false
      })
  }

  function closeVideo() {
    videoUrl.value = null
  }

  return {
    sessions, currentSessionId, messages, streaming, streamingContent, currentStatus, videoUrl,
    uid, uname,
    setUser, clearUser,
    fetchSessions, newChat, loadSession, removeSession, sendMessage, closeVideo,
  }
})
