import { render } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { routes } from "../app/routes";
import { FakeBackend } from "../mocks/fake-backend";
import { Composition } from "../socle/composition";
import { createQueryClient } from "../socle/query-client";
import { fakeApi, ManualStream } from "./fakes";

/** The whole app (routes, guards, query layer) over fake ports, starting at `path`. */
export function renderApp(path: string, backend = new FakeBackend()) {
  const stream = new ManualStream();
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const queryClient = createQueryClient();
  const view = render(
    <Composition ports={{ api: fakeApi(backend), stream }} queryClient={queryClient}>
      <RouterProvider router={router} />
    </Composition>,
  );
  return { ...view, router, backend, stream, queryClient };
}
