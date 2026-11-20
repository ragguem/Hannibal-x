import { expect, test } from "@playwright/test";

test("préparation → mission → ordre → validation → débrief", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => localStorage.clear());
  await page.goto("/");

  await page.getByLabel("Identifiant").fill("instructeur");
  await page.getByLabel("Mot de passe").fill("demo");
  await page.getByRole("button", { name: "Se connecter" }).click();

  await expect(page.getByRole("heading", { name: "Tableau de bord" })).toBeAttached();
  await page.getByRole("navigation", { name: "Navigation principale" }).getByRole("link", { name: "Missions" }).click();
  await page.getByRole("radio", { name: /Transit en colonne/ }).check();
  await page.getByRole("radio", { name: /alfa/i }).check();
  await page.getByRole("button", { name: "Démarrer la mission" }).click();

  await expect(page).toHaveURL(/\/missions\/m-1$/);
  await expect(page.getByRole("status").filter({ hasText: "temps réel" })).toBeVisible();

  const order = page.getByLabel("Ordre (signal)");
  await order.fill("ALL SHIPS CORPEN 045 SPEED 14");
  await page.getByRole("button", { name: "Simuler" }).click();
  await expect(page.getByRole("region", { name: "Simulation" })).toBeVisible();

  await page.getByRole("button", { name: "Soumettre" }).click();
  const decision = page.getByRole("region", { name: /^Ordre (en attente|transmis)/ });
  await expect(decision).toHaveAccessibleName("Ordre en attente de validation");
  await decision.getByRole("button", { name: "Valider" }).click();
  await expect(decision).toHaveAccessibleName("Ordre transmis");
  await expect(page.getByRole("log")).toContainText("ALL SHIPS CORPEN 045 SPEED 14");

  await page.getByLabel("Classification de TRK021").selectOption("hostile");

  await page.getByRole("link", { name: "Vue 3D" }).click();
  const view = page.frameLocator('iframe[title="Vue 3D de la mission"]');
  // The dev server compiles three.js on first load of the frame.
  await expect(view.locator("#sc")).toHaveText("Transit en colonne", { timeout: 30_000 });
  await page.getByRole("link", { name: "Retour à la console" }).click();

  await page.getByRole("button", { name: "Arrêter la mission" }).click();
  await page.getByRole("button", { name: "Confirmer l'arrêt" }).click();
  await expect(page.getByRole("heading", { name: "Débriefing" })).toBeVisible();
  await expect(page.getByText(/Score/)).toContainText("100");
});

test("vue 3D en mode démonstration", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/view3d.html?demo");
  await expect(page.locator("#sc")).toContainText("Démonstration");
  expect(errors).toEqual([]);
});
