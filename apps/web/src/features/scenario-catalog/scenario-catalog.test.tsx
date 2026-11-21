import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { FakeBackend } from "../../mocks/fake-backend";
import { renderApp } from "../../test/render";

const signedIn = (username: string) => {
  const backend = new FakeBackend();
  backend.signIn(username, "demo");
  return backend;
};

const scenarioRow = async (id: string) => {
  const table = await screen.findByRole("table", { name: "Scénarios" }, { timeout: 5000 });
  return within(table)
    .getAllByRole("row")
    .find((row) => within(row).queryByText(id) !== null)!;
};

describe("scenario catalog page", () => {
  it("imports a new version, publishes it, then archives the scenario", async () => {
    const user = userEvent.setup();
    const backend = signedIn("instructeur");
    renderApp("/scenarios", backend);

    expect(await scenarioRow("transit-colonne")).toHaveTextContent("v1");
    const yaml = "schema_version: 1\nid: transit-colonne\ntitre: Transit en colonne\nniveau: débutant\nduree_s: 600\n";
    await user.upload(screen.getByLabelText("Importer un fichier YAML"), new File([yaml], "transit.yaml", { type: "application/yaml" }));

    await user.click(await within(await scenarioRow("transit-colonne")).findByRole("button", { name: "Publier v2" }));
    await waitFor(() => expect(backend.listCatalogScenarios().find((s) => s.id === "transit-colonne")?.published_version).toBe(2));
    expect(backend.exportScenario("transit-colonne", 2)).toBe(yaml);

    await user.click(within(await scenarioRow("transit-colonne")).getByRole("button", { name: "Archiver" }));
    await waitFor(async () => expect(await scenarioRow("transit-colonne")).toHaveTextContent("Archivé"));
  });

  it("shows why an import is refused", async () => {
    const user = userEvent.setup();
    renderApp("/scenarios", signedIn("instructeur"));

    await scenarioRow("transit-colonne");
    await user.upload(screen.getByLabelText("Importer un fichier YAML"), new File(["titre: sans id\n"], "bad.yaml"));
    expect(await screen.findByRole("alert")).toHaveTextContent("id manquant");
  });

  it("is refused to roles without catalog:manage", async () => {
    renderApp("/scenarios", signedIn("eleve"));

    expect(await screen.findByRole("heading", { name: "Accès refusé" }, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Scénarios" })).not.toBeInTheDocument();
  });
});
