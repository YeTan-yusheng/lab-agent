import { ref } from 'vue'
import { getAuditPendingCountApi } from '@/api/reservation'
import { useUser } from '@/utils/user'
import Capability from '@/utils/permissions'

const pendingCount = ref(0)

export function useAuditPendingCount() {
  const { can } = useUser()

  const refresh = async () => {
    if (!can(Capability.AUDIT_RESERVATION)) {
      pendingCount.value = 0
      return
    }

    try {
      const res = await getAuditPendingCountApi()
      if (res.code === 200) {
        pendingCount.value = res.data?.count ?? 0
      }
    } catch {}
  }

  return { pendingCount, refresh }
}
