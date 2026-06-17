import puppeteer from "puppeteer";
import { mkdir } from "fs/promises";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(__dirname, "..", "screenshots");

async function main() {
  await mkdir(outDir, { recursive: true });
  const browser = await puppeteer.launch({ headless: "new" });
  const page = await browser.newPage();
  await page.setViewport({ width: 390, height: 844, isMobile: true });

  await page.goto("http://127.0.0.1:5180/", { waitUntil: "networkidle2" });
  await page.screenshot({ path: path.join(outDir, "01-login.png"), fullPage: true });

  await page.evaluate(() => {
    const root = document.getElementById("root");
    root.innerHTML = `
      <div class="app-shell">
        <div class="logo"><h1>Azmus Driver</h1><p>driver1 <span class="badge badge-live">TRIP ACTIVE</span></p></div>
        <div class="card"><h2>Trip in progress</h2><p class="muted">GPS every 5s · foreground service on Android</p>
        <button class="btn btn-danger" style="margin-top:0.75rem">Stop Trip</button></div>
        <div class="card"><h2>Status</h2>
        <div class="stat-grid">
          <div class="stat"><div class="stat-label">Vehicle</div><div class="stat-value">01A777AA</div></div>
          <div class="stat"><div class="stat-label">Driver</div><div class="stat-value">Bekzod</div></div>
          <div class="stat"><div class="stat-label">Last sent</div><div class="stat-value">15:42:05</div></div>
          <div class="stat"><div class="stat-label">GPS quality</div><div class="stat-value">Good</div></div>
          <div class="stat"><div class="stat-label">Battery</div><div class="stat-value">87%</div></div>
          <div class="stat"><div class="stat-label">Network</div><div class="stat-value">Online</div></div>
          <div class="stat"><div class="stat-label">Speed</div><div class="stat-value">62 km/h</div></div>
          <div class="stat"><div class="stat-label">Queued</div><div class="stat-value">0</div></div>
        </div>
        <p class="muted" style="margin-top:0.75rem">📍 41.31108, 69.27974 (±12m)</p></div>
      </div>`;
  });
  await page.screenshot({ path: path.join(outDir, "02-tracking-active.png"), fullPage: true });

  await browser.close();
  console.log("Screenshots saved to", outDir);
}

main();
