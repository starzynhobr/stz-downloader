/** "rar", ".RAR " and "*.rar" all become ".rar"; anything else is rejected. */
export function normalizeExtension(raw: string): string | null {
  const clean = raw.trim().toLowerCase().replace(/^\*?\.?/, '')
  return /^[a-z0-9]{1,10}$/.test(clean) ? `.${clean}` : null
}
