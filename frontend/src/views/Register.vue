<template>
  <main class="auth-container">
    <section class="auth-card">
      <header class="auth-header">
        <h2>注册</h2>
        <p class="subtitle">创建你的账号 🚀</p>
      </header>

      <!-- 步骤条 -->
      <el-steps :active="activeStep" align-center class="steps">
        <el-step title="验证邮箱" />
        <el-step title="设置账号" />
      </el-steps>

      <!-- 第一步：验证邮箱 -->
      <div v-show="activeStep === 0" class="step-content">
        <el-form
          :model="form"
          :rules="step1Rules"
          ref="step1FormRef"
          label-width="70px"
        >
          <el-form-item label="邮箱" prop="email">
            <div class="email-group">
              <el-input
                v-model="form.email"
                placeholder="请输入邮箱"
              />
              <el-button
                class="code-btn"
                type="primary"
                :disabled="codeSending || countdown > 0"
                @click="handleSendCode"
              >
                {{ countdown > 0 ? `${countdown}s` : '获取验证码' }}
              </el-button>
            </div>
          </el-form-item>

          <el-form-item label="验证码" prop="code">
            <el-input
              v-model="form.code"
              placeholder="请输入6位验证码"
              maxlength="6"
            />
          </el-form-item>

          <el-button
            type="primary"
            class="step-btn"
            @click="handleStep1Next"
          >
            下一步
          </el-button>
        </el-form>
      </div>

      <!-- 第二步：设置账号 -->
      <div v-show="activeStep === 1" class="step-content">
        <el-form
          :model="form"
          :rules="step2Rules"
          ref="step2FormRef"
          label-width="80px"
        >
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model="form.username"
              placeholder="请输入用户名（3-20个字符）"
            />
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="请设置密码（至少6位）"

              show-password
            />
          </el-form-item>

          <el-form-item label="确认密码" prop="confirmPassword">
            <el-input
              v-model="form.confirmPassword"
              type="password"
              placeholder="请再次输入密码"
            />
          </el-form-item>

          <div class="step-actions">
            <el-button @click="activeStep = 0">上一步</el-button>
            <el-button
              type="primary"
              :loading="loading"
              @click="handleRegister"
            >
              {{ loading ? '注册中...' : '完成注册' }}
            </el-button>
          </div>
        </el-form>
      </div>

      <footer class="auth-footer">
        <span>已有账号？</span>
        <el-link type="primary" @click="$router.push('/login')">去登录</el-link>
      </footer>
    </section>
  </main>
</template>

<style scoped lang="scss">
@use '@/assets/styles/variables' as *;
@use '@/assets/styles/mixins' as *;

.auth-container {
  @include flex-center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.auth-card {
  width: 100%;
  max-width: 420px;
  background: $bg-white;
  border-radius: $radius-lg;
  box-shadow: $shadow-lg;
  padding: $spacing-xl;

  :deep(.el-form-item) {
    margin-bottom: $spacing-md;
  }

  :deep(.el-input__wrapper) {
    box-shadow: 0 0 0 1px $border-color inset;
    text-align: left;

    .el-input__inner {
      text-align: left;
    }

    &:hover {
      box-shadow: 0 0 0 1px $primary-color inset;
    }
  }

  :deep(.el-input .el-input__prefix) {
    margin-right: 8px;
  }

  :deep(.el-input.is-focus .el-input__wrapper) {
    box-shadow: 0 0 0 1px $primary-color inset;
  }
}

.auth-header {
  @include flex-center(column);
  gap: $spacing-xs;
  margin-bottom: $spacing-md;

  h2 {
    font-size: $font-size-xl;
    color: $text-primary;
    margin: 0;
  }

  .subtitle {
    color: $text-secondary;
    font-size: $font-size-sm;
  }
}

.steps {
  margin: $spacing-md 0 $spacing-lg;

  :deep(.el-step__title) {
    font-size: $font-size-sm;
  }
}

.step-btn {
  width: 100%;
  margin-top: $spacing-sm;
}

.step-actions {
  display: flex;
  gap: $spacing-md;
  margin-top: $spacing-sm;

  .el-button {
    flex: 1;
  }
}

.auth-footer {
  @include flex-center;
  gap: $spacing-sm;
  color: $text-secondary;
  font-size: $font-size-sm;
  margin-top: $spacing-lg;
  padding-top: $spacing-md;
  border-top: 1px solid $border-color;
}

// ===== 邮箱 + 验证码按钮组合 =====
.email-group {
  display: flex;
  gap: 10px;

  .el-input {
    flex: 1;
  }

  .code-btn {
    flex-shrink: 0;
    width: 120px;
  }
}
</style>

<script setup lang="ts">
import { reactive, ref, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { sendCode, verifyCode } from '@/api/auth'

const router = useRouter()
const userStore = useUserStore()

const activeStep = ref(0)
const step1FormRef = ref<FormInstance>()
const step2FormRef = ref<FormInstance>()

const form = reactive({
  email: '',
  code: '',
  username: '',
  password: '',
  confirmPassword: '',
})

// ===== 第一步校验规则 =====
const step1Rules: FormRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' },
  ],
  code: [
    { required: true, message: '请输入验证码', trigger: 'blur' },
    { len: 6, message: '验证码为6位数字', trigger: 'blur' },
  ],
}

// ===== 第二步校验规则 =====
const step2Rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度在 3 到 20 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请设置密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== form.password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

// ===== 状态 =====
const loading = ref(false)
const codeSending = ref(false)
const verifying = ref(false)
const countdown = ref(0)
let timer: number | null = null

// ===== 发送验证码 =====
const handleSendCode = async () => {
  if (!form.email) {
    ElMessage.warning('请先输入邮箱')
    return
  }

  const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/
  if (!emailRegex.test(form.email)) {
    ElMessage.warning('请输入正确的邮箱格式')
    return
  }

  codeSending.value = true
  try {
    await sendCode({ email: form.email })
    ElMessage.success('验证码已发送，请查收邮箱')

    countdown.value = 60
    timer = window.setInterval(() => {
      countdown.value--
      if (countdown.value <= 0) {
        clearInterval(timer!)
        timer = null
      }
    }, 1000)
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '发送失败')
  } finally {
    codeSending.value = false
  }
}

// ===== 第一步：验证验证码 → 进入第二步 =====
const handleStep1Next = async () => {
  if (!step1FormRef.value) return

  await step1FormRef.value.validate(async (valid) => {
    if (!valid) return

    verifying.value = true
    try {
      // 调用后端接口验证验证码
      await verifyCode({ email: form.email, code: form.code })
      ElMessage.success('验证通过')
      activeStep.value = 1
    } catch (e: any) {
      ElMessage.error(e.response?.data?.detail || '验证码无效')
    } finally {
      verifying.value = false
    }
  })
}

// ===== 第二步：完成注册 =====
const handleRegister = async () => {
  if (!step2FormRef.value) return

  await step2FormRef.value.validate(async (valid) => {
    if (!valid) return

    loading.value = true
    try {
      await userStore.register(
        form.username,
        form.email,
        form.code,
        form.password
      )
      ElMessage.success('注册成功，请登录')
      router.push('/login')
    } catch (e: any) {
      ElMessage.error(e.response?.data?.detail || '注册失败')
    } finally {
      loading.value = false
    }
  })
}

// ===== 清理定时器 =====
onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
})
</script>