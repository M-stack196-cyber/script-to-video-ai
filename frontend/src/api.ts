import type {
  ConfigStatus,
  CreateWorkflowPayload,
  DemoRenderResponse,
  DeploymentReadiness,
  VideoJobWorkflowState,
} from "./types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "";

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function detailMessage(payload: unknown): string | null {
  if (!payload || typeof payload !== "object" || !("detail" in payload)) {
    return null;
  }
  const detail = (payload as { detail: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (!item || typeof item !== "object" || !("msg" in item)) return null;
        return String((item as { msg: unknown }).msg);
      })
      .filter((message): message is string => Boolean(message));
    return messages.length ? messages.join(". ") : null;
  }
  return null;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  signal?: AbortSignal,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...options, signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new Error("Unable to reach the video backend. Check that it is running.");
  }

  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      // Raw HTML/text errors are intentionally not exposed to the UI.
    }
    throw new ApiError(
      detailMessage(payload) || `Request failed with status ${response.status}.`,
      response.status,
    );
  }
  return (await response.json()) as T;
}

export function createWorkflowJob(
  payload: CreateWorkflowPayload,
  signal?: AbortSignal,
): Promise<VideoJobWorkflowState> {
  return request(
    "/api/workflow/jobs",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    signal,
  );
}

export function getWorkflowJob(
  jobId: string,
  signal?: AbortSignal,
): Promise<VideoJobWorkflowState> {
  return request(`/api/workflow/jobs/${encodeURIComponent(jobId)}`, {}, signal);
}

export function advanceWorkflowJob(
  jobId: string,
  signal?: AbortSignal,
): Promise<VideoJobWorkflowState> {
  return request(
    `/api/workflow/jobs/${encodeURIComponent(jobId)}/advance`,
    { method: "POST" },
    signal,
  );
}

export function getConfigStatus(signal?: AbortSignal): Promise<ConfigStatus> {
  return request("/api/config/status", {}, signal);
}

export function getDeploymentReadiness(
  signal?: AbortSignal,
): Promise<DeploymentReadiness> {
  return request("/api/deployment/readiness", {}, signal);
}

export function renderLocalDemo(
  payload: CreateWorkflowPayload,
  signal?: AbortSignal,
): Promise<DemoRenderResponse> {
  return request(
    "/api/video/demo-render",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    signal,
  );
}

export function resolveMediaUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  if (path.startsWith("/")) return `${API_BASE_URL}${path}`;
  return `${API_BASE_URL}/${path}`;
}
