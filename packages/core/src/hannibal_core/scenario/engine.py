"""Moteur de scénario : événements, ordres, pistes, exercice, capitaines, barre manuelle, évaluation, débrief.

Repris de legacy/app_v3/server.py (classe `Hannibal`) sans ROS, Docker, threads, registre d'audit ni service voix.
L'appelant fournit l'horloge (`clock`, secondes), l'aléa (`rng`) et, à chaque `tick`, l'état des navires ; le moteur
rend les points de route à envoyer au simulateur. Une instance par mission ; les appels doivent être sérialisés.
"""

import math
import random
from collections.abc import Callable
from typing import Any, cast

from hannibal_core.fleet.control import FORMS, KN, VMAX, FleetController, angdiff, clamp, slots
from hannibal_core.orders import grammar as mtp
from hannibal_core.orders import kinematics as sim
from hannibal_core.orders import recommendations as reco

NM = 1852.0
START = (0.0, -300.0)
VMAX_GUIDE = 10.3
TURN_CONTACT = 3.0
TOL = 90


class ScenarioEngine:
    MOTION = ("CORPEN", "TURN", "SPEED", "FORM", "RESUME")

    def __init__(
        self,
        sc,
        player,
        *,
        clock: Callable[[], float],
        rng: random.Random | None = None,
        fleet: FleetController | None = None,
        auto=False,
        manual=False,
    ) -> None:
        self.clock = clock
        self.rng = rng or random.Random()  # noqa: S311 — tirage d'exercice, pas de la cryptographie
        self.fleet = fleet or FleetController()
        self.st: dict[str, Any] = {}
        self.msg_id = 0
        cap = float(sc.get("cap_initial", 0))
        f0 = sc.get("formation_depart", "column")
        guide = next(f["nom"] for f in sc["flotte"] if f["role"] == "guide")
        ships = {
            f["nom"]: {"role": f["role"], "mode": "formation", "cap": cap, "v": 0.0, "dI": 0.0}
            for f in sc["flotte"]
        }
        self.run = {
            "sc": sc,
            "player": player,
            "guide": guide,
            "t0": clock(),
            "ships": ships,
            "gcap": cap,
            "gspeed": clamp(sc.get("vitesse_initiale_kn", 12) * KN, 1.5, VMAX_GUIDE),
            "form": f0,
            "events": sorted([e for e in sc.get("evenements", []) if "t" in e], key=lambda e: e["t"]),
            "cond": [e for e in sc.get("evenements", []) if "t" not in e],
            "drill": self._drill_init(sc),
            "dyn": [],
            "contacts": {},
            "msgs": [],
            "pending": [],
            "reported": set(),
            "plog": [],
            "ended": False,
            "debrief": None,
            "min_ship": 1e9,
            "min_cpa": {},
            "plan": [],
            "auto": bool(auto),
            "manual": bool(manual),
            "helm": {
                "cap": cap,
                "kn": float(sc.get("vitesse_initiale_kn", 12)),
                "rudder": 0,
                "last": 0,
                "steady": True,
            },
        }
        self.say(
            "SYSTÈME",
            "TOUS",
            "",
            f"Scénario « {sc['titre']} » démarré. Tu es {player.upper()}"
            + (" (guide)." if player == guide else ", escorte du guide " + guide.upper() + "."),
            "info",
        )

    @staticmethod
    def initial_positions(sc):
        """Positions de création des navires (repère local du monde), au poste de la formation de départ."""
        cap = float(sc.get("cap_initial", 0))
        f0 = sc.get("formation_depart", "column")
        gx, gy = START
        r = math.radians(cap)
        u = (math.sin(r), math.cos(r))
        sd = (math.cos(r), -math.sin(r))
        pos = {}
        for f in sc["flotte"]:
            a, c = FORMS[f0][f["nom"]]
            pos[f["nom"]] = (gx + a * u[0] + c * sd[0], gy + a * u[1] + c * sd[1])
        return pos

    def _t(self):
        return self.clock() - self.run["t0"]

    # --- messages
    def say(self, frm, to, text_en, text_fr, kind, pending=False):
        run = self.run
        self.msg_id += 1
        m = {
            "id": self.msg_id,
            "t": round(self._t(), 1),
            "from": frm,
            "to": to,
            "en": text_en,
            "fr": text_fr,
            "kind": kind,
            "pending": pending,
        }
        run["msgs"].append(m)
        run["msgs"] = run["msgs"][-80:]
        return m

    # --- ordres
    def _group(self, run, o):
        if o["type"] == "FORM":
            run["form"] = o["name"]
            run["axis"] = None
            if o["name"] == "bearing":
                run["form_rel"] = (o["rel"] if "rel" in o else o["true"] - run["gcap"]) % 360
            run["form_key"] = o["name"] + (f":{round(run['form_rel'])}" if o["name"] == "bearing" else "")
            run["form_t"] = self._t()
        elif o["type"] in ("CORPEN", "TURN", "SPEED"):
            if o["type"] == "TURN":
                o = dict(o, together=True)
            if o["type"] != "SPEED":
                if o.get("together"):
                    if run.get("axis") is None:
                        run["axis"] = run["gcap"]
                else:
                    run["axis"] = None
            cap, spd = sim.apply_orders(run["gcap"], run["gspeed"], [o])
            for n_ in run["ships"] if o.get("together") else [run["guide"]]:
                self._bord(n_, o, run["gcap"], cap)
            if o["type"] != "SPEED":
                run["tog"] = bool(o.get("together"))
            run["gcap"], run["gspeed"] = cap, clamp(spd, 1.5, VMAX_GUIDE)

    def _bord(self, n, o, cap0, cap1):
        """Transmet le bord du virage au pilote : TURN porte toujours un bord, CORPEN seulement s'il est ordonné."""
        if o["type"] == "TURN":
            self.fleet.turn_side(n, 1 if o["side"] == "STBD" else -1, o["deg"])
        elif o["type"] == "CORPEN" and o.get("side"):
            sg = 1 if o["side"] == "STBD" else -1
            self.fleet.turn_side(n, sg, ((cap1 - cap0) * sg) % 360)
        elif o["type"] == "CORPEN":
            self.fleet.turn_side(n, 1, 0)

    def _free(self, run, n, o):
        sh = run["ships"][n]
        s = self.st.get(n)
        base_cap = sh["cap"] if sh["mode"] in ("free", "pending") else (s["hdg"] if s else run["gcap"])
        base_v = sh["v"] if sh["mode"] in ("free", "pending") else (s["sog"] if s else run["gspeed"])
        cap, spd = sim.apply_orders(base_cap, base_v, [o])
        self._bord(n, o, base_cap, cap)
        sh.update(mode="free", cap=cap, v=clamp(spd, 1.5, VMAX))

    def _to_pending(self, run, n, o, group):
        sh = run["ships"][n]
        s = self.st.get(n)
        if run.get("manual") and n == run["player"]:
            tg = {}
            if s and o["type"] in ("CORPEN", "TURN", "SPEED"):
                cap, v = sim.apply_orders(s["hdg"], s["sog"], [o])
                tg = {"cap": cap, "v": v}
            run["pending"].append({"orders": [o], "group": group, "t": self._t(), "target": tg})
            if not run.get("await_ack"):
                run["await_ack"] = {"t": self._t(), "n": 0}
            return
        if sh["mode"] == "formation":
            sh.update(cap=s["hdg"] if s else run["gcap"], v=s["sog"] if s else run["gspeed"])
        sh["mode"] = "pending"
        run["pending"].append({"orders": [o], "group": group, "t": self._t()})

    def execute(self, to, orders, source, by_player):
        """Applique des ordres. by_player=True : le joueur exécute (pour son navire s'il est escorte)."""
        run = self.run
        me = run["player"]
        guide = run["guide"]
        S = run["ships"]
        for o in orders:
            t = o["type"]
            if t not in self.MOTION:
                continue
            if by_player and me != guide:
                p = next((p for p in run["pending"] if p["orders"] == [o]), None)
                if t in ("RESUME", "FORM"):
                    S[me]["mode"] = "formation"
                    run["pending"] = [q for q in run["pending"] if q["orders"][0]["type"] != "FORM"]
                elif p and p["group"]:
                    S[me]["mode"] = "formation"
                    run["pending"] = [q for q in run["pending"] if not q["group"]]
                else:
                    if p:
                        run["pending"].remove(p)
                    self._free(run, me, o)
                continue
            if to == ["TOUS"]:
                if t == "RESUME":
                    for n in S:
                        S[n]["mode"] = "formation"
                    continue
                self._group(run, o)
                if not by_player and me != guide:
                    self._to_pending(run, me, o, True)
                continue
            for tn in to:
                n = tn.lower()
                if n not in S:
                    continue
                if n == guide:
                    if t != "RESUME":
                        self._group(run, o)
                    continue
                if t == "RESUME":
                    S[n]["mode"] = "formation"
                    continue
                if t == "FORM":
                    continue
                if n == me and not by_player:
                    self._to_pending(run, n, o, False)
                else:
                    self._free(run, n, o)

    def player_order(self, text, force_to=None):
        run = self.run
        me, guide = run["player"], run["guide"]
        pr = mtp.parse(text, list(run["ships"]))
        if not pr["ok"]:
            return {"ok": False, "error": pr["error"], "hint": pr["hint"]}
        to, orders = pr["to"], pr["orders"]
        motion = [o for o in orders if o["type"] in self.MOTION]
        if me != guide and motion and to not in (["TOUS"], [me.upper()]):
            return {
                "ok": False,
                "error": "Seul le guide peut ordonner à un autre navire.",
                "hint": f"Adresse l'ordre à {me.upper()}.",
            }
        if me != guide and motion and to == ["TOUS"]:
            to = [me.upper()]
        txt_en = mtp.to_text(to, orders, me)
        fr = mtp.fr_message(to, orders)
        self.execute(to, orders, me, True)
        run["plog"].append({"t": self._t(), "to": to, "orders": orders})
        for o in orders:
            if o["type"] == "EMERG":
                for c in run["contacts"]:
                    run["reported"].add(c)
        self.say(me.upper(), "TOUS" if to == ["TOUS"] else to[0], txt_en, fr, "joueur")
        return {"ok": True, "fr": fr, "en": txt_en}

    def classify(self, cid, cls):
        c = self.run["contacts"].get(cid)
        if not c or cls not in ("ami", "neutre", "hostile", "inconnu"):
            return False
        c["cls"] = cls
        c["cls_t"] = self._t()
        return True

    def approve(self, rec):
        """Message approuvé par l'opérateur (`rec` : to, orders, legacy, fr, signal, written_signal) -> texte émis."""
        run = self.run
        to, orders = rec["to"], rec["orders"]
        me = run["player"]
        dest = "ALL SHIPS" if to == ["TOUS"] else to[0]
        en = (
            mtp.to_text(to, orders, me)
            if rec["legacy"]
            else f"{dest} THIS IS {me.upper()} {rec['written_signal']} OVER"
        )
        emerg = (rec.get("signal") or "").startswith("EMERG") or any(o["type"] == "EMERG" for o in orders)
        if orders:
            self.execute(to, orders, me, True)
        run["plog"].append(
            {
                "t": self._t(),
                "to": to,
                "orders": orders
                + (
                    [{"type": "EMERG", "text": rec.get("signal") or ""}]
                    if emerg and not rec["legacy"]
                    else []
                ),
            }
        )
        if emerg:
            for c in run["contacts"]:
                run["reported"].add(c)
        self.say(me.upper(), "TOUS" if to == ["TOUS"] else to[0], en, rec["fr"], "joueur")
        who = (
            [n for n in run["ships"] if n != me]
            if to == ["TOUS"]
            else [n.lower() for n in to if n.lower() in run["ships"] and n.lower() != me]
        )
        t = self._t()
        self._captain_orders(run, to, orders, t)
        if any(o["type"] in ("CAPT", "ACK") for o in orders):
            who = []
        if me != run["guide"]:
            run.pop("await_ack", None)
        for i, n in enumerate(who):
            run["events"].append(
                {"t": t + 2.5 + 1.6 * i, "de": n, "a": me, "ordres": [{"type": "ACK", "text": "ROGER"}]}
            )
        run["events"].sort(key=lambda e: e["t"])
        return en

    # --- boucle à 2 Hz
    def tick(self, states):
        """Un pas : `states` = état des navires (x, y, lat, lon, sog, hdg) -> points de route {navire: (lat, lon)}."""
        self.st = states
        run = self.run
        if run["ended"]:
            return {}
        t = self._t()
        self.events(run, t)
        self.autopilot(run, t)
        waypoints = self.fleet.control(run, self.st, self.clock())
        now = self.clock()
        dt = now - run.get("last", now)
        run["last"] = now
        self.observe(run, t, dt)
        self._contacts(run, t, dt)
        self._drill(run, t)
        self._captains(run, t, dt)
        self._manual(run, t)
        if t > run["sc"]["duree_s"] or t > run.get("end_at", 1e12):
            self.finish(run)
        return waypoints

    def autopilot(self, run, t):
        """Mode automatique : le navire du joueur agit seul comme un capitaine (accusé, exécution)."""
        if not run.get("auto") or run.get("manual"):
            return
        me, guide = run["player"], run["guide"]
        if me == guide:
            return
        acked = run.setdefault("auto_acked", set())
        for m in run["msgs"]:
            if m["kind"] == "urgence" and m["id"] not in acked and t - m["t"] > 6:
                acked.add(m["id"])
                self.player_order(f"{guide.upper()} THIS IS {me.upper()} ROGER OVER")
        for p in list(run["pending"]):
            if t - p["t"] > 5 and p in run["pending"]:
                self.player_order(mtp.to_text([me.upper()], p["orders"], me))

    def set_auto(self, on):
        self.run["auto"] = bool(on)
        return True

    def events(self, run, t):
        me, guide = run["player"], run["guide"]
        while run["events"] and run["events"][0]["t"] <= t:
            ev = run["events"].pop(0)
            if "piste" in ev:
                self._spawn_contact(run, ev["piste"], t)
                continue
            to = ["TOUS"] if ev["a"] == "TOUS" else [ev["a"].upper()]
            orders = ev["ordres"]
            frm = ev["de"].upper()
            en = mtp.to_text(to, orders, frm)
            fr = mtp.fr_message(to, orders)
            urgent = any(o["type"] == "EMERG" for o in orders)
            to_me = to == ["TOUS"] or to == [me.upper()]
            mot = [o for o in orders if o["type"] in self.MOTION]
            if me == guide and ev["de"] == guide and run.get("auto"):
                run["plog"].append({"t": t, "to": to, "orders": orders})
            elif me == guide and ev["de"] == guide:
                self.say(frm, to[0], en, fr, "plan")
                continue
            ack = all(o["type"] == "ACK" for o in orders)
            self.say(
                frm,
                to[0],
                en,
                fr,
                "ack" if ack else "urgence" if urgent else "ordre",
                pending=bool(to_me and mot and me != guide),
            )
            self.execute(to, orders, frm, False)

    # --- pistes qui manoeuvrent, comptes rendus, exercice de formations
    def _spawn_contact(self, run, p, t):
        g = self.st.get(run["guide"])
        if not g:
            return
        b = math.radians(g["hdg"] + p["rel"])
        d = p["dist_nm"] * NM
        cr = math.radians(p["cap"])
        v = p["vit_kn"] * KN
        run["contacts"][p["id"]] = {
            "id": p["id"],
            "type": p["type"],
            "x": g["x"] + d * math.sin(b),
            "y": g["y"] + d * math.cos(b),
            "vx": v * math.sin(cr),
            "vy": v * math.cos(cr),
            "cls": "inconnu",
            "cls_reel": p.get("cls_reel", "inconnu"),
            "t0": t,
            "cap": p["cap"],
            "vit": p["vit_kn"],
            "beh": p.get("comportement"),
            "etat": "approche",
            "echec_nm": p.get("echec_dist_nm"),
            "bloc_nm": p.get("blocage_nm", 1.0),
            "bloc_s": p.get("blocage_s", 20),
            "blk": 0.0,
            "rep_left": sorted(p.get("rapports_nm", []), reverse=True),
        }

    def _drill_init(self, sc):
        steps = sc.get("etapes")
        if not steps:
            return None
        n = sc.get("etapes_aleatoires")
        if n:
            pool, out = list(steps), cast(list[dict[str, Any]], [])
            while len(out) < n:
                c = self.rng.choice(pool)
                if "rel_tens" in c:
                    tens = self.rng.choice(c["rel_tens"])
                    side = self.rng.choice(["STBD", "PORT"])
                    c = {
                        "key": f"bearing:{(tens * 10) if side == 'STBD' else (360 - tens * 10)}",
                        "ordre": f"FORM {side} {tens}",
                        "texte": f"Ligne de relèvement à {tens * 10}° sur {'tribord' if side == 'STBD' else 'bâbord'}",
                    }
                if (out[-1]["key"] if out else sc.get("formation_depart")) != c["key"]:
                    out.append(dict(c))
            steps = out
        return {
            "steps": [dict(x) for x in steps],
            "i": 0,
            "t_step": None,
            "ok_since": None,
            "delai": sc.get("etapes_delai_s", 150),
            "hint": False,
        }

    def _drill(self, run, t):
        d = run["drill"]
        if not d or d["i"] >= len(d["steps"]):
            return
        st = d["steps"][d["i"]]
        if d["t_step"] is None:
            if t < 8:
                return
            d["t_step"] = t
            d["hint"] = False
            run["dyn"].append(
                {
                    "texte": f"{d['i'] + 1}. {st['texte']}",
                    "avant_t": round(t + d["delai"]),
                    "ok": False,
                    "t": None,
                }
            )
            self.say(
                "DIRECTION",
                "TOUS",
                "",
                f"Exercice {d['i'] + 1} sur {len(d['steps'])} : faites prendre la formation « {st['texte']} ».",
                "info",
            )
            return
        el = t - d["t_step"]
        if not d["hint"] and el > d["delai"] * 0.4 and run.get("form_key") != st["key"]:
            d["hint"] = True
            self.say("DIRECTION", "TOUS", "", f"Indice : le signal est {st['ordre']}.", "info")
        S = run["ships"]
        in_st = all(
            sh["mode"] == "formation" and sh.get("err", 1e9) < 150 for n, sh in S.items() if n != run["guide"]
        )
        good = run.get("form_key") == st["key"] and run.get("form_t", -1) >= d["t_step"] - 1
        d["ok_since"] = (d["ok_since"] or t) if (good and in_st) else None
        obj = run["dyn"][-1]
        if d["ok_since"] and t - d["ok_since"] >= 4:
            obj.update(ok=True, t=round(t))
            d["i"] += 1
            d["t_step"] = None
            d["ok_since"] = None
            self.say(
                "DIRECTION",
                "TOUS",
                "",
                f"Formation prise en {int(el // 60)} min {int(el % 60):02d} s.",
                "info",
            )
        elif el > d["delai"]:
            d["i"] += 1
            d["t_step"] = None
            d["ok_since"] = None
            self.say(
                "DIRECTION",
                "TOUS",
                "",
                f"Délai dépassé pour « {st['texte']} » (signal : {st['ordre']}).",
                "info",
            )
        if d["i"] >= len(d["steps"]):
            self.say("DIRECTION", "TOUS", "", "Exercice terminé.", "info")
            run["end_at"] = t + 5

    def _contacts(self, run, t, dt):
        """Pistes qui manoeuvrent : interception du guide, comptes rendus des escortes, repoussée par une escorte."""
        g = self.st.get(run["guide"])
        me = run["player"]
        if not g:
            return
        for e in list(run["cond"]):
            c0 = run["contacts"].get(e.get("apres_repousse"))
            if c0 and c0["etat"] == "repousse" and t - c0["rep_t"] >= e.get("delai_s", 30):
                run["cond"].remove(e)
                if "piste" in e:
                    self._spawn_contact(run, e["piste"], t)
        for c in run["contacts"].values():
            dx, dy = g["x"] - c["x"], g["y"] - c["y"]
            dist = math.hypot(dx, dy)
            d_nm = dist / NM
            brg_from_guide = math.degrees(math.atan2(-dx, -dy)) % 360
            esc = [
                (math.hypot(s["x"] - c["x"], s["y"] - c["y"]), n)
                for n in run["ships"]
                if n != run["guide"]
                for s in [self.st.get(n)]
                if s
            ]
            near = min(esc)[1] if esc else run["guide"]
            while c["rep_left"] and d_nm < c["rep_left"][0] and c["etat"] == "approche":
                c["rep_left"].pop(0)
                self.say(
                    near.upper(),
                    me.upper(),
                    f"{me.upper()} THIS IS {near.upper()} CONTACT {c['id']} BEARING {round(brg_from_guide) % 360:03d} "
                    f"RANGE {d_nm:.1f} MILES CLOSING OVER",
                    f"{near.capitalize()} : contact {c['id']} au {round(brg_from_guide) % 360:03d}, "
                    f"distance {d_nm:.1f} NM du guide, en rapprochement.",
                    "rapport",
                )
            if not c.get("beh"):
                continue
            if c["etat"] == "approche":
                gv = (
                    g["sog"] * math.sin(math.radians(g["hdg"])),
                    g["sog"] * math.cos(math.radians(g["hdg"])),
                )
                v = c["vit"] * KN
                lead = min(dist / max(v, 1.0), 120.0) * 0.6
                want = math.degrees(math.atan2(dx + gv[0] * lead, dy + gv[1] * lead)) % 360
                if esc and min(esc)[0] < c["bloc_nm"] * NM:
                    c["blk"] += dt
                else:
                    c["blk"] = max(0.0, c["blk"] - dt * 0.5)
                if c["blk"] >= c["bloc_s"]:
                    c["etat"] = "repousse"
                    c["rep_t"] = t
                    self.say(
                        near.upper(),
                        me.upper(),
                        f"{me.upper()} THIS IS {near.upper()} CONTACT {c['id']} TURNING AWAY OVER",
                        f"{near.capitalize()} : le contact {c['id']} fait demi-tour.",
                        "rapport",
                    )
                elif c.get("echec_nm") and d_nm < c["echec_nm"]:
                    c["etat"] = "atteint"
                    self.say(
                        "DIRECTION",
                        "TOUS",
                        "",
                        f"{c['id']} est arrivé à moins de {c['echec_nm']} NM du guide : la force est atteinte.",
                        "urgence",
                    )
                    run["end_at"] = t + 4
            else:
                want = brg_from_guide
            if c["etat"] in ("approche", "repousse"):
                d = angdiff(want, c["cap"])
                c["cap"] = (c["cap"] + clamp(d, -TURN_CONTACT * dt, TURN_CONTACT * dt)) % 360
                v = c["vit"] * KN
                c["vx"], c["vy"] = v * math.sin(math.radians(c["cap"])), v * math.cos(math.radians(c["cap"]))
        act = [c for c in run["contacts"].values() if c.get("beh")]
        if (
            act
            and not run["cond"]
            and all(c["etat"] == "repousse" and t - c["rep_t"] > 25 for c in act)
            and "end_at" not in run
        ):
            self.say("DIRECTION", "TOUS", "", "Toutes les pistes hostiles sont repoussées.", "info")
            run["end_at"] = t + 5

    # --- barre manuelle
    def helm(self, b):
        run = self.run
        if not run.get("manual"):
            return {"ok": False, "error": "La barre manuelle n'est pas active."}
        h = run["helm"]
        if "rudder" in b:
            h["rudder"] = int(clamp(int(b["rudder"]), -1, 1))
        if "dcap" in b:
            h["cap"] = (h["cap"] + float(b["dcap"])) % 360
            h["rudder"] = 0
            h["steady"] = True
        if "cap" in b:
            h["cap"] = float(b["cap"]) % 360
            h["rudder"] = 0
            h["steady"] = True
        if "dkn" in b:
            h["kn"] = clamp(h["kn"] + float(b["dkn"]), 0.0, 29.0)
        if "kn" in b:
            h["kn"] = clamp(float(b["kn"]), 0.0, 29.0)
        return {"ok": True, "helm": h}

    def _manual(self, run, t):
        """Joueur à la barre d'une escorte : le guide attend un accusé, un ordre est exécuté quand le navire y est."""
        me, guide = run["player"], run["guide"]
        if not run.get("manual") or me == guide:
            return
        s = self.st.get(me)
        sh = run["ships"][me]
        aw = run.get("await_ack")
        if aw and t - aw["t"] > 25 and aw["n"] < 2:
            aw["t"] = t
            aw["n"] += 1
            self.say(
                guide.upper(),
                me.upper(),
                f"{me.upper()} THIS IS {guide.upper()} ACKNOWLEDGE OVER",
                f"{guide.capitalize()} : accusez réception.",
                "ordre",
            )
        if not s:
            return
        for p in list(run["pending"]):
            o = p["orders"][0]
            tp = o["type"]
            if tp in ("FORM", "RESUME") or (p["group"] and tp in ("CORPEN", "TURN", "SPEED") and run["form"]):
                ok = sh.get("err", 1e9) < 250 and t - p["t"] > 8
                if tp in ("CORPEN", "TURN"):
                    ok = ok and abs(angdiff(run["gcap"], s["hdg"])) < 10
                if tp == "SPEED" and p["group"]:
                    ok = ok and abs(s["sog"] - run["gspeed"]) < 1.5
            else:
                tg = p.get("target") or {}
                ok = (
                    abs(angdiff(tg.get("cap", s["hdg"]), s["hdg"])) < 8
                    and abs(tg.get("v", s["sog"]) - s["sog"]) < 1.3
                )
            p["ok_t"] = (p.get("ok_t") or t) if ok else None
            if p["ok_t"] and t - p["ok_t"] > 4:
                run["pending"].remove(p)
                run["plog"].append({"t": t, "to": [me.upper()], "orders": [o]})
                self.say("SYSTÈME", me.upper(), "", "Ordre exécuté : " + mtp.fr_order(o) + ".", "info")

    # --- capitaines : réponses, comptes rendus, initiatives
    def _cap(self, run, n):
        return run.setdefault("capt", {}).setdefault(
            n, {"task": None, "target": None, "rs": False, "rs_t": 0.0, "in_t": None}
        )

    def _radio(self, run, frm, en_body, fr, kind="rapport", delay=0.0):
        run.setdefault("later", []).append((self._t() + delay, frm, en_body, fr, kind))

    def _threat(self, run):
        g = self.st.get(run["guide"])
        cs = [
            c
            for c in run["contacts"].values()
            if c.get("etat", "approche") == "approche" and c["cls"] != "ami"
        ]
        return min(cs, key=lambda c: math.hypot(c["x"] - g["x"], c["y"] - g["y"])) if g and cs else None

    def _start_intercept(self, run, n, cid):
        cp = self._cap(run, n)
        cp.update(task="intercept", target=cid, rs=False)
        run.get("requests", {}).pop(n, None)

    def _captain_orders(self, run, to, orders, t):
        """Suites données par les commandants à un message approuvé."""
        me = run["player"]
        S = run["ships"]
        names = (
            [n for n in S if n != me]
            if to == ["TOUS"]
            else [x.lower() for x in to if x.lower() in S and x.lower() != me]
        )

        def kn(n):
            return round((self.st.get(n) or {}).get("sog", 0.0) / KN)

        for o in orders:
            if o["type"] in self.MOTION:
                for n in names:
                    cp = self._cap(run, n)
                    if cp["task"] and to == ["TOUS"]:
                        continue
                    if cp["task"]:
                        cp.update(task=None, target=None)
                    if o["type"] in ("FORM", "RESUME") and run.get("auto"):
                        cp.update(rs=True, rs_t=t, in_t=None)
                continue
            if o["type"] != "CAPT":
                continue
            do = o["do"]
            if do == "investigate":
                c0 = self._threat(run)
                if not c0:
                    for n in names[:1]:
                        self._radio(run, n, "NEGAT TA62", "aucun contact à reconnaître.", delay=3)
                    continue
                if to == ["TOUS"]:
                    free = [
                        (math.hypot(s["x"] - c0["x"], s["y"] - c0["y"]), n)
                        for n in names
                        if n != run["guide"] and not self._cap(run, n)["task"]
                        for s in [self.st.get(n)]
                        if s
                    ]
                    names_i = [min(free)[1]] if free else []
                else:
                    names_i = names
                for n in names_i:
                    self._start_intercept(run, n, c0["id"])
                    self._radio(
                        run,
                        n,
                        f"WILCO BA TA62 {c0['id']}",
                        f"bien reçu, je pars reconnaître {c0['id']} et je manœuvre pour lui barrer la route.",
                        delay=3,
                    )
            elif do == "int_speed":
                for i, n in enumerate(names):
                    self._radio(
                        run, n, f"M SPEED {kn(n)}", f"ma vitesse est de {kn(n)} nœuds.", delay=3 + 2 * i
                    )
            elif do == "int_corpen":
                for i, n in enumerate(names):
                    h = round((self.st.get(n) or {}).get("hdg", 0.0)) % 360
                    self._radio(
                        run,
                        n,
                        f"M CORPEN {h:03d} SPEED {kn(n)}",
                        f"ma route est au {h:03d}, vitesse {kn(n)} nœuds.",
                        delay=3 + 2 * i,
                    )
            elif do == "int_station":
                for i, n in enumerate(names):
                    sh = S[n]
                    cp = self._cap(run, n)
                    if cp["task"] == "intercept":
                        self._radio(
                            run,
                            n,
                            f"BA TA62 {cp['target']}",
                            f"je suis détaché, en reconnaissance de {cp['target']}.",
                            delay=3 + 2 * i,
                        )
                    elif sh["mode"] == "formation" and sh.get("err", 1e9) < 150:
                        self._radio(run, n, "A STATION", "je suis en station.", delay=3 + 2 * i)
                    elif sh["mode"] == "formation":
                        self._radio(
                            run,
                            n,
                            "B STATION",
                            f"je rejoins mon poste, encore à {int(sh.get('err', 0))} m.",
                            delay=3 + 2 * i,
                        )
                    else:
                        self._radio(
                            run,
                            n,
                            "B STATION",
                            "je suis hors formation, sur la route que vous m'avez ordonnée.",
                            delay=3 + 2 * i,
                        )
            elif do == "report_station":
                for n in names:
                    self._cap(run, n).update(rs=True, rs_t=t, in_t=None)
            elif do in ("affirm", "negat"):
                for n in names:
                    rq = run.get("requests", {}).get(n)
                    if not rq:
                        self._radio(run, n, "ROGER", "bien reçu.", delay=3)
                        continue
                    if do == "affirm":
                        self._start_intercept(run, n, rq["cid"])
                        self._radio(
                            run,
                            n,
                            f"WILCO BA TA62 {rq['cid']}",
                            f"bien reçu, je pars reconnaître {rq['cid']}.",
                            delay=3,
                        )
                    else:
                        run["requests"].pop(n, None)
                        self._radio(run, n, "ROGER", "bien reçu, je reste à mon poste.", delay=3)

    def reply(self, ship, yes):
        """Réponse de l'opérateur à une demande d'autorisation (bouton de la console). Le registre est à l'appelant."""
        run = self.run
        if ship not in run.get("requests", {}):
            return {"ok": False, "error": "Aucune demande en attente pour ce navire."}
        me = run["player"]
        en = f"{ship.upper()} THIS IS {me.upper()} {'AFFIRMATIVE' if yes else 'NEGATIVE'} OVER"
        self.say(
            me.upper(),
            ship.upper(),
            en,
            f"À {ship.capitalize()} : {'affirmatif, autorisation accordée' if yes else 'négatif, restez à votre poste'}.",
            "joueur",
        )
        self._captain_orders(
            run, [ship.upper()], [{"type": "CAPT", "do": "affirm" if yes else "negat"}], self._t()
        )
        return {"ok": True, "en": en}

    def _captains(self, run, t, dt):
        me = run["player"]
        guide = run["guide"]
        S = run["ships"]
        g = self.st.get(guide)
        auto = run.get("auto")
        for item in sorted(run.setdefault("later", [])):
            if t >= item[0]:
                run["later"].remove(item)
                _, frm, en_body, fr, kind = item
                self.say(
                    frm.upper(),
                    me.upper(),
                    f"{me.upper()} THIS IS {frm.upper()} {en_body} OVER",
                    f"{frm.capitalize()} : {fr}",
                    kind,
                )
        if not g:
            return
        RQ = run.setdefault("requests", {})
        for n in list(RQ):
            c = run["contacts"].get(RQ[n]["cid"])
            if not c or c.get("etat", "approche") != "approche":
                RQ.pop(n)
        if auto:
            for c in run["contacts"].values():
                if (
                    c.get("etat", "approche") != "approche"
                    or c["cls"] == "ami"
                    or not (c.get("beh") or c["cls"] == "hostile")
                ):
                    continue
                d_nm = math.hypot(c["x"] - g["x"], c["y"] - g["y"]) / NM
                if any(
                    cp["task"] == "intercept" and cp["target"] == c["id"]
                    for cp in run.get("capt", {}).values()
                ):
                    continue
                rq = next((r for r in RQ.values() if r["cid"] == c["id"]), None)
                brg = round(math.degrees(math.atan2(c["x"] - g["x"], c["y"] - g["y"]))) % 360
                if rq is None and d_nm < 3.0 and t - c.get("asked_t", -1e9) > 75:
                    free = [
                        (math.hypot(s["x"] - c["x"], s["y"] - c["y"]), n)
                        for n in S
                        if n not in (me, guide) and not self._cap(run, n)["task"] and n not in RQ
                        for s in [self.st.get(n)]
                        if s
                    ]
                    if free:
                        n = min(free)[1]
                        c["asked_t"] = t
                        RQ[n] = {
                            "ship": n,
                            "cid": c["id"],
                            "t": t,
                            "fr": f"{n.capitalize()} demande l'autorisation d'aller reconnaître {c['id']} "
                            f"(au {brg:03d}, à {d_nm:.1f} NM du guide).",
                        }
                        self._radio(
                            run,
                            n,
                            f"BH TA62 {c['id']}",
                            f"demande l'autorisation d'aller reconnaître {c['id']}, au {brg:03d} à {d_nm:.1f} NM du guide.",
                            "demande",
                        )
                elif rq and d_nm < 1.7 and t - rq["t"] > 25:
                    n = rq["ship"]
                    self._start_intercept(run, n, c["id"])
                    self._radio(
                        run,
                        n,
                        f"BA TA62 {c['id']}",
                        f"sans réponse et {c['id']} à {d_nm:.1f} NM du guide : j'interviens de ma propre initiative.",
                    )
        for n, cp in run.get("capt", {}).items():
            s = self.st.get(n)
            sh = S.get(n)
            if not s or not sh:
                continue
            if cp["task"] == "intercept":
                c = run["contacts"].get(cp["target"])
                if not c or c.get("etat", "approche") != "approche":
                    done = cp["target"]
                    cp.update(task=None, target=None, rs=True, rs_t=t, in_t=None)
                    sh["mode"] = "formation"
                    self._radio(
                        run, n, f"BB TA62 {done}", f"{done} ne menace plus, je reprends mon poste.", delay=4
                    )
                    continue
                dx, dy = c["x"] - s["x"], c["y"] - s["y"]
                d = math.hypot(dx, dy)
                lead = min(d / (VMAX + c["vit"] * KN * 0.5), 90.0) * 0.8
                sh.update(
                    mode="free",
                    cap=math.degrees(math.atan2(dx + c["vx"] * lead, dy + c["vy"] * lead)) % 360,
                    v=VMAX,
                )
            elif cp["rs"] and sh["mode"] == "formation":
                err = sh.get("err", 1e9)
                cp["in_t"] = (cp["in_t"] or t) if err < 150 else None
                if cp["in_t"] and t - cp["in_t"] > 3 and t - cp["rs_t"] > 6:
                    cp.update(rs=False, in_t=None)
                    self._radio(run, n, "A STATION", "en station.")
                elif t - cp["rs_t"] > 330:
                    cp.update(rs=False, in_t=None)
                    self._radio(
                        run, n, "B STATION", f"je n'arrive pas à tenir mon poste, encore à {int(err)} m."
                    )
        if auto:
            names = list(S)
            W = run.setdefault("warned", {})
            for i, a in enumerate(names):
                for b in names[i + 1 :]:
                    sa, sb = self.st.get(a), self.st.get(b)
                    if not sa or not sb or math.hypot(sa["x"] - sb["x"], sa["y"] - sb["y"]) > 230:
                        continue
                    if t - W.get((a, b), -1e9) < 90:
                        continue
                    W[(a, b)] = t
                    who, other = (b, a) if a == me else (a, b)
                    self._radio(
                        run,
                        who,
                        "EMERG C",
                        f"route de collision avec {other.capitalize()}, je m'écarte.",
                        "urgence",
                    )

    # --- observation, évaluation, débrief
    def observe(self, run, t, dt):
        S = run["ships"]
        names = list(S)
        for i, a in enumerate(names):
            for b in names[i + 1 :]:
                sa, sb = self.st.get(a), self.st.get(b)
                if sa and sb:
                    run["min_ship"] = min(run["min_ship"], math.hypot(sa["x"] - sb["x"], sa["y"] - sb["y"]))
        for cid, c in run["contacts"].items():
            c["x"] += c["vx"] * dt
            c["y"] += c["vy"] * dt
            me = self.st.get(run["player"])
            if me:
                d = math.hypot(c["x"] - me["x"], c["y"] - me["y"]) / NM
                run["min_cpa"][cid] = min(run["min_cpa"].get(cid, 1e9), d)

    def _eval(self, run):
        res = []
        for a in run["sc"].get("attendu", []):
            ok, when = False, None
            if "repousse" in a:
                c = run["contacts"].get(a["repousse"])
                ok = bool(c and c["etat"] == "repousse")
                when = c.get("rep_t") if ok else None
            elif "garde_nm" in a:
                c = run["contacts"].get(a["piste"])
                ok = bool(c) and run["min_cpa"].get(a["piste"], 1e9) >= a["garde_nm"]
            elif "ordre" in a:
                for p in run["plog"]:
                    if any(o["type"] == a["ordre"] for o in p["orders"]) and p["t"] <= a["avant_t"] + TOL:
                        ok, when = True, p["t"]
                        break
                    if any(o["type"] == a["ordre"] for o in p["orders"]) and p["t"] > a["avant_t"]:
                        when = p["t"]
                if not ok and a["ordre"] == "ACK":
                    ok = any(
                        o["type"] in ("ACK", "EMERG")
                        for p in run["plog"]
                        if p["t"] <= a["avant_t"] + TOL
                        for o in p["orders"]
                    )
            elif "classe" in a:
                c = run["contacts"].get(a["classe"])
                ok = bool(c and c["cls"] == a["cls"])
            res.append(
                {
                    "texte": a["texte"],
                    "avant_t": a.get("avant_t", run["sc"]["duree_s"]),
                    "ok": ok,
                    "t": None if when is None else round(when),
                }
            )
        return res + [dict(x) for x in run.get("dyn", [])]

    def finish(self, run):
        run["ended"] = True
        res = self._eval(run)
        run["debrief"] = {
            "checks": res,
            "score": sum(1 for r in res if r["ok"]),
            "total": len(res),
            "min_ship_m": None if run["min_ship"] > 1e8 else int(run["min_ship"]),
            "min_cpa": {k: round(v, 2) for k, v in run["min_cpa"].items()},
            "classes": {
                k: {"choisie": c["cls"], "reelle": c["cls_reel"]} for k, c in run["contacts"].items()
            },
        }
        self.say("SYSTÈME", "TOUS", "", "Fin du scénario.", "info")

    # --- état pour l'interface et calculs à la demande
    def state(self):
        run = self.run
        t = self._t()
        me = run["player"]
        guide = run["guide"]
        ships = []
        for n, sh in run["ships"].items():
            s = self.st.get(n)
            if not s:
                continue
            if n == guide:
                etat = "Guide"
            elif sh["mode"] == "pending":
                etat = "Hors formation"
            elif run.get("capt", {}).get(n, {}).get("task") == "intercept":
                etat = "Reconnaissance " + run["capt"][n]["target"]
            elif sh["mode"] == "free":
                etat = "Libre"
            else:
                etat = (
                    "En station"
                    if sh.get("err", 0) < 150
                    else ("Hors formation" if sh.get("err", 0) > 600 else "Rejoint")
                )
            if n == me:
                etat = "Vous" if n != guide else "Vous (guide)"
            ships.append(
                {
                    "name": n,
                    "x": s["x"],
                    "y": s["y"],
                    "hdg": s["hdg"],
                    "sog": s["sog"],
                    "role": sh["role"],
                    "etat": etat,
                    "etat_c": ("Guide" if n == guide else etat),
                }
            )
        own = next((s for s in ships if s["name"] == me), None)
        contacts = []
        for c in run["contacts"].values():
            info = sim.cpa_now(own, c) if own else {}
            contacts.append(
                {
                    "id": c["id"],
                    "type": c["type"],
                    "x": c["x"],
                    "y": c["y"],
                    "cap": round(c["cap"]),
                    "vit": c["vit"],
                    "cls": c["cls"],
                    "etat": c.get("etat"),
                    "range_nm": info.get("range_nm"),
                    "brg": info.get("brg"),
                    "cpa_nm": info.get("cpa_nm"),
                    "tcpa_min": info.get("tcpa_min"),
                }
            )
        plan = [{"t": m["t"], "en": m["en"], "fr": m["fr"]} for m in run["msgs"] if m["kind"] == "plan"]
        own_sh = run["ships"][me]
        return {
            "t": round(t, 1),
            "duree": run["sc"]["duree_s"],
            "titre": run["sc"]["titre"],
            "player": me,
            "guide": guide,
            "form": run["form"],
            "gcap": run["gcap"],
            "gspeed_kn": run["gspeed"] / KN,
            "ships": ships,
            "contacts": contacts,
            "msgs": run["msgs"][-40:],
            "plan": plan[-3:],
            "pending": [{"fr": mtp.fr_order(p["orders"][0])} for p in run["pending"]],
            "ended": run["ended"],
            "debrief": run["debrief"],
            "attendu": self._eval(run),
            "auto": bool(run.get("auto")),
            "requests": list(run.get("requests", {}).values()),
            "manual": bool(run.get("manual")),
            "helm": {
                "cap": round(run["helm"]["cap"], 1),
                "kn": round(run["helm"]["kn"], 1),
                "rudder": run["helm"]["rudder"],
            },
            "station": None
            if me == guide or "slot" not in own_sh
            else {"x": own_sh["slot"][0], "y": own_sh["slot"][1], "err": round(own_sh.get("err", 0))},
            "tasks": {n: cp["target"] for n, cp in run.get("capt", {}).items() if cp["task"] == "intercept"},
        }

    def sim_state_for_calc(self):
        run = self.run
        ships = [
            {"name": n, "x": s["x"], "y": s["y"], "hdg": s["hdg"], "sog": s["sog"]}
            for n in run["ships"]
            for s in [self.st.get(n)]
            if s
        ]
        contacts = [
            {"id": c["id"], "x": c["x"], "y": c["y"], "vx": c["vx"], "vy": c["vy"], "cls": c["cls"]}
            for c in run["contacts"].values()
        ]
        return ships, contacts

    def simulate(self, text):
        run = self.run
        pr = mtp.parse(text, list(run["ships"]))
        if not pr["ok"]:
            return {"ok": False, "error": pr["error"], "hint": pr["hint"]}
        mot = [o for o in pr["orders"] if o["type"] in ("CORPEN", "TURN", "SPEED")]
        if not mot:
            return {
                "ok": False,
                "error": "Rien à simuler : utilise CORPEN, TURN ou SPEED.",
                "hint": "Exemple : TURN 30 STBD",
            }
        ships, contacts = self.sim_state_for_calc()
        to = pr["to"]
        if run["player"] != run["guide"] and to == ["TOUS"]:
            to = [run["player"].upper()]
        g = sim.ghost(ships, to, mot, contacts, 900)
        return {"ok": True, "to": to, "fr": mtp.fr_message(pr["to"], pr["orders"]), **g}

    def recommend(self):
        run = self.run
        ships, contacts = self.sim_state_for_calc()
        for c in contacts:
            c["cls"] = run["contacts"][c["id"]]["cls"]
        etats = {x["name"]: x["etat"] for x in self.state()["ships"]}
        st = {"ships": [dict(s, etat=etats.get(s["name"], "")) for s in ships], "contacts": contacts}
        return reco.recommend(st, run["player"], run["guide"], run["pending"], run["reported"])


__all__ = ["ScenarioEngine", "slots"]
