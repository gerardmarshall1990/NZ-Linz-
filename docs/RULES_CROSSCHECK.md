# Rules cross-check (machine, independent of the loader)

Checked 144 operative numeric rules against the Council PDFs on 2026-10-19: **142 agree, 2 agree after reading the page by hand, 0 partial, 0 disagree.**

Agree = the stored number is in the stored quote, the quote is found on the cited page in the PDF text layer and/or the OCR, and the number appears in the surrounding text on that page. This is a tool check, not an owner confirmation: rules stay `owner_verified = false`.

## REVIEWED (2)
| rule id | zone | parameter | value | ref | page | quote in text layer | quote in OCR | value near quote |
|---|---|---|---|---|---|---|---|---|
| 52 | Residential - Mixed Housing Suburban Zone | yard_coastal_protection_min | 10 m | H4.6.7 | 14 | False | False | False |
| 82 | Residential - Mixed Housing Urban Zone | yard_coastal_protection_min | 10 m | H5.6.8 | 15 | False | False | False |
- rule 52: value 10 m confirmed in the H4 yards table on page 15 ('Coastal protection yard 10m, or as otherwise specified in Appendix 6'); the quote omits the word 'yard' and the cited page 14 is one page early
- rule 82: value 10 m confirmed in the H5 yards table on page 16 (same wording); the cited page 15 is one page early
