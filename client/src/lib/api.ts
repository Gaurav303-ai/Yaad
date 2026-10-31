// TODO: Add typed API request helpers.
const apiBaseUrl = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

export function apiUrl(path: string): string {
  return `${apiBaseUrl}${path}`
}

export async function apiRequest<ResponseT>(
  path: string,
  init?: RequestInit,
): Promise<ResponseT> {
  let response: Response
  try {
    response = await fetch(apiUrl(path), init)
  } catch (requestError: unknown) {
    if (!(requestError instanceof TypeError)) throw requestError
    const apiTarget = apiBaseUrl || 'the Vite /api proxy'
    throw new Error(
      `Could not reach the Yaad API at ${apiTarget}. Make sure the FastAPI server is running on port 8000.`,
    )
  }
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
