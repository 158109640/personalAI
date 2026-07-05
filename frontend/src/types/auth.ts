export interface UserInfo {
  id?: number
  username: string
  email?: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  email: string
  code: string
  password: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user?: UserInfo
}

export interface SendCodeRequest {
  email: string
}
