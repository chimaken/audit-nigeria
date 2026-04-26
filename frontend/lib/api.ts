import type {
  LgaPollingUnitsResponse,
  NationalTotalsResponse,
  PuDetailResponse,
  PuLookupResponse,
  SheetUploadResponse,
  StateDrilldownResponse,
  StateListItem,
} from "./types";

/** Base URL or same-origin path (e.g. `/api-proxy` when using next.config.mjs rewrites). */
const API_BASE = (() => {
  const raw = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
  return raw || "http://localhost:8000";
})();

/** Cross-origin dashboard → App Runner (CloudFront → API). */
const apiFetchInit: RequestInit = { mode: "cors", cache: "no-store" };

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, apiFetchInit);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

export function getApiBase() {
  return API_BASE;
}

export type HealthResponse = {
  status: string;
  /** When false, uploads must include pu_id (vision header read is disabled). */
  openrouter_configured?: boolean;
  /** When true, POST /demo/reset-collated-votes is available (needs X-Dashboard-Reset-Token). */
  reset_collated_votes_enabled?: boolean;
  /** When true, use presign → S3 PUT → complete → poll (see uploadResultSheetAsync). */
  async_upload_enabled?: boolean;
};

export async function fetchHealth(): Promise<HealthResponse> {
  return fetchJson<HealthResponse>("/health");
}

export type ResetCollatedVotesResponse = {
  election_id: number;
  upload_rows_deleted: number;
  cluster_rows_deleted: number;
  national_tally_rows_deleted: number;
  state_tally_rows_deleted: number;
  lga_tally_rows_deleted: number;
  proof_files_removed: number;
};

export async function resetCollatedVotes(
  electionId: number,
  token: string,
): Promise<ResetCollatedVotesResponse> {
  const res = await fetch(
    `${API_BASE}/demo/reset-collated-votes?election_id=${encodeURIComponent(String(electionId))}`,
    {
      ...apiFetchInit,
      method: "POST",
      headers: { "X-Dashboard-Reset-Token": token.trim() },
    },
  );
  const text = await res.text();
  let body: unknown;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!res.ok) {
    const detail =
      typeof body === "object" && body !== null && "detail" in body
        ? (body as { detail: unknown }).detail
        : body;
    const msg =
      typeof detail === "string"
        ? detail
        : detail != null
          ? JSON.stringify(detail).slice(0, 800)
          : text.slice(0, 400);
    throw new Error(`${res.status} ${res.statusText}: ${msg}`);
  }
  return body as ResetCollatedVotesResponse;
}

export async function fetchStates(): Promise<StateListItem[]> {
  return fetchJson<StateListItem[]>("/results/states");
}

export async function fetchNational(electionId: number): Promise<NationalTotalsResponse> {
  return fetchJson<NationalTotalsResponse>(
    `/results/national?election_id=${electionId}`,
  );
}

export async function fetchState(
  stateId: number,
  electionId: number,
): Promise<StateDrilldownResponse> {
  return fetchJson<StateDrilldownResponse>(
    `/results/state/${stateId}?election_id=${electionId}`,
  );
}

export async function fetchLga(
  lgaId: number,
  electionId: number,
): Promise<LgaPollingUnitsResponse> {
  return fetchJson<LgaPollingUnitsResponse>(
    `/results/lga/${lgaId}?election_id=${electionId}`,
  );
}

export async function fetchPu(
  puId: number,
  electionId: number,
): Promise<PuDetailResponse> {
  return fetchJson<PuDetailResponse>(
    `/results/pu/${puId}?election_id=${electionId}`,
  );
}

export async function lookupPuCode(puCode: string): Promise<PuLookupResponse> {
  const q = encodeURIComponent(puCode.trim());
  return fetchJson<PuLookupResponse>(`/results/lookup-pu?pu_code=${q}`);
}

/** Opt out with NEXT_PUBLIC_USE_ASYNC_UPLOAD=false or 0 (e.g. local debugging of sync /upload). */
const ASYNC_UPLOAD_ENV = (process.env.NEXT_PUBLIC_USE_ASYNC_UPLOAD ?? "").trim().toLowerCase();
const CLIENT_FORCES_SYNC_UPLOAD = ASYNC_UPLOAD_ENV === "0" || ASYNC_UPLOAD_ENV === "false";

export type AsyncUploadPresignResponse = {
  job_id: string;
  staging_key: string;
  upload_url: string;
  headers: Record<string, string>;
  expires_in: number;
};

export type AsyncUploadJobResponse = {
  id: string;
  status: string;
  election_id: number;
  pu_id: number | null;
  created_at: string | null;
  updated_at: string | null;
  error_message?: string;
  result?: SheetUploadResponse;
};

/** Fired during `uploadResultSheet` / `uploadResultSheetAsync` for UI progress bars. */
export type SheetUploadProgress = {
  phase:
    | "presign"
    | "s3_upload"
    | "finalize"
    | "processing"
    | "direct_upload"
    | "direct_processing"
    | "done";
  message: string;
  /** 0–100 when known; `null` for indeterminate (server-side work). */
  percent: number | null;
};

function xhrPutFile(
  uploadUrl: string,
  file: File,
  headers: Record<string, string>,
  onUploadProgress?: (loaded: number, total: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", uploadUrl);
    for (const [k, v] of Object.entries(headers)) {
      xhr.setRequestHeader(k, v);
    }
    xhr.upload.onprogress = (evt) => {
      if (evt.lengthComputable && onUploadProgress) {
        onUploadProgress(evt.loaded, evt.total);
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
      } else {
        reject(new Error(`S3 PUT ${xhr.status}: ${xhr.responseText.slice(0, 200)}`));
      }
    };
    xhr.onerror = () => reject(new Error("S3 PUT failed (network)."));
    xhr.onabort = () => reject(new Error("S3 PUT aborted."));
    xhr.send(file);
  });
}

function xhrPostMultipartForm(
  url: string,
  form: FormData,
  onUploadProgress?: (loaded: number, total: number) => void,
  onUploadFinished?: () => void,
): Promise<{ status: number; body: unknown }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.responseType = "text";
    xhr.upload.onprogress = (evt) => {
      if (evt.lengthComputable && onUploadProgress) {
        onUploadProgress(evt.loaded, evt.total);
      }
    };
    xhr.upload.onloadend = () => {
      onUploadFinished?.();
    };
    xhr.onload = () => {
      let body: unknown;
      try {
        body = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        body = xhr.responseText;
      }
      resolve({ status: xhr.status, body });
    };
    xhr.onerror = () => reject(new Error("Upload failed (network)."));
    xhr.onabort = () => reject(new Error("Upload aborted."));
    xhr.send(form);
  });
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const text = await res.text();
  let parsed: unknown;
  try {
    parsed = text ? JSON.parse(text) : null;
  } catch {
    parsed = text;
  }
  if (!res.ok) {
    const detail =
      typeof parsed === "object" && parsed !== null && "detail" in parsed
        ? (parsed as { detail: unknown }).detail
        : parsed;
    const msg =
      typeof detail === "string"
        ? detail
        : detail != null
          ? JSON.stringify(detail).slice(0, 800)
          : text.slice(0, 400);
    throw new Error(`${res.status} ${res.statusText}: ${msg}`);
  }
  return parsed as T;
}

/**
 * Whether the client may use the async pipeline when /health reports async_upload_enabled.
 * Defaults to true so CloudFront builds are not required to set NEXT_PUBLIC_USE_ASYNC_UPLOAD=1
 * (sync POST /upload can hit App Runner's ~120s limit: blur + OpenRouter + S3 on low CPU).
 */
export function clientAsyncUploadPreferred(): boolean {
  return !CLIENT_FORCES_SYNC_UPLOAD;
}

export async function requestAsyncUploadPresign(params: {
  electionId: number;
  file: File;
  puId?: number | null;
  metadata?: string | null;
}): Promise<AsyncUploadPresignResponse> {
  let metadataField: string | Record<string, unknown> | null | undefined;
  if (params.metadata != null && params.metadata.trim()) {
    const s = params.metadata.trim();
    try {
      metadataField = JSON.parse(s) as Record<string, unknown>;
    } catch {
      metadataField = s;
    }
  }
  return postJson<AsyncUploadPresignResponse>("/upload/async/presign", {
    election_id: params.electionId,
    pu_id: params.puId != null && params.puId > 0 ? params.puId : null,
    filename: params.file.name,
    metadata: metadataField ?? null,
  });
}

export async function putFileToPresignedUrl(
  uploadUrl: string,
  file: File,
  headers: Record<string, string>,
  onUploadProgress?: (loaded: number, total: number) => void,
): Promise<void> {
  if (onUploadProgress) {
    await xhrPutFile(uploadUrl, file, headers, onUploadProgress);
    return;
  }
  const res = await fetch(uploadUrl, {
    method: "PUT",
    body: file,
    headers,
    mode: "cors",
    cache: "no-store",
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(`S3 PUT ${res.status}: ${t.slice(0, 200)}`);
  }
}

export async function completeAsyncUpload(jobId: string): Promise<{ job_id: string; status: string }> {
  return postJson("/upload/async/complete", { job_id: jobId });
}

export async function fetchUploadAsyncJob(jobId: string): Promise<AsyncUploadJobResponse> {
  return fetchJson<AsyncUploadJobResponse>(`/upload/async/jobs/${encodeURIComponent(jobId)}`);
}

/** Presign → S3 PUT → enqueue → poll until completed or failed. */
export async function uploadResultSheetAsync(params: {
  electionId: number;
  file: File;
  puId?: number | null;
  metadata?: string | null;
  pollIntervalMs?: number;
  maxWaitMs?: number;
  onProgress?: (p: SheetUploadProgress) => void;
}): Promise<SheetUploadResponse> {
  const onProgress = params.onProgress;
  onProgress?.({
    phase: "presign",
    message: "Preparing your upload…",
    percent: null,
  });
  const presign = await requestAsyncUploadPresign(params);
  onProgress?.({
    phase: "s3_upload",
    message: "Sending your photo…",
    percent: 5,
  });
  await putFileToPresignedUrl(
    presign.upload_url,
    params.file,
    presign.headers,
    onProgress
      ? (loaded, total) => {
          const frac = total > 0 ? loaded / total : 0;
          const pct = Math.min(55, Math.round(5 + frac * 50));
          onProgress({
            phase: "s3_upload",
            message: `Sending photo… ${Math.round(frac * 100)}%`,
            percent: pct,
          });
        }
      : undefined,
  );
  onProgress?.({
    phase: "finalize",
    message: "Handing off to the results checker…",
    percent: 58,
  });
  await completeAsyncUpload(presign.job_id);
  const interval = params.pollIntervalMs ?? 2000;
  const maxWait = params.maxWaitMs ?? 900_000;
  const t0 = Date.now();
  let pollN = 0;
  while (Date.now() - t0 < maxWait) {
    pollN += 1;
    onProgress?.({
      phase: "processing",
      message: `Reading your sheet… this can take a few minutes (step ${pollN})`,
      percent: null,
    });
    const job = await fetchUploadAsyncJob(presign.job_id);
    if (job.status === "completed" && job.result) {
      onProgress?.({ phase: "done", message: "Done", percent: 100 });
      return job.result;
    }
    if (job.status === "failed") {
      const msg = job.error_message ?? JSON.stringify(job.result ?? {});
      throw new Error(msg);
    }
    await new Promise((r) => setTimeout(r, interval));
  }
  throw new Error("This is taking too long. Please try again or contact support.");
}

export async function uploadResultSheet(params: {
  electionId: number;
  file: File;
  puId?: number | null;
  metadata?: string | null;
  onProgress?: (p: SheetUploadProgress) => void;
}): Promise<SheetUploadResponse> {
  const form = new FormData();
  form.append("election_id", String(params.electionId));
  if (params.puId != null && params.puId > 0) {
    form.append("pu_id", String(params.puId));
  }
  if (params.metadata != null && params.metadata.trim()) {
    form.append("metadata", params.metadata.trim());
  }
  form.append("file", params.file);

  const onProgress = params.onProgress;

  if (onProgress) {
    onProgress({
      phase: "direct_upload",
      message: "Sending your photo…",
      percent: 0,
    });
    const { status, body } = await xhrPostMultipartForm(
      `${API_BASE}/upload`,
      form,
      (loaded, total) => {
        const pct = total > 0 ? Math.min(88, Math.round((85 * loaded) / total)) : 0;
        onProgress({
          phase: "direct_upload",
          message: `Sending… ${Math.round(total > 0 ? (100 * loaded) / total : 0)}%`,
          percent: pct,
        });
      },
      () => {
        onProgress({
          phase: "direct_processing",
          message: "Checking your sheet… this may take a minute or two.",
          percent: null,
        });
      },
    );
    if (!status || status < 200 || status >= 300) {
      const detail =
        typeof body === "object" && body !== null && "detail" in body
          ? (body as { detail: unknown }).detail
          : body;
      const msg =
        typeof detail === "string"
          ? detail
          : detail != null
            ? JSON.stringify(detail).slice(0, 800)
            : String(body).slice(0, 400);
      throw new Error(`${status}: ${msg}`);
    }
    onProgress({ phase: "done", message: "Done", percent: 100 });
    return body as SheetUploadResponse;
  }

  const res = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    body: form,
    mode: "cors",
    cache: "no-store",
  });
  const text = await res.text();
  let body: unknown;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!res.ok) {
    const detail =
      typeof body === "object" && body !== null && "detail" in body
        ? (body as { detail: unknown }).detail
        : body;
    const msg =
      typeof detail === "string"
        ? detail
        : detail != null
          ? JSON.stringify(detail).slice(0, 800)
          : text.slice(0, 400);
    throw new Error(`${res.status} ${res.statusText}: ${msg}`);
  }
  return body as SheetUploadResponse;
}
