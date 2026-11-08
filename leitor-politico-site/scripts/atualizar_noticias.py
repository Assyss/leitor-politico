#!/usr/bin/env python3
"""Baixa os feeds de fontes.json e gera _site/news.json (executado pelo GitHub Actions)."""
import calendar, html, json, re, sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests

RAIZ = Path(__file__).resolve().parent.parent
HEADERS = {"User-Agent": "LeitorPoliticoBot/1.0"}


def limpar(t, n):
    t = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t or ""))).strip()
    return t[:n] + ("…" if len(t) > n else "")


def imagem(e):
    """Miniatura da notícia (feeds costumam trazê-la); vazio se não houver."""
    cand = [m.get("url") for k in ("media_thumbnail", "media_content") for m in (e.get(k) or [])]
    cand += [l.get("href") for l in e.get("links", []) if l.get("rel") == "enclosure" and str(l.get("type", "")).startswith("image")]
    m = re.search(r'<img[^>]+src=["\']([^"\']+)', e.get("summary") or "")
    cand.append(m.group(1) if m else "")
    return next((c for c in cand if c and c.lower().startswith("http")), "")


def baixar(fonte):
    rg, nome, url, nota = fonte
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        feed = feedparser.parse(r.content)
    except Exception as e:  # noqa: BLE001
        return fonte, [], str(e)[:120]
    itens = []
    for e in feed.entries[:12]:
        t = e.get("published_parsed") or e.get("updated_parsed")
        itens.append({"titulo": limpar(e.get("title"), 200), "resumo": limpar(e.get("summary"), 220),
                      "link": e.get("link", ""), "fonte": nome, "nota": nota, "regiao": rg,
                      "ts": calendar.timegm(t) if t else 0, "img": imagem(e)})
    return fonte, itens, (None if itens else "feed sem itens")


def main():
    fontes = json.loads((RAIZ / "fontes.json").read_text(encoding="utf-8"))
    lista = [(rg, nome, *(v if isinstance(v, list) else [v, ""])) for rg, d in fontes.items() for nome, v in d.items()]
    with ThreadPoolExecutor(12) as ex:
        resultados = list(ex.map(baixar, lista))
    itens, falhas, vistos = [], [], set()
    for (rg, nome, _, _), its, erro in resultados:
        if erro:
            falhas.append(f"{nome}: {erro}")
            print(f"FALHOU  {nome}: {erro}")
        for it in its:
            if it["link"] and it["link"] not in vistos:
                vistos.add(it["link"])
                itens.append(it)
    itens.sort(key=lambda i: i["ts"], reverse=True)
    saida = RAIZ / "_site"
    saida.mkdir(exist_ok=True)
    (saida / "news.json").write_text(json.dumps(
        {"atualizado": datetime.now(timezone.utc).isoformat(), "itens": itens, "falhas": falhas},
        ensure_ascii=False), encoding="utf-8")
    print(f"{len(itens)} notícias de {len(lista) - len(falhas)}/{len(lista)} fontes")
    if not itens:
        sys.exit(1)


if __name__ == "__main__":
    main()
