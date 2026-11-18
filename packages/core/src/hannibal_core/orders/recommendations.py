"""Recommandations a base de regles (sans IA)."""

from hannibal_core.orders import grammar as mtp
from hannibal_core.orders import kinematics as sim


def recommend(state, player, guide, pending, reported):
    """state: dict(ships=[...], contacts=[...]). -> liste de {text, reason, kind} par priorite."""
    out: list[dict[str, str]] = []
    gdest = "ALL SHIPS" if player.upper() == guide.upper() else guide.upper()
    me = next((s for s in state["ships"] if s["name"].upper() == player.upper()), None)
    if not me:
        return out
    # 1. ordre recu non execute
    for p in pending:
        out.append(
            {
                "kind": "executer",
                "text": mtp.to_text([player.upper()], p["orders"], player)
                .replace(" OVER", "")
                .replace(f"{player.upper()} THIS IS {player.upper()} ", f"{player.upper()} "),
                "reason": "Ordre reçu du guide, pas encore exécuté : "
                + mtp.fr_message(["TOUS"], p["orders"]).split(" : ", 1)[1],
            }
        )
        out.append(
            {
                "kind": "accuse",
                "text": f"{gdest} THIS IS {player.upper()} ROGER WILCO OVER",
                "reason": "Accuser réception de l'ordre",
            }
        )
    # 2. contact non classe proche
    for c in state["contacts"]:
        info = sim.cpa_now(me, c)
        if c.get("cls", "inconnu") == "inconnu" and info["range_nm"] < 6.0 and c["id"] not in reported:
            brg = int(round(info["brg"])) % 360
            out.append(
                {
                    "kind": "emerg",
                    "text": f"{gdest} THIS IS {player.upper()} EMERG JULIET INVESTIGATING UNCLASSIFIED CONTACT BEARING {brg:03d} DISTANCE {info['range_nm']:.0f} OVER",
                    "reason": f"Contact {c['id']} non classé à {info['range_nm']:.1f} NM, relèvement {brg:03d}°",
                }
            )
        # 3. CPA trop faible
        if info["cpa_nm"] < 1.0 and info["tcpa_min"] < 20 and info["range_nm"] < 8.0:
            best = None
            for side in ("STBD", "PORT"):
                for deg in (30, 60):
                    g = sim.ghost([me], [me["name"]], [{"type": "TURN", "deg": deg, "side": side}], [c], 900)
                    cp = g["cpa"][0]["cpa_nm"]
                    if best is None or cp > best[0]:
                        best = (cp, side, deg)
            if best:
                dest = "TOUS" if player.upper() == guide.upper() else player.upper()
                out.append(
                    {
                        "kind": "eviter",
                        "text": f"{dest} TURN {best[2]} {best[1]}",
                        "reason": f"CPA actuel {info['cpa_nm']:.1f} NM avec {c['id']} ; après ce virage : {best[0]:.1f} NM",
                    }
                )
    # 4. hors formation
    if player.upper() != guide.upper() and me.get("etat") == "Hors formation":
        out.append(
            {
                "kind": "station",
                "text": f"{player.upper()} RESUME STATION",
                "reason": "Le navire est hors de sa station",
            }
        )
    if not out:
        out.append(
            {
                "kind": "veille",
                "text": f"{gdest} THIS IS {player.upper()} ROGER OVER",
                "reason": "Rien d'urgent : accusé de réception",
            }
        )
    return out
