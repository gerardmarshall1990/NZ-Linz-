// Opens a demo listing at phone width and visits every tab, reporting page errors, failed requests and red error banners. Usage: node tab_sweep.js <baseUrl> <outDir>   (password in UI_PASSWORD)
const { chromium } = require('/opt/node-tools/node_modules/playwright');
(async () => {
  const [base, out] = process.argv.slice(2);
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  const problems = [];
  page.on('pageerror', e => problems.push('pageerror: ' + e.message));
  page.on('response', r => { if (r.status() >= 400 && !r.url().includes('tile.openstreetmap')) problems.push(`HTTP ${r.status()} ${r.request().method()} ${r.url().replace(base, '')}`); });
  await page.goto(base + '/', { waitUntil: 'networkidle' });
  await page.fill('#p', process.env.UI_PASSWORD); await page.click('button'); await page.waitForURL(base + '/'); await page.waitForLoadState('networkidle');
  await page.waitForSelector('path.leaflet-interactive'); await page.waitForTimeout(1500);
  { const n = await page.locator('path.leaflet-interactive').count(); for (let i = 0; i < n; i++) { await page.locator('path.leaflet-interactive').nth(i).click({ force: true }); await page.waitForTimeout(1200); if ((await page.locator('#panel').innerText()).includes('DEMO')) break; } }
  await page.click('button[data-t=resthome]'); await page.waitForTimeout(1500);
  const mk = page.locator('#panel button', { hasText: 'Create Property Record' }); if (await mk.count()) { await mk.first().click(); await page.waitForTimeout(6000); }
  const tabs = await page.locator('#tabs button').evaluateAll(bs => bs.map(b => b.dataset.t));
  for (const t of tabs) {
    problems.push(`-- tab ${t}`);
    await page.click(`button[data-t=${t}]`); await page.waitForTimeout(1800);
    const txt = await page.locator('#panel').innerText();
    const reds = await page.locator('#panel .banner.red').allInnerTexts();
    const err = reds.filter(x => /error|failed|not found|undefined|null|exception|\[object/i.test(x));
    if (err.length) problems.push('  red banner: ' + err.map(x => x.slice(0, 160)).join(' | '));
    if (/undefined|\[object Object\]|NaN/.test(txt)) problems.push('  text contains undefined/NaN/[object]');
    if (txt.trim().length < 20) problems.push('  empty panel');
    await page.screenshot({ path: `${out}/tab_${t}.png`, fullPage: true });
  }
  console.log(problems.join('\n')); await browser.close();
})().catch(e => { console.log('FAIL: ' + e.message); process.exit(1); });
