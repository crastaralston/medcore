# Documents for the Verify screen

Upload these one at a time on the **Verify** screen. Each shows a different result.

| File | What it is | What Verify says |
| --- | --- | --- |
| `1_genuine_sealed_lab_report.pdf` | A lab report sealed by its lab and not touched since. | **Genuine**: Sealed by Accucheck Diagnostic Centre on 2026-10-25. Every signed fact matches the printed page, and so does the rest of the text. |
| `2_edited_after_sealing.pdf` | The same kind of report: after sealing, the platelet count was changed and the real QR code copied onto the edited page. | **Altered after sealing**: Platelet count: signed '1,13,000', printed '30,000' |
| `3_fake_qr_unregistered_lab.pdf` | A forger made their own QR code, claiming to be 'TrustMe Diagnostics', which is not a registered lab. | **Sealed by an unregistered issuer**: The seal claims to come from 'trustme-diagnostics', which is not in the registry. Anyone can print a QR code; only registered issuers can make a valid seal. |
| `4_stolen_key_never_logged.pdf` | Signed with a real lab's key, as if the key had been stolen, but never recorded in the public log. | **Seal is not in the public log**: The signature is Accucheck Diagnostic Centre's, but this seal was never recorded in the public log. Every genuine seal is logged when it is made, so the signing key may have been stolen. |
| `5_unsealed_lab_report.pdf` | An ordinary lab report with no QR code at all. | **No seal on this document**: This document has no QR seal, so only the three content checks apply. |

To show revocation: open **Registry and log**, press *Revoke* on a seal, then verify `1_genuine_sealed_lab_report.pdf` again. It now says the seal was revoked.
