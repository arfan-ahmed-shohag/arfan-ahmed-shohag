#!/usr/bin/env python3
"""Generate self-hosted GitHub profile SVG cards from public GitHub REST data."""
import json, os, sys, urllib.request, urllib.error, html
from collections import Counter
from pathlib import Path

USER = os.getenv('STATS_USERNAME', 'arfan-ahmed-shohag')
TOKEN = os.getenv('GH_STATS_TOKEN') or os.getenv('GITHUB_TOKEN', '')
OUT = Path('assets'); OUT.mkdir(exist_ok=True)
HEADERS = {'Accept':'application/vnd.github+json','User-Agent':'self-hosted-profile-stats','X-GitHub-Api-Version':'2022-11-28'}
if TOKEN: HEADERS['Authorization'] = 'Bearer ' + TOKEN

def api(path):
    req=urllib.request.Request('https://api.github.com'+path,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=25) as r: return json.load(r)

def esc(s): return html.escape(str(s),quote=True)
def text(x,y,s,size=18,fill='#e6edf3',weight=600):
    return f'<text x="{x}" y="{y}" fill="{fill}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" font-weight="{weight}">{esc(s)}</text>'
def frame(w,h,contents):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="GitHub profile statistics"><rect x="1" y="1" width="{w-2}" height="{h-2}" rx="16" fill="#0d1117" stroke="#30363d" stroke-width="2"/>{contents}</svg>'''

def write_if_changed(path,data):
    encoded=data.encode('utf-8')
    if not path.exists() or path.read_bytes()!=encoded: path.write_bytes(encoded)

try:
    profile=api('/users/'+USER)
    repos=[]; page=1
    while True:
        batch=api(f'/users/{USER}/repos?per_page=100&page={page}&type=owner&sort=updated')
        repos.extend(batch)
        if len(batch)<100: break
        page+=1
        if page>30: raise RuntimeError('Too many repository pages: refusing partial stats')
    # Count owned public repositories only; no private repo data claimed.
    owned=[r for r in repos if not r.get('fork')]
    stars=sum(r.get('stargazers_count',0) for r in owned)
    forks=sum(r.get('forks_count',0) for r in owned)
    langs=Counter()
    for r in owned:
        # Per-repo language byte sizes (not lines of code or overall commits).
        try:
            for name,bytes_count in api('/repos/'+r['full_name']+'/languages').items():
                langs[name]+=bytes_count
        except urllib.error.HTTPError as e:
            raise RuntimeError(f'Languages API failed for {r["full_name"]}: {e}')
    counts=[('PUBLIC REPOS',str(profile.get('public_repos',0))),('TOTAL STARS',str(stars)),('REPO FORKS',str(forks)),('FOLLOWERS',str(profile.get('followers',0)))]
    header=text(28,44,'Arfan Ahmed · GitHub Overview',23)+text(28,70,'Automatically generated from public GitHub data',12,'#8b949e',400)
    items=''
    for i,(label,value) in enumerate(counts):
        x=28+(i%2)*251; y=96+(i//2)*91
        items+=f'<rect x="{x}" y="{y}" width="231" height="76" rx="9" fill="#161b22" stroke="#30363d"/>'
        items+=text(x+15,y+24,label,11,'#8b949e',500)+text(x+15,y+58,value,27,'#58a6ff',700)
    write_if_changed(OUT/'overview.svg',frame(538,300,header+items+text(28,286,'Source: public repositories · No live image server',11,'#8b949e',400)))
    total=sum(langs.values())
    ranked=langs.most_common(7)
    colors={'TypeScript':'#3178c6','JavaScript':'#f1e05a','HTML':'#e34c26','CSS':'#663399','Python':'#3572a5','PHP':'#4f5d95','Java':'#b07219','Jupyter Notebook':'#da5b0b','C++':'#f34b7d','Go':'#00add8','Shell':'#89e051'}
    palette=['#8b5cf6','#14b8a6','#ef4444','#fb923c','#a78bfa','#22c55e','#38bdf8']
    content=text(28,44,'Most Used Languages',23)+text(28,68,'Share of language bytes across non-fork public repos',12,'#8b949e',400)
    if total:
        x=28
        for i,(name,amount) in enumerate(ranked):
            width=482*amount/total
            if width>0: content+=f'<rect x="{x:.2f}" y="88" width="{width:.2f}" height="12" fill="{colors.get(name,palette[i])}"/>'
            x+=width
        for i,(name,amount) in enumerate(ranked):
            x=28+(i%2)*251; y=132+(i//2)*35
            color=colors.get(name,palette[i])
            content+=f'<circle cx="{x+6}" cy="{y-5}" r="5" fill="{color}"/>'+text(x+19,y,name[:20],13,'#c9d1d9',500)+text(x+205,y,f'{amount/total:.1%}',12,'#8b949e',500)
    else:
        content+=text(28,125,'No public repository language data available',14,'#8b949e',400)
    write_if_changed(OUT/'languages.svg',frame(538,290,content))
    print(f'Generated cards for {USER}: {len(owned)} non-fork public repos; {stars} stars; {len(langs)} languages')
except Exception as e:
    # Fail before overwriting existing artifacts so the previous working cards remain available.
    print('Failed to update stats; existing SVGs preserved:',e,file=sys.stderr)
    sys.exit(1)
