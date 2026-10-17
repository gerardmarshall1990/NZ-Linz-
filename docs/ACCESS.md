# Opening the app on your iPhone: free, private, login required

**Design:** the app listens on `127.0.0.1` only (never on all network interfaces). Tailscale (free personal plan) forwards a private HTTPS address on **your own tailnet** to it, so only devices you have signed in to Tailscale can even reach it. Nothing is on the public internet. On top of that, every page and every API call needs the app login (`APP_PASSWORD`), with rate-limited sign-in, a server-side session, an HttpOnly + SameSite=Strict + Secure cookie, refusal of cross-site writes and security headers. With no `APP_PASSWORD` set, the app refuses to serve anything. The Anthropic key, database passwords, LINZ key and backup passphrase live only in the server environment: no page or API response contains them (tested).

## One-time setup (you, on the iPhone and the Claude app)
1. **Tailscale account:** go to login.tailscale.com, sign in with Apple or Google (free Personal plan). Install **Tailscale** from the App Store on your iPhone, sign in with the same account, and leave it connected.
2. **Tailscale admin console → DNS:** switch on **MagicDNS** and **HTTPS Certificates** (needed for the https address).
3. **Admin console → Settings → Keys → Generate auth key:** tick **Reusable** and **Ephemeral**, expiry 90 days. Copy the key.
4. **Claude app → this session's cloud environment menu (title bar) → Edit → environment variables** (use *Network secrets* if offered). Add two: `APP_PASSWORD` (a long random passphrase of 16+ characters from your password manager) and `TS_AUTHKEY` (the key from step 3). Save. **Never paste either into chat.** A new session picks them up.
5. **Network access (same Edit screen):** allow these domains for the sandbox (Allowed domains, keep "Allow package managers" ticked): `controlplane.tailscale.com`, `login.tailscale.com`, `pkgs.tailscale.com` (one-time install), `log.tailscale.com` and `*.tailscale.com` (relay servers such as `derp1.tailscale.com`). Nothing else is needed for access. (Your phone's browser fetches the map library from `cdnjs.cloudflare.com` and map tiles from `tile.openstreetmap.org`; those are your phone's requests, not the sandbox's.)

## Each time (I do this at the start of a session)
`make app-private` (runs `scripts/start_private.sh`): it refuses to start unless both variables are set, starts the app on `127.0.0.1:8000`, joins your tailnet as `nz-linz`, and prints the address, `https://nz-linz.<your-tailnet>.ts.net`. Open it in Safari on the iPhone (Tailscale connected), sign in with `APP_PASSWORD`, then Share → **Add to Home Screen**.

## What is and is not verified
Verified: the app's login, session, rate limiting, headers and secrets-never-in-responses (10 tests + a browser test that signs in); the app binds to localhost only; the sandbox can reach the Tailscale control plane and installer (a test node asked for a login link; I removed it). **Not verified end to end:** joining your tailnet and serving HTTPS to the phone, because that needs your `TS_AUTHKEY`. The first run may need a small fix; I will say so.
Other routes I tried: Cloudflare Tunnel needs outbound TCP 7844, which the sandbox network does not allow, so it is not an option here.

## Limits you should know
- The sandbox is temporary and the database lives in it. The app is reachable only while a session is running, and everything you enter is safe only because of the encrypted backups (`docs/BACKUP.md`). For an always-on app you would need a small permanent server (for example a free-tier cloud VM); say if you want that later.
- Anyone who gets both your Tailscale login and `APP_PASSWORD` can open the app: use a strong passphrase and turn on two-step sign-in for your Tailscale account.
