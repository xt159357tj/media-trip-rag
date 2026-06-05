<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '../stores/chat'
import { register, login } from '../api'

const router = useRouter()
const store = useChatStore()

const mode = ref('login')
const uname = ref('')
const password = ref('')
const confirmPwd = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  if (!uname.value.trim() || !password.value) {
    error.value = '请填写完整信息'
    return
  }
  if (mode.value === 'register' && password.value !== confirmPwd.value) {
    error.value = '两次密码不一致'
    return
  }
  if (mode.value === 'register' && password.value.length < 6) {
    error.value = '密码至少6位'
    return
  }

  loading.value = true
  try {
    const fn = mode.value === 'login' ? login : register
    const { data } = await fn(uname.value.trim(), password.value)
    if (data.code === 0) {
      store.setUser(data.data.uid, data.data.uname)
      router.push('/chat')
    } else {
      error.value = data.message || '操作失败'
    }
  } catch (e) {
    error.value = '网络错误，请检查后端服务'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="logo">
        <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
          <rect width="32" height="32" rx="8" fill="var(--accent-dim)"/>
          <path d="M10 16L14.5 21L22 11" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <h1>Media Trip RAG</h1>
      <p class="subtitle">视频字幕 · 出行规划 · 知识库检索</p>

      <div class="tabs">
        <button :class="{ active: mode === 'login' }" @click="mode = 'login'">登录</button>
        <button :class="{ active: mode === 'register' }" @click="mode = 'register'">注册</button>
      </div>

      <form @submit.prevent="submit">
        <input v-model="uname" type="text" placeholder="用户名" name="username" autocomplete="username" />
        <input v-model="password" type="password" placeholder="密码" name="password"
          :autocomplete="mode === 'register' ? 'new-password' : 'current-password'" />
        <input v-if="mode === 'register'" v-model="confirmPwd" type="password" placeholder="确认密码"
          name="confirm-password" autocomplete="new-password" />

        <p v-if="error" class="error">{{ error }}</p>

        <button type="submit" class="submit-btn" :disabled="loading">
          {{ loading ? '处理中...' : (mode === 'login' ? '登录' : '注册') }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  background: var(--bg-primary);
}
.login-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 40px;
  width: 380px;
  max-width: 90vw;
}
.logo { text-align: center; margin-bottom: 16px; }
h1 { color: var(--text-primary); text-align: center; margin: 0 0 4px; font-size: 20px; font-weight: 600; letter-spacing: -.01em; }
.subtitle { color: var(--text-tertiary); text-align: center; margin: 0 0 28px; font-size: 13px; }
.tabs { display: flex; margin-bottom: 24px; border-radius: var(--radius); background: var(--bg-primary); padding: 2px; }
.tabs button {
  flex: 1; border: none; padding: 8px; cursor: pointer;
  background: none; color: var(--text-tertiary); font-size: 13px;
  font-weight: 500; border-radius: 4px; transition: all .15s;
}
.tabs button.active { background: var(--accent); color: #fff; }
input {
  width: 100%; padding: 9px 12px; margin-bottom: 10px; border-radius: var(--radius);
  border: 1px solid var(--border); background: var(--bg-primary);
  color: var(--text-primary); font-size: 13px; font-family: inherit;
  outline: none; transition: border-color .15s;
}
input:focus { border-color: var(--accent); }
.error { color: var(--danger); font-size: 12px; margin: 4px 0 0; }
.submit-btn {
  width: 100%; margin-top: 16px; padding: 10px; border: none; border-radius: var(--radius);
  background: var(--accent); color: #fff; font-size: 14px; font-weight: 500;
  cursor: pointer; transition: background .15s;
}
.submit-btn:hover { background: var(--accent-hover); }
.submit-btn:disabled { opacity: .5; cursor: not-allowed; }
</style>
