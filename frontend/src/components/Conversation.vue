<template>
  <!-- 侧边栏容器 -->
  <aside 
    class="sidebar" 
    :class="{ 
      collapsed: isCollapsed && !isMobile, 
      expanded: isExpanded,
      'mobile-open': mobileOpen 
    }"
    @mouseenter="handleMouseEnter"
    @mouseleave="handleMouseLeave"
  >
    <!-- 折叠状态下的图标按钮（仅桌面端） -->
    <div v-if="isCollapsed && !isExpanded && !isMobile" class="collapsed-header">
      <el-button 
        type="primary" 
        :icon="ChatDotRound" 
        circle 
        size="large"
        @click="toggleSidebar"
        class="toggle-btn"
      />
    </div>

    <!-- 展开状态 -->
    <div v-show="(!isCollapsed || isExpanded) || mobileOpen" class="sidebar-content">
      <!-- 头部 -->
      <div class="sidebar-header">
        <el-button 
          type="primary" 
          size="default" 
          @click="createNewConversation"
          class="new-chat-btn"
        >
          <el-icon><Plus /></el-icon>
          新建对话
        </el-button>
        
        <!-- 折叠按钮（仅桌面端） -->
        <el-button 
          v-if="!isMobile"
          text 
          @click="toggleSidebar"
          class="collapse-btn"
          :title="isCollapsed ? '展开' : '折叠'"
        >
          <el-icon>
            <DArrowLeft v-if="!isCollapsed" />
            <DArrowRight v-else />
          </el-icon>
        </el-button>
      </div>

      <!-- 对话列表 -->
      <div class="conversation-list" ref="listRef">
        <div
          v-for="conv in conversations"
          :key="conv.id"
          :class="['conversation-item', { active: conv.id === currentConversationId }]"
          @click="switchConversation(conv.id)"
        >
          <div class="conv-info">
            <div class="conv-title">
              <el-icon class="conv-icon"><ChatLineRound /></el-icon>
              <span>{{ conv.title }}</span>
            </div>
            <div class="conv-time">{{ formatTime(conv.updated_at) }}</div>
          </div>
          <el-button
            type="danger"
            size="small"
            text
            @click.stop="deleteConversation(conv.id)"
            class="delete-btn"
          >
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>

        <!-- 空状态 -->
        <div v-if="conversations.length === 0" class="empty-conversations">
          <el-empty description="暂无对话记录" :image-size="80">
            <el-button type="primary" size="small" @click="createNewConversation">
              开始新对话
            </el-button>
          </el-empty>
        </div>
      </div>

      <!-- 底部用户信息 -->
      <div class="sidebar-footer" v-if="user">
        <div class="user-info">
          <el-avatar :size="32" :src="user.avatar">
            {{ user.username?.charAt(0)?.toUpperCase() }}
          </el-avatar>
          <div class="user-name" v-if="!(isCollapsed && !isMobile)">{{ user.username }}</div>
        </div>
      </div>
    </div>

    <!-- 移动端遮罩 - 移到侧边栏外部 -->
  </aside>
  
  <!-- 移动端遮罩（独立于侧边栏） -->
  <div v-if="mobileOpen" class="mobile-overlay" @click="toggleConversationList(false)"></div>
</template>

<style scoped lang="scss">
@use '@/assets/styles/variables' as *;
@use '@/assets/styles/mixins' as *;

.sidebar {
  position: relative;
  width: $aside-width;
  height: 100vh;
  background: $bg-white;
  border-right: 1px solid $border-color;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  z-index: 100;

  // 折叠状态（仅桌面端）
  &.collapsed {
    width: 60px;
    
    .sidebar-content {
      opacity: 0;
      pointer-events: none;
    }
  }

  // 悬浮展开
  &.expanded {
    width: $aside-width;
    box-shadow: 2px 0 12px rgba(0, 0, 0, 0.1);
    
    .sidebar-content {
      opacity: 1;
      pointer-events: all;
    }
  }

  // 移动端打开
  &.mobile-open {
    position: fixed;
    left: 0;
    top: 0;
    width: $aside-width;
    height: 100vh;
    box-shadow: 2px 0 12px rgba(0, 0, 0, 0.15);
    z-index: 1001; // 比遮罩高
    
    .sidebar-content {
      opacity: 1 !important;
      pointer-events: all !important;
    }
  }

  // 折叠时的头部（桌面端）
  .collapsed-header {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    padding: $spacing-md;

    .toggle-btn {
      :deep(.el-icon) {
        font-size: 20px;
      }
    }
  }

  // 移动端触发按钮
  .mobile-trigger {
    position: fixed;
    left: 16px;
    top: 16px;
    z-index: 99;
    
    .el-button {
      width: 44px;
      height: 44px;
      box-shadow: 0 2px 12px rgba(0, 0, 0, 0.15);
      
      :deep(.el-icon) {
        font-size: 20px;
      }
    }
  }

  // 侧边栏内容
  .sidebar-content {
    display: flex;
    flex-direction: column;
    height: 100%;
    transition: opacity 0.3s ease;
    opacity: 1;
    position: relative;
    z-index: 2; // 确保内容在遮罩之上
  }

  // 头部
  &-header {
    padding: $spacing-md;
    border-bottom: 1px solid $border-color;
    display: flex;
    align-items: center;
    gap: $spacing-sm;
    flex-shrink: 0;

    .new-chat-btn {
      flex: 1;
      min-width: 0;
      
      :deep(.el-icon) {
        margin-right: 4px;
      }
    }

    .collapse-btn,
    .close-btn {
      flex-shrink: 0;
      padding: 4px;
      color: $text-light;
      transition: transform 0.3s ease;

      &:hover {
        color: $primary-color;
        background: $bg-gray;
        border-radius: $radius-sm;
      }
    }
  }

  // 对话列表
  .conversation-list {
    flex: 1;
    overflow-y: auto;
    padding: $spacing-sm;
    
    // 自定义滚动条
    &::-webkit-scrollbar {
      width: 4px;
    }
    
    &::-webkit-scrollbar-track {
      background: transparent;
    }
    
    &::-webkit-scrollbar-thumb {
      background: $border-color;
      border-radius: 2px;
      
      &:hover {
        background: $text-light;
      }
    }
  }

  // 对话项
  .conversation-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: $spacing-sm 0;
    border-radius: $radius-sm;
    cursor: pointer;
    transition: all 0.2s ease;
    margin-bottom: 2px;
    position: relative;

    &:hover {
      background: $bg-gray;
      
      .delete-btn {
        opacity: 1;
      }
    }

    &.active {
      background: $primary-color;
      color: $bg-white;
      
      .conv-time {
        color: rgba(255, 255, 255, 0.7);
      }
      
      .conv-icon {
        color: $bg-white;
      }
    }

    .conv-info {
      flex: 1;
      overflow: hidden;
      min-width: 0;
    }

    .conv-title {
      font-size: $font-size-sm;
      display: flex;
      align-items: center;
      gap: 6px;
      
      .conv-icon {
        font-size: 16px;
        flex-shrink: 0;
        color: $text-light;
      }
      
      span {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
    }

    .conv-time {
      font-size: 11px;
      color: $text-light;
      margin-top: 2px;
      padding-left: 22px;
    }

    .delete-btn {
      opacity: 0;
      transition: opacity 0.2s ease;
      color: $danger-color;
      flex-shrink: 0;
      
      &:hover {
        background: rgba($danger-color, 0.1);
        border-radius: $radius-sm;
      }
    }
  }

  // 空状态
  .empty-conversations {
    padding: $spacing-xl $spacing-sm;
    
    :deep(.el-empty) {
      padding: 0;
      
      .el-empty__description {
        margin-top: $spacing-sm;
        color: $text-light;
      }
    }
  }

  // 底部
  &-footer {
    padding: $spacing-md;
    border-top: 1px solid $border-color;
    flex-shrink: 0;

    .user-info {
      display: flex;
      align-items: center;
      gap: $spacing-sm;
      
      .user-name {
        font-size: $font-size-sm;
        font-weight: 500;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
    }
  }
}

// 移动端遮罩（独立于侧边栏）
.mobile-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 1000; // 在侧边栏之下，但在页面内容之上
}

// 响应式 - 平板
@media (max-width: 1024px) {
  .sidebar {
    width: 220px;
    
    &.collapsed {
      width: 50px;
    }
    
    &.expanded {
      width: 220px;
    }
  }
}

// 响应式 - 手机
@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    left: -$aside-width;
    top: 0;
    width: $aside-width;
    height: 100vh;
    transition: left 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 2px 0 12px rgba(0, 0, 0, 0.15);
    z-index: 1001; // 比遮罩高
    border-right: none;

    &.mobile-open {
      left: 0;
    }

    // 移动端不折叠
    &.collapsed {
      width: $aside-width;
    }
  }

  // 移动端显示触发按钮
  .mobile-trigger {
    display: flex !important;
  }
}

// 桌面端隐藏移动触发按钮
.mobile-trigger {
  display: none;
}
</style>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { Plus, Delete, ChatDotRound, ChatLineRound, DArrowLeft, DArrowRight, Close } from '@element-plus/icons-vue'
import { formatTime } from '@/utils'
import type { PropType } from 'vue'
import type { Conversation } from '@/types/chat'

const props = defineProps({
  conversations: {
    type: Array as PropType<Conversation[]>,
    default: () => []
  },
  currentConversationId: {
    type: Number,
    default: 0
  },
  user: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['switchConversation', 'deleteConversation', 'createNewConversation'])

// ===== 状态 =====
const isCollapsed = ref(false)
const isExpanded = ref(false)
const mobileOpen = ref(false)
const isMobile = ref(window.innerWidth < 768)
const hideTimeout = ref<number | null>(null)

// ===== 方法 =====
const toggleSidebar = () => {
  if (isMobile.value) {
    mobileOpen.value = !mobileOpen.value
  } else {
    isCollapsed.value = !isCollapsed.value
    if (!isCollapsed.value) {
      isExpanded.value = false
    }
  }
}

const toggleConversationList = (isOpen: boolean) => {
  mobileOpen.value = isOpen
}

const handleMouseEnter = () => {
  if (isCollapsed.value && !isMobile.value) {
    if (hideTimeout.value) {
      clearTimeout(hideTimeout.value)
      hideTimeout.value = null
    }
    isExpanded.value = true
  }
}

const handleMouseLeave = () => {
  if (isCollapsed.value && !isMobile.value) {
    // 延迟收起，避免鼠标抖动
    hideTimeout.value = setTimeout(() => {
      isExpanded.value = false
      hideTimeout.value = null
    }, 300)
  }
}

const switchConversation = (id: number) => {
  emit('switchConversation', id)
  // 移动端点击后关闭侧边栏
  if (isMobile.value) {
    mobileOpen.value = false
  }
}

const deleteConversation = (id: number) => {
  emit('deleteConversation', id)
}

const createNewConversation = () => {
  emit('createNewConversation')
  // 移动端点击后关闭侧边栏
  if (isMobile.value) {
    mobileOpen.value = false
  }
}

// ===== 响应式 =====
const handleResize = () => {
  const mobile = window.innerWidth < 768
  isMobile.value = mobile
  
  // 切换到桌面时关闭移动端菜单
  if (!mobile) {
    mobileOpen.value = false
  }
  
  // 在小屏幕下自动折叠
  if (window.innerWidth < 1024 && window.innerWidth >= 768) {
    isCollapsed.value = true
  } else if (window.innerWidth >= 1024) {
    isCollapsed.value = false
  }
}

// ===== 暴露方法给父组件 =====
defineExpose({
  toggleSidebar,
  toggleConversationList,
  isMobileOpen: mobileOpen
})

// ===== 生命周期 =====
onMounted(() => {
  window.addEventListener('resize', handleResize)
  // 初始化时判断屏幕大小
  handleResize()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (hideTimeout.value) {
    clearTimeout(hideTimeout.value)
  }
})

// 监听折叠状态变化
watch(isCollapsed, (newVal) => {
  if (!newVal) {
    isExpanded.value = false
  }
})
</script>