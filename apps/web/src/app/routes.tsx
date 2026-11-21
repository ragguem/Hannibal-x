import type { RouteObject } from "react-router";
import { DashboardPage } from "../pages/DashboardPage";
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
          { index: true, element: <DashboardPage /> },
          {
            path: "missions/nouvelle",
            element: (
              <RequirePermission permission="mission:plan">
                <SetupPage />
              </RequirePermission>
            ),
          },
          {
            path: "missions",
            lazy: async () => {
              const { MissionHistoryPage } = await import("../pages/MissionHistoryPage");
              return {
                Component: () => (
                  <RequirePermission permission="mission:plan">
                    <MissionHistoryPage />
                  </RequirePermission>
                ),
              };
            },
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
          {
            path: "utilisateurs",
            lazy: async () => {
              const { UsersPage } = await import("../pages/UsersPage");
              return {
                Component: () => (
                  <RequirePermission permission="user:manage">
                    <UsersPage />
                  </RequirePermission>
                ),
              };
            },
          },
          {
            path: "navires",
            lazy: async () => {
              const { ShipsPage } = await import("../pages/ShipsPage");
              return {
                Component: () => (
                  <RequirePermission permission="catalog:manage">
                    <ShipsPage />
                  </RequirePermission>
                ),
              };
            },
          },
          {
            path: "scenarios",
            lazy: async () => {
              const { ScenarioCatalogPage } = await import("../pages/ScenarioCatalogPage");
              return {
                Component: () => (
                  <RequirePermission permission="catalog:manage">
                    <ScenarioCatalogPage />
                  </RequirePermission>
                ),
              };
            },
          },
          {
            path: "mot-de-passe",
            lazy: async () => ({ Component: (await import("../pages/ChangePasswordPage")).ChangePasswordPage }),
          },
          { path: "*", element: <NotFoundPage /> },
        ],
      },
      { path: "vue3d/:missionId?", lazy: async () => ({ Component: (await import("../pages/SimViewPage")).SimViewPage }) },
    ],
  },
];
