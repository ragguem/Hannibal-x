import { Icon, type IconName } from "../../components/Icon";
import type { Indicator } from "./dashboard-sample";

const ICON_BY_INDICATOR: Record<string, IconName> = {
  fleet: "ship",
  missions: "target",
  ready: "check",
  alerts: "alert",
  weather: "weather",
};

export function IndicatorStrip({ indicators }: { indicators: Indicator[] }) {
  return (
    <ul className="indicator-strip" aria-label="Indicateurs">
      {indicators.map((indicator) => (
        <li key={indicator.id} className={`card indicator ${indicator.tone}`}>
          <span className="indicator-icon">
            <Icon name={ICON_BY_INDICATOR[indicator.id] ?? "gauge"} size={30} />
          </span>
          <span className="indicator-body">
            <b className="indicator-value">{indicator.value}</b>
            <span className="mut">{indicator.label}</span>
            {indicator.progress !== undefined && (
              <span className="meter" aria-hidden="true">
                <span style={{ width: `${String(indicator.progress)}%` }} />
              </span>
            )}
          </span>
          {indicator.trend && <span className="indicator-trend good">↑ {indicator.trend}</span>}
          {indicator.progress !== undefined && <span className="chip">{indicator.progress} %</span>}
        </li>
      ))}
    </ul>
  );
}
