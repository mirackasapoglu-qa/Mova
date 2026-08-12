"""Path parametrelerini canli koleksiyonlardan gercek ID'lerle cozumler.

Neden gerekli: Postman koleksiyonundaki {{last_customer_id}} gibi degiskenler kosum
aninda doluyordu; statik sozlesmeye gercek bir referans deger gecmedi. Yer tutucu ID
ile cagrilan detay uclari 404 doner ve 404 sozlesmeye uygun oldugu icin sonuc
"uyumlu" gorunur — yanit govdesi hic dogrulanmadigi halde. Bu modul o kor noktayi
kapatir.

Yontem: her path parametresi icin ondan ONCEKI yol parcasi o kaynagin koleksiyonudur.

    /v1/customers/{customerId}                 -> GET /v1/customers -> data[0].id
    /v1/customers/{customerId}/notes/{noteId}  -> customerId cozulur, sonra
                                                  GET /v1/customers/<id>/notes -> data[0].id

Koleksiyon yanitlari onbelleklenir; bir sweep'te ayni koleksiyon onlarca operasyon
tarafindan paylasilir.
"""
import re

import requests

PLACEHOLDER_ID = "00000000-0000-0000-0000-000000000000"
PARAM_RE = re.compile(r"^\{(\w+)\}$")


def list_items(body):
    """Yanittan liste cikarir — OPRAS'ta iki kalip var: data[] ve data.data[]."""
    if not isinstance(body, dict):
        return []
    data = body.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return data["data"]
    return []


class PathParamResolver:
    """Canli veriden path parametresi cozumleyici (koleksiyon onbellekli)."""

    def __init__(self, base_url, headers=None, timeout=15):
        self.base_url = (base_url or "").rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout
        self._cache = {}       # koleksiyon yolu -> ilk kaydin id'si (ya da None)
        self.requests_made = 0

    def _first_id(self, collection):
        """Koleksiyondan ilk kaydin id'sini doner; bulunamazsa None."""
        if collection in self._cache:
            return self._cache[collection]

        value = None
        try:
            self.requests_made += 1
            resp = requests.get(f"{self.base_url}{collection}", headers=self.headers,
                                params={"page": 1, "limit": 1}, timeout=self.timeout)
            if resp.ok:
                items = list_items(resp.json())
                if items and isinstance(items[0], dict):
                    value = items[0].get("id")
        except (requests.RequestException, ValueError):
            value = None

        self._cache[collection] = value
        return value

    def resolve(self, path):
        """{'values': {...}, 'resolvedFrom': {...}, 'error': str|None} doner.

        Kismi cozum de dondurulur: derin bir seviye cozulemezse ustteki degerler
        yine kullanilabilir durumda kalir.
        """
        values, resolved_from, prefix = {}, {}, []

        for segment in path.strip("/").split("/"):
            match = PARAM_RE.match(segment)
            if not match:
                prefix.append(segment)
                continue

            name = match.group(1)
            collection = "/" + "/".join(prefix)
            value = self._first_id(collection)

            if not value:
                return {"values": values, "resolvedFrom": resolved_from,
                        "error": f"'{name}' icin canli kayit bulunamadi "
                                 f"(kaynak: GET {collection})"}

            values[name] = value
            resolved_from[name] = f"GET {collection}"
            prefix.append(str(value))

        return {"values": values, "resolvedFrom": resolved_from, "error": None}

    def fill(self, path, values=None):
        """Yolu verilen degerlerle doldurur; eksik kalanlara yer tutucu koyar."""
        values = values or {}
        out = path
        for name, value in values.items():
            out = out.replace("{" + name + "}", str(value))
        return re.sub(r"\{(\w+)\}", PLACEHOLDER_ID, out)
