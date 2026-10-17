// Demo screenshots at phone width: map with the sample listings, a listing's verdict, and the Offer Builder result. Usage: node demo_shots.js <baseUrl> <outDir> <addressSubstring>
const { chromium } = require('/opt/node-tools/node_modules/playwright');
(async () => {
  const [base, out, addr] = process.argv.slice(2);
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  await page.goto(base + '/', { waitUntil: 'networkidle' });
  await page.fill('#p', process.env.UI_PASSWORD); await page.click('button'); await page.waitForURL(base + '/'); await page.waitForLoadState('networkidle');
  await page.waitForSelector('path.leaflet-interactive'); await page.waitForTimeout(2500);
  await page.screenshot({ path: out + '/1_map.png' });
  // open the listing whose panel mentions the address
  const dots = await page.locator('path.leaflet-interactive').count();
  for (let i = 0; i < dots; i++) {
    await page.locator('path.leaflet-interactive').nth(i).click({ force: true }); await page.waitForTimeout(1200);
    if ((await page.locator('#panel').innerText()).includes(addr)) break;
  }
  await page.locator('#panel').scrollIntoViewIfNeeded(); await page.waitForTimeout(500);
  await page.screenshot({ path: out + '/2_listing_verdict.png', fullPage: true });
  await page.click('button[data-t=offer]'); await page.waitForSelector('#o-opt');
  await page.click('#panel button.pri'); await page.waitForSelector('#oo .card', { timeout: 20000 });
  await page.locator('#oo').scrollIntoViewIfNeeded(); await page.waitForTimeout(500);
  await page.screenshot({ path: out + '/3_offer_builder.png', fullPage: true });
  console.log('OK'); await browser.close();
})().catch(e => { console.log('FAIL: ' + e.message); process.exit(1); });
