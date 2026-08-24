#!/usr/bin/env python3
from pathlib import Path
import json,re,time,os,sys
from google import genai
from google.genai import types

ROOT=Path(__file__).resolve().parent
BOOK=ROOT/'101_THINGS_BEFORE_BUYING_THE_DEX.md'
OUT=ROOT/'nft-collection'
IMG=OUT/'images'; PROMPTS=OUT/'prompts'
IMG.mkdir(parents=True,exist_ok=True); PROMPTS.mkdir(parents=True,exist_ok=True)
MANIFEST=OUT/'manifest.json'

# Load a Google key without printing it.
key=None
for p in (Path.home()/'.env',Path.home()/'.hermes/.env'):
    try: lines=p.read_text(errors='ignore').splitlines()
    except Exception: continue
    for raw in lines:
        s=raw.strip()
        if not s or s.startswith('#') or '=' not in s: continue
        n,v=s.split('=',1)
        if n.strip().upper() in {'GEMINI_API_KEY','GOOGLE_API_KEY','GOOGLE_GENERATIVE_API_KEY','GENERATIVE_API_KEY'}:
            key=v.strip().strip('"').strip("'"); break
    if key: break
if not key: raise SystemExit('No Gemini API key found')

text=BOOK.read_text()
items=[]
for m in re.finditer(r'^### (\d+)\. ([^\n]+)\n\n([^\n]+)',text,re.M):
    n=int(m.group(1)); title=m.group(2).strip(); desc=m.group(3).strip()
    if 1<=n<=101: items.append({'number':n,'title':title,'description':desc})
if [x['number'] for x in items] != list(range(1,102)):
    raise SystemExit(f'Expected 101 numbered items, got {len(items)}')

base='''A coherent collectible NFT illustration series for a public trust field manual about meme markets. Square 1:1 composition. Recurring protagonist in every image: a small, clever orange-and-cream market clerk fox with a red scarf, expressive but restrained, working at a tiny night market information counter. Recurring visual grammar: deep midnight blue, warm amber, muted coral, brass, paper, glass, subtle Solana-like electric cyan accents but no logos. The scene should feel like an editorial fable: practical, slightly absurd, humane, and observant. One strong central metaphor, clean silhouette, rich painterly detail, collectible-card quality, readable at thumbnail size. No text anywhere, no words, no letters, no numbers, no logos, no watermark, no readable marks.'''

def metaphor(title,desc):
    s=(title+' '+desc).lower()
    if 'print.world' in s or 'collection' in s or 'believer' in s or 'nft' in s:
        return 'the fox carefully hangs a set of luminous handmade identity tokens on a gallery wall while several early visitors stand together, a bridge behind them symbolizing transferability without guaranteed value'
    if 'bot' in s or 'strategy' in s or 'false positive' in s or 'false negative' in s:
        return 'the fox studies a mechanical clockwork trading machine under a magnifying glass, with one bright false signal separated from a quieter true signal'
    if 'lock' in s or 'burn' in s or 'unlock' in s or 'supply' in s:
        return 'the fox examines brass padlocks, a sealed glass jar, and a small controlled flame on an evidence table, with receipts represented as blank paper sheets'
    if 'wallet' in s or 'mint' in s or 'chain' in s or 'identity' in s or 'creator' in s:
        return 'the fox traces a transparent chain of physical brass links between a stamped blank identity card and a public glass case, inspecting rather than celebrating'
    if 'migration' in s or 'dex' in s or 'liquidity' in s or 'bonding' in s or 'pool' in s:
        return 'the fox stands before a narrow bridge from a wooden launch dock to a much larger turbulent pool, testing the bridge with a long pole before crossing'
    if 'community' in s or 'contributor' in s or 'mission' in s or 'holder' in s or 'name' in s:
        return 'the fox and a small diverse group of market visitors assemble a shared mosaic from separate glowing tiles, with no one figure dominating the composition'
    if 'failure' in s or 'loss' in s or 'falsifier' in s or 'correction' in s or 'mistake' in s or 'wrong' in s:
        return 'the fox pins a cracked compass and a corrected route on a dark evidence wall, calmly circling the detour instead of hiding it'
    if 'publish' in s or 'media' in s or 'thread' in s or 'card' in s or 'archive' in s:
        return 'the fox lays out a sequence of blank illustrated evidence cards on a long table, arranging them into a clear path for a visitor to follow'
    if 'question' in s or 'ask' in s or 'check' in s or 'read' in s or 'record' in s:
        return 'the fox holds a brass magnifying glass over a small mystery box on a clean evidence table, with several paths visible and one being carefully tested'
    return 'the fox pauses at an evidence table with a small glowing object, a balanced scale, and an open path into the night market, choosing inspection over hype'

manifest={'collection':'Before You Buy the DEX','model':'gemini-3-pro-image-preview','aspect_ratio':'1:1','style':'recurring orange-cream market clerk fox; editorial fable; no text','source_book':str(BOOK),'items':[]}
client=genai.Client(api_key=key)
for item in items:
    n=item['number']; slug=re.sub(r'[^a-z0-9]+','-',item['title'].lower()).strip('-')[:54]
    stem=f'{n:03d}-{slug}'
    out=IMG/(stem+'.png'); pp=PROMPTS/(stem+'.txt')
    prompt=base+'\n\nSpecific scene for item '+str(n)+': '+item['title']+'. '+metaphor(item['title'],item['description'])+'. The image must communicate the idea through objects and action alone; do not depict or imply a guaranteed financial outcome.'
    pp.write_text(prompt)
    rec={'number':n,'title':item['title'],'description':item['description'],'image':str(out),'prompt':str(pp),'status':'pending','attempts':0}
    if out.exists() and out.stat().st_size>50000:
        rec['status']='existing'; rec['bytes']=out.stat().st_size; manifest['items'].append(rec); continue
    for attempt in range(1,4):
        rec['attempts']=attempt
        try:
            r=client.models.generate_content(model='gemini-3-pro-image-preview',contents=types.Content(role='user',parts=[types.Part.from_text(text=prompt)]),config=types.GenerateContentConfig(response_modalities=['IMAGE','TEXT'],image_config=types.ImageConfig(aspect_ratio='1:1')))
            data=None
            for part in r.candidates[0].content.parts:
                if part.inline_data: data=part.inline_data.data; break
            if not data: raise RuntimeError('no image bytes returned')
            out.write_bytes(data); rec['status']='generated'; rec['bytes']=len(data); break
        except Exception as e:
            rec['error']=str(e)[:500]
            if attempt<3: time.sleep(5*attempt)
    if rec['status']=='pending': rec['status']='failed'
    manifest['items'].append(rec)
    MANIFEST.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'number':n,'status':rec['status'],'bytes':rec.get('bytes',0)}),flush=True)
MANIFEST.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
from PIL import Image,ImageDraw,ImageFont
valid=[x for x in manifest['items'] if Path(x['image']).exists()]
thumb=240; cols=10; rows=(len(valid)+cols-1)//cols
sheet=Image.new('RGB',(cols*thumb,rows*(thumb+28)),(18,24,34)); draw=ImageDraw.Draw(sheet)
for i,x in enumerate(valid):
    im=Image.open(x['image']).convert('RGB'); im.thumbnail((thumb,thumb)); xx=(i%cols)*thumb; yy=(i//cols)*(thumb+28); sheet.paste(im,(xx,yy)); draw.text((xx+5,yy+thumb+5),f"#{x['number']:03d}",(240,220,170))
sheet.save(OUT/'contact-sheet.jpg',quality=88)
print(json.dumps({'complete':sum(x['status'] in {'generated','existing'} for x in manifest['items']),'failed':sum(x['status']=='failed' for x in manifest['items']),'manifest':str(MANIFEST),'contact_sheet':str(OUT/'contact-sheet.jpg')}))
