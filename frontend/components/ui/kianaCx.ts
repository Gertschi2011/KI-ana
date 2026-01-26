export function kianaCx(...parts: Array<string | undefined | null | false>) {
  return parts.filter(Boolean).join(' ')
}
