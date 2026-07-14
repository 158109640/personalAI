<template>
  <main class="auth-container">
    <section class="auth-card">
      <header class="auth-header">
        <h2>登录</h2>
        <p class="subtitle">欢迎回来 👋</p>
      </header>

      <el-form
        :model="form"
        :rules="rules"
        ref="formRef"
        @submit.prevent="handleLogin"
        label-width="70px"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
           
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
           
            show-password
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
           
            native-type="submit"
            :loading="loading"
            class="submit-btn"
          >
            {{ loading ? '登录中...' : '登录' }}
          </el-button>
        </el-form-item>

        <footer class="auth-footer">
          <span>还没有账号？</span>
          <el-link type="primary" @click="$router.push('/register')">去注册</el-link>
        </footer>
      </el-form>
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
  width: 80%;
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
    &:hover {
      box-shadow: 0 0 0 1px $primary-color inset;
    }
  }

  :deep(.el-input.is-focus .el-input__wrapper) {
    box-shadow: 0 0 0 1px $primary-color inset;
  }
}

.auth-header {
  @include flex-center(column);
  gap: $spacing-xs;
  margin-bottom: $spacing-lg;

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

.submit-btn {
  width: 100%;
  margin-top: $spacing-sm;
}

.auth-footer {
  @include flex-center;
  gap: $spacing-sm;
  color: $text-secondary;
  font-size: $font-size-sm;
  margin-top: $spacing-sm;
}
</style>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()
const formRef = ref<FormInstance>()

const form = reactive({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const loading = ref(false)

const handleLogin = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    loading.value = true
    try {
      await userStore.login(form.username, form.password)
      ElMessage.success('登录成功')
      router.push('/chat')
    } catch (e: any) {
      ElMessage.error(e.response?.data?.detail || '登录失败')
    } finally {
      loading.value = false
    }
  })
}
</script>