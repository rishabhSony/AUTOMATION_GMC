"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback } from "react";

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
};

/**
 * Fetcher for the FastAPI backend: every call carries the Clerk session token as
 * `Authorization: Bearer …`, which the API verifies against Clerk's JWKS.
 */
export function useApi() {
  const { getToken } = useAuth();

  const request = useCallback(
    async (
      path: string,
      { method = "GET", params, body }: RequestOptions = {},
    ) => {
      const token = await getToken();
      const res = await fetch(`${API_URL}${path}${toQuery(params)}`, {
        method,
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        },
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => null);
        throw new ApiError(res.status, payload?.detail ?? null);
      }
      return res;
    },
    [getToken],
  );

  const json = useCallback(
    async <T>(path: string, options?: RequestOptions): Promise<T> =>
      (await request(path, options)).json() as Promise<T>,
    [request],
  );

  /** Downloads a file response (exports) using the server-provided filename. */
  const download = useCallback(
    async (path: string): Promise<string> => {
      const res = await request(path);
      const disposition = res.headers.get("Content-Disposition") ?? "";
      const filename =
        /filename="([^"]+)"/.exec(disposition)?.[1] ?? "export.xlsx";
      const url = URL.createObjectURL(await res.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
      return filename;
    },
    [request],
  );

  return { json, download };
}
