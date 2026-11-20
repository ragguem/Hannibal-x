import type { ShipStatus } from "./dashboard-sample";

export const SHIP_STATUS_LABEL: Record<ShipStatus, string> = {
  at_sea: "En mer",
  in_transit: "En transit",
  offline: "Hors ligne",
};
