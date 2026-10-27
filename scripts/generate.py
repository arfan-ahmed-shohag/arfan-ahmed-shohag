#!/usr/bin/env python3
"""Generate polished self-hosted GitHub profile SVG cards from public GitHub REST data."""
import json, os, sys, urllib.request, urllib.error, html
from collections import Counter
from pathlib import Path

USER = os.getenv('STATS_USERNAME', 'arfan-ahmed-shohag')
TOKEN = os.getenv('GH_STATS_TOKEN') or os.getenv('GITHUB_TOKEN', '')
OUT = Path('assets'); OUT.mkdir(exist_ok=True)
HEADERS = {
    'Accept': 'application/vnd.github+json',
    'User-Agent': 'self-hosted-profile-stats',
    'X-GitHub-Api-Version': '2022-11-28'
}
if TOKEN:
    HEADERS['Authorization'] = 'Bearer ' + TOKEN


def api(path):
    req = urllib.request.Request('https://api.github.com' + path, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def esc(s):
    return html.escape(str(s), quote=True)


def write_if_changed(path, data):
    encoded = data.encode('utf-8')
    if not path.exists() or path.read_bytes() != encoded:
        path.write_bytes(encoded)


def svg_template(width, height, title, desc, body, accent='#8b5cf6'):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">
  <defs>
    <linearGradient id="borderGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#3b82f6" stop-opacity="0.85"/>
      <stop offset="50%" stop-color="{accent}" stop-opacity="0.8"/>
      <stop offset="100%" stop-color="#22d3ee" stop-opacity="0.8"/>
    </linearGradient>
    <linearGradient id="panelGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#101827"/>
      <stop offset="100%" stop-color="#0b1220"/>
    </linearGradient>
    <linearGradient id="chipGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#1d4ed8" stop-opacity="0.95"/>
      <stop offset="100%" stop-color="{accent}" stop-opacity="0.95"/>
    </linearGradient>
    <filter id="softShadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="10" stdDeviation="16" flood-color="#000000" flood-opacity="0.35"/>
    </filter>
    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="24" result="blur"/>
    </filter>
  </defs>

  <rect width="{width}" height="{height}" rx="24" fill="#070d18"/>
  <circle cx="{width - 90}" cy="58" r="46" fill="{accent}" opacity="0.22" filter="url(#glow)"/>
  <circle cx="80" cy="{height - 48}" r="40" fill="#2563eb" opacity="0.16" filter="url(#glow)"/>

  <rect x="1.25" y="1.25" width="{width - 2.5}" height="{height - 2.5}" rx="22.75" fill="url(#panelGrad)" stroke="url(#borderGrad)" stroke-opacity="0.38" stroke-width="1.5"/>
  <rect x="18" y="18" width="{width - 36}" height="{height - 36}" rx="20" fill="#0b1220" fill-opacity="0.84" stroke="#1e293b" stroke-opacity="0.8"/>

  <text x="30" y="48" fill="#f8fafc" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="16" font-weight="700">{esc(title)}</text>
  <text x="30" y="68" fill="#94a3b8" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="10.5" font-weight="500">{esc(desc)}</text>

  {body}
</svg>'''


def metric_card(x, y, w, h, label, value, suffix=''):
    return f'''
    <g>
      <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="#101a2c" stroke="#22314d"/>
      <rect x="{x+1}" y="{y+1}" width="{w-2}" height="{h-2}" rx="13" fill="none" stroke="#0f172a" opacity="0.7"/>
      <text x="{x+16}" y="{y+22}" fill="#8ea2c0" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="9.5" font-weight="700">{esc(label)}</text>
      <text x="{x+16}" y="{y+53}" fill="#f8fafc" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="24" font-weight="800">{esc(value)}<tspan fill="#93c5fd" font-size="12" font-weight="700">{esc(suffix)}</tspan></text>
    </g>'''


def generate_overview(profile, repos, stars, forks):
    name = profile.get('name') or USER
    followers = profile.get('followers', 0)
    public_repos = profile.get('public_repos', 0)
    created = (profile.get('created_at') or '')[:4]
    body = []
    body.append(f'<rect x="356" y="28" width="150" height="28" rx="14" fill="url(#chipGrad)" opacity="0.95"/><text x="431" y="46.5" text-anchor="middle" fill="#ffffff" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="11" font-weight="700">@{esc(USER)}</text>')
    body.append(metric_card(30, 92, 228, 78, 'PUBLIC REPOSITORIES', public_repos))
    body.append(metric_card(280, 92, 228, 78, 'TOTAL STARS', stars))
    body.append(metric_card(30, 186, 228, 78, 'REPOSITORY FORKS', forks))
    body.append(metric_card(280, 186, 228, 78, 'FOLLOWERS', followers))
    body.append(f'''
      <g>
        <text x="32" y="291" fill="#64748b" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="10">Built from public GitHub API data · Reliable self-hosted card</text>
        <text x="508" y="291" text-anchor="end" fill="#93c5fd" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="10.5" font-weight="700">Since {esc(created or 'GitHub')}</text>
      </g>
    ''')
    return svg_template(
        540,
        310,
        f'{name} · GitHub Overview',
        'A polished snapshot of your public GitHub profile metrics',
        ''.join(body),
        accent='#8b5cf6'
    )


def generate_languages(profile, langs):
    name = profile.get('name') or USER
    total = sum(langs.values())
    ranked = langs.most_common(6)
    colors = {
        'TypeScript': '#3178c6', 'JavaScript': '#f1e05a', 'HTML': '#e34c26',
        'CSS': '#663399', 'Python': '#3572A5', 'PHP': '#4F5D95',
        'Java': '#b07219', 'Jupyter Notebook': '#DA5B0B', 'C++': '#f34b7d',
        'Go': '#00ADD8', 'Shell': '#89e051', 'C': '#555555', 'C#': '#178600'
    }
    palette = ['#8b5cf6', '#22c55e', '#f97316', '#38bdf8', '#e879f9', '#f43f5e']
    body = []
    body.append(f'<rect x="383" y="28" width="123" height="28" rx="14" fill="url(#chipGrad)" opacity="0.95"/><text x="444.5" y="46.5" text-anchor="middle" fill="#ffffff" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="11" font-weight="700">Top {len(ranked)} Languages</text>')
    body.append('<rect x="30" y="92" width="478" height="16" rx="8" fill="#0f172a" stroke="#22314d"/>')
    if total:
        cursor = 31
        for i, (lang, amount) in enumerate(ranked):
            seg = max(6, round(476 * amount / total, 2))
            color = colors.get(lang, palette[i % len(palette)])
            body.append(f'<rect x="{cursor}" y="93" width="{seg}" height="14" rx="7" fill="{color}"/>')
            cursor += seg
        start_y = 148
        row_gap = 34
        for i, (lang, amount) in enumerate(ranked):
            col = i % 2
            row = i // 2
            x = 34 + col * 234
            y = start_y + row * row_gap
            pct = amount / total * 100
            color = colors.get(lang, palette[i % len(palette)])
            body.append(f'''
            <g>
              <circle cx="{x}" cy="{y - 4}" r="5" fill="{color}"/>
              <text x="{x + 14}" y="{y}" fill="#e2e8f0" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="12" font-weight="700">{esc(lang)}</text>
              <text x="{x + 184}" y="{y}" text-anchor="end" fill="#93a4bd" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="11.5" font-weight="600">{pct:.1f}%</text>
            </g>''')
        body.append(f'<text x="30" y="286" fill="#64748b" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="10">Calculated from non-fork public repositories · Byte share across detected languages</text>')
    else:
        body.append('<text x="30" y="140" fill="#94a3b8" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="13">No public repository language data available right now.</text>')
    return svg_template(
        540,
        310,
        'Most Used Languages',
        f"An elegant breakdown of {esc(name)}'s public repository language usage",
        ''.join(body),
        accent='#0ea5e9'
    )


try:
    profile = api('/users/' + USER)
    repos = []
    page = 1
    while True:
        batch = api(f'/users/{USER}/repos?per_page=100&page={page}&type=owner&sort=updated')
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
        if page > 30:
            raise RuntimeError('Too many repository pages: refusing partial stats')

    owned = [r for r in repos if not r.get('fork')]
    stars = sum(r.get('stargazers_count', 0) for r in owned)
    forks = sum(r.get('forks_count', 0) for r in owned)

    langs = Counter()
    for r in owned:
        try:
            for name, bytes_count in api('/repos/' + r['full_name'] + '/languages').items():
                langs[name] += bytes_count
        except urllib.error.HTTPError as e:
            raise RuntimeError(f'Languages API failed for {r["full_name"]}: {e}')

    write_if_changed(OUT / 'overview.svg', generate_overview(profile, owned, stars, forks))
    write_if_changed(OUT / 'languages.svg', generate_languages(profile, langs))
    print(f'Generated polished cards for {USER}: {len(owned)} non-fork public repos; {stars} stars; {len(langs)} languages')
except Exception as e:
    print('Failed to update stats; existing SVGs preserved:', e, file=sys.stderr)
    sys.exit(1)
