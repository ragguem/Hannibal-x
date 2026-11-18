# ADR 0005 — Contrats d'abord

- Statut : accepté
- Date : 2026-11-18
- Lot : 0

## Contexte

Les prochaines versions échangeront avec d'autres applications et systèmes (passerelle navire, C2, NMEA/AIS).
Un contrat déduit après coup du code fige des détails internes.

## Décision

- Tout échange est décrit d'abord dans `packages/contracts` (modèles Pydantic, `extra="forbid"`, immuables),
  qui produit les schémas JSON publiés dans `packages/contracts/schemas/`.
- Un test de dérive échoue si un modèle change sans régénération (`uv run hx-export-schemas`).
- L'API publie son OpenAPI 3.1 ; les événements seront décrits en AsyncAPI 3.0 et enveloppés en CloudEvents 1.0.2.
- Conventions : identifiants UUIDv7, unités SI, positions WGS 84, heures UTC ISO 8601,
  erreurs `{ code, message, request_id }`.

## Conséquences

- Le front et les clients externes se génèrent depuis les schémas.
- Toute rupture de contrat est visible dans la revue (diff de `schemas/`).
