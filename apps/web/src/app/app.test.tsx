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
  }, 15_000);

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
    renderApp("/missions/nouvelle", backend);
    expect(await screen.findByRole("heading", { name: "Accès refusé" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Missions" })).not.toBeInTheDocument();
  });

  it("lands on the dashboard after sign-in and follows the selected ship", async () => {
    const user = userEvent.setup();
    renderApp("/", signedIn());

    expect(await screen.findByRole("heading", { name: "Tableau de bord" })).toBeInTheDocument();
    const fleet = screen.getByRole("region", { name: "Flotte" });
    await user.click(within(fleet).getByRole("button", { name: /DELTA/ }));
    const detail = screen.getByRole("region", { name: "Détails du navire" });
    expect(within(detail).getByRole("heading", { name: "DELTA" })).toBeInTheDocument();
    expect(within(fleet).getByRole("button", { name: /DELTA/ })).toHaveAttribute("aria-pressed", "true");
  });

  it("keeps the register away from a trainee", async () => {
    renderApp("/registre", signedIn("eleve"));
    expect(await screen.findByRole("heading", { name: "Accès refusé" }, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Registre" })).not.toBeInTheDocument();
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
    const { router, stream, backend } = renderApp("/missions/nouvelle", signedIn());

    await user.click(await screen.findByRole("radio", { name: /alfa/i }));
    await user.click(screen.getByRole("button", { name: "Démarrer la mission" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/missions/m-1"));
    const mainNav = screen.getByRole("navigation", { name: "Navigation principale" });
    expect(within(mainNav).getByRole("link", { name: "Missions" })).toHaveAttribute("aria-current", "page");
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

  it("lists each command in the register with its audio, signal and decision", async () => {
    const user = userEvent.setup();
    const backend = signedIn();
    const mission = backend.startMission({ scenario_id: "transit-colonne", player_ship: "alfa", autopilot: false, manual_helm: false });
    const voice = backend.submitVoiceOrder(mission.id, new Blob([new Uint8Array(4000)], { type: "audio/wav" }));
    backend.decideCommand(voice.command_id!, "reject");
    backend.submitOrder(mission.id, { text: "ALL SHIPS SPEED 10", mode: "review" });
    renderApp("/registre", backend);

    const table = await screen.findByRole("table", { name: "Registre des commandes" }, { timeout: 5000 });
    expect(within(table).getByLabelText(`Audio de la commande ${voice.command_id!.slice(0, 8)}`)).toBeInTheDocument();
    expect(within(table).getByText("rejeté", { selector: ".badge" })).toBeInTheDocument();
    expect(screen.getByText(/Chaîne intacte/)).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Source"), "keyboard");
    expect(within(table).queryByText("rejeté", { selector: ".badge" })).not.toBeInTheDocument();
    expect(within(table).getByText("en attente", { selector: ".badge" })).toBeInTheDocument();
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

  it("sends a recorded order, flags doubtful words and corrects it at the keyboard", async () => {
    const user = userEvent.setup();
    const backend = signedIn();
    const mission = backend.startMission({ scenario_id: "transit-colonne", player_ship: "alfa", autopilot: false, manual_helm: false });
    renderApp(`/missions/${mission.id}`, backend);

    const wav = new File([new Uint8Array(4000)], "ordre.wav", { type: "audio/wav" });
    await user.upload(await screen.findByLabelText("Importer un WAV", {}, { timeout: 5000 }), wav);
    const card = await screen.findByRole("region", { name: "Entendu" });
    expect(within(card).getByText("SHIPS").tagName).toBe("MARK");
    expect(within(card).getByRole("status")).toHaveTextContent("Compris : ALL SHIPS CORPEN 045 SPEED 12");
    expect(await screen.findByRole("region", { name: "Ordre en attente de validation" })).toBeInTheDocument();

    await user.click(within(card).getByRole("button", { name: "Corriger au clavier" }));
    const field = screen.getByLabelText("Ordre (signal)");
    expect(field).toHaveValue("ALL SHIPS CORPEN 045 SPEED 12");
    await user.clear(field);
    await user.type(field, "ALL SHIPS CORPEN 050 SPEED 12");
    await user.click(screen.getByRole("button", { name: "Soumettre" }));
    await waitFor(() => expect(backend.state.commands).toHaveLength(2));
    expect(backend.state.commands[1]).toMatchObject({ source: "keyboard", parent_id: backend.state.commands[0]!.id });
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
