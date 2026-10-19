# Hosting: keeping the database and app running past the 2-hour limit

Written 2026-10-19. **Prices and limits below come from web searches of third-party pages, not from the providers' own price lists. Check the provider's page on the day you sign up.** Nothing here has been tested on a real server.

## What the app needs
- PostgreSQL with PostGIS. The database is **7.1 GB** today (raw 4.6 GB, core 2.0 GB, analytics 0.2 GB). The 4.6 GB `raw` part can be rebuilt from public sources (`make bootstrap`, hours, needs the LINZ key). Your own data (property records, listings, inputs, uploads) is small and is what the backup protects.
- About 4 GB of memory and 20 GB of disk (the sandbox has 16 GB and 252 GB).
- One Python web process on port 8000, reached privately through Tailscale (the same `https://nz-linz.tailcbf7ad.ts.net` address, no public exposure).
- Secrets in `.env` (never committed): `APP_PASSWORD`, `TS_AUTHKEY`, `LINZ_API_KEY`, `BACKUP_PASSPHRASE`.

## Option A: stay in the Claude cloud session (free, fragile)
- **Cost:** nothing extra beyond your Claude plan.
- **How:** type `restart app` to me in the session, or I run `make restart`. A nightly routine (2:46 am NZ) runs `make restart` and `make backup`. Supervisor tasks stop after 2 hours, so the app can be down until the next message or nightly run.
- **Phone steps:** none. Open the address in Safari; if it does not load, message me `restart app`.
- **Risks:** the container is reclaimed after inactivity and **the database is lost with it** unless the encrypted off-box backup exists (not set up yet: see BACKUP.md). Rebuilding `raw` takes hours. Treat this as a testing setup only.

## Option B: Oracle Cloud "Always Free" VM (free, awkward)
- **Cost:** $0 while you stay inside the Always Free limits. Reports say Oracle cut the free Ampere A1 allowance from 4 OCPU / 24 GB to **2 OCPU / 12 GB on 15 June 2026** ([InfoQ](https://infoq.com/news/2026/07/oracle-cloud-free-tier-limits/), [Linuxiac](https://linuxiac.com/oracle-quietly-cuts-free-tier-ampere-a1-resources-in-half/)); Oracle's own page lists 200 GB of free block storage, with a 47 GB minimum boot volume ([Oracle docs](https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm)). 12 GB and 200 GB are enough for this app.
- **Phone steps:** sign up at oracle.com/cloud/free (needs a credit card for identity); create an Ubuntu ARM instance; paste the setup commands into the browser console; install Tailscale on it with a fresh `TS_AUTHKEY`; restore the encrypted backup and run `make bootstrap`.
- **Risks:** "out of capacity" errors when creating the VM, accounts or idle instances reclaimed without notice, allowance cut again, ARM builds of some Python packages. Sign-up from a phone is fiddly.

## Option C: small paid VPS (recommended)
- **Hetzner Cloud**, 2 vCPU / 4 GB: **about EUR 4 to 6 a month plus about EUR 0.50 for an IPv4 address.** Sources disagree on the exact figure after the 1 April 2026 price rise (CX22 was replaced by CX23, about EUR 3.99 to 5.99; CPX22 about EUR 8 to 20). See [Cloud Pricing Comparison, Aug 2026](https://kimmo.suominen.com/stuff/cpc-2026-08.txt) and [Hetzner pricing summary](https://agentdeals.dev/hetzner-pricing-2026). Check hetzner.com/cloud; pick a plan with at least 4 GB memory and 40 GB disk.
- **DigitalOcean** alternative: about **US$24 a month** for 2 vCPU / 4 GB / 80 GB; weekly backups add 20% ([third-party summary](https://www.linuxteck.com/guides/digitalocean-review-2026/); unverified against DigitalOcean's own page).
- **Phone steps:** create the account in Safari; create an Ubuntu 24.04 server; open the provider's web console and paste the setup commands I give you; join Tailscale with a fresh `TS_AUTHKEY`; restore the encrypted backup; run `make bootstrap`; I then check the app from the server's `make restart`.
- **Risks:** a monthly bill you must watch; you must keep the server updated; if the backup passphrase is lost the backup is unreadable.

## Recommendation
Use **Option C (Hetzner, about EUR 6 a month)** once the private backup repository and passphrase are in place. It is the only option where the database survives and the app stays up without anyone messaging me. Keep Option A for testing until then. Option B is worth trying only if saving EUR 6 a month matters more than a reliable sign-up.

## Before any move
1. Backup repo and passphrase working (docs/BACKUP.md), with a tested restore.
2. A fresh Tailscale auth key for the new machine.
3. The same `.env` values, entered on the server, never in chat or git.
