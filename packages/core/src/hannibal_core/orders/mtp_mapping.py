"""Signal MTP reconnu -> ordres du moteur de flotte, trame radio, destinataire, phrase française.

Repris de legacy/app_v3/hxbridge.py sans l'appel au service voix ni le registre d'audit.
"""

import re

KN_MIN, KN_MAX = 3, 28

STATUS_FR = {
    "ok": "Signal reconnu",
    "unknown_signal": "Signal inconnu : ce groupe n'est pas dans la publication",
    "spare": "Code sans sens attribué dans la publication",
    "not_releasable": "Sens non disponible (NOT RELEASABLE dans cette édition)",
    "invalid_parameter": "Paramètre hors limites",
    "missing_parameter": "Élément obligatoire manquant",
    "empty": "Aucun signal dans le message",
}


def fix_frame(text, ships, me):
    """Retablit la trame quand « THIS IS » n'a pas ete dit ou entendu. -> (texte, note)

    Dans la console, un message qui commence par un indicatif s'adresse a ce navire :
    « ALFA CORPEN ... » est un ordre a ALFA, pas le signal d'information « A CORPEN ».
    """
    t = re.sub(r"[^A-Za-z0-9 ]", " ", text).upper().split()
    names = [s.upper() for s in ships]
    if "THIS" in t or not t:
        return text, None
    if len(t) >= 3 and t[0] in names and t[1] in names and t[0] != t[1]:
        return f"{t[0]} THIS IS {t[1]} " + " ".join(
            t[2:]
        ), "« THIS IS » non entendu : rétabli d'après les indicatifs."
    if t[0] in names and t[0] != me.upper() and len(t) >= 2:
        return f"{t[0]} THIS IS {me.upper()} " + " ".join(
            t[1:]
        ), f"Le message commence par {t[0]} : pris comme destinataire."
    if t[:2] == ["ALL", "SHIPS"] and len(t) >= 3:
        return f"ALL SHIPS THIS IS {me.upper()} " + " ".join(t[2:]), None
    return text, None


HINTS = {
    "missing_parameter": "TURN et CORPEN exigent le bord. Dites par exemple : « Alfa, this is Hannibal, corpen starboard three three zero, over ».",
    "invalid_parameter": "Un cap se dit en trois chiffres (zero niner zero), un virage relatif en dizaines de degrés (niner = 90°), une vitesse en nœuds.",
    "unknown_signal": "Signaux qui font manœuvrer les navires : TURN PORT/STBD, CORPEN PORT/STBD, SPEED, FORMATION 1, 3, 4, FORMATION PORT/STBD, STATION.",
    "empty": "Dites le destinataire, « this is Hannibal », puis le signal, puis « over ».",
}


def reply_word(text, ships):
    """« CHARLIE THIS IS HANNIBAL AFFIRMATIVE OVER » -> ('affirm', 'charlie'). None si ce n'est pas une reponse."""
    t = re.sub(r"[^A-Za-z0-9 ]", " ", text).upper().split()
    names = [s.upper() for s in ships]
    dest = t[0].lower() if t and t[0] in names and "THIS" in t else None
    if "THIS" in t and t.index("THIS") + 2 < len(t):
        t = t[t.index("THIS") + 3 :]
    body = [w for w in t if w not in ("OVER", "OUT", "PERMISSION", "GRANTED", "DENIED", "IS", "THE")]
    if not body or len(body) > 2:
        return None
    if all(w in ("AFFIRMATIVE", "AFFIRM", "AFFIRMATIF") for w in body):
        return "affirm", dest
    if all(w in ("NEGATIVE", "NEGAT", "NEGATIF") for w in body):
        return "negat", dest
    if all(w in ("ROGER", "WILCO") for w in body):
        return ("wilco" if "WILCO" in body else "roger"), dest
    return None


def destination(interp, ships, default):
    """Destinataire -> (['TOUS'] ou ['NOM'], note)."""
    to = (interp.get("to") or "").upper().strip()
    names = [s.upper() for s in ships]
    if to in ("ALL SHIPS", "ALL", "ALL UNITS"):
        return ["TOUS"], None
    if to in names:
        return [to], None
    if to:
        return None, f"Destinataire « {to} » inconnu dans cette formation."
    d = (default or "TOUS").upper()
    return (
        ["TOUS"] if d == "TOUS" else [d]
    ), "Destinataire non énoncé : celui sélectionné à l'écran est utilisé."


def to_orders(interp, speed_kn):
    """Signal MTP reconnu -> (ordres du simulateur, note). speed_kn = vitesse actuelle visee."""
    if interp.get("status") != "ok":
        return [], None
    head, p, extra = interp.get("signal") or "", interp.get("params") or {}, interp.get("extra") or []
    num = next((int(x) for x in extra if str(x).isdigit()), None)

    def spd(kn, note=None):
        if kn > 45 or kn < 0:
            return None, f"Vitesse de {kn} nœuds invraisemblable."
        k = max(KN_MIN, min(KN_MAX, int(round(kn))))
        if k != kn:
            note = f"Vitesse ramenée à {k} nœuds (limites du simulateur : {KN_MIN} à {KN_MAX})."
        return [{"type": "SPEED", "kn": k}], note

    if head.startswith(("TURN [", "CORPEN [")):
        tog = head.startswith("TURN")
        how = (
            "Virage ensemble : chaque navire vire en même temps, les positions relatives sont conservées"
            if tog
            else "Évolution par conversion : la formation tourne avec le guide"
        )
        if "true_course" in p:
            return [
                dict(
                    {"type": "CORPEN", "cap": p["true_course"], "together": tog},
                    **({"side": p["side"]} if p.get("side") in ("PORT", "STBD") else {}),
                )
            ], how + f", jusqu'au cap {p['true_course']:03d}" + (
                f", en virant sur {'tribord' if p['side'] == 'STBD' else 'bâbord'}."
                if p.get("side") in ("PORT", "STBD")
                else " par le plus court."
            )
        if "relative_degrees" in p:
            return [
                {"type": "TURN", "deg": min(360, p["relative_degrees"]), "side": p["side"], "together": tog}
            ], how + "."
    if head == "SPEED" and "speed_knots" in p:
        return spd(p["speed_knots"])
    if head in ("SPEED H", "SPEED Q", "SPEED G") and num is not None:
        return spd(num)
    if head == "SPEED I" and num is not None:
        return spd(speed_kn + num)
    if head in ("SPEED D", "SPEED R") and num is not None:
        return spd(speed_kn - num)
    if head in ("SPEED 0", "SPEED S", "SPEED A"):
        return [{"type": "SPEED", "kn": KN_MIN}], f"Arrêt non simulé : vitesse minimale de {KN_MIN} nœuds."
    if head in ("FORM 1", "FORM 2"):
        return [{"type": "FORM", "name": "column"}], "Formation en colonne."
    if head == "FORM 3":
        return [
            {"type": "FORM", "name": "line_abreast_stbd"}
        ], "Ligne de front, les navires se rangent sur tribord du guide."
    if head == "FORM 4":
        return [
            {"type": "FORM", "name": "line_abreast_port"}
        ], "Ligne de front, les navires se rangent sur bâbord du guide."
    if head.startswith("FORM [PORT or STBD]") or head.startswith("FORM (PORT or STBD)"):
        deg = p.get("relative_bearing_degrees", 0)
        return (
            [
                {
                    "type": "FORM",
                    "name": "bearing",
                    "rel": deg if p.get("side") == "STBD" else (360 - deg) % 360,
                }
            ],
            f"Ligne de relèvement : les navires se rangent au {deg}° sur {'tribord' if p.get('side') == 'STBD' else 'bâbord'} du guide.",
        )
    if head.startswith("FORM [000") or head.startswith("FORM (000"):
        return [
            {"type": "FORM", "name": "bearing", "true": p.get("true_bearing", 180)}
        ], f"Ligne de relèvement : les navires se rangent au {p.get('true_bearing', 180):03d} vrai du guide."
    if head in ("STATION", "STATION E"):
        return [{"type": "RESUME"}], "Reprise de station."
    CAPT = {
        "TA62": (
            "investigate",
            "Le commandant du navire part reconnaître le contact le plus menaçant et manœuvre seul pour lui barrer la route.",
        ),
        "SU12": (
            "investigate",
            "Le commandant du navire part reconnaître le contact le plus menaçant et manœuvre seul pour lui barrer la route.",
        ),
        "INT SPEED": ("int_speed", "Le navire répond par sa vitesse."),
        "INT CORPEN": ("int_corpen", "Le navire répond par sa route et sa vitesse."),
        "INT STATION": ("int_station", "Le navire répond s'il est en station."),
        "STATION R": ("report_station", "Le navire rendra compte dès qu'il sera en station."),
    }
    if head in CAPT:
        return [{"type": "CAPT", "do": CAPT[head][0]}], CAPT[head][1]
    return (
        [],
        "Signal compris et consigné ; il n'a pas d'effet sur le mouvement des navires dans le simulateur.",
    )


def fr_signal(interp, to):
    """Phrase francaise pour les signaux de manoeuvre a parametres. None si non couvert.
    Vocabulaire a faire valider par l'expert."""
    head, p = interp.get("signal") or "", interp.get("params") or {}
    who = "À tous les navires" if to == ["TOUS"] else "À " + ", ".join(x.capitalize() for x in (to or []))
    side = {"PORT": "bâbord", "STBD": "tribord"}.get(p.get("side") or "")
    one = bool(to) and to != ["TOUS"]  # ordre a un seul navire
    if head.startswith("TURN [") and side:
        verb = "virer" if one else "virer ensemble"
        if "true_course" in p:
            return f"{who} : {verb} par {side} jusqu'au cap {p['true_course']:03d}."
        return f"{who} : {verb} de {p['relative_degrees']}° sur {side}."
    if head.startswith("CORPEN [") and side:
        if "true_course" in p:
            return f"{who} : changer de route par conversion sur {side} jusqu'au cap {p['true_course']:03d}."
        return f"{who} : changer de route par conversion de {p['relative_degrees']}° sur {side}."
    ASK = {
        "TA62": "aller reconnaître le contact.",
        "SU12": "aller reconnaître la piste, prêt à éclairer et à engager.",
        "INT SPEED": "quelle est votre vitesse ?",
        "INT CORPEN": "quelle est votre route (et votre vitesse) ?",
        "INT STATION": "quel est votre poste ?",
        "STATION R": "rendez compte quand vous serez en station.",
        "STATION": "prenez votre poste.",
        "STATION E": "reprenez votre poste.",
    }
    if head in ASK:
        return f"{who} : {ASK[head]}"
    if head.startswith(("FORM [PORT", "FORM (PORT")) and side:
        return f"{who} : se ranger sur la ligne de relèvement à {p.get('relative_bearing_degrees')}° sur {side} du guide."
    if head.startswith(("FORM [000", "FORM (000")):
        return (
            f"{who} : se ranger sur la ligne de relèvement au {p.get('true_bearing', 0):03d} vrai du guide."
        )
    if head == "SPEED" and "speed_knots" in p:
        if one:
            return f"{who} : prendre la vitesse de {p['speed_knots']} nœuds."
        return f"{who} : le guide prend la vitesse de {p['speed_knots']} nœuds, les autres navires tiennent leur poste."
    return None
