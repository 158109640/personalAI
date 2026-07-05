import request from '@/utils/request'
import type { LoginRequest, RegisterRequest, AuthResponse, SendCodeRequest } from '@/types/auth'

// 新增：发送验证码
export const sendCode = (data: SendCodeRequest) => {
  return request.post('/auth/send-code', data)
}

// 验证验证码
export const verifyCode = (data: { email: string; code: string }) => {
  return request.post('/auth/verify-code', data)
}

export const register = (data: RegisterRequest) => {
  return request.post<AuthResponse>('/auth/register', data)
}

export const login = (data: LoginRequest) => {
  return request.post<AuthResponse>('/auth/login', data)
}