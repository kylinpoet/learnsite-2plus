<script setup lang="ts">
import GovernanceOpsPanel from '../../components/admin/GovernanceOpsPanel.vue'
import MigrationAdminPanel from '../../components/admin/MigrationAdminPanel.vue'
import SchoolIdentityPanel from '../../components/admin/SchoolIdentityPanel.vue'
import { useSession } from '../../composables/useSession'

const { sessionState } = useSession()
</script>

<template>
  <div
    v-if="sessionState?.role === 'school_admin' || sessionState?.role === 'platform_admin'"
    class="stack"
  >
    <SchoolIdentityPanel />
    <GovernanceOpsPanel />
    <MigrationAdminPanel />
  </div>

  <div v-else class="empty-state">
    当前教师账号没有治理后台权限。
  </div>
</template>
