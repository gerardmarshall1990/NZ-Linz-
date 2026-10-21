# Final phone script: your real listings to a draft consent pack (Block 5)

Do this once the server is up (or on the sandbox address) with your real CSV and one real property. Send me **one message** with anything that looked wrong.

1. **Import.** Open the address, log in. **Import** tab, choose your CSV, **Dry run**. Read the "things to check" list (rent units, rows with no street number, weak address matches). Fix the file or accept, then **Import**.
2. **Address matches.** Under "Address matches to check", fix any weak match by entering the parcel id (open the parcel on the map to see it).
3. **Verdicts.** Zoom the map to your listings, clear the verdict filter, tap each dot: **Listing** tab shows GREEN / AMBER / RED / GREY with reasons. AMBER with "placeholder inputs" is expected until you replace the placeholders (**My inputs**, **Placeholders**).
4. **Offer.** **Offer** tab, **Quick answer**: check the current rent and beds, type your fee, occupancy and the profit you want per bed, tap **Show me**: net revenue, most you could pay, offers at 1.0x to 1.5x. Use the detailed builder for fixed rent / profit share / minimum plus share.
5. **One real property.** Search its address, **Find**, **Open**, **Rest Home** tab, **Create Property Record from open data**.
6. **Plan.** **Plans, scale and review**: upload the floor plan (DXF reads exactly; a PDF or photo needs a scale: tap two points of a known length, **Set scale**), check each room's type, fix wrong ones, **Confirm level**.
7. **Layouts and compliance.** Back on **Rest Home**: **Layout options** (conservative / base / max beds), **Compliance checks** (PASS / FAIL / NEEDS_PROFESSIONAL, each with its source).
8. **Deal Sheet.** Tap **Deal sheet PDF**. It opens with the DRAFT stamp, assumptions and what is missing.
9. **Consent pack.** Tap **Consent pack**: it lists what is missing (Council forms not yet seen, professional documents, record of title). Fill the fields you know; **Export** gives the draft zip. "Ready to lodge" stays refused until every required item is in.
10. **Sign out.** Then tell me what failed.

## Known gaps at handover
Placeholders cap verdicts at AMBER until you replace them. Ngā Paerewa bed-rule values are blank unless you type them (Standards tab). Building Code and Acceptable Solution text was not fetched (site blocks scripts). The plan reader for photos and scans needs the Anthropic key; DXF needs none. The consent pack follows the spec list until the Council's resource consent checklist is seen. Server setup has not run on a real server yet.
