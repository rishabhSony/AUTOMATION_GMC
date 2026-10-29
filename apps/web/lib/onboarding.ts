// First-run product tour (/onboarding). Dismissal is remembered per browser in
// localStorage (user decision); App Flow's Clerk-metadata flag isn't used.
const KEY = "qp_onboarding_v1_done";

/** True once the tour was finished or skipped. Unreadable storage counts as done, so a
 *  blocked or private-mode browser isn't sent to the tour on every visit. */
export function isOnboardingDone(): boolean {
  try {
    return window.localStorage.getItem(KEY) !== null;
  } catch {
    return true;
  }
}

export function markOnboardingDone(): void {
  try {
    window.localStorage.setItem(KEY, new Date().toISOString());
  } catch {
    // storage unavailable: the tour may show again, which is harmless
  }
}
