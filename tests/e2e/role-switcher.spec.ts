import { expect, test, type Page } from "@playwright/test";

const API =
  process.env.CARETWIN_E2E_API_URL ?? "http://127.0.0.1:8000/api/v1";
const PATIENT_ID = "pat_maya";

async function boot(page: Page, userId: string, path: string) {
  await page.addInitScript(
    ({ key, value }) => window.localStorage.setItem(key, value),
    { key: "caretwin.demoUserId", value: userId },
  );
  await page.goto(path);
}

test.describe.configure({ mode: "serial" });

test("role switcher lists roles and confirms a clinician switch", async ({ page }) => {
  await boot(page, "usr_maya", "/workspace");

  const trigger = page.getByRole("button", { name: "Switch demo role" });
  await trigger.click();

  const dialog = page.getByRole("dialog", { name: "Switch demo access" });
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: "Maya Rao, current demo identity" }),
  ).toHaveAttribute("aria-current", "true");
  await expect(
    dialog.getByRole("button", { name: "Switch to Arjun Rao, Caregiver" }),
  ).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: "Switch to Dr. Nandini Iyer, Clinician" }),
  ).toBeVisible();

  await dialog
    .getByRole("button", { name: "Switch to Dr. Nandini Iyer, Clinician" })
    .click();

  await expect(page.getByText(/Now viewing as Dr. Nandini Iyer/)).toBeVisible();
  await expect(page).toHaveURL(/\/workspace\/clinician$/);
  await expect(trigger).toContainText("Dr. Nandini Iyer");

  const confirmed = await page.request.get(`${API}/auth/session`, {
    headers: { "X-Demo-User-Id": "usr_nandini" },
  });
  expect(confirmed.ok()).toBeTruthy();
  expect((await confirmed.json()).user.role).toBe("clinician");
});

test("keyboard escape closes the switcher and restores focus", async ({ page }) => {
  await boot(page, "usr_maya", "/workspace");

  const trigger = page.getByRole("button", { name: "Switch demo role" });
  await trigger.focus();
  await page.keyboard.press("Enter");

  const dialog = page.getByRole("dialog", { name: "Switch demo access" });
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByRole("button", { name: "Close demo role switcher" }),
  ).toBeFocused();

  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(trigger).toBeFocused();
});

test("revoked caregiver remains denied at the API boundary", async ({
  request,
}) => {
  const denied = await request.get(`${API}/patients/${PATIENT_ID}/twin`, {
    headers: { "X-Demo-User-Id": "usr_priya" },
  });
  expect(denied.status()).toBe(403);
});

test("mobile navigation opens the same role switcher", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await boot(page, "usr_nandini", "/workspace/clinician");

  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("button", { name: "Switch demo access" }).click();

  const dialog = page.getByRole("dialog", { name: "Switch demo access" });
  await expect(dialog).toBeVisible();
  await dialog
    .getByRole("button", { name: "Switch to Maya Rao, Patient" })
    .click();

  await expect(page).toHaveURL(/\/workspace$/);
  await expect(
    page.getByRole("button", { name: "Switch demo role" }),
  ).toContainText("Maya Rao");
});
