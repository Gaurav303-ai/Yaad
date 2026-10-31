// TODO: Add typed API request helpers.
const apiBaseUrl: string = import.meta.env.VITE_API_URL ?? ''

export async function apiRequest<ResponseT>(
  path: string,
  init?: RequestInit,
): Promise<ResponseT> {
  const response = await fetch(`${apiBaseUrl}${path}`, init)
  if (!response.ok) {
    throw new Error(`API request failed with status ${response.status}.`)
  }
  return (await response.json()) as ResponseT
}
