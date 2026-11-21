import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { FakeBackend } from "../../mocks/fake-backend";
import { renderApp } from "../../test/render";

const signedIn = (username: string, password = "demo") => {
  const backend = new FakeBackend();
  backend.signIn(username, password);
  return backend;
};

const rowOf = async (username: string) => {
  const table = await screen.findByRole("table", { name: "Comptes" }, { timeout: 5000 });
  return within(table)
    .getAllByRole("row")
    .find((row) => within(row).queryByText(username) !== null)!;
};

describe("users page", () => {
  it("creates an account and shows its temporary password once", async () => {
    const user = userEvent.setup();
    const backend = signedIn("instructeur");
    renderApp("/utilisateurs", backend);

    await user.type(await screen.findByLabelText("Identifiant", undefined, { timeout: 5000 }), "marin.duval");
    await user.selectOptions(screen.getByLabelText("Rôle"), "eleve");
    await user.click(screen.getByRole("button", { name: "Créer le compte" }));

    const notice = await screen.findByRole("status");
    const password = within(notice).getByText(/^[A-Za-z0-9_-]{16,}$/).textContent;
    expect(await rowOf("marin.duval")).toHaveTextContent("Provisoire");
    await user.click(within(notice).getByRole("button", { name: "J'ai transmis le mot de passe" }));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();

    backend.signOut();
    expect(backend.signIn("marin.duval", password).role).toBe("eleve");
  });

  it("disables another account, never its own", async () => {
    const user = userEvent.setup();
    renderApp("/utilisateurs", signedIn("instructeur"));

    expect(within(await rowOf("instructeur")).getByRole("button", { name: "Désactiver" })).toBeDisabled();
    expect(within(await rowOf("instructeur")).getByLabelText("Rôle de instructeur")).toBeDisabled();

    await user.click(within(await rowOf("eleve")).getByRole("button", { name: "Désactiver" }));

    await waitFor(async () => expect(await rowOf("eleve")).toHaveTextContent("Désactivé"));
    expect(within(await rowOf("eleve")).getByRole("button", { name: "Réactiver" })).toBeEnabled();
  });

  it("is refused to roles without user:manage and absent from their navigation", async () => {
    renderApp("/utilisateurs", signedIn("eleve"));

    expect(await screen.findByRole("heading", { name: "Accès refusé" }, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Utilisateurs" })).not.toBeInTheDocument();
  });
});

describe("change password page", () => {
  it("replaces the password and sends the user back to sign in", async () => {
    const user = userEvent.setup();
    const backend = signedIn("eleve");
    renderApp("/mot-de-passe", backend);

    await user.type(await screen.findByLabelText("Mot de passe actuel", undefined, { timeout: 5000 }), "demo");
    await user.type(screen.getByLabelText("Nouveau mot de passe"), "un-mot-de-passe-long");
    await user.type(screen.getByLabelText("Confirmation"), "un-mot-de-passe-long");
    await user.click(screen.getByRole("button", { name: "Changer le mot de passe" }));

    expect(await screen.findByRole("button", { name: /connecter/i }, { timeout: 5000 })).toBeInTheDocument();
    expect(backend.signIn("eleve", "un-mot-de-passe-long").username).toBe("eleve");
  });
});
