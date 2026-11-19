import type { RouteObject } from "react-router";
import { LoginPage } from "../pages/LoginPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { SetupPage } from "../pages/SetupPage";
import { RequirePermission, RequireSession } from "./guards";
import { Layout } from "./Layout";

/** Console and 3D view are split out: the setup screen must not download the radar, nor three.js. */
export const routes: RouteObject[] = [
  { path: "/login", element: <LoginPage /> },
  {
    element: <RequireSession />,
    children: [
      {
        element: <Layout />,
        children: [
          {
            index: true,
            element: (
              <RequirePermission permission="mission:play">
                <SetupPage />
              </RequirePermission>
            ),
          },
          {
            path: "missions/:missionId",
            lazy: async () => ({ Component: (await import("../pages/ConsolePage")).ConsolePage }),
          },
          {
            path: "registre",
            lazy: async () => {
              const { AuditRegisterPage } = await import("../pages/AuditRegisterPage");
              return {
                Component: () => (
                  <RequirePermission permission="audit:read">
                    <AuditRegisterPage />
                  </RequirePermission>
                ),
              };
            },
          },
          {
            path: "doctrine",
            lazy: async () => {
              const { DoctrinePage } = await import("../pages/DoctrinePage");
              return {
                Component: () => (
                  <RequirePermission permission="doctrine:ask">
                    <DoctrinePage />
                  </RequirePermission>
                ),
              };
            },
          },
          { path: "*", element: <NotFoundPage /> },
        ],
      },
      { path: "vue3d/:missionId?", lazy: async () => ({ Component: (await import("../pages/SimViewPage")).SimViewPage }) },
    ],
  },
];
