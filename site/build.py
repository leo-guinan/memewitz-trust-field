#!/usr/bin/env python3
"""Build the Memewitz 101-item field manual as a static picture book."""
from __future__ import annotations
import html, json, re, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public"
BOOK = ROOT / "101_THINGS_BEFORE_BUYING_THE_DEX.md"
IMAGES = ROOT / "nft-collection" / "images"


def items():
    text = BOOK.read_text()
    found = []
    for m in re.finditer(r"^### (\d+)\. ([^\n]+)\n\n([^\n]+)", text, re.M):
        n = int(m.group(1))
        if 1 <= n <= 101:
            found.append({"number": n, "title": m.group(2).strip(), "text": m.group(3).strip()})
    if [x["number"] for x in found] != list(range(1, 102)):
        raise SystemExit(f"expected 101 consecutive items, got {len(found)}")
    return found


def main():
    data = items()
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "images").mkdir(parents=True)
    records = []
    for item in data:
        prefix = f"{item['number']:03d}-"
        candidates = sorted(IMAGES.glob(prefix + "*.png"))
        if len(candidates) != 1:
            raise SystemExit(f"expected one image for #{item['number']:03d}, got {candidates}")
        name = candidates[0].name
        shutil.copy2(candidates[0], OUT / "images" / name)
        records.append({**item, "image": "images/" + name})

    payload = json.dumps(records, ensure_ascii=False).replace("</", "<\\/")
    title = "101 Things to Do Before Buying the DEX"
    page = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#11141d">
<meta name="description" content="A 101-page illustrated field manual for building trust before paying for the DEX.">
<title>{html.escape(title)} — Memewitz</title>
<style>
:root{{--ink:#11141d;--paper:#f5eddd;--muted:#a8a092;--amber:#e9a85c;--coral:#dc7563;--cyan:#78d8d1;--line:rgba(245,237,221,.16)}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--ink);color:var(--paper);font-family:ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;min-height:100vh}}button{{font:inherit;color:inherit}} .shell{{min-height:100vh;display:grid;grid-template-rows:auto 1fr auto}}header{{padding:18px clamp(18px,4vw,56px);display:flex;justify-content:space-between;gap:20px;align-items:center;border-bottom:1px solid var(--line)}}.brand{{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--amber)}}.status{{font-size:11px;color:var(--muted)}}main{{display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:clamp(18px,4vw,64px);padding:clamp(20px,4vw,56px);align-items:center;max-width:1500px;width:100%;margin:auto}}.book{{min-width:0}}.eyebrow{{color:var(--coral);font-size:13px;letter-spacing:.12em;text-transform:uppercase;margin-bottom:12px}}h1{{font-family:Georgia,serif;font-weight:400;font-size:clamp(34px,6vw,82px);line-height:.95;letter-spacing:-.045em;margin:0 0 22px;max-width:850px}}.lede{{color:#d8cfbf;font-family:Georgia,serif;font-size:clamp(17px,2vw,23px);line-height:1.45;max-width:760px;margin:0 0 28px}}.art-frame{{background:#172131;border:1px solid var(--line);box-shadow:0 22px 70px rgba(0,0,0,.3);padding:10px;max-width:900px;position:relative}}.art-frame img{{display:block;width:100%;height:auto;aspect-ratio:1;object-fit:cover;background:#19202c}}.caption{{display:flex;justify-content:space-between;gap:18px;padding:15px 4px 4px;font-size:12px;color:var(--muted)}}.caption strong{{color:var(--paper);font-weight:500}}.text-panel{{max-width:760px;padding-top:24px}}.item-title{{font-family:Georgia,serif;font-size:clamp(25px,3vw,43px);line-height:1.05;margin:0 0 14px}}.item-text{{font-family:Georgia,serif;color:#d8cfbf;font-size:18px;line-height:1.55;margin:0}}aside{{align-self:stretch;display:flex;flex-direction:column;justify-content:center;border-left:1px solid var(--line);padding-left:28px;min-width:0}}.rail-label{{font-size:11px;letter-spacing:.15em;text-transform:uppercase;color:var(--muted);margin-bottom:10px}}.progress{{height:5px;background:#28303b;margin-bottom:24px}}.progress i{{display:block;height:100%;background:linear-gradient(90deg,var(--coral),var(--amber));width:1%;transition:width .25s}}.thumbs{{display:grid;grid-template-columns:repeat(5,1fr);gap:5px;max-height:48vh;overflow:auto;padding-right:4px}}.thumb{{border:0;padding:0;background:#25303b;cursor:pointer;aspect-ratio:1;opacity:.46;outline:1px solid transparent}}.thumb:hover,.thumb.active{{opacity:1;outline:2px solid var(--amber)}}.thumb img{{width:100%;height:100%;object-fit:cover;display:block}}.controls{{display:flex;gap:10px;margin-top:22px}}.controls button{{border:1px solid var(--line);background:transparent;padding:12px 16px;cursor:pointer;font-size:12px;letter-spacing:.08em;text-transform:uppercase}}.controls button:hover{{border-color:var(--amber);color:var(--amber)}}footer{{padding:16px clamp(18px,4vw,56px);border-top:1px solid var(--line);display:flex;justify-content:space-between;gap:15px;color:var(--muted);font-size:11px}}footer a{{color:var(--cyan);text-decoration:none}}@media(max-width:900px){{main{{display:block;padding:24px 18px}}aside{{border-left:0;border-top:1px solid var(--line);padding:24px 0 0;margin-top:32px}}.thumbs{{max-height:180px}}header{{padding:16px 18px}}footer{{padding:14px 18px}}}}@media(prefers-reduced-motion:reduce){{*{{scroll-behavior:auto!important;transition:none!important}}}}
</style>
</head>
<body><div class="shell"><header><div class="brand">Memewitz · Entropy Press</div><div class="status">A picture book about trust before infrastructure</div></header><main><section class="book"><div class="eyebrow" id="eyebrow">Field manual · page 001 of 101</div><h1>{html.escape(title)}</h1><p class="lede">Most meme-token advice begins after the buy. This begins before the DEX: inspect the mechanism, make something together, and keep the artifact meaningful if the token fails.</p><div class="art-frame"><img id="art" alt="" src=""><div class="caption"><span id="caption">Illustrated field note</span><strong id="page-number">001 / 101</strong></div></div><div class="text-panel"><h2 class="item-title" id="item-title"></h2><p class="item-text" id="item-text"></p></div></section><aside><div class="rail-label">Navigate the field manual</div><div class="progress"><i id="progress"></i></div><div class="thumbs" id="thumbs"></div><div class="controls"><button id="prev" type="button">← Previous</button><button id="next" type="button">Next →</button></div><p class="status" style="line-height:1.5;margin-top:18px">Arrow keys move through the book. The image is the memory device; the text is the receipt.</p></aside></main><footer><span>Participation is optional. Price, liquidity, migration, and resale are not guaranteed.</span><a href="https://github.com/leo-guinan/memewitz-trust-field">Source &amp; receipts ↗</a></footer></div>
<script id="book-data" type="application/json">{payload}</script>
<script>
const pages=JSON.parse(document.getElementById('book-data').textContent);let current=0;
const $=id=>document.getElementById(id);const thumbs=$('thumbs');
pages.forEach((p,i)=>{{const b=document.createElement('button');b.className='thumb';b.type='button';b.title=`${{String(p.number).padStart(3,'0')}} — ${{p.title}}`;b.innerHTML=`<img loading="lazy" src="${{p.image}}" alt="">`;b.onclick=()=>show(i);b.dataset.index=i;thumbs.appendChild(b)}});
function show(i){{current=Math.max(0,Math.min(pages.length-1,i));const p=pages[current];$('art').src=p.image;$('art').alt=`Illustration for page ${{p.number}}: ${{p.title}}`;$('item-title').textContent=`${{String(p.number).padStart(3,'0')}}. ${{p.title}}`;$('item-text').textContent=p.text;$('eyebrow').textContent=`Field manual · page ${{String(p.number).padStart(3,'0')}} of 101`;$('page-number').textContent=`${{String(p.number).padStart(3,'0')}} / 101`;$('caption').textContent=p.title;$('progress').style.width=`${{((current+1)/pages.length)*100}}%`;document.querySelectorAll('.thumb').forEach((x,j)=>x.classList.toggle('active',j===current));document.querySelector('.thumb.active')?.scrollIntoView({{block:'nearest',inline:'nearest'}});$('prev').disabled=current===0;$('next').disabled=current===pages.length-1;history.replaceState(null,'',`#page-${{p.number}}`)}}
$('prev').onclick=()=>show(current-1);$('next').onclick=()=>show(current+1);document.addEventListener('keydown',e=>{{if(['ArrowLeft','PageUp'].includes(e.key))show(current-1);if(['ArrowRight','PageDown',' '].includes(e.key)){{e.preventDefault();show(current+1)}}}});const hash=location.hash.match(/page-(\d+)/);show(hash?Number(hash[1])-1:0);
</script></body></html>'''
    (OUT / "index.html").write_text(page)
    print(json.dumps({"pages": len(data), "output": str(OUT), "images": len(list((OUT / 'images').glob('*.png')))}))

if __name__ == "__main__":
    main()
