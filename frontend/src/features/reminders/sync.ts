import { savePushSubscription } from '../../api'

// A browser keeps its push subscription across fields: after "Delete my data" and a new
// registration (or a second field on the same phone) the subscription exists, but the
// server has it under no token or another one. Saving it again for this field makes the
// "on" state true. The server stores a subscription once per endpoint, so repeats are harmless.
export async function syncExistingSubscription(
  token: string,
  registration: ServiceWorkerRegistration,
  save: (token: string, subscription: PushSubscriptionJSON) => Promise<void> = savePushSubscription,
): Promise<boolean> {
  const existing = await registration.pushManager.getSubscription()
  if (!existing) return false
  try {
    await save(token, existing.toJSON())
    return true
  } catch {
    return false
  }
}
