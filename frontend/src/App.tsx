import { useEffect, useMemo, useState } from "react";
import {
  ApiError,
  advanceWorkflowJob,
  createWorkflowJob,
  getConfigStatus,
  getWorkflowJob,
  resolveMediaUrl,
} from "./api";
import { ConfigNotice } from "./components/ConfigNotice";
import { ErrorAlert } from "./components/ErrorAlert";
import { Header } from "./components/Header";
import { SceneList } from "./components/SceneList";
import { ScriptForm } from "./components/ScriptForm";
import { VideoResult } from "./components/VideoResult";
import { WorkflowProgress } from "./components/WorkflowProgress";
import type {
  ConfigStatus,
  CreateWorkflowPayload,
  VideoJobNextAction,
  VideoJobWorkflowState,
} from "./types";

const JOB_STORAGE_KEY = "script-to-video-current-job";

const actionLabels: Partial<Record<VideoJobNextAction, string>> = {
  submit_video: "Start AI Video Generation",
  refresh: "Check Generation Status",
  download_video: "Download Generated Scenes",
  compose: "Create Final Video",
};

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "An unexpected error occurred. Please try again.";
}

export default function App() {
  const [workflow, setWorkflow] = useState<VideoJobWorkflowState | null>(null);
  const [config, setConfig] = useState<ConfigStatus | null>(null);
  const [configFailed, setConfigFailed] = useState(false);
  const [backendConnected, setBackendConnected] = useState<boolean | null>(null);
  const [creating, setCreating] = useState(false);
  const [advancing, setAdvancing] = useState(false);
  const [recovering, setRecovering] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [formKey, setFormKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getConfigStatus(controller.signal)
      .then((result) => {
        setConfig(result);
        setConfigFailed(false);
        setBackendConnected(true);
      })
      .catch((requestError: unknown) => {
        if (requestError instanceof DOMException && requestError.name === "AbortError") return;
        setConfigFailed(true);
        setBackendConnected(false);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const jobId = localStorage.getItem(JOB_STORAGE_KEY);
    if (!jobId) {
      setRecovering(false);
      return;
    }
    const controller = new AbortController();
    getWorkflowJob(jobId, controller.signal)
      .then((result) => {
        setWorkflow(result);
        setBackendConnected(true);
      })
      .catch((requestError: unknown) => {
        if (requestError instanceof DOMException && requestError.name === "AbortError") return;
        if (requestError instanceof ApiError && requestError.status === 404) {
          localStorage.removeItem(JOB_STORAGE_KEY);
        } else {
          setError(`Could not restore the current job. ${errorMessage(requestError)}`);
        }
      })
      .finally(() => setRecovering(false));
    return () => controller.abort();
  }, []);

  async function handleCreate(payload: CreateWorkflowPayload) {
    setCreating(true);
    setError(null);
    try {
      const result = await createWorkflowJob(payload);
      setWorkflow(result);
      localStorage.setItem(JOB_STORAGE_KEY, result.job.job_id);
      setBackendConnected(true);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setCreating(false);
    }
  }

  async function handleAdvance() {
    if (!workflow || advancing) return;
    setAdvancing(true);
    setError(null);
    try {
      const result = await advanceWorkflowJob(workflow.job.job_id);
      setWorkflow(result);
      localStorage.setItem(JOB_STORAGE_KEY, result.job.job_id);
    } catch (requestError) {
      // Preserve the last known job state so the user can retry or recover later.
      setError(errorMessage(requestError));
    } finally {
      setAdvancing(false);
    }
  }

  function handleNewVideo() {
    localStorage.removeItem(JOB_STORAGE_KEY);
    setWorkflow(null);
    setError(null);
    setFormKey((current) => current + 1);
  }

  const actionLabel = workflow ? actionLabels[workflow.next_action] : undefined;
  const finalVideoUrl =
    workflow?.job.status === "completed" ? workflow.job.final_video_url : null;
  const helperText = useMemo(() => {
    if (workflow?.next_action === "refresh") {
      return "Video generation runs asynchronously. Check status when ready.";
    }
    if (workflow?.next_action === "submit_video") {
      return "This action starts paid AI video generation for every planned scene.";
    }
    return null;
  }, [workflow?.next_action]);

  return (
    <div className="app-shell">
      <Header
        backendConnected={backendConnected}
        demoUrl={resolveMediaUrl("/demo")}
        hasJob={Boolean(workflow)}
        onNewVideo={handleNewVideo}
      />

      <main>
        <ConfigNotice config={config} loadFailed={configFailed} />
        {error && <ErrorAlert message={error} onDismiss={() => setError(null)} />}

        <div className="studio-grid">
          <ScriptForm
            key={formKey}
            disabled={creating || recovering}
            locked={Boolean(workflow)}
            onSubmit={handleCreate}
          />

          <section className="workspace-panel" aria-label="Video workflow workspace">
            {recovering ? (
              <div className="empty-state" aria-live="polite">
                <span className="loader-orbit" aria-hidden="true" />
                <h2>Restoring your workspace</h2>
                <p>Checking for a saved video job…</p>
              </div>
            ) : workflow ? (
              <>
                <WorkflowProgress workflow={workflow} />
                {workflow.job.error && (
                  <ErrorAlert message={workflow.job.error} />
                )}
                {actionLabel && (
                  <div className="next-action-card">
                    <div>
                      <span className="eyebrow">Next action</span>
                      <p>{helperText || "Continue the workflow when you’re ready."}</p>
                    </div>
                    <button
                      className="button primary action-button"
                      type="button"
                      disabled={advancing}
                      onClick={handleAdvance}
                    >
                      {advancing && <span className="spinner" aria-hidden="true" />}
                      {advancing ? "Working…" : actionLabel}
                    </button>
                  </div>
                )}
                {workflow.next_action === "none" && !workflow.is_terminal && (
                  <p className="passive-status" aria-live="polite">
                    This stage is currently being processed. Refresh this page to restore its latest state.
                  </p>
                )}
                <SceneList scenes={workflow.job.scenes} />
                {finalVideoUrl && <VideoResult videoUrl={finalVideoUrl} />}
              </>
            ) : (
              <div className="empty-state">
                <div className="empty-visual" aria-hidden="true">
                  <span className="play-triangle" />
                  <i className="orbit orbit-one" />
                  <i className="orbit orbit-two" />
                </div>
                <span className="eyebrow">Your workspace</span>
                <h2>Ready when your script is</h2>
                <p>
                  Add your script and choose a format. Your scene plan and production workflow will appear here.
                </p>
                <div className="empty-features">
                  <span>Scene planning</span>
                  <span>Explicit generation</span>
                  <span>Narrated MP4</span>
                </div>
              </div>
            )}
          </section>
        </div>
      </main>
      <footer>
        <span>Script-to-Video AI Studio</span>
        <span>Workflow actions run one step at a time.</span>
      </footer>
    </div>
  );
}
