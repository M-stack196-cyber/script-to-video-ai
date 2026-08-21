import { useState } from "react";
import type { VideoJobWorkflowState, VideoWorkflowStage } from "../types";

interface WorkflowProgressProps {
  workflow: VideoJobWorkflowState;
}

const stages = ["Plan", "Generate", "Download", "Narrate", "Compose", "Done"];

const stageIndex: Record<VideoWorkflowStage, number> = {
  planning: 0,
  waiting_to_submit: 0,
  generating_video: 1,
  downloading: 2,
  generating_audio: 3,
  composing: 4,
  completed: 5,
  failed: -1,
};

export function WorkflowProgress({ workflow }: WorkflowProgressProps) {
  const [copied, setCopied] = useState(false);
  const currentIndex = stageIndex[workflow.stage];
  const progress = Math.max(0, Math.min(100, workflow.job.progress));

  async function copyJobId() {
    await navigator.clipboard?.writeText(workflow.job.job_id);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }

  return (
    <section className="workflow-card" aria-labelledby="workflow-heading">
      <div className="workflow-topline">
        <div>
          <span className="eyebrow">Workflow</span>
          <h2 id="workflow-heading">Production status</h2>
        </div>
        <span className={`job-status status-${workflow.job.status}`}>
          {workflow.job.status.replaceAll("_", " ")}
        </span>
      </div>

      <ol className={`stage-track ${workflow.stage === "failed" ? "failed" : ""}`}>
        {stages.map((stage, index) => (
          <li
            key={stage}
            className={index < currentIndex ? "complete" : index === currentIndex ? "active" : ""}
          >
            <span className="stage-node">{index < currentIndex ? "✓" : index + 1}</span>
            <span>{stage}</span>
          </li>
        ))}
      </ol>

      <div className="progress-meta">
        <p>{workflow.job.message}</p>
        <strong>{progress}%</strong>
      </div>
      <div
        className="progress-bar"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progress}
      >
        <span style={{ width: `${progress}%` }} />
      </div>

      <div className="job-id-row">
        <span>Job</span>
        <code>{workflow.job.job_id}</code>
        <button type="button" onClick={copyJobId} aria-label="Copy job ID">
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </section>
  );
}
