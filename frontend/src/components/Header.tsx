interface HeaderProps {
  backendConnected: boolean | null;
  demoUrl: string;
  localDemoAvailable: boolean;
  appEnv: string | null;
  hasJob: boolean;
  onNewVideo: () => void;
}

export function Header({
  backendConnected,
  demoUrl,
  localDemoAvailable,
  appEnv,
  hasJob,
  onNewVideo,
}: HeaderProps) {
  const connectionLabel =
    backendConnected === null
      ? "Checking backend"
      : backendConnected
        ? "Backend connected"
        : "Backend unavailable";

  return (
    <header className="app-header">
      <div className="brand-lockup">
        <div className="brand-mark" aria-hidden="true">
          <span />
        </div>
        <div>
          <h1>Script-to-Video AI</h1>
          <p>Turn scripts into AI-generated narrated video.</p>
        </div>
      </div>
      <div className="header-actions">
        <span
          className={`connection-status ${backendConnected === false ? "offline" : ""}`}
          title={connectionLabel}
        >
          <span className="status-dot" aria-hidden="true" />
          {connectionLabel}
        </span>
        {localDemoAvailable ? (
          <a className="button secondary compact" href={demoUrl} target="_blank" rel="noreferrer">
            Local fallback demo
          </a>
        ) : appEnv === "production" ? (
          <span className="demo-unavailable" title="The FFmpeg fallback is for local development only.">
            Local demo unavailable in production
          </span>
        ) : null}
        {hasJob && (
          <button className="button ghost compact" type="button" onClick={onNewVideo}>
            New Video
          </button>
        )}
      </div>
    </header>
  );
}
