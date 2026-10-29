/** Accepts only same-origin relative paths, so `?redirect=` can't be used as an open redirect. */
export function safeRedirectPath(
  value: string | string[] | undefined,
  fallback = "/dashboard",
) {
  const path = Array.isArray(value) ? value[0] : value;
  if (
    !path ||
    !path.startsWith("/") ||
    path.startsWith("//") ||
    path.startsWith("/\\")
  ) {
    return fallback;
  }
  return path;
}
