"""Contrôle d'une explication d'ordre rédigée par le modèle, sans modèle.

Repris de legacy/hx/scripts/rag.py (`validate`, `params_en`, `params_fr`) : le bord, le cap vrai et chaque valeur
décodée doivent se retrouver, sans inversion, dans les deux langues. Une liste vide signifie « conforme ».
"""

import re
from collections.abc import Mapping

SIDE_FR = {"PORT": "bâbord", "STBD": "tribord"}
SIDE_EN = {"PORT": "port", "STBD": "starboard"}
CHECKED_VALUES = (
    "relative_degrees",
    "true_course",
    "true_bearing",
    "relative_bearing_degrees",
    "speed_knots",
    "formation_number",
)


def parameters_en(parameters: Mapping[str, int | str]) -> str:
    """Sens des paramètres, en anglais, imposé au modèle."""
    out = []
    if (side := parameters.get("side")) in SIDE_EN:
        out.append(f"side: {SIDE_EN[str(side)]}")
    if "relative_degrees" in parameters:
        out.append(f"amount: {parameters['relative_degrees']} degrees relative to the present course")
    if "true_course" in parameters:
        course = int(parameters["true_course"])
        out.append(f"the TRUE COURSE to end on: {course:03d}, NOT a change of {course} degrees")
    if "true_bearing" in parameters:
        out.append(f"true bearing {int(parameters['true_bearing']):03d}")
    if "relative_bearing_degrees" in parameters:
        out.append(f"relative bearing {parameters['relative_bearing_degrees']} degrees")
    if "speed_knots" in parameters:
        out.append(f"speed {parameters['speed_knots']} knots")
    if "formation_number" in parameters:
        out.append(f"formation number {parameters['formation_number']}")
    return "; ".join(out) or "none"


def parameters_fr(parameters: Mapping[str, int | str]) -> str:
    """Paramètres décodés, dits en français (repris tels quels par le modèle)."""
    out = []
    if (side := parameters.get("side")) in SIDE_FR:
        out.append(f"bord : {SIDE_FR[str(side)]} ({side})")
    if "relative_degrees" in parameters:
        out.append(f"{parameters['relative_degrees']} degrés par rapport au cap actuel")
    if "true_course" in parameters:
        course = int(parameters["true_course"])
        out.append(f"cap vrai à atteindre : {course:03d} (ce n'est PAS un changement de {course} degrés)")
    if "true_bearing" in parameters:
        out.append(f"relèvement vrai {int(parameters['true_bearing']):03d}")
    if "relative_bearing_degrees" in parameters:
        out.append(f"relèvement relatif {parameters['relative_bearing_degrees']} degrés")
    if "speed_knots" in parameters:
        out.append(f"vitesse {parameters['speed_knots']} nœuds")
    if "formation_number" in parameters:
        out.append(f"formation numéro {parameters['formation_number']}")
    return " ; ".join(out) or "aucun"


def explanation_errors(
    explanation_en: str, explanation_fr: str, parameters: Mapping[str, int | str]
) -> list[str]:
    en = explanation_en.lower()
    fr = explanation_fr.lower()
    if not en or not fr:
        return ["explication manquante"]
    errors = []
    side = str(parameters.get("side", ""))
    if side in SIDE_FR:
        other = "PORT" if side == "STBD" else "STBD"
        if SIDE_FR[side] not in fr:
            errors.append(f"le français doit contenir « {SIDE_FR[side]} »")
        if SIDE_FR[other] in fr:
            errors.append(f"le français contient « {SIDE_FR[other]} » alors que le bord est {side}")
        if SIDE_EN[side] not in en:
            errors.append(f"l'anglais doit contenir « {SIDE_EN[side]} »")
        if re.search(rf"\b{SIDE_EN[other]}\b", en):
            errors.append(f"l'anglais contient « {SIDE_EN[other]} » alors que le bord est {side}")
    if "true_course" in parameters:
        course = int(parameters["true_course"])
        if re.search(rf"\bby 0*{course} degrees", en) or re.search(
            rf"(modifi|chang|alt[ée]r)\w* (votre |le |son |leur )?cap de 0*{course}\b", fr
        ):
            errors.append(f"{course:03d} est un cap vrai à atteindre, pas un changement de {course} degrés")
        if not (re.search(rf"course (of |to )?0*{course}\b", en) or "true course" in en):
            errors.append("l'anglais doit nommer le cap à atteindre (course)")
        if not re.search(rf"cap (vrai )?(de |au |à )?0*{course}\b", fr):
            errors.append("le français doit nommer le cap à atteindre (cap vrai …)")
    for key in CHECKED_VALUES:
        if key not in parameters:
            continue
        value = int(parameters[key])
        forms = {str(value), f"{value:03d}"}
        for language, text in (("anglais", en), ("français", fr)):
            if not any(re.search(rf"(?<!\d){re.escape(form)}(?!\d)", text) for form in forms):
                errors.append(f"la valeur {value} ({key}) est absente du {language}")
    return errors
