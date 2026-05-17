export const DASHBOARD_PATH = '/dash'

const AUTH_PATHS = new Set(['/', '/login', '/register'])

export function authReturnPath(from: string | undefined): string {
  if (!from || AUTH_PATHS.has(from)) return DASHBOARD_PATH
  return from
}
