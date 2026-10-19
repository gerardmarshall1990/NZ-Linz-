# Known-outcome parcels (BLOCKERS item 16): not met

Asked for 10 or more public Auckland consent decisions with provenance. **Result: 6 candidates, none usable yet as a test oracle.**

- All 6 (`known_outcomes_raw.json`) are retirement villages (4 granted, 1 granted with conditions, 1 declined). None is a rest-home or house conversion, which is what the verdict engine screens.
- Every record comes from a search-result snippet only. No page was read in full: the fetch tool could not resolve the hosts, nzlii.org returned 403, and aucklandcouncil.govt.nz answers scripts with a block that is not bypassed.
- Decision dates, consent numbers and zones are mostly missing, so none can be matched to a parcel and run through the verdicts. **No verdict-versus-outcome comparison was made, and none is claimed.**
- Treat the file as leads to verify by hand, not as evidence.

What would close it: a list from you (or a licensed property-data provider) of 10+ Auckland sites with known consent outcomes for care or conversion use, or Council hearing decision PDFs saved into `docs/sources_manual/other/`. Then `make validate` compares the verdicts and lists disagreements.
