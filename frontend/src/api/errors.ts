/**
 * Turn a caught error into a clear, user-facing message.
 *
 * Distinguishes actual network failures (offline, unreachable server) from
 * ordinary API/validation errors, so people aren't left staring at a
 * spinner or a cryptic "Failed to fetch" wondering what went wrong.
 */
export function getErrorMessage(err: unknown, fallback: string): string {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) {
    return "You're offline. Check your internet connection and try again."
  }

  // Browsers throw a bare TypeError for fetch()-level failures (DNS
  // failure, connection refused, CORS, etc.) as opposed to ordinary HTTP
  // error responses, which come back as a resolved (non-ok) Response.
  if (err instanceof TypeError) {
    return "Couldn't reach the server. Check your connection and try again."
  }

  if (err instanceof Error && err.message) {
    return err.message
  }

  return fallback
}
