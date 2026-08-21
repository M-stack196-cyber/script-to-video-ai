import { resolveMediaUrl } from "../api";

interface VideoResultProps {
  videoUrl: string;
}

export function VideoResult({ videoUrl }: VideoResultProps) {
  const resolvedUrl = resolveMediaUrl(videoUrl);

  return (
    <section className="result-card" aria-labelledby="result-heading">
      <div className="success-icon" aria-hidden="true">✓</div>
      <div className="result-heading-copy">
        <span className="eyebrow">Complete</span>
        <h2 id="result-heading">Your video is ready</h2>
      </div>
      <video controls preload="metadata" src={resolvedUrl}>
        Your browser does not support HTML5 video.
      </video>
      <div className="result-actions">
        <a className="button primary" href={resolvedUrl} download>
          Download Video
        </a>
        <a className="button secondary" href={resolvedUrl} target="_blank" rel="noreferrer">
          Open Video
        </a>
      </div>
    </section>
  );
}
