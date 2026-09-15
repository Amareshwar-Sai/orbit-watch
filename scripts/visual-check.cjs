// Optional local QA: npm's Playwright package and its Chromium browser are required.
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
(async () => {
  const out = path.resolve(process.argv[2] || 'var/screenshots');
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  for (const [name, viewport] of [['desktop', { width: 1440, height: 1000 }], ['mobile', { width: 390, height: 844 }]]) {
    await page.setViewportSize(viewport);
    await page.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });
    await page.screenshot({ path: path.join(out, `${name}.png`), fullPage: true });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    if (overflow) throw new Error(`${name}: horizontal overflow`);
  }
  for (const route of ['/cases', '/queue', '/sources', '/sparta', '/case?id=ka-sat-2022']) {
    const response = await page.goto('http://127.0.0.1:8000' + route);
    if (response.status() !== 200) throw new Error(`${route}: ${response.status()}`);
  }
  await browser.close();
  if (errors.length) throw new Error(errors.join('\n'));
  console.log('Desktop/mobile screenshots and route checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
