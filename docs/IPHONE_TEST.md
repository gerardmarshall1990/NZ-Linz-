# Test the app on your iPhone (about 15 minutes)

## One-time setup (you; I cannot do these)
1. **Tailscale** (free): sign in at login.tailscale.com with Apple or Google, install the Tailscale app from the App Store on the iPhone, sign in with the same account and leave it connected. In the admin console switch on MagicDNS and HTTPS Certificates, then Settings, Keys, Generate auth key (Reusable, Ephemeral, 90 days) and copy it.
2. **Claude app, this session's cloud environment, Edit, environment variables** (use *Network secrets* if offered): add `APP_PASSWORD` (16+ random characters from your password manager) and `TS_AUTHKEY` (the key from step 1). Allow the Tailscale domains listed in `docs/ACCESS.md`. Start a **new session** so the variables load.
3. Optional now, needed later: `BACKUP_PASSPHRASE`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`.

## Each time (the session does this)
`bash scripts/db_up.sh`, `make demo-seed`, `make preflight` (shows OK/MISSING by name, never a value), then `make app-private`. It prints a private `https://nz-linz...ts.net` address that only your own devices on Tailscale can open. Nothing is public: without the Tailscale connection the address does not resolve, and without `APP_PASSWORD` the app refuses every request.

## Login
Open the printed address in Safari. Enter `APP_PASSWORD`. Five wrong tries in 15 minutes lock you out for a while. **Sign out** is at the top right. Tip: Share, Add to Home Screen.

## The 3 DEMO listings
`make demo-seed` loads three listings with real Auckland addresses and **invented** rent and bedrooms, each badged **DEMO** in the app: 80 Hinemoa Street, Birkenhead (30 beds, $4,800); 282 Lincoln Road, Henderson (24 beds, $3,900); 14 Shipherds Avenue, Epsom (7 beds, $1,950). `make demo-clear` removes them. They never change your saved inputs.

## 10-step test script (tick each; note anything odd and tell me)
1. Open the address: you land on the **login** page, not the map. Wrong password is refused. Correct password opens the map.
2. The map shows three coloured dots (verdict colours). Tap one: the **Listing** tab shows the red **DEMO** banner, the address, a verdict (GREEN / AMBER / RED / GREY) with reasons.
3. If a banner says **"Uses placeholder inputs: not decision-grade"**, tap the link: the **Placeholders** page lists each placeholder, its value, its source and an edit box. The verdict is never GREEN while placeholders are used.
4. **Parcel** tab: zone, area, title type; the hazard note says flood and other hazards are information only for conversions.
5. **My inputs** tab: blank costs are shown as blank ("Nothing is guessed"). Enter a number, save, reload: it stays. Clear it: it goes back to blank.
6. **Offer** tab on a DEMO listing: choose fixed rent / profit share / minimum payment plus share. You see walk-away rent, cash required and the downside cases. Inputs missing: it says "Needs your input", not a number.
7. **Import** tab: paste a CSV row of a listing you know; it reports matched / not matched before saving (dry run), then import.
8. Search an address in the search box; tap **Rest Home**: create the Property Record, then **Plans, scale and review** to upload a floor plan (PDF, photo or DXF) and review the reading. (Needs a plan; skip if you have none.)
9. After a confirmed plan: **Layout options**, **Compliance checks**, **What-if** sliders, **Deal sheet PDF**, **Consent pack** (answers sheet for the Council's AC1009 checklist; everything stamped DRAFT; "ready to lodge" refused until all required items are in).
10. **Sign out**, then reload: you are back at the login page. Run `make demo-clear` to remove the demo listings.

## What to expect honestly
Verdicts and numbers use your inputs and clearly flagged placeholders. Regulatory values (room sizes, ensuite ratios) are blank until you supply the standards, so bed counts are upper bounds and say so. Chat ("Ask") says "not available" until the Anthropic key is set.
