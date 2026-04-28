<template>
  <router-view />
</template>

<style>
/* ─── 全局样式（主题无关） ───────────────────────────────── */
body {
  margin: 0;
  padding: 0;
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Microsoft YaHei', Arial, sans-serif;
}
::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-thumb {
  border-radius: 3px;
}

/* ─── 表格响应式工具类 ───────────────────────────────────── */
@media (max-width: 767px) {
  .hide-mobile {
    display: none !important;
  }
}
@media (max-width: 480px) {
  .hide-xs {
    display: none !important;
  }
}

/* ─── 卡片间距移动端适配 ─────────────────────────────────── */
@media (max-width: 767px) {
  .el-card {
    --el-card-padding: 12px;
  }
  .el-dialog {
    --el-dialog-padding-primary: 16px;
    width: 92% !important;
    max-width: 92% !important;
  }
  .el-message-box {
    width: 85% !important;
    max-width: 85% !important;
  }
}

/* ─── 工具类 ────────────────────────────────────────────── */
.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  align-items: center;
  flex-wrap: wrap;
}
@media (max-width: 767px) {
  .toolbar { gap: 6px; margin-bottom: 12px; }
  .toolbar .el-button { font-size: 12px; }
}
h2 {
  font-size: 20px;
  margin: 0 0 16px 0;
}
@media (max-width: 767px) {
  h2 { font-size: 17px; margin-bottom: 12px; }
}
.text-muted { color: #666; }
</style>
