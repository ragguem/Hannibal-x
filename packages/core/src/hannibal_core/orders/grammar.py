"""Parseur MTP a grammaire stricte (sans IA). Entree : texte anglais OTAN. Sortie : ordres."""

import re

from hannibal_core.orders.limits import DEFAULT_SPEED, SpeedLimits

FORMS = {"COLUMN": "column", "LINE ABREAST": "line_abreast", "SCREEN": "screen"}
FORM_FR = {
    "column": "colonne",
    "line_abreast": "ligne de front",
    "screen": "écran",
    "line_abreast_stbd": "ligne de front sur tribord",
    "line_abreast_port": "ligne de front sur bâbord",
    "bearing": "ligne de relèvement",
}
SIDES = {"PORT": "PORT", "STBD": "STBD", "STARBOARD": "STBD"}


def _norm(text):
    t = re.sub(r"[,.;:]", " ", text.upper())
    return re.sub(r"\s+", " ", t).strip()


def parse(text, ships, sender=None, speed: SpeedLimits = DEFAULT_SPEED):
    """-> dict(ok, to, orders, notes, error, hint). ships = noms en minuscules."""
    notes: list[str] = []
    t = _norm(text)
    names = [s.upper() for s in ships]
    to = ["TOUS"]
    # destinataire : "CHARLIE THIS IS HANNIBAL ..." ou "ALL SHIPS ..." ou "CHARLIE ..."
    m = re.match(
        r"^(ALL SHIPS|ALL|TOUS|" + "|".join(map(re.escape, names)) + r")\b(?: THIS IS [A-Z0-9]+)?\s*(.*)$", t
    )
    if m and m.group(2):
        dest = m.group(1)
        to = ["TOUS"] if dest in ("ALL SHIPS", "ALL", "TOUS") else [dest]
        t = m.group(2)
    elif m and not m.group(2):
        return _err("Message vide après le destinataire.", "Exemple : CHARLIE CORPEN 090")
    toks = [w for w in (t.split(" ") if t else []) if w != "OVER"]
    orders, i = [], 0
    while i < len(toks):
        k = toks[i]
        if k == "CORPEN":
            if i + 1 >= len(toks) or not re.fullmatch(r"\d{1,3}", toks[i + 1]):
                return _err("CORPEN attend un cap sur 3 chiffres.", "Exemple : CORPEN 090")
            cap = int(toks[i + 1])
            if cap > 359:
                return _err(f"Cap {cap} hors limites (0 à 359).", "Exemple : CORPEN 090")
            orders.append({"type": "CORPEN", "cap": cap})
            i += 2
        elif k == "TURN":
            if i + 1 >= len(toks) or not re.fullmatch(r"\d{1,3}", toks[i + 1]):
                return _err("TURN attend un angle en degrés.", "Exemple : TURN 30 STBD")
            deg = int(toks[i + 1])
            i += 2
            side = None
            if i < len(toks) and toks[i] == "TO":
                i += 1
            if i < len(toks) and toks[i] in SIDES:
                side = SIDES[toks[i]]
                i += 1
            if side is None:
                return _err("TURN attend un bord : PORT ou STBD.", "Exemple : TURN 30 STBD")
            if i < len(toks) and toks[i] == "TOGETHER":
                i += 1
            if deg < 1 or deg > 360:
                return _err("Angle de TURN hors limites (1 à 360).", "Exemple : TURN 30 STBD")
            orders.append({"type": "TURN", "deg": deg, "side": side})
            i += 1 - 1
        elif k == "SPEED":
            if i + 1 >= len(toks) or not re.fullmatch(r"\d{1,2}", toks[i + 1]):
                return _err("SPEED attend une vitesse en nœuds.", "Exemple : SPEED 12")
            kn = int(toks[i + 1])
            i += 2
            if i < len(toks) and toks[i] in ("KNOTS", "KTS", "KN"):
                i += 1
            kn, note = speed.clamp(kn)
            if note:
                notes.append(note)
            orders.append({"type": "SPEED", "kn": kn})
        elif k == "FORM":
            rest = " ".join(toks[i + 1 :])
            name = next((v for key, v in FORMS.items() if rest.startswith(key)), None)
            if not name:
                return _err("Formation inconnue.", "Formations : COLUMN, LINE ABREAST, SCREEN")
            orders.append({"type": "FORM", "name": name})
            i += 1 + len(next(key for key in FORMS if rest.startswith(key)).split(" "))
        elif k == "EMERG":
            orders.append({"type": "EMERG", "text": " ".join(toks[i + 1 :])})
            i = len(toks)
        elif k in ("ROGER", "WILCO"):
            orders.append({"type": "ACK", "text": k})
            i += 1
        elif k == "RESUME" and i + 1 < len(toks) and toks[i + 1] == "STATION":
            orders.append({"type": "RESUME"})
            i += 2
        else:
            return _err(
                f"Mot inconnu : {k}.",
                "Mots reconnus : CORPEN, TURN, SPEED, FORM, EMERG, ROGER, WILCO, RESUME STATION",
            )
    if not orders:
        return _err("Aucun ordre reconnu.", "Exemple : CORPEN 090 SPEED 12")
    return {"ok": True, "to": to, "orders": orders, "notes": notes, "error": None, "hint": None}


def _err(msg, hint):
    return {"ok": False, "to": [], "orders": [], "notes": [], "error": msg, "hint": hint}


def fr_order(o):
    t = o["type"]
    if t == "CORPEN":
        return f"Faire route au cap {o['cap']:03d}°"
    if t == "TURN":
        return f"Virer de {o['deg']}° à {'droite' if o['side'] == 'STBD' else 'gauche'}"
    if t == "SPEED":
        return f"Prendre la vitesse de {o['kn']} nœuds"
    if t == "FORM":
        return f"Prendre la formation : {FORM_FR.get(o['name'], o['name'])}"
    if t == "RESUME":
        return "Reprendre sa station"
    if t == "ACK":
        return "Accusé de réception"
    if t == "EMERG":
        return "Message d'urgence : " + o.get("text", "")
    return str(o)


def fr_message(to, orders):
    who = "À tous les navires" if to == ["TOUS"] else "À " + ", ".join(x.capitalize() for x in to)
    return who + " : " + " ; ".join(fr_order(o) for o in orders)


def to_text(to, orders, sender):
    """ordre structure -> texte anglais OTAN (pour les messages programmes)."""
    parts = []
    for o in orders:
        t = o["type"]
        if t == "CORPEN":
            parts.append(f"CORPEN {o['cap']:03d}")
        elif t == "TURN":
            parts.append(f"TURN {o['deg']} {o['side']}")
        elif t == "SPEED":
            parts.append(f"SPEED {o['kn']}")
        elif t == "FORM":
            parts.append("FORM " + {v: k for k, v in FORMS.items()}.get(o["name"], o["name"].upper()))
        elif t == "RESUME":
            parts.append("RESUME STATION")
        elif t == "ACK":
            parts.append(o.get("text", "ROGER"))
        elif t == "EMERG":
            parts.append("EMERG " + o.get("text", ""))
    dest = "ALL SHIPS" if to == ["TOUS"] else to[0]
    return f"{dest} THIS IS {sender.upper()} " + " ".join(parts) + " OVER"
