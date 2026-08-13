"""Kart beklentisi ↔ canli yanit karsilastirici.

Jira kartlari beklenen response'u kod blogu olarak yaziyor (168 kartta var).
Bu modul o beklentiyi canli yanitla ALAN ALAN karsilastirir.

Neden deger degil TIP karsilastiriliyor: kart ornekleri yer tutucu tasir
("uuid", "$string", ornek tarihler). Degerleri karsilastirmak her alani
"farkli" gosterirdi. Anlamli olan sorular sunlar:
  - Kartin vaat ettigi alan canlida VAR MI?
  - Tipi tutuyor mu (sayi vaat edilip string donmus mu)?
  - Canlida kartta olmayan alanlar var mi (kart eskimis olabilir)?

Cikti: {"eksik": [...], "tipFarki": [...], "fazla": [...], "verdict": "..."}
"""
import re

# Kart orneklerinde gecen yer tutucular — bunlar "gercek deger" sayilmaz
PLACEHOLDER_RE = re.compile(
    r"^(uuid|string|number|bool(ean)?|null|\$\w+|\.\.\.|<[^>]+>)$", re.I)

# Karsilastirmaya dahil edilmeyen, her yanitta degisen alanlar
VOLATILE_FIELDS = {"correlationId", "timestamp", "createdAt", "updatedAt",
                   "deletedAt", "expiresAt", "id", "tenantId"}


def _type_name(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _compatible(expected, actual):
    """Tipler uyumlu mu? Yer tutucular ve sayisal genisleme tolere edilir."""
    exp_type, act_type = _type_name(expected), _type_name(actual)

    if exp_type == act_type:
        return True
    # kart "uuid"/"$string" yazmis, canli gercek string donmus
    if exp_type == "string" and isinstance(expected, str) and PLACEHOLDER_RE.match(expected.strip()):
        return True
    # integer <-> number
    if {exp_type, act_type} <= {"integer", "number"}:
        return True
    # kart null ornek vermis (alan opsiyonel)
    if exp_type == "null" or act_type == "null":
        return True
    return False


def compare(expected, actual, path="", missing=None, mismatched=None, extra=None):
    """Beklenen yapiyi canli yanitla karsilastirir (ozyinelemeli)."""
    missing = [] if missing is None else missing
    mismatched = [] if mismatched is None else mismatched
    extra = [] if extra is None else extra

    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            mismatched.append({"alan": path or "(kok)", "beklenen": "object",
                               "gelen": _type_name(actual)})
            return missing, mismatched, extra

        for key, exp_value in expected.items():
            child = f"{path}.{key}" if path else key
            if key not in actual:
                missing.append(child)
                continue
            compare(exp_value, actual[key], child, missing, mismatched, extra)

        for key in actual:
            if key not in expected and key not in VOLATILE_FIELDS:
                extra.append(f"{path}.{key}" if path else key)

    elif isinstance(expected, list):
        if not isinstance(actual, list):
            mismatched.append({"alan": path or "(kok)", "beklenen": "array",
                               "gelen": _type_name(actual)})
            return missing, mismatched, extra
        # ilk elemanlari temsilci kabul et
        if expected and actual:
            compare(expected[0], actual[0], f"{path}[0]", missing, mismatched, extra)

    else:
        leaf = path.split(".")[-1].split("[")[0]
        if leaf in VOLATILE_FIELDS:
            return missing, mismatched, extra
        if not _compatible(expected, actual):
            mismatched.append({"alan": path, "beklenen": _type_name(expected),
                               "gelen": _type_name(actual),
                               "beklenenDeger": expected, "gelenDeger": actual})

    return missing, mismatched, extra


def compare_card_to_live(expected_response, live_body, live_status,
                         documented_statuses=None):
    """Kart beklentisi ile canli yaniti karsilastirip verdict uretir."""
    result = {"eksik": [], "tipFarki": [], "fazla": [], "verdict": "",
              "durum": "bilinmiyor", "notlar": []}

    if expected_response is None:
        result["verdict"] = "Kartta beklenen response yok — karsilastirilamadi."
        result["durum"] = "dogrulanamadi"
        return result

    if live_body is None:
        result["verdict"] = f"Canli yanit JSON degil (HTTP {live_status}) — karsilastirilamadi."
        result["durum"] = "dogrulanamadi"
        return result

    # Kart 2xx ornegi verirken canli hata donduyse yapi karsilastirmasi anlamsiz
    expects_success = bool(expected_response.get("success")) if isinstance(expected_response, dict) else False
    if expects_success and live_status >= 400:
        result["verdict"] = (f"Kart basarili yanit tarif ediyor ama canli HTTP "
                             f"{live_status} dondu — once bu giderilmeli.")
        result["durum"] = "uyumsuz"
        if documented_statuses and str(live_status) not in documented_statuses:
            result["notlar"].append(
                f"HTTP {live_status} sozlesmede de tanimli degil "
                f"(dokumante: {', '.join(documented_statuses)})")
        return result

    missing, mismatched, extra = compare(expected_response, live_body)
    result["eksik"] = missing
    result["tipFarki"] = mismatched
    result["fazla"] = extra

    if missing or mismatched:
        parts = []
        if missing:
            parts.append(f"{len(missing)} alan eksik")
        if mismatched:
            parts.append(f"{len(mismatched)} tip farki")
        result["verdict"] = "UYUMSUZ — " + ", ".join(parts)
        result["durum"] = "uyumsuz"
    else:
        result["verdict"] = "UYUMLU — kartin tarif ettigi tum alanlar canlida mevcut ve tipleri tutuyor"
        result["durum"] = "uyumlu"

    if extra:
        result["notlar"].append(
            f"Canlida kartta olmayan {len(extra)} alan var — kart eskimis olabilir: "
            + ", ".join(extra[:8]))

    return result
