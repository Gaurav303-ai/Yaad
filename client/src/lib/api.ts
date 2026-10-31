// TODO: Add typed API request helpers.
const apiBaseUrl = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

export async function apiRequest<ResponseT>(
  path: string,
  init?: RequestInit,
): Promise<ResponseT> {
  const response = await fetch(`${apiBaseUrl}${path}`, init)
  if (!response.ok) {
    let message = `API request failed (${response.status}).`
    try {
      const body: unknown = await response.json()
      if (
        typeof body === 'object' &&
        body !== null &&
        'detail' in body &&
        typeof body.detail === 'string'
      ) {
        message = body.detail
      }
    } catch {
      message = `API request failed (${response.status}).`
    }
    throw new Error(message)
  }
  return (await response.json()) as ResponseT
}
