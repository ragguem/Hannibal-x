import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { FakeBackend } from "../mocks/fake-backend";
import { renderApp } from "../test/render";

const signedIn = (username = "instructeur") => {
  const backend = new FakeBackend();
  backend.signIn(username, "demo");
  return backend;
};

describe("routing and session guards", () => {
  it("sends an anonymous visitor to sign-in, then back where they were going", async () => {
    const user = userEvent.setup();
    const { router } = renderApp("/missions/m-9");

    await screen.findByRole("heading", { name: "Connexion" }, { timeout: 5000 });
    await user.type(screen.getByLabelText("Identifiant"), "instructeur");
    await user.type(screen.getByLabelText("Mot de passe"), "demo");
    await user.click(screen.getByRole("button", { name: "Se connecter" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/missions/m-9"));
  });

  it("explains a wrong password without leaving the page", async () => {
    const user = userEvent.setup();
    renderApp("/login");
    await user.type(await screen.findByLabelText("Identifiant"), "instructeur");
    await user.type(screen.getByLabelText("Mot de passe"), "faux");
    await user.click(screen.getByRole("button", { name: "Se connecter" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Identifiant ou mot de passe incorrect.");
  });

  it("ignores an off-site return address after sign-in", async () => {
    const backend = signedIn();
    const { router } = renderApp("/login", backend);
    await router.navigate("/login", { state: { from: "//evil.example" } });
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
  });

  it("refuses the setup screen to a role without mission:play", async () => {
    const backend = signedIn();
    backend.state.session = { ...backend.state.session!, permissions: ["audit:read"] };
    renderApp("/", backend);
    expect(await screen.findByRole("heading", { name: "Accès refusé" })).toBeInTheDocument();
  });

  it("returns to sign-in when the session expires mid-mission", async () => {
    const backend = signedIn();
    const mission = backend.startMission({ scenario_id: "transit-colonne", player_ship: "alfa", autopilot: false, manual_helm: false });
    backend.signOut();
    const { router } = renderApp(`/missions/${mission.id}`, backend);
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
  });
});

describe("mission flow", () => {
  it("prepares, starts, orders, validates and debriefs a mission", async () => {
    const user = userEvent.setup();
    const { router, stream, backend } = renderApp("/", signedIn());

    await user.click(await screen.findByRole("radio", { name: /alfa/i }));
    await user.click(screen.getByRole("button", { name: "Démarrer la mission" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/missions/m-1"));
    await user.type(await screen.findByLabelText("Ordre (signal)", {}, { timeout: 5000 }), "all ships corpen 045 speed 14");
    await user.click(screen.getByRole("button", { name: "Soumettre" }));
    const decision = await screen.findByRole("region", { name: "Ordre en attente de validation" });
    await user.click(within(decision).getByRole("button", { name: "Valider" }));
    expect(await within(decision).findByText(/transmis|transmission/)).toBeInTheDocument();

    stream.push("m-1", { type: "situation", mission: backend.readMission("m-1") });
    await user.click(screen.getByRole("button", { name: "Arrêter la mission" }));
    await user.click(screen.getByRole("button", { name: "Confirmer l'arrêt" }));
    expect(await screen.findByRole("heading", { name: "Débriefing" })).toBeInTheDocument();
  });

  it("refuses an unknown signal with the server's reason", async () => {
    const user = userEvent.setup();
    const backend = signedIn();
    const mission = backend.startMission({ scenario_id: "transit-colonne", player_ship: "alfa", autopilot: false, manual_helm: false });
    renderApp(`/missions/${mission.id}`, backend);

    await user.type(await screen.findByLabelText("Ordre (signal)"), "bonjour");
    await user.click(screen.getByRole("button", { name: "Soumettre" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Signal non reconnu.");
  });

  it("hides the validation buttons from a trainee", async () => {
    const user = userEvent.setup();
    const backend = signedIn("eleve");
    const mission = backend.startMission({ scenario_id: "transit-colonne", player_ship: "alfa", autopilot: false, manual_helm: false });
    renderApp(`/missions/${mission.id}`, backend);

    await user.type(await screen.findByLabelText("Ordre (signal)"), "ALL SHIPS CORPEN 045");
    await user.click(screen.getByRole("button", { name: "Soumettre" }));
    expect(await screen.findByText("Un superviseur doit valider.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Valider" })).not.toBeInTheDocument();
  });
});
