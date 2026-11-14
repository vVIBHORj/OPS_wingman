/**
 * Centralized API configuration and client helpers for OpsWingman.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function fetchJson<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
  let res: Response;
  try {
    res = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });
  } catch (err: any) {
    if (err instanceof TypeError && (err.message === "Failed to fetch" || err.message.includes("NetworkError"))) {
      throw new Error(
        `Unable to connect to backend at ${API_BASE_URL}. Ensure backend service is reachable on port 8000 and CORS permits this origin.`
      );
    }
    throw err;
  }

  if (!res.ok) {
    let errorDetail = res.statusText;
    try {
      const errorJson = await res.json();
      errorDetail = errorJson.detail || errorJson.error || JSON.stringify(errorJson);
    } catch {
      // fallback to statusText
    }
    throw new Error(`API Error [${res.status}]: ${errorDetail}`);
  }

  return res.json() as Promise<T>;
}
