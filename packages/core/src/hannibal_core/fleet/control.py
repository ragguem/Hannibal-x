"""Pilotage de la flotte : carotte, rampe au diamètre tactique, virage du bord, postes, sillage, évitement.

Repris de legacy/app_v3/server.py (`Ros._ramp`, `Ros.turn_side`, `Ros.carrot`, `Hannibal.control`, `_wake_pt`,
`_slots`, `_helm_tick`) sans ROS ni horloge système : l'appelant fournit l'état des navires (`states`, mêmes clés
que `Ros.st` : x, y, lat, lon, sog en m/s, hdg en degrés) et l'instant `now` en secondes ; le contrôleur rend les
points de route à envoyer au simulateur.
"""

import math

M, KN = 111320.0, 0.514444
VMAX = 15.0
SPACING = 300.0
DTAC = 731.0
FORMS = {
    "column": {"hannibal": (0, 0), "alfa": (-400, 0), "charlie": (-800, 0), "delta": (-1200, 0)},
    "line_abreast": {"hannibal": (0, 0), "alfa": (0, -400), "charlie": (0, 400), "delta": (0, 800)},
    "screen": {"hannibal": (0, 0), "alfa": (600, -500), "charlie": (600, 500), "delta": (-500, 0)},
    "line_abreast_stbd": {"hannibal": (0, 0), "alfa": (0, 300), "charlie": (0, 600), "delta": (0, 900)},
    "line_abreast_port": {"hannibal": (0, 0), "alfa": (0, -300), "charlie": (0, -600), "delta": (0, -900)},
}

Waypoint = tuple[float, float]


def clamp(x, a, b):
    return max(a, min(b, x))


def angdiff(a, b):
    return ((a - b + 540.0) % 360.0) - 180.0


def slots(run):
    if run["form"] != "bearing":
        return FORMS[run["form"]]
    r = math.radians(run.get("form_rel", 180.0))
    out = {run["guide"]: (0.0, 0.0)}
    for i, n in enumerate([x for x in run["ships"] if x != run["guide"]], start=1):
        out[n] = (SPACING * i * math.cos(r), SPACING * i * math.sin(r))
    return out


def wake_pt(run, g, d):
    """Point situé à d mètres derrière le guide le long de sa route passée, et cap de la route à cet endroit."""
    tr = run.get("gtrack") or []
    px, py = g["x"], g["y"]
    hd = g["hdg"]
    for qx, qy in reversed(tr):
        seg = math.hypot(px - qx, py - qy)
        if seg < 1e-6:
            continue
        hd = math.degrees(math.atan2(px - qx, py - qy)) % 360
        if seg >= d:
            f = d / seg
            return px + (qx - px) * f, py + (qy - py) * f, hd
        d -= seg
        px, py = qx, qy
    r = math.radians(hd)
    return px - d * math.sin(r), py - d * math.cos(r), hd


def helm_tick(run, states):
    """Barre : tant qu'elle est tenue le navire vire ; relâchée, il se stabilise sur son cap du moment."""
    h = run["helm"]
    s = states.get(run["player"])
    if not s:
        return h["cap"], max(h["kn"] * KN, 0.8)
    if h["rudder"]:
        h["cap"] = (s["hdg"] + 40.0 * h["rudder"]) % 360
        h["last"] = h["rudder"]
        h["steady"] = False
    elif not h["steady"]:
        h["cap"] = (s["hdg"] + 5.0 * h["last"]) % 360
        h["steady"] = True
    return h["cap"], clamp(h["kn"] * KN, 0.8, VMAX)


class FleetController:
    """État de pilotage par navire (rampe de cap, bord ordonné) ; une instance par mission."""

    def __init__(self, dtac: float = DTAC) -> None:
        self.dtac = dtac
        self.ramp: dict[str, list[float]] = {}
        self.side: dict[str, list[float]] = {}

    def turn_side(self, name, sign, deg):
        """Bord ordonné : le navire vire de ce côté, même si c'est le plus long."""
        if deg >= 20:
            self.side[name] = [sign, float(deg)]
        else:
            self.side.pop(name, None)

    def ramp_course(self, name, course, s, now):
        """Cap commandé qui tourne à la vitesse angulaire du diamètre tactique (v / rayon), du bord ordonné."""
        rp = self.ramp.get(name)
        if rp is None or now - rp[1] > 3.0 or abs(angdiff(rp[0], s["hdg"])) > 40.0:
            rp = [s["hdg"], now]
        dt = min(now - rp[1], 1.0)
        w = math.degrees(max(s["sog"], 2.0) / (self.dtac / 2.0)) * dt
        d = angdiff(course, rp[0])
        sd = self.side.get(name)
        if sd:
            if sd[1] < 20.0:
                self.side.pop(name, None)
            else:
                d = sd[0] * min(sd[1], 179.0)
        st = clamp(d, -w, w)
        if sd and name in self.side:
            sd[1] -= abs(st)
        rp[0] = (rp[0] + st) % 360
        rp[1] = now
        self.ramp[name] = rp
        return rp[0]

    def carrot(self, name, course, v_cmd, dI, s, now, limit=False) -> tuple[float, Waypoint | None]:
        """Point de route devant le navire : sa distance règle la vitesse (loi mesurée). -> (dI, (lat, lon))."""
        if not s:
            return dI, None
        if abs(v_cmd - s["sog"]) < 1.5:
            dI = clamp(dI + 0.15 * (v_cmd - s["sog"]) * 0.5, -6, 8)
        D = clamp((v_cmd - 1.6) / 0.414 + dI, 4.0, 80.0)
        if limit and self.dtac > 0:
            course = self.ramp_course(name, course, s, now)
        diff = angdiff(course, s["hdg"])
        r = math.radians(s["hdg"] + clamp(diff, -25.0, 25.0))
        lat = s["lat"] + D * math.cos(r) / M
        lon = s["lon"] + D * math.sin(r) / (M * math.cos(math.radians(s["lat"])))
        return dI, (lat, lon)

    def control(self, run, states, now) -> dict[str, Waypoint]:
        """Un pas de pilotage (2 Hz) : met à jour `run` comme l'ancien serveur et rend les points de route."""
        out: dict[str, Waypoint] = {}
        g = states.get(run["guide"])
        S = run["ships"]
        if not g:
            return out

        def steer(n, course, v, limit):
            S[n]["dI"], wp = self.carrot(n, course, v, S[n]["dI"], states.get(n), now, limit=limit)
            if wp:
                out[n] = wp

        man = run.get("manual")
        me = run["player"]
        if man:
            hcap, hv = helm_tick(run, states)
        if man and me == run["guide"]:
            run["gcap"], run["gspeed"] = hcap, hv
        steer(run["guide"], run["gcap"], run["gspeed"], True)
        r = math.radians(g["hdg"] if run.get("axis") is None else run["axis"])
        u = (math.sin(r), math.cos(r))
        sd = (math.cos(r), -math.sin(r))
        form = slots(run)
        tr = run.setdefault("gtrack", [])
        if not tr or math.hypot(g["x"] - tr[-1][0], g["y"] - tr[-1][1]) > 10.0:
            tr.append((g["x"], g["y"]))
            if len(tr) > 400:
                del tr[:100]
        wake = run["form"] == "column" and run.get("axis") is None and self.dtac > 0
        togturn = bool(run.get("tog")) and self.dtac > 0 and abs(angdiff(run["gcap"], g["hdg"])) > 6.0
        if not togturn:
            run["tog"] = False
        for n, sh in S.items():
            s = states.get(n)
            if n == run["guide"] or not s:
                continue
            sa, sc = form[n]
            sx, sy = g["x"] + sa * u[0] + sc * sd[0], g["y"] + sa * u[1] + sc * sd[1]
            vx, vy = sx - s["x"], sy - s["y"]
            dist = math.hypot(vx, vy)
            rh = g["hdg"]
            if wake and sc == 0 and sa < 0:
                sx, sy, rh = wake_pt(run, g, -sa)
                vx, vy = sx - s["x"], sy - s["y"]
                dist = math.hypot(vx, vy)
            sh["err"] = dist
            sh["slot"] = (sx, sy)
            if man and n == me:
                course, v = hcap, hv
            elif sh["mode"] == "formation" and togturn:
                course, v = run["gcap"], run["gspeed"]
            elif sh["mode"] == "formation" and dist > 120:
                # loin de son poste : glisse vers lui sans demi-tour, en s'écartant d'un navire à moins de 260 m
                gr = math.radians(rh)
                gu = (math.sin(gr), math.cos(gr))
                gs_ = (math.cos(gr), -math.sin(gr))
                e_al = vx * gu[0] + vy * gu[1]
                e_cr = vx * gs_[0] + vy * gs_[1]
                al = g["sog"] + clamp(0.045 * e_al, -max(g["sog"] - 0.8, 0.0), 13.0)
                cr = clamp(0.045 * e_cr, -13.0, 13.0)
                wx, wy = al * gu[0] + cr * gs_[0], al * gu[1] + cr * gs_[1]
                for n2 in S:
                    o2 = states.get(n2)
                    if n2 == n or not o2:
                        continue
                    ox, oy = s["x"] - o2["x"], s["y"] - o2["y"]
                    od = math.hypot(ox, oy)
                    if 1.0 < od < 260.0:
                        f = 16.0 * ((260.0 - od) / 260.0) ** 0.6
                        wx += f * ox / od
                        wy += f * oy / od
                course = math.degrees(math.atan2(wx, wy)) % 360
                v = clamp(math.hypot(wx, wy), 0.8, VMAX)
            elif sh["mode"] == "formation":
                ea = sa - ((s["x"] - g["x"]) * u[0] + (s["y"] - g["y"]) * u[1])
                if rh != g["hdg"] or (wake and sc == 0 and sa < 0):
                    ea = vx * math.sin(math.radians(rh)) + vy * math.cos(math.radians(rh))
                brg = math.degrees(math.atan2(vx, vy)) % 360
                w = clamp(dist / 200.0, 0.0, 1.0)
                course = (rh + w * angdiff(brg, rh)) % 360
                v = clamp(
                    run["gspeed"] + clamp(0.02 * ea, -3.0, 5.0) + (2.0 if dist > 300 else 0.0), 1.5, VMAX
                )
            else:
                course, v = sh["cap"], sh["v"]
            steer(n, course, v, sh["mode"] != "formation" or togturn)
        return out
