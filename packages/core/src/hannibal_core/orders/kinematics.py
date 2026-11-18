"""Simulation cinematique simple (trajectoires fantomes, CPA). Aucun appel au moteur."""

import math

KN = 0.514444
NM = 1852.0
TURN_RATE = 4.0  # deg/s (limite fixee a la creation des navires)
ACCEL = 0.5  # m/s^2


def _angdiff(a, b):
    return ((a - b + 540.0) % 360.0) - 180.0


def apply_orders(hdg, sog, orders):
    cap, spd = hdg, sog
    for o in orders:
        if o["type"] == "CORPEN":
            cap = float(o["cap"])
        elif o["type"] == "TURN":
            cap = (cap + (1 if o["side"] == "STBD" else -1) * o["deg"]) % 360
        elif o["type"] == "SPEED":
            spd = o["kn"] * KN
    return cap, spd


def path(ship, orders, horizon=900, dt=1.0, step=10):
    """Trajectoire [(t,x,y)] d'un navire qui execute les ordres immediatement."""
    cap, spd = apply_orders(ship["hdg"], ship["sog"], orders)
    x, y, h, v = ship["x"], ship["y"], ship["hdg"], ship["sog"]
    pts = [(0.0, x, y)]
    t = 0.0
    while t < horizon:
        d = _angdiff(cap, h)
        w = min(TURN_RATE, math.degrees(max(v, 2.0) / 365.5)) * dt  # diametre tactique 731 m
        h = (h + max(-w, min(w, d))) % 360
        v += max(-ACCEL * dt, min(ACCEL * dt, spd - v))
        x += v * math.sin(math.radians(h)) * dt
        y += v * math.cos(math.radians(h)) * dt
        t += dt
        if int(round(t)) % step == 0:
            pts.append((t, x, y))
    return pts


def cpa_pairs(pa, pb):
    """CPA entre deux trajectoires echantillonnees aux memes temps -> (dist_min, t)."""
    best = (1e18, 0.0)
    for (t, xa, ya), (_, xb, yb) in zip(pa, pb):
        d = math.hypot(xa - xb, ya - yb)
        if d < best[0]:
            best = (d, t)
    return best


def contact_path(c, horizon=900, step=10):
    return [(float(t), c["x"] + c["vx"] * t, c["y"] + c["vy"] * t) for t in range(0, horizon + 1, step)]


def ghost(ships, to, orders, contacts, horizon=900):
    """ships: liste de dicts (name,x,y,hdg,sog). to: ['TOUS'] ou [NOM]. -> trajectoires + CPA."""
    affected = {s["name"].upper() for s in ships} if to == ["TOUS"] else {n.upper() for n in to}
    paths, base = {}, {}
    for s in ships:
        o = orders if s["name"].upper() in affected else []
        paths[s["name"]] = path(s, o, horizon)
        base[s["name"]] = path(s, [], horizon)
    cpas = []
    for s in ships:
        for c in contacts:
            d, t = cpa_pairs(paths[s["name"]], contact_path(c, horizon))
            d0, t0 = cpa_pairs(base[s["name"]], contact_path(c, horizon))
            cpas.append(
                {
                    "ship": s["name"],
                    "contact": c["id"],
                    "cpa_nm": round(d / NM, 2),
                    "tcpa_s": int(t),
                    "cpa_nm_sans_ordre": round(d0 / NM, 2),
                    "risque": d < 0.5 * NM,
                }
            )
    names = [s["name"] for s in ships]
    mini = []
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            d, t = cpa_pairs(paths[a], paths[b])
            mini.append({"a": a, "b": b, "dist_m": int(d), "t_s": int(t), "risque": d < 150})
    return {
        "paths": {n: [[round(x, 1), round(y, 1), int(t)] for t, x, y in p] for n, p in paths.items()},
        "cpa": cpas,
        "ships_min": mini,
    }


def cpa_now(own, c):
    """CPA instantane du navire own vs piste c."""
    rx, ry = c["x"] - own["x"], c["y"] - own["y"]
    ovx, ovy = (
        own["sog"] * math.sin(math.radians(own["hdg"])),
        own["sog"] * math.cos(math.radians(own["hdg"])),
    )
    vx, vy = c["vx"] - ovx, c["vy"] - ovy
    v2 = vx * vx + vy * vy
    t = 0.0 if v2 < 1e-6 else max(0.0, -(rx * vx + ry * vy) / v2)
    d = math.hypot(rx + vx * t, ry + vy * t)
    rng = math.hypot(rx, ry)
    brg = math.degrees(math.atan2(rx, ry)) % 360
    return {"range_nm": rng / NM, "brg": brg, "cpa_nm": d / NM, "tcpa_min": t / 60.0}
