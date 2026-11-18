# ADR 0003 — Le pilotage de la flotte s'exécute dans `sim-bridge`

- Statut : accepté
- Date : 2026-11-18
- Lot : 0 (décision), 1 et 2 (réalisation)

## Contexte

Dans `app_v3`, le serveur web calcule à 2 Hz les waypoints « carotte », la rampe de vitesse, l'évitement
et le sillage, puis les publie sur ROS. La 1.1.0 plaçait ce calcul dans l'API.
Une boucle de commande à 2 Hz dans le processus HTTP couple la latence des requêtes à la tenue des navires.

## Décision

- L'API envoie des **intentions** (`PUT /intents` : route, vitesse, formation, guide) à `sim-bridge`.
- `sim-bridge` exécute la boucle de pilotage avec `core.fleet.control`, code pur testé sans ROS.
- Rythmes : moteur de scénario 500 ms, état de la flotte 250 ms, diffusion SSE 250 ms.

## Conséquences

- L'API peut redémarrer sans que les navires perdent leur consigne.
- Le contrat `FleetIntent` devient l'interface stable vers tout autre simulateur ou vers un système réel.
