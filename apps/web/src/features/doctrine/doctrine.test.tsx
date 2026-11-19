import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { FakeBackend } from "../../mocks/fake-backend";
import { renderApp } from "../../test/render";
import { replaceTerm } from "./use-doctrine";

const signedIn = (username: string) => {
  const backend = new FakeBackend();
  backend.signIn(username, "demo");
  return backend;
};

const ask = async (question: string) => {
  const user = userEvent.setup();
  const field = await screen.findByLabelText("Question", undefined, { timeout: 5000 });
  await user.clear(field);
  await user.type(field, question);
  await user.click(screen.getByRole("button", { name: "Demander" }));
  return user;
};

describe("doctrine page", () => {
  it("shows a cited answer with its extract", async () => {
    renderApp("/doctrine", signedIn("eleve"));
    await ask("Quelle est la vitesse tactique ?");

    const answer = await screen.findByRole("region", { name: "Réponse de doctrine" });
    expect(answer).toHaveTextContent("12 nœuds");
    const extracts = within(answer).getByRole("list", { name: "Extraits cités" });
    expect(extracts).toHaveTextContent("DEMO-MANUEL, art. 102, p. 1-4");
  });

  it("says why it refuses and offers the close term", async () => {
    renderApp("/doctrine", signedIn("eleve"));
    const user = await ask("Distance en RSA ?");

    const answer = await screen.findByRole("region", { name: "Réponse de doctrine" });
    expect(answer).toHaveTextContent("aucun passage ne répond à la question");
    await user.click(within(answer).getByRole("button", { name: /RAS/ }));

    await waitFor(() => expect(screen.getByLabelText("Question")).toHaveValue("Distance en RAS ?"));
    expect(await screen.findByText(/écart de 40 mètres/)).toBeInTheDocument();
  });

  it("offers classified publications only to roles allowed to read them", async () => {
    renderApp("/doctrine", signedIn("eleve"));
    const select = await screen.findByLabelText("Publication", undefined, { timeout: 5000 });
    await waitFor(() => expect(within(select).getAllByRole("option").map((o) => o.textContent)).toEqual(["Toutes", "DEMO-MANUEL"]));
  });

  it("finds a glossary entry by its abbreviation", async () => {
    const user = userEvent.setup();
    renderApp("/doctrine", signedIn("eleve"));
    await user.type(await screen.findByLabelText("Terme, traduction ou sigle", undefined, { timeout: 5000 }), "ras");
    expect(await screen.findByText(/ravitaillement à la mer/)).toBeInTheDocument();
  });

  it("is listed in the navigation for roles that may ask", async () => {
    renderApp("/doctrine", signedIn("instructeur"));
    expect(await screen.findByRole("link", { name: "Doctrine" }, { timeout: 5000 })).toHaveAttribute("href", "/doctrine");
  });
});

describe("replaceTerm", () => {
  it("swaps whole words only", () => {
    expect(replaceTerm("RSA et TRSA, rsa", "RSA", "RAS")).toBe("RAS et TRSA, RAS");
  });
});
