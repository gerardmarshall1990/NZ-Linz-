// After opening a demo listing and creating its Property Record, clicks every button on the Rest Home, Offer, Develop and Track tabs and reports page errors, failed requests and red banners. Usage: node click_sweep.js <baseUrl>  (password in UI_PASSWORD)
const { chromium } = require('/opt/node-tools/node_modules/playwright');
(async () => {
  const base = process.argv[2];
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--no-sandbox'] });
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, acceptDownloads: true }); const page = await ctx.newPage();
  const out = []; let cur = '';
  page.on('pageerror', e => out.push(`[${cur}] pageerror: ${e.message}`));
  page.on('response', r => { if (r.status() >= 400 && !r.url().includes('tile.openstreetmap') && !r.url().includes('/api/property/') ) out.push(`[${cur}] HTTP ${r.status()} ${r.request().method()} ${r.url().replace(base, '')}`); });
  page.on('framenavigated', f => { if (f === page.mainFrame()) console.error('NAV', f.url()); });
  page.on('crash', () => console.error('CRASH'));
  page.on('dialog', d => d.dismiss().catch(() => {}));
  await page.goto(base + '/', { waitUntil: 'networkidle' });
  await page.fill('#p', process.env.UI_PASSWORD); await page.click('button'); await page.waitForURL(base + '/'); await page.waitForLoadState('networkidle');
  await page.waitForSelector('path.leaflet-interactive'); await page.waitForTimeout(1000);
  { const n = await page.locator('path.leaflet-interactive').count(); for (let i = 0; i < n; i++) { await page.locator('path.leaflet-interactive').nth(i).click({ force: true }); await page.waitForTimeout(1200); if ((await page.locator('#panel').innerText()).includes('DEMO')) break; } }
  await page.click('button[data-t=resthome]'); await page.waitForTimeout(1500);
  const mk = page.locator('#panel button', { hasText: 'Create Property Record' }); if (await mk.count()) { await mk.first().click(); await page.waitForTimeout(6000); }
  for (const t of ['resthome', 'offer', 'develop', 'track', 'best', 'screen']) {
    await page.locator(`button[data-t=${t}]`).dispatchEvent('click'); await page.waitForTimeout(1500);
    const labels = (await page.locator('#panel button').allInnerTexts()).map(x => x.trim()).filter(Boolean);
    for (let i = 0; i < labels.length; i++) {
      if (!(await page.locator('#tabs').count())) { out.push(`[${cur}] the app page was replaced: ${page.url()} :: ${(await page.locator('body').innerText()).slice(0, 200).replace(/\n/g, ' | ')}`); break; }
      cur = `${t}/${labels[i]}`.slice(0, 60); console.error('click', cur);
      await page.locator(`button[data-t=${t}]`).dispatchEvent('click'); await page.waitForTimeout(900);
      const b = page.locator('#panel button').nth(i); const lab = ((await b.innerText().catch(() => '')) || '').trim(); if (!lab || /sign out|delete|remove|send|mark sent|plans, scale/i.test(lab)) continue;
      try { await b.click({ timeout: 4000 }); } catch (e) { out.push(`[${cur}] could not click: ${e.message.split('\n')[0]}`); continue; }
      await page.waitForTimeout(2500);
      const txt = await page.locator('body').innerText(); const reds = await page.locator('.banner.red').allInnerTexts();
      const bad = reds.filter(x => /error|failed|not found|undefined|exception|\[object|HTTP|api\/|POST|422|500/i.test(x));
      if (bad.length) out.push(`[${cur}] red: ${bad.map(x => x.slice(0, 200)).join(' | ')}`);
      if (/undefined|\[object Object\]|NaN/.test(txt)) out.push(`[${cur}] text contains undefined/NaN/[object]`);
    }
  }
  console.log(out.join('\n') || 'no problems found'); await browser.close();
})().catch(async e => { console.log('FAIL: ' + e.message.split('\n')[0]); process.exit(1); });
