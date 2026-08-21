import type { ConfigStatus } from "../types";

interface ConfigNoticeProps {
  config: ConfigStatus | null;
  loadFailed: boolean;
}

export function ConfigNotice({ config, loadFailed }: ConfigNoticeProps) {
  const notices: string[] = [];
  if (loadFailed) notices.push("Backend readiness could not be checked. You can still edit your script.");
  if (config) {
    if (!config.s3_configured) {
      notices.push("AI video generation is not configured yet. Local demo remains available.");
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
