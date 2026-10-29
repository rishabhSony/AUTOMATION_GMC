"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback } from "react";

import { useSessionUser } from "@/components/providers/session-user";
import type { ExportResult } from "@/lib/api/types";
import { DEV_MOCK_AUTH } from "@/lib/dev-mode";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: unknown,
  ) {
    super(ApiError.describe(status, detail));
  }

  /** FastAPI errors: `detail` is a string, `{message}`, or a 422 validation list. */
  static describe(status: number, detail: unknown): string {
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail))
      return detail
        .map((d: { msg?: string; loc?: unknown[] }) =>
          [d.loc?.slice(1).join("."), d.msg].filter(Boolean).join(": "),
        )
        .join("; ");
    if (detail && typeof detail === "object" && "message" in detail)
      return String((detail as { message: unknown }).message);
    return `Request failed (${status})`;
  }
}

/** Encodes a path segment that may contain "/" (field and procedure names). */
export const segment = (value: string) => encodeURIComponent(value);

function toQuery(params?: Record<string, unknown>): string {
  if (!params) return "";
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    for (const v of Array.isArray(value) ? value : [value])
      qs.append(key, String(v));
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH";
  params?: Record<string, unknown>;
  body?: unknown;
  form?: FormData; // multipart uploads (the browser sets the boundary header)
};

/**
 * Fetcher for the FastAPI backend: every call carries the Clerk session token as
 * `Authorization: Bearer …`, which the API verifies against Clerk's JWKS.
 */
type AuthHeaders = () => Promise<Record<string, string>>;

function useClerkHeaders(): AuthHeaders {
  const { getToken } = useAuth();
  return useCallback(async (): Promise<Record<string, string>> => {
    const token = await getToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, [getToken]);
}

/** Dev mock mode: identifies the mock user to an API running ENABLE_DEV_MOCK_AUTH=true. */
function useDevMockHeaders(): AuthHeaders {
  const { id, role } = useSessionUser();
  return useCallback(
    async () => ({ "X-Dev-User-Id": id, "X-Dev-User-Role": role }),
    [id, role],
  );
}

// Chosen once at build time: Clerk's hooks need a ClerkProvider, absent in mock mode.
const useAuthHeaders = DEV_MOCK_AUTH ? useDevMockHeaders : useClerkHeaders;

export function useApi() {
  const authHeaders = useAuthHeaders();

  const request = useCallback(
    async (
      path: string,
      { method = "GET", params, body, form }: RequestOptions = {},
    ) => {
      const res = await fetch(`${API_URL}${path}${toQuery(params)}`, {
        method,
        headers: {
          ...(await authHeaders()),
          ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        },
        body: form ?? (body !== undefined ? JSON.stringify(body) : undefined),
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => null);
        throw new ApiError(res.status, payload?.detail ?? null);
      }
      return res;
    },
    [authHeaders],
  );

  const json = useCallback(
    async <T>(path: string, options?: RequestOptions): Promise<T> =>
      (await request(path, options)).json() as Promise<T>,
    [request],
  );

  /** Downloads a file response (exports) using the server-provided filename. */
  /** Raw file bytes (e.g. the source-document preview). */
  const blob = useCallback(
    async (path: string): Promise<Blob> => (await request(path)).blob(),
    [request],
  );

  /** Downloads a file response (exports) using the server-provided filename. */
  const download = useCallback(
    async (path: string): Promise<ExportResult> => {
      const res = await request(path);
      const disposition = res.headers.get("Content-Disposition") ?? "";
      const filename =
        /filename="([^"]+)"/.exec(disposition)?.[1] ?? "export.xlsx";
      const url = URL.createObjectURL(await res.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link); // Firefox needs the link in the document
      link.click();
      link.remove();
      // Revoking synchronously can cancel the download in some browsers.
      setTimeout(() => URL.revokeObjectURL(url), 30_000);
      return { filename, auditLogId: res.headers.get("X-Audit-Log-Id") };
    },
    [request],
  );

  return { json, blob, download };
}
