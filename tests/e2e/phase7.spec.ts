import { expect, test, type Page } from "@playwright/test";

/**
 * Phase 7 browser validation: the real document workflow, the honest AI states,
 * Digital Twin motion, responsive layout and console hygiene.
 *
 * The e2e API server is started with an empty GEMINI_API_KEY, so every AI surface
 * here must show the deterministic fallback. No test asserts a fabricated model
 * success, and none spends provider credits.
 */

async function boot(page: Page, userId: string, path: string) {
  await page.addInitScript(
    ({ key, value }) => window.localStorage.setItem(key, value),
    { key: "caretwin.demoUserId", value: userId },
  );
  await page.goto(path);
}

function minimalPdf(text: string): Buffer {
  const clean = text.replace(/[()\\]/g, " ");
  const stream = `BT /F1 12 Tf 72 720 Td (${clean}) Tj ET`;
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
  ];
  let pdf = "%PDF-1.4\n";
  const offsets: number[] = [];
  objects.forEach((body, index) => {
    offsets.push(pdf.length);
    pdf += `${index + 1} 0 obj\n${body}\nendobj\n`;
  });
  const startxref = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const offset of offsets) {
    pdf += `${String(offset).padStart(10, "0")} 00000 n \n`;
  }
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${startxref}\n%%EOF`;
  return Buffer.from(pdf, "latin1");
}

test.describe.configure({ mode: "serial" });

test("document upload, deterministic extraction and honest AI state", async ({ page }) => {
  await boot(page, "usr_maya", "/workspace/documents");
  await expect(
    page.getByRole("heading", { name: "Document intelligence" }),
  ).toBeVisible();

  const name = "phase7-blood-report.pdf";
  const file = {
    name,
    mimeType: "application/pdf",
    buffer: minimalPdf(
      "Patient Maya Rao 2026-04-01 Hemoglobin 11.2 g/dL reference range 12.0-15.5 Follow-up 2026-04-20 clinic visit",
    ),
  };

  await page.locator('input[type="file"]').first().setInputFiles(file);
  await page.getByRole("button", { name: "Upload & extract" }).click();
  await expect(page.getByText(new RegExp(`${name} uploaded and processed`))).toBeVisible({
    timeout: 30_000,
  });

  // The new upload is selected, with deterministic analysis and no model claim.
  await expect(page.getByText("AI explanation").first()).toBeVisible();
  await expect(page.getByText("AI explanation is unavailable")).toBeVisible();
  await expect(page.getByText("AI unavailable").first()).toBeVisible();
  await expect(page.getByText("evidence validated")).toHaveCount(0);
  await expect(page.getByText("What this document contains")).toBeVisible();
  // Extracted values must stay visibly unverified until a clinician reviews them.
  await expect(page.getByText(/unverified/i).first()).toBeVisible();

  // Duplicate detection preserves the original upload and flags the repeat.
  await page.locator('input[type="file"]').first().setInputFiles(file);
  await page.getByRole("button", { name: "Upload & extract" }).click();
  await expect(page.getByText(new RegExp(`${name} was stored and flagged as a duplicate`))).toBeVisible({
    timeout: 30_000,
  });
});

test("assistant answers from records without a fake AI success state", async ({ page }) => {
  await boot(page, "usr_maya", "/workspace/assistant");
  await page
    .getByPlaceholder("e.g. Explain my latest blood report")
    .fill("Explain my latest blood report");
  await page.getByRole("button", { name: "Ask CareTwin AI" }).click();

  await expect(page.getByText("deterministic records").first()).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByText("Extracted facts").first()).toBeVisible();
  await expect(page.getByText("AI explanation · grounded")).toHaveCount(0);

  // The deterministic answer states that no model is configured instead of implying one ran.
  await expect(page.getByText(/No external model key is configured/i).first()).toBeVisible();
});

test("digital twin keeps rotating through control interactions", async ({ page }) => {
  await boot(page, "usr_maya", "/workspace/twin");
  await expect(page.getByText("Live projection")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/^Version \d+$/).first()).toBeVisible();

  const stage = page.getByLabel(/Rotating three-dimensional anatomical digital twin/);
  await expect(stage).toBeVisible();

  const first = await stage.screenshot();
  await page.waitForTimeout(900);
  const second = await stage.screenshot();
  expect(Buffer.compare(first, second), "twin rotation must change frames over time").not.toBe(0);

  await page.getByRole("button", { name: "Zoom in" }).click();
  await page.waitForTimeout(800);
  const third = await stage.screenshot();
  expect(Buffer.compare(second, third)).not.toBe(0);

  await page.getByRole("button", { name: "Pause twin rotation" }).click();
  await expect(page.getByRole("button", { name: "Resume twin rotation" })).toBeVisible();
  await page.getByRole("button", { name: "Resume twin rotation" }).click();
  await page.waitForTimeout(900);
  const fourth = await stage.screenshot();
  expect(Buffer.compare(third, fourth), "rotation must resume after pause").not.toBe(0);

  // Unverified records must never be presented as confirmed conditions.
  await expect(page.getByText(/confirmed condition/i)).toHaveCount(0);
});

test("invalid upload, mobile layout and console hygiene", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(String(error)));

  await boot(page, "usr_maya", "/workspace/documents");
  // Wait for the hydrated upload card so the file input's change handler is attached.
  await expect(page.getByRole("heading", { name: "Upload a document" })).toBeVisible();
  await page.locator('input[type="file"]').first().setInputFiles({
    name: "forged.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("this is not a pdf"),
  });
  await expect(page.getByText("forged.pdf").first()).toBeVisible();
  await page.getByRole("button", { name: "Upload & extract" }).click();
  await expect(page.getByText(/Invalid or unsupported file signature/i)).toBeVisible({
    timeout: 20_000,
  });
  // The rejected upload legitimately produces a 422 network log; console hygiene
  // is asserted for normal navigation below, not for a deliberate failure.
  errors.length = 0;

  for (const width of [390, 420]) {
    await page.setViewportSize({ width, height: 844 });
    for (const path of [
      "/workspace",
      "/workspace/documents",
      "/workspace/assistant",
      "/workspace/alerts",
      "/workspace/twin",
    ]) {
      await page.goto(path);
      await page.waitForTimeout(700);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow, `${path} must not overflow at ${width}px`).toBeLessThanOrEqual(1);
    }
  }

  expect(errors, `console errors: ${errors.join(" | ")}`).toEqual([]);
});
