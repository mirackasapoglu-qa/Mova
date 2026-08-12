"""contract/openapi.json -> tests/api/endpoints.py uretir.

Endpoint yollari tek yerde toplanir; testler string literal tasimaz. Boylece
koleksiyon/spec guncellenince yollar tek komutla tazelenir:

    python contract/postman_to_openapi.py   # koleksiyon -> openapi.json
    python contract/gen_endpoints.py        # openapi.json -> endpoints.py

Sabit adlandirma: /v1 onceki surum eki atilir, statik segmentler _ ile
birlestirilir, path parametreleri sonda _BY_<PARAM> olarak belirtilir.
    /v1/users/{userId}                      -> USERS_BY_USER_ID
    /v1/customers/{customerId}/notes        -> CUSTOMERS_NOTES_BY_CUSTOMER_ID
"""
import argparse
import json
import pathlib
import re
from collections import OrderedDict, defaultdict

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent
DEFAULT_SPEC = HERE / "openapi.json"
DEFAULT_OUT = ROOT / "tests" / "api" / "endpoints.py"

VERSION_RE = re.compile(r"^v\d+$")


def snake_upper(text):
    """camelCase / kebab-case -> SNAKE_UPPER"""
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", text)
    text = re.sub(r"[^A-Za-z0-9]+", "_", text)
    return text.upper().strip("_")


def const_name(path):
    segments = [s for s in path.strip("/").split("/") if s]
    static, params = [], []
    for seg in segments:
        if seg.startswith("{") and seg.endswith("}"):
            params.append(snake_upper(seg[1:-1]))
        elif VERSION_RE.match(seg) and not static:
            continue  # bastaki /v1 surum ekini at
        else:
            static.append(snake_upper(seg))
    name = "_".join(static) or "ROOT"
    if params:
        name += "_BY_" + "_".join(params)
    return name


def group_of(spec, path):
    """Path'in ait oldugu tag (spec'teki ilk operasyondan)."""
    for method, op in spec["paths"][path].items():
        if method == "parameters":
            continue
        tags = op.get("tags") or []
        if tags:
            return tags[0]
    return "Diger"


def build(spec_path, out_path):
    spec = json.loads(pathlib.Path(spec_path).read_text(encoding="utf-8"))
    paths = spec["paths"]

    groups = defaultdict(list)
    for path in sorted(paths):
        groups[group_of(spec, path)].append(path)

    names = OrderedDict()
    lines = [
        '"""Endpoint yollari — OTOMATIK URETILDI, ELLE DUZENLEME.',
        "",
        "Kaynak: contract/openapi.json (Postman koleksiyonundan turetildi).",
        "Yenilemek icin:",
        "    python contract/postman_to_openapi.py",
        "    python contract/gen_endpoints.py",
        "",
        "Parametreli yollar .format() ile kullanilir:",
        "    api.get(endpoints.USERS_BY_USER_ID.format(userId=uid))",
        '"""',
        "",
    ]

    for group in sorted(groups):
        lines.append(f"# --- {group} " + "-" * max(0, 60 - len(group)))
        for path in groups[group]:
            base = const_name(path)
            name, i = base, 2
            while name in names:
                name, i = f"{base}_{i}", i + 1
            names[name] = path
            methods = sorted(m.upper() for m in paths[path] if m != "parameters")
            lines.append(f'{name} = "{path}"  # {" ".join(methods)}')
        lines.append("")

    lines.append("# Tum yollar — kapsam/smoke testleri icin")
    lines.append("ALL_PATHS = (")
    for name in names:
        lines.append(f"    {name},")
    lines.append(")")
    lines.append("")

    out = pathlib.Path(out_path)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"OK -> {out}  ({len(names)} endpoint, {len(groups)} grup)")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--spec", default=str(DEFAULT_SPEC))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()
    build(args.spec, args.out)


if __name__ == "__main__":
    main()
