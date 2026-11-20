import { useState } from "react";
import { AlertsPanel } from "../features/dashboard/AlertsPanel";
import {
  SAMPLE_ALERT_ZONE,
  SAMPLE_ALERTS,
  SAMPLE_EVENTS,
  SAMPLE_FLAGSHIP,
  SAMPLE_FLEET,
  SAMPLE_INDICATORS,
  SAMPLE_MISSIONS,
  SAMPLE_SHIP_DETAIL,
} from "../features/dashboard/dashboard-sample";
import { EventLogPanel } from "../features/dashboard/EventLogPanel";
import { FleetPanel } from "../features/dashboard/FleetPanel";
import { IndicatorStrip } from "../features/dashboard/IndicatorStrip";
import { MissionsPanel } from "../features/dashboard/MissionsPanel";
import { OperationalMap } from "../features/dashboard/OperationalMap";
import { ShipDetailPanel } from "../features/dashboard/ShipDetailPanel";
import { View3dPreview } from "../features/dashboard/View3dPreview";
import { hasPermission, useSession } from "../features/session/use-session";

/** Landing screen after sign-in. Mock-up: every panel shows invented figures until its feature is wired. */
export function DashboardPage() {
  const { data: session } = useSession();
  const [selectedShip, setSelectedShip] = useState(SAMPLE_FLAGSHIP.name);
  const ship = SAMPLE_FLEET.find((s) => s.name === selectedShip) ?? SAMPLE_FLAGSHIP;

  return (
    <main className="page dashboard">
      <h1 className="visually-hidden">Tableau de bord</h1>
      <p className="chip warn sample-note">Maquette : données d'illustration</p>
      <IndicatorStrip indicators={SAMPLE_INDICATORS} />
      <div className="dash-grid">
        <div className="dash-side">
          <MissionsPanel missions={SAMPLE_MISSIONS} />
          <FleetPanel ships={SAMPLE_FLEET} selected={ship.name} onSelect={setSelectedShip} />
        </div>
        <OperationalMap ships={SAMPLE_FLEET} zone={SAMPLE_ALERT_ZONE} selected={ship.name} onSelect={setSelectedShip} />
        <ShipDetailPanel ship={ship} detail={SAMPLE_SHIP_DETAIL} />
        <EventLogPanel events={SAMPLE_EVENTS} seeAllTo={hasPermission(session, "audit:read") ? "/registre" : undefined} />
        <View3dPreview />
        <AlertsPanel alerts={SAMPLE_ALERTS} />
      </div>
    </main>
  );
}
