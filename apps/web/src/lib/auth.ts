/**
 * Provider-independent authentication plumbing.
 *
 * Demo mode keeps the synthetic identity header. Production mode never sends it:
 * a verified bearer token is required instead, and it is held by this module only
 * after the future OpenID Connect callback stores it. There is deliberately no
 * fake login form here.
 */

export type AuthMode = "demo" | "production";

export const AUTH_MODE: AuthMode =
  process.env.NEXT_PUBLIC_AUTH_MODE === "production" ? "production" : "demo";

let accessToken: string | null = null;

/** Called by the provider callback once a real token has been obtained. */
export function setAccessToken(token: string | null) {
  accessToken = token?.trim() || null;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function clearAccessToken() {
  accessToken = null;
}

/** Authorization headers for production mode; empty in demo mode. */
export function authHeaders(): Record<string, string> {
  if (AUTH_MODE !== "production") return {};
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
