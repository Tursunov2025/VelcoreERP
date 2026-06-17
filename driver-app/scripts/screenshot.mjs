import puppeteer from "puppeteer";
import { mkdir } from "fs/promises";
import { spawn } from "child_process";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(__dirname, "..", "screenshots");

function wait(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function main() {
  await mkdir(outDir, { recursive: true });
  const vite = spawn("npx", ["vite", "preview", "--port", "5180", "--host", "127.0.0.1"], {
    cwd: path.join(__dirname, ".."),
    shell: true,
    stdio: "ignore",
  });
  await wait(2500);

  const browser = await puppeteer.launch({ headless: "new" });
  const page = await browser.newPage();
  await page.setViewport({ width: 390, height: 844, isMobile: true });

  await page.goto("http://127.0.0.1:5180/", { waitUntil: "networkidle2" });
  await page.screenshot({ path: path.join(outDir, "01-login.png"), fullPage: true });

  await browser.close();
  vite.kill();
  console.log(JSON.stringify({ outDir, files: ["01-login.png"] }, null, 2));
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
