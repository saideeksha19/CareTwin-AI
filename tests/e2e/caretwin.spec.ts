import { expect, test, type Page } from "@playwright/test";

const API = "http://127.0.0.1:8000/api/v1";
const PATIENT_ID = "pat_maya";

async function boot(page: Page, userId: string, path: string) {
  await page.addInitScript(
    ({ key, value }) => window.localStorage.setItem(key, value),
    { key: "caretwin.demoUserId", value: userId },
  );
  await page.goto(path);
}

async function apiGet(page: Page, path: string, userId: string) {
  const response = await page.request.get(`${API}${path}`, {
    headers: { "X-Demo-User-Id": userId },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}

test.describe.configure({ mode: "serial" });

test("patient validates and submits a worsening check-in with deduplication", async ({
  page,
}) => {
  await boot(page, "usr_maya", "/demo");

  await expect(
    page.getByRole("heading", {
      name: "Choose who is viewing Maya's recovery.",
    }),
  ).toBeVisible();
  await expect(
    page.getByText("Synthetic demo access", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Maya Rao", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Arjun Rao", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Priya Rao", { exact: true })).toHaveCount(0);
  await expect(
    page.getByText("Dr. Nandini Iyer", { exact: true }).first(),
  ).toBeVisible();

  await page.goto("/workspace/check-in");
  await expect(
    page.getByRole("heading", {
      name: "Tell your care team how today is going.",
    }),
  ).toBeVisible();

  await page.locator("#temperature").fill("50");
  await page.getByRole("button", { name: "Submit daily check-in" }).click();
  await expect(
    page.getByText("Temperature must be between 30 and 45 °C, or left blank."),
  ).toBeVisible();
  await expect(page.getByText("Check-in recorded")).toHaveCount(0);

  await page.getByRole("button", { name: "Worsening day" }).click();
  await page.locator("#temperature").fill("38.9");
  await page.getByRole("button", { name: "Submit daily check-in" }).click();

  await expect(page.getByText("Check-in recorded")).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByText("Twin v6", { exact: true })).toBeVisible();
  await expect(page.getByText(/1 new rule alert/)).toBeVisible();
  await expect(page.getByText("2 existing alerts retained")).toBeVisible();
  await expect(
    page.getByText(
      "Existing unresolved alert retained instead of creating a duplicate",
    ),
  ).toBeVisible();

  const twin = await apiGet(page, `/patients/${PATIENT_ID}/twin`, "usr_maya");
  expect(twin.version).toBe(6);
  expect(twin.status).toBe("urgent_review");
  expect(twin.openAlerts).toHaveLength(3);
  expect(twin.recentCheckIns[0].overallFeeling).toBe("worse");

  const alerts = await apiGet(
    page,
    `/patients/${PATIENT_ID}/alerts`,
    "usr_nandini",
  );
  expect(alerts.filter((alert: { status: string }) => alert.status === "open")).toHaveLength(
    3,
  );

  const timeline = await apiGet(
    page,
    `/patients/${PATIENT_ID}/timeline`,
    "usr_maya",
  );
  const deduplicatedEvents = timeline.events.filter(
    (event: { eventType: string }) => event.eventType === "alert_deduplicated",
  );
  expect(deduplicatedEvents).toHaveLength(2);
  expect(
    deduplicatedEvents.every(
      (event: { evidence: unknown }) => event.evidence !== null,
    ),
  ).toBeTruthy();

  const audit = await apiGet(
    page,
    `/patients/${PATIENT_ID}/audit?limit=100`,
    "usr_nandini",
  );
  expect(
    audit.filter(
      (entry: { action: string }) =>
        entry.action === "safety_alert.deduplicated",
    ),
  ).toHaveLength(2);

  await page.goto("/workspace/twin");
  await expect(page.getByText("Version 6", { exact: true })).toBeVisible();
  await expect(page.getByText("Urgent review", { exact: true })).toBeVisible();
});

test("clinician acknowledges and resolves a critical alert without dropping urgency", async ({
  page,
}) => {
  await boot(page, "usr_nandini", "/workspace/alerts");

  await expect(
    page.getByRole("heading", {
      name: "Rule-based concerns, with provenance.",
    }),
  ).toBeVisible();
  await expect(page.getByText("3 open", { exact: true }).first()).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Acknowledge alert" }).first(),
  ).toBeVisible();

  await page.getByRole("tab", { name: /Resolved/ }).click();
  await expect(page.getByText("No alerts in this view")).toBeVisible();
  await page.getByRole("tab", { name: /^Open/ }).click();

  await page
    .locator('textarea[id^="ack-note-"]')
    .first()
    .fill("Playwright critical alert review started.");
  await page
    .getByRole("button", { name: "Acknowledge alert" })
    .first()
    .click();
  await expect(page.getByText(/Alert acknowledged and recorded/)).toBeVisible();

  const afterAck = await apiGet(
    page,
    `/patients/${PATIENT_ID}/twin`,
    "usr_nandini",
  );
  expect(afterAck.version).toBe(7);
  expect(afterAck.status).toBe("urgent_review");
  expect(afterAck.statusReason.toLowerCase()).toContain("acknowledged");
  expect(afterAck.statusReason.toLowerCase()).toContain("not resolved");

  await page.getByRole("tab", { name: /Acknowledged/ }).click();
  await page
    .locator('textarea[id^="resolve-note-"]')
    .first()
    .fill("Chest pain evaluated and escalation completed during Playwright review.");
  await page.getByRole("button", { name: "Resolve alert" }).first().click();
  await expect(page.getByText(/Alert resolved and recorded/)).toBeVisible();
  await expect(page.getByText(/Twin v8/)).toBeVisible();

  const afterResolve = await apiGet(
    page,
    `/patients/${PATIENT_ID}/twin`,
    "usr_nandini",
  );
  expect(afterResolve.version).toBe(8);
  expect(afterResolve.status).toBe("needs_attention");
  expect(afterResolve.statusReason).toBe(
    "One or more open rule-based concerns require review.",
  );

  await page.getByRole("tab", { name: /Resolved/ }).click();
  await expect(
    page.getByText(/Resolved by Dr. Nandini Iyer/).first(),
  ).toBeVisible();

  const alerts = await apiGet(
    page,
    `/patients/${PATIENT_ID}/alerts`,
    "usr_nandini",
  );
  const resolved = alerts.find(
    (alert: { status: string }) => alert.status === "resolved",
  );
  expect(resolved).toBeTruthy();
  expect(resolved.resolvedBy).toBe("Dr. Nandini Iyer");
  expect(resolved.resolvedAt).toBeTruthy();
  expect(resolved.resolutionNote).toContain("Chest pain evaluated");

  const timeline = await apiGet(
    page,
    `/patients/${PATIENT_ID}/timeline`,
    "usr_nandini",
  );
  expect(
    timeline.events.some(
      (event: { eventType: string }) => event.eventType === "alert_acknowledged",
    ),
  ).toBeTruthy();
  expect(
    timeline.events.some(
      (event: { eventType: string }) => event.eventType === "alert_resolved",
    ),
  ).toBeTruthy();

  const audit = await apiGet(
    page,
    `/patients/${PATIENT_ID}/audit?limit=100`,
    "usr_nandini",
  );
  expect(
    audit.some(
      (entry: { action: string }) => entry.action === "safety_alert.resolved",
    ),
  ).toBeTruthy();
});

test("revoked caregiver still hits the consent boundary in the browser", async ({
  page,
}) => {
  await boot(page, "usr_priya", "/workspace/twin");
  await expect(
    page.getByText("This twin is not shared with this role"),
  ).toBeVisible();
  await expect(
    page.getByText(/Caregiver visibility depends on an active patient consent/),
  ).toBeVisible();

  await page.goto("/workspace/alerts");
  await expect(
    page.getByText("Safety alerts are not shared with this role"),
  ).toBeVisible();
});
