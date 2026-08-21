import { resolveMediaUrl } from "../api";

interface VideoResultProps {
  videoUrl: string;
  title?: string;
  badge?: string;
  helperText?: string;
  metadata?: string[];
}

export function VideoResult({
  videoUrl,
  title = "Your video is ready",
  badge,
  helperText,
  metadata = [],
}: VideoResultProps) {
  const resolvedUrl = resolveMediaUrl(videoUrl);

  return (
    <section className="result-card" aria-labelledby="result-heading">
      <div className="success-icon" aria-hidden="true">✓</div>
      <div className="result-heading-copy">
        <span className="eyebrow">{badge || "Complete"}</span>
        <h2 id="result-heading">{title}</h2>
      </div>
      {helperText && <p className="result-helper">{helperText}</p>}
      {metadata.length > 0 && (
        <div className="result-metadata" aria-label="Video details">
          {metadata.map((item) => <span key={item}>{item}</span>)}
        </div>
      )}
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
