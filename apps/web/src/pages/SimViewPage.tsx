import { useParams } from "react-router";

/** SimView: the 3D engine keeps its own page and DOM; React only frames it. No mission → demo mode. */
export function SimViewPage() {
  const { missionId } = useParams();
  const src = missionId ? `/view3d.html?mission=${encodeURIComponent(missionId)}` : "/view3d.html?demo";
  return <iframe className="sim-view" src={src} title="Vue 3D de la mission" allow="fullscreen" />;
}
