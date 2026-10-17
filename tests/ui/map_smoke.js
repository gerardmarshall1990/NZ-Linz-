// Browser smoke test of the map app at phone width. Usage: node map_smoke.js <baseUrl> <screenshotPath> <address-substring>
const { chromium } = require('/opt/node-tools/node_modules/playwright');
(async () => {
  const [base, shot, addr] = process.argv.slice(2);
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 390, height: 800 } });
  const errors = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error' && !/tile\.openstreetmap|Failed to load resource/.test(m.text())) errors.push('console: ' + m.text()); });
  const fail = msg => { console.log('FAIL: ' + msg); console.log(errors.join('\n')); process.exit(1); };
  await page.goto(base + '/', { waitUntil: 'networkidle' });
  if (!page.url().endsWith('/login')) fail('not redirected to /login when signed out: ' + page.url());
  await page.fill('#p', process.env.UI_PASSWORD); await page.click('button'); await page.waitForURL(base + '/', { timeout: 10000 }).catch(() => fail('login did not complete'));
  await page.waitForLoadState('networkidle');
  if (!(await page.locator('.leaflet-container').count())) fail('map did not render');
  if (!/Rest Home Finder/.test(await page.title())) fail('title');
  // listings appear as clickable dots
  await page.waitForSelector('path.leaflet-interactive', { timeout: 15000 }).catch(() => fail('no listing dots on the map'));
  const dots = await page.locator('path.leaflet-interactive').count();
  await page.locator('path.leaflet-interactive').first().click({ force: true });
  await page.waitForFunction(a => document.querySelector('#panel')?.innerText.includes(a), addr, { timeout: 15000 }).catch(() => {});
  let txt = await page.locator('#panel').innerText();
  if (!txt.includes(addr)) fail('listing panel does not show the address: ' + txt.slice(0, 200));
  if (!/GREEN|AMBER|RED|GREY/.test(txt)) fail('no verdict shown');
  if (!/Natural hazard|hazard/i.test(await page.locator('footer').innerText())) fail('hazard note missing from footer');
  // tabs
  await page.click('button[data-t=parcel]'); txt = await page.locator('#panel').innerText();
  if (!/Zone/.test(txt) || !/information only/.test(txt)) fail('parcel tab: zone or hazard information-only note missing');
  await page.click('button[data-t=inputs]'); await page.waitForSelector('#a-fee_per_bed_per_week', { timeout: 10000 });
  txt = await page.locator('#panel').innerText(); if (!/blank:/.test(txt) || !/Nothing is guessed/.test(txt)) fail('inputs tab');
  await page.click('button[data-t=import]'); await page.waitForSelector('#lf', { timeout: 10000 });
  txt = await page.locator('#panel').innerText(); if (!/Trade Me/.test(txt) || !/realestate\.co\.nz/.test(txt)) fail('import tab coverage');
  await page.click('button[data-t=offer]'); await page.waitForFunction(() => /layout option|Offer Builder/.test(document.querySelector('#panel').innerText), null, { timeout: 10000 }).catch(() => fail('offer tab'));
  await page.click('button[data-t=chat]'); await page.fill('#cq', 'hello'); await page.click('#panel button.pri');
  await page.waitForFunction(() => /Not available|Analyst/.test(document.querySelector('#panel').innerText) && /hello/.test(document.querySelector('#panel').innerText), null, { timeout: 10000 }).catch(() => fail('chat tab'));
  // no horizontal scroll at phone width
  const sw = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth); if (sw > 2) fail('horizontal overflow of ' + sw + 'px');
  await page.screenshot({ path: shot });
  if (errors.length) fail('browser errors');
  console.log('OK dots=' + dots); await browser.close();
})().catch(e => { console.log('FAIL: ' + e.message); process.exit(1); });
