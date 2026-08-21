import type { ConfigStatus, DeploymentReadiness } from "../types";

interface ConfigNoticeProps {
  config: ConfigStatus | null;
  loadFailed: boolean;
  readiness: DeploymentReadiness | null;
  readinessFailed: boolean;
}

export function ConfigNotice({
  config,
  loadFailed,
  readiness,
  readinessFailed,
}: ConfigNoticeProps) {
  const notices: string[] = [];
  if (loadFailed) notices.push("Backend configuration could not be checked. You can still edit your script.");
  if (readiness?.app_env === "production" && !readiness.ready) {
    notices.push("Backend production setup incomplete");
    notices.push(...readiness.blockers);
  } else if (readinessFailed) {
    notices.push("Deployment readiness is unavailable; the page remains usable.");
  }
  if (config) {
    if (!config.s3_configured) {
      notices.push(
        config.local_media_enabled
          ? "AI video generation is not configured yet."
          : "AI video generation is not configured yet; local media is disabled.",
      );
    }
    if (!config.video_model_configured) notices.push("Nova Reel model is not configured.");
    if (config.narration_provider === "local") notices.push("Local narration fallback is active.");
    if (config.narration_provider === "nova-sonic") notices.push("Nova Sonic narration is selected.");
  }
  if (!notices.length) return null;

  return (
    <aside className="config-notice" aria-label="Configuration notice">
      <span className="notice-icon" aria-hidden="true">i</span>
      <div>
        {notices.map((notice) => <p key={notice}>{notice}</p>)}
      </div>
    </aside>
  );
}
