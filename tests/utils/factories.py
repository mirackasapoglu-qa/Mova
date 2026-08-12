"""Benzersiz test verisi ureticileri + spec'ten dokumante ornek cekme.

Tasarim: create/update govdelerini elle yeniden yazmak yerine OpenAPI spec'inde
dokumante edilmis ornegi kaynak alip yalnizca CAKISAN alanlari (email, kod, isim)
benzersizlestiririz. Boylece koleksiyon guncellenince testler otomatik uyum saglar
ve "dokumandaki govde ile canli govde ayni mi" sorusu testin dogal parcasi olur.
"""
import copy
import random
import re
import time

VAR_RE = re.compile(r"\{\{(\w+)\}\}")


def unique_suffix():
    """Zaman + rastgele ekiyle benzersiz kisa ek."""
    return f"{int(time.time())}{random.randint(100, 999)}"


def gen_email(prefix="qa_auto"):
    return f"{prefix}_{unique_suffix()}@example.com"


def gen_phone():
    """+90 formatinda (buyuk ihtimalle) benzersiz cep numarasi."""
    return "+9053" + str(random.randint(10000000, 99999999))


def gen_code(prefix="QA"):
    """Benzersiz kod alanlari icin (projectCode, schoolCode vb.)."""
    return f"{prefix}-{unique_suffix()}"


def gen_name(prefix="QA Auto"):
    return f"{prefix} {unique_suffix()}"


def spec_example(spec, path, method):
    """Spec'te dokumante edilmis request body ornegini doner (kopya)."""
    op = spec.get("paths", {}).get(path, {}).get(method.lower())
    if not op:
        return None
    example = (
        op.get("requestBody", {})
        .get("content", {})
        .get("application/json", {})
        .get("example")
    )
    return copy.deepcopy(example) if example is not None else None


def resolve_vars(payload, values=None):
    """Govdedeki {{degisken}} yer tutucularini doldurur.

    values ile verilmeyen degiskenler None'a cevrilir — boylece gonderilmeden
    once eksik baglantilarin (ornegin customerId) farkina variriz.
    """
    values = values or {}

    def walk(node):
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        if isinstance(node, str):
            match = VAR_RE.fullmatch(node.strip())
            if match:
                return values.get(match.group(1))
            return VAR_RE.sub(lambda m: str(values.get(m.group(1), "")), node)
        return node

    return walk(payload)


def uniquify(payload, fields=("email", "projectCode", "schoolCode", "code", "taxNumber")):
    """Cakisma (409) uretebilecek alanlari benzersizlestirir."""
    out = copy.deepcopy(payload)

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in fields and isinstance(value, str):
                    if key == "email":
                        node[key] = gen_email()
                    elif key == "taxNumber":
                        node[key] = str(random.randint(10**10, 10**11 - 1))
                    else:
                        node[key] = gen_code(value.split("-")[0] if "-" in value else "QA")
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(out)
    return out
