<template>
  <div class="page">
    <h2>防火墙</h2>
    <p class="text-muted">防火墙配置将通过 CLI 在后续 Sprint 中实现完整 Web 管理界面。</p>

    <el-card class="config-card">
      <template #header>
        <span>当前防火墙 Zone</span>
      </template>
      <el-empty description="CLI 查看: sudo nft list ruleset" />
    </el-card>
  </div>
</template>

<style scoped>
h2 { color: #e0e0e0; }
.config-card { margin-top: 16px; }
.text-muted { color: #666; }
</style>
