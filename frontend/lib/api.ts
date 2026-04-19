export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Helper to get the JWT token from localStorage
 */
export const getToken = () => typeof window !== "undefined" ? localStorage.getItem("omni_token") : null;

/**
 * Core fetch wrapper with auth header support
 */
export async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorMsg = "API Error";
    try {
      const errData = await response.json();
      errorMsg = errData?.error?.message || errData?.detail || response.statusText;
    } catch {
      errorMsg = response.statusText;
    }
    throw new Error(errorMsg);
  }

  // Some endpoints (like DELETE) might return 204 No Content
  if (response.status === 204) return {} as T;

  return response.json();
}
