import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as apiLogin, register as apiRegister } from '@/api/auth'
import type { UserInfo } from '@/types/auth'

export const useUserStore = defineStore('user', () => {
  const token = ref<string | null>(null)
  const userInfo = ref<UserInfo | null>(null)

  const setAuth = (t: string, user: UserInfo) => {
    token.value = t
    userInfo.value = user
  }

  const clearAuth = () => {
    token.value = null
    userInfo.value = null
  }

  const login = async (username: string, password: string) => {
    const res = await apiLogin({ username, password })
    setAuth(res.data.access_token, { username })
    return res
  }

  const register = async (username: string, email: string, code: string, password: string) => {
    return await apiRegister({ username, email, code, password })
  }

  const logout = () => {
    clearAuth()
  }

  return { token, userInfo, login, register, logout, clearAuth }
}, {
  persist: {
    key: 'user-store',
    storage: localStorage,
    pick: ['token', 'userInfo'],  // 用 pick 代替 paths
  },
})