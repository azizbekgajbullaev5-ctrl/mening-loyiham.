import fs from "node:fs";
import { chromium } from "playwright";
/**
 * Browser end-to-end test against a running stack (frontend on :3000 + backend + worker).
 *   npm run e2e                       # screenshots/reports go to ./e2e-output
 *   E2E_BASE_URL=... CHROMIUM_PATH=... npm run e2e
 */
import path from "node:path";
import { fileURLToPath } from "node:url";
const here = path.dirname(fileURLToPath(import.meta.url));
const SP = process.env.E2E_OUT || path.join(here, "..", "e2e-output");
const SAMPLES = path.join(here, "..", "..", "backend", "tests", "fixtures", "samples");
const base = process.env.E2E_BASE_URL || "http://localhost:3000";
fs.mkdirSync(path.join(SP, "shots"), { recursive: true });
const log = (...a) => console.log("•", ...a);
const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 }, acceptDownloads: true });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));

// 1. unauthenticated -> redirected to login
await page.goto(base + "/");
await page.waitForURL("**/login");
log("redirected to login");

// 2. register
await page.goto(base + "/register");
await page.fill("#name", "E2E Tadqiqotchi");
await page.fill("#email", `e2e${Date.now()}@example.org`);
await page.fill("#password", "Kuchli-parol-2026");
await page.click("button[type=submit]");
await page.waitForURL(base + "/");
await page.getByText("So'nggi tahlillar").waitFor();
log("registered + dashboard");
await page.screenshot({ path: `${SP}/shots/1-dashboard.png`, fullPage: true });

// 3. upload two documents
await page.setInputFiles("[data-testid=file-input]", [`${SAMPLES}/sample_uz.docx`, `${SAMPLES}/sample_ru.pdf`]);
await page.getByText("sample_uz.docx").waitFor();
await page.click("text=Tahlilni boshlash");
await page.locator("table >> text=sample_uz.docx").waitFor();
log("uploaded");
// wait until both completed (worker)
await page.waitForFunction(() => document.querySelectorAll("table tbody tr").length >= 2 && [...document.querySelectorAll("table tbody tr")].every((r) => r.textContent.includes("Tayyor")), null, { timeout: 120000 });
log("both analyses completed via RQ worker");
await page.screenshot({ path: `${SP}/shots/2-dashboard-done.png`, fullPage: true });

// 4. open result
await page.click("table >> text=sample_uz.docx");
await page.getByTestId("ai-score").waitFor();
const score = await page.getByTestId("ai-score").textContent();
log("AI-likelihood shown:", score);
const body = await page.textContent("body");
for (const s of ["isbot emas", "Tashqi provayder sozlanmagan", "AI-ehtimollik ≠ plagiat", "AI-ehtimollik boblar bo'yicha", "O'xshashlik boblar bo'yicha"]) {
  if (!body.includes(s)) throw new Error("missing text: " + s);
}
await page.waitForSelector(".recharts-bar-rectangle");
await page.screenshot({ path: `${SP}/shots/3-result-overview.png`, fullPage: true });

// 5. chapters, passages + filters, similarity, academic, document, method
await page.click("nav >> text=Boblar");
await page.getByText("I BOB. MUSTAQIL").first().waitFor();
await page.screenshot({ path: `${SP}/shots/4-chapters.png`, fullPage: true });
await page.click("nav >> text=Shubhali parchalar");
await page.getByTestId("passage").first().waitFor();
const n1 = await page.getByTestId("passage").count();
await page.fill("#f-q", "intizom-yoq-soz");
await page.waitForTimeout(800);
const n2 = await page.getByTestId("passage").count();
log(`passages: ${n1}, after search: ${n2}`);
await page.fill("#f-q", "");
await page.waitForTimeout(600);
await page.screenshot({ path: `${SP}/shots/5-passages.png`, fullPage: true });
await page.click("nav >> text=O'xshashlik");
await page.locator("li >> text=Hujjat ichida takrorlangan matn").first().waitFor();
await page.screenshot({ path: `${SP}/shots/6-similarity.png`, fullPage: true });
await page.click("nav >> text=Akademik yozuv");
await page.getByText("Aniqlangan holatlar").waitFor();
await page.screenshot({ path: `${SP}/shots/7-academic.png`, fullPage: true });
await page.click("nav >> text=Hujjat");
await page.getByText("¶1").first().waitFor();
await page.screenshot({ path: `${SP}/shots/8-document.png` });

// 6. download reports
for (const [label, ext] of [["PDF hisobot", "pdf"], ["DOCX hisobot", "docx"]]) {
  const [dl] = await Promise.all([page.waitForEvent("download"), page.click(`text=${label}`)]);
  const p = `${SP}/report.${ext}`;
  await dl.saveAs(p);
  log(`${ext} report downloaded:`, fs.statSync(p).size, "bytes");
}

// 7. structure correction -> re-analysis
await page.click("text=Tuzilmani tuzatish");
await page.getByText("Hujjat tuzilmasini tuzatish").waitFor();
await page.screenshot({ path: `${SP}/shots/9-structure.png`, fullPage: false });
await page.click("text=Saqlash va qayta tahlil qilish");
await page.waitForURL("**/analyses/**");
await page.getByTestId("ai-score").waitFor({ timeout: 120000 });
if (!(await page.textContent("body")).includes("tuzilma qo'lda tuzatilgan")) throw new Error("manual structure flag missing");
log("structure correction re-analysis completed");

// 8. mobile layout
const m = await browser.newContext({ viewport: { width: 390, height: 844 }, storageState: await ctx.storageState() });
const mp = await m.newPage();
await mp.goto(base + "/");
await mp.getByText("So'nggi tahlillar").waitFor();
await mp.screenshot({ path: `${SP}/shots/10-mobile.png`, fullPage: true });
const overflow = await mp.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
log("mobile horizontal overflow:", overflow);

// 9. delete a document
page.on("dialog", (d) => d.accept());
await page.goto(base + "/");
await page.locator("table tbody tr").first().waitFor();
const before = await page.locator("table tbody tr").count();
await page.locator("table tbody tr").last().getByText("O'chirish").click();
await page.waitForFunction((b) => document.querySelectorAll("table tbody tr").length < b, before);
log("deleted document; rows", before, "->", await page.locator("table tbody tr").count());

log("console/page errors:", errors.length ? errors : "none");
await browser.close();

if (errors.some((e) => !/401|Failed to fetch RSC/.test(e))) process.exitCode = 1;
