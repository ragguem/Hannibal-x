import { useState } from "react";
import { createBrowserRouter, RouterProvider } from "react-router";
import { Composition } from "../socle/composition";
import { routes } from "./routes";

export function App() {
  const [router] = useState(() => createBrowserRouter(routes));
  return (
    <Composition>
      <RouterProvider router={router} />
    </Composition>
  );
}
