"""MedCore Seal: hospitals and labs stamp each document with a signed QR code.

The QR code carries the document's key facts and a digital signature. A verifier reads
the printed page again and compares it with the signed facts, field by field, so a
genuine QR code pasted onto an edited document is caught. Every seal is recorded in a
hash-chained public log, so a seal made with a stolen key (signed but never logged),
a revoked seal, or a deleted log entry is caught too.
"""
