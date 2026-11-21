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

const fleetRow = async (callSign: string) => {
  const table = await screen.findByRole("table", { name: "Flotte" }, { timeout: 5000 });
  return within(table)
    .getAllByRole("row")
    .find((row) => within(row).queryByText(callSign) !== null)!;
};

describe("ships page", () => {
  it("lists the seeded catalog", async () => {
    renderApp("/navires", signedIn("instructeur"));

    const classes = await screen.findByRole("table", { name: "Classes" }, { timeout: 5000 });
    expect(within(classes).getByText("Frégate")).toBeInTheDocument();
    expect(within(classes).getByText("3 – 24")).toBeInTheDocument();
    expect(await fleetRow("hannibal")).toHaveTextContent("En service");
  });

  it("creates a class, then a ship of that class", async () => {
    const user = userEvent.setup();
    const backend = signedIn("instructeur");
    renderApp("/navires", backend);

    const classForm = await screen.findByRole("form", { name: "Nouvelle classe" }, { timeout: 5000 });
    await user.type(within(classForm).getByLabelText("Code"), "corvette");
    await user.type(within(classForm).getByLabelText("Libellé"), "Corvette");
    await user.type(within(classForm).getByLabelText("Rayon de giration (m)"), "350");
    await user.type(within(classForm).getByLabelText("Longueur (m)"), "95");
    await user.click(within(classForm).getByRole("button", { name: "Créer la classe" }));
    expect(await within(await screen.findByRole("table", { name: "Classes" })).findByText("Corvette")).toBeInTheDocument();

    const shipForm = screen.getByRole("form", { name: "Nouveau navire" });
    await user.type(within(shipForm).getByLabelText("Nom d'appel"), "echo");
    await user.selectOptions(within(shipForm).getByLabelText("Classe"), "corvette");
    await user.click(within(shipForm).getByRole("button", { name: "Ajouter le navire" }));

    await waitFor(async () => expect(within(await fleetRow("echo")).getByLabelText("Classe de echo")).toHaveValue("corvette"));
    expect(backend.listShips().find((s) => s.call_sign === "echo")?.class_code).toBe("corvette");
  });

  it("retires a ship and puts it back in service", async () => {
    const user = userEvent.setup();
    renderApp("/navires", signedIn("instructeur"));

    await user.click(within(await fleetRow("delta")).getByRole("button", { name: "Retirer" }));
    await waitFor(async () => expect(await fleetRow("delta")).toHaveTextContent("Retiré"));

    await user.click(within(await fleetRow("delta")).getByRole("button", { name: "Remettre en service" }));
    await waitFor(async () => expect(await fleetRow("delta")).toHaveTextContent("En service"));
  });

  it("is refused to roles without catalog:manage", async () => {
    renderApp("/navires", signedIn("eleve"));

    expect(await screen.findByRole("heading", { name: "Accès refusé" }, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Navires" })).not.toBeInTheDocument();
  });
});
