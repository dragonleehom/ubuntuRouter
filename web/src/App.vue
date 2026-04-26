<template>
  <router-view />
</template>

<style>
/* ─── 全局样式 ───────────────────────────────────────────── */
body {
  margin: 0;
  padding: 0;
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Microsoft YaHei', Arial, sans-serif;
  background-color: #0a0a0a;
  color: #e0e0e0;
}
::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 3px;
}

/* ─── 表格响应式工具类 ───────────────────────────────────── */
/* 在小屏上隐藏指定列 */
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

/* ─── Element Plus 暗色主题表格适应 ─────────────────────── */
.el-table--striped .el-table__body tr.el-table__row--striped td {
  background: rgba(255,255,255,0.02);
}
.el-table--striped .el-table__body tr.el-table__row--striped:hover td {
  background: rgba(255,255,255,0.05);
}
.el-table th.el-table__cell {
  background-color: #1a1a1a !important;
  color: #888 !important;
}
.el-table td.el-table__cell {
  background-color: #141414 !important;
  color: #ccc !important;
}
.el-table--enable-row-hover .el-table__body tr:hover > td {
  background-color: #1e1e1e !important;
}
.el-table__body tr.current-row > td {
  background-color: #1a2633 !important;
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
/* 页面标题 */
h2 {
  font-size: 20px;
  margin: 0 0 16px 0;
  color: #e0e0e0;
}
@media (max-width: 767px) {
  h2 { font-size: 17px; margin-bottom: 12px; }
}
/* 空状态 */
.text-muted { color: #666; }
</style>
