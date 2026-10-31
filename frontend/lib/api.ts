import useSWR, { type SWRConfiguration } from "swr";

export type Freshness = "live" | "delayed" | "historical" | "estimated" | "reference" | "unavailable";
export type Meta = { source: string[]; freshness: Freshness; as_of: string | null; fetched_at: string | null; stale: boolean; note: string | null };
export type Envelope<T> = { data: T; meta: Meta };

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

async function parse(res: Response) {
  if (res.status === 204) return null;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail;
    throw new ApiError(typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : `Request failed (${res.status})`, res.status);
  }
  return body;
}

export const get = (url: string) => fetch(url).then(parse);

export const send = (url: string, method: string, body?: unknown) =>
  fetch(url, { method, headers: { "content-type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) }).then(parse);

export const upload = (url: string, file: File) => {
  const form = new FormData();
  form.append("file", file);
  return fetch(url, { method: "POST", body: form }).then(parse);
};

export function useApi<T>(url: string | null, opts?: SWRConfiguration) {
  return useSWR<T>(url, get, { revalidateOnFocus: false, shouldRetryOnError: false, ...opts });
}

export const useEnvelope = <T,>(url: string | null, opts?: SWRConfiguration) => useApi<Envelope<T>>(url, opts);
