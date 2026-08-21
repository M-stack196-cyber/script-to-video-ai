import type { SceneJob } from "../types";

interface SceneListProps {
  scenes: SceneJob[];
}

export function SceneList({ scenes }: SceneListProps) {
  if (!scenes.length) return null;

  return (
    <section className="scene-section" aria-labelledby="scenes-heading">
      <div className="section-heading-row">
        <div>
          <span className="eyebrow">Scene plan</span>
          <h2 id="scenes-heading">{scenes.length} planned scene{scenes.length === 1 ? "" : "s"}</h2>
        </div>
      </div>
      <div className="scene-list">
        {scenes.map((scene) => (
          <article className="scene-card" key={scene.scene_number}>
            <div className="scene-number">{String(scene.scene_number).padStart(2, "0")}</div>
            <div className="scene-content">
              <div className="scene-title-row">
                <h3>Scene {scene.scene_number}</h3>
                <div className="scene-badges">
                  {scene.duration != null && <span>{scene.duration} sec</span>}
                  <span className={`scene-status status-${scene.status}`}>
                    {scene.status.replaceAll("_", " ")}
                  </span>
                  {scene.video_downloaded && <span className="downloaded">✓ Downloaded</span>}
                </div>
              </div>
              {scene.overlay_text && <p className="overlay-copy">“{scene.overlay_text}”</p>}
              {scene.narration && (
                <div className="scene-copy-block">
                  <span>Narration</span>
                  <p>{scene.narration}</p>
                </div>
              )}
              <details>
                <summary>View video prompt</summary>
                <p>{scene.prompt}</p>
              </details>
              {scene.error && <p className="scene-error">{scene.error}</p>}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
