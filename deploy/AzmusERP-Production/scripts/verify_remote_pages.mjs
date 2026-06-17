import puppeteer from "puppeteer";
import { mkdir } from "fs/promises";

const uiBase = process.argv[2] || "https://cove-distributions-forests-peer.trycloudflare.com";
const outDir = process.argv[3] || "D:/AzmusERP/Data/logs/screenshots";

await mkdir(outDir, { recursive: true });

const browser = await puppeteer.launch({ headless: "new" });
const page = await browser.newPage();
await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true });
await page.setUserAgent(
  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
);

const routes = [
  { name: "driver-tracking", path: "/driver-tracking" },
  { name: "live-map", path: "/transport/live-map" },
];

const results = [];
for (const route of routes) {
  const url = `${uiBase}${route.path}`;
  let status = "ok";
  let title = "";
  let error = "";
  try {
    const resp = await page.goto(url, { waitUntil: "networkidle2", timeout: 60000 });
    status = String(resp?.status() ?? "no-response");
    title = await page.title();
    await new Promise((r) => setTimeout(r, 2500));
    await page.screenshot({ path: `${outDir}/${route.name}.png`, fullPage: true });
  } catch (e) {
    status = "error";
    error = String(e.message || e);
    await page.screenshot({ path: `${outDir}/${route.name}-error.png`, fullPage: true }).catch(() => {});
  }
  results.push({ route: route.name, url, status, title, error });
}

await browser.close();
console.log(JSON.stringify({ uiBase, outDir, results }, null, 2));
