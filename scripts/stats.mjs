// Draws the self-hosted GitHub stats cards in the portfolio theme (no dependencies).
// Runs in GitHub Actions with GH_STATS_TOKEN; locally it falls back to the `gh` CLI.
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const USER = process.env.STATS_USERNAME || "arfan-ahmed-shohag";
const TOKEN = process.env.GH_STATS_TOKEN || process.env.GITHUB_TOKEN || "";
const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, "..", "assets", "stats");

const C = { bg: "#070b0a", surface: "#0e1c1a", border: "#1f3a36", accent: "#7fe8cf", deep: "#1f6f64", fg: "#eaf5f2", muted: "#9db5b0" };
const SHADES = [C.accent, C.fg, "#4cc7ad", C.deep, "#a6f5df", C.muted];

/* ---------- data ---------- */
async function gql(query, variables = {}) {
  let body;
  if (TOKEN) {
    const res = await fetch("https://api.github.com/graphql", {
      method: "POST",
      headers: { Authorization: `Bearer ${TOKEN}`, "User-Agent": "profile-stats-cards" },
      body: JSON.stringify({ query, variables }),
    });
    if (!res.ok) throw new Error(`GitHub API ${res.status}`);
    body = await res.json();
  } else {
    body = JSON.parse(
      execFileSync("gh", ["api", "graphql", "--input", "-"], {
        input: JSON.stringify({ query, variables }),
        maxBuffer: 1 << 26,
      }).toString(),
    );
  }
  if (body.errors) throw new Error(body.errors.map((e) => e.message).join("; "));
  return body.data;
}

async function collect() {
  const { user, prs, issues } = await gql(
    `query($login:String!,$prs:String!,$issues:String!){
      user(login:$login){ followers{totalCount} contributionsCollection{contributionYears} }
      prs: search(query:$prs, type:ISSUE){issueCount}
      issues: search(query:$issues, type:ISSUE){issueCount}
    }`,
    { login: USER, prs: `author:${USER} type:pr is:public`, issues: `author:${USER} type:issue is:public` },
  );

  // public repositories only, so nothing about private code is ever published
  const repos = [];
  let after = null;
  let repoCount = 0;
  do {
    const page = (
      await gql(
        `query($login:String!,$after:String){ user(login:$login){
          repositories(first:100, after:$after, ownerAffiliations:OWNER, privacy:PUBLIC){
            totalCount pageInfo{hasNextPage endCursor}
            nodes{ isFork stargazerCount languages(first:20){edges{size node{name}}} } } } }`,
        { login: USER, after },
      )
    ).user.repositories;
    repos.push(...page.nodes);
    repoCount = page.totalCount;
    after = page.pageInfo.hasNextPage ? page.pageInfo.endCursor : null;
  } while (after);

  const days = new Map();
  const now = new Date();
  for (const year of user.contributionsCollection.contributionYears) {
    const to = year === now.getUTCFullYear() ? now.toISOString() : `${year}-12-31T23:59:59Z`;
    const data = await gql(
      `query($login:String!,$from:DateTime!,$to:DateTime!){ user(login:$login){
        contributionsCollection(from:$from,to:$to){ contributionCalendar{ weeks{ contributionDays{ date contributionCount } } } } } }`,
      { login: USER, from: `${year}-01-01T00:00:00Z`, to },
    );
    for (const week of data.user.contributionsCollection.contributionCalendar.weeks)
      for (const d of week.contributionDays) days.set(d.date, d.contributionCount);
  }
  const today = now.toISOString().slice(0, 10);
  const calendar = [...days].filter(([date]) => date <= today).sort(([a], [b]) => a.localeCompare(b));
  if (!calendar.length) throw new Error("empty contribution calendar");

  const owned = repos.filter((r) => !r.isFork);
  const langs = new Map();
  for (const r of owned)
    for (const e of r.languages.edges) langs.set(e.node.name, (langs.get(e.node.name) || 0) + e.size);

  return {
    calendar,
    followers: user.followers.totalCount,
    pullRequests: prs.issueCount,
    issues: issues.issueCount,
    repos: repoCount,
    stars: owned.reduce((n, r) => n + r.stargazerCount, 0),
    langs: [...langs].sort((a, b) => b[1] - a[1]),
  };
}

function streaks(calendar) {
  let longest = { length: 0 };
  let run = { length: 0 };
  for (const [date, count] of calendar) {
    run = count ? { length: run.length + 1, from: run.from || date, to: date } : { length: 0 };
    if (run.length > longest.length) longest = run;
  }
  // today may still be empty: the current streak then ends yesterday
  const list = calendar.at(-1)[1] ? calendar : calendar.slice(0, -1);
  let current = { length: 0 };
  for (let i = list.length - 1; i >= 0 && list[i][1]; i--)
    current = { length: current.length + 1, from: list[i][0], to: current.to || list[i][0] };
  return { current, longest };
}

/* ---------- drawing ---------- */
const font = (file) => readFileSync(join(HERE, "fonts", file)).toString("base64");
const FONTS =
  `@font-face{font-family:'SG';src:url(data:font/woff2;base64,${font("space-grotesk.woff2")}) format('woff2');font-weight:300 700}` +
  `@font-face{font-family:'IS';src:url(data:font/woff2;base64,${font("instrument-serif-italic.woff2")}) format('woff2');font-style:italic}`;

const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const num = (n) => n.toLocaleString("en-US");
const day = (iso, year = false) =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", ...(year && { year: "numeric" }), timeZone: "UTC" });
const text = (x, y, s, { size = 16, fill = C.fg, w = 400, anchor = "start" } = {}) =>
  `<text x="${x}" y="${y}" class="s" font-size="${size}" font-weight="${w}" fill="${fill}" text-anchor="${anchor}">${s}</text>`;
const title = (x, y, s) => `<text x="${x}" y="${y}" class="i" font-size="32" fill="${C.accent}">${s}</text>`;

function save(name, width, height, label, body, delay = 0) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(label)}">
<style>${FONTS}.s{font-family:'SG',system-ui,sans-serif}.i{font-family:'IS',Georgia,serif;font-style:italic}.glide{animation:glide 7s linear infinite;animation-delay:${delay}s}@keyframes glide{to{stroke-dashoffset:-100}}@media (prefers-reduced-motion:reduce){.glide{animation:none;opacity:0}}</style>
<defs><radialGradient id="glow"><stop offset="0" stop-color="${C.deep}" stop-opacity=".65"/><stop offset="1" stop-color="${C.deep}" stop-opacity="0"/></radialGradient>
<linearGradient id="card" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${C.surface}"/><stop offset="1" stop-color="${C.bg}"/></linearGradient>
<linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${C.accent}" stop-opacity=".4"/><stop offset="1" stop-color="${C.accent}" stop-opacity="0"/></linearGradient></defs>
<rect width="${width}" height="${height}" rx="20" fill="${C.bg}"/>
<rect x="1" y="1" width="${width - 2}" height="${height - 2}" rx="18" fill="url(#card)" stroke="${C.border}"/>
<ellipse cx="${width / 2}" cy="24" rx="${width * 0.36}" ry="24" fill="url(#glow)" opacity=".8"/>
<rect class="glide" x="1" y="1" width="${width - 2}" height="${height - 2}" rx="18" fill="none" stroke="${C.accent}" stroke-width="1.6" pathLength="100" stroke-dasharray="16 84"/>
${body}
</svg>
`;
  writeFileSync(join(OUT, name), svg);
}

function overview(d) {
  const total = d.calendar.reduce((n, [, c]) => n + c, 0);
  const lastYear = d.calendar.slice(-365).reduce((n, [, c]) => n + c, 0);
  const tiles = [
    ["Total contributions", total],
    ["Last 12 months", lastYear],
    ["Public repositories", d.repos],
    ["Pull requests", d.pullRequests],
    ["Stars earned", d.stars],
    ["Followers", d.followers],
  ];
  save("overview.svg", 592, 360, "Overall GitHub stats: " + tiles.map(([l, v]) => `${l} ${v}`).join(", "),
    `${title(30, 52, "Overall Stats")}${text(562, 48, `since ${d.calendar.find(([, c]) => c)?.[0].slice(0, 4) ?? ""}`, { size: 14, fill: C.muted, anchor: "end" })}
${tiles.map(([label, value], i) => {
      const x = 30 + (i % 2) * 272, y = 78 + Math.floor(i / 2) * 88;
      return `<rect x="${x}" y="${y}" width="260" height="76" rx="14" fill="${C.bg}" stroke="${C.border}"/>
${text(x + 18, y + 28, label, { size: 13.5, fill: C.muted })}${text(x + 18, y + 60, num(value), { size: 28, w: 600 })}`;
    }).join("\n")}`);
}

function streakCard(d) {
  const { current, longest } = streaks(d.calendar);
  const active = d.calendar.filter(([, c]) => c).length;
  const ring = longest.length ? Math.min(100, (current.length / longest.length) * 100) : 0;
  const range = (s) => (s.length ? `${day(s.from)} – ${day(s.to)}` : "start one today");
  const side = (y, label, value, note) =>
    `<rect x="314" y="${y}" width="248" height="122" rx="14" fill="${C.bg}" stroke="${C.border}"/>
${text(334, y + 32, label, { size: 13.5, fill: C.muted })}${text(334, y + 76, value, { size: 36, w: 600 })}${text(334, y + 102, note, { size: 13, fill: C.accent })}`;
  save("streak.svg", 592, 360, `Current streak ${current.length} days, longest streak ${longest.length} days, ${active} active days`,
    `${title(30, 52, "Streak")}
<circle cx="162" cy="192" r="92" fill="none" stroke="${C.border}" stroke-width="12"/>
${ring ? `<circle cx="162" cy="192" r="92" fill="none" stroke="${C.accent}" stroke-width="12" stroke-linecap="round" pathLength="100" stroke-dasharray="${ring.toFixed(1)} 100" transform="rotate(-90 162 192)"/>` : ""}
${text(162, 204, num(current.length), { size: 58, w: 600, anchor: "middle" })}${text(162, 232, current.length === 1 ? "day" : "days", { size: 14, fill: C.muted, anchor: "middle" })}
${text(162, 316, "Current streak", { size: 15, fill: C.accent, w: 600, anchor: "middle" })}${text(162, 337, range(current), { size: 13, fill: C.muted, anchor: "middle" })}
${side(78, "Longest streak", `${num(longest.length)} days`, longest.length ? `${day(longest.from, true)} – ${day(longest.to, true)}` : "")}
${side(214, "Active days", num(active), "days with a contribution")}`, -1.7);
}

function month(d) {
  const days = d.calendar.slice(-30);
  const total = days.reduce((n, [, c]) => n + c, 0);
  const best = days.reduce((a, b) => (b[1] > a[1] ? b : a));
  const active = days.filter(([, c]) => c).length;
  const left = 74, right = 1164, top = 122, bottom = 340;
  // round the top of the scale up to a multiple of 4 so the grid labels are whole numbers
  const max = Math.max(4, Math.ceil(best[1] / 4) * 4);
  const x = (i) => left + (i * (right - left)) / (days.length - 1);
  const y = (v) => bottom - (v / max) * (bottom - top);
  const line = days.map(([, c], i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(c).toFixed(1)}`).join("");
  const stat = (px, label, value) =>
    `<rect x="${px}" y="28" width="168" height="58" rx="12" fill="${C.bg}" stroke="${C.border}"/>
${text(px + 16, 50, label, { size: 12.5, fill: C.muted })}${text(px + 16, 74, value, { size: 19, w: 600 })}`;
  save("month.svg", 1200, 390, `Contributions in the last 30 days: ${total} in total, ${active} active days, best day ${best[1]}`,
    `${title(34, 56, "Last 30 Days")}${text(36, 82, `${day(days[0][0])} – ${day(days.at(-1)[0], true)}`, { size: 14, fill: C.muted })}
${stat(630, "Contributions", num(total))}${stat(814, "Active days", `${active} / ${days.length}`)}${stat(998, "Best day", best[1] ? `${best[1]} on ${day(best[0])}` : "–")}
${[0, 1, 2, 3, 4].map((k) => {
      const v = (max / 4) * k;
      return `<line x1="${left}" y1="${y(v)}" x2="${right}" y2="${y(v)}" stroke="${C.border}" stroke-dasharray="${k ? "3 6" : "0"}"/>${text(left - 14, y(v) + 4, v, { size: 12, fill: C.muted, anchor: "end" })}`;
    }).join("")}
<path d="${line}L${right} ${bottom}L${left} ${bottom}Z" fill="url(#area)"/>
<path d="${line}" fill="none" stroke="${C.accent}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
${days.map(([date, c], i) => `<circle cx="${x(i).toFixed(1)}" cy="${y(c).toFixed(1)}" r="4" fill="${C.bg}" stroke="${C.accent}" stroke-width="2"><title>${day(date)}: ${c}</title></circle>`).join("")}
${days.map(([date], i) => ((days.length - 1 - i) % 4 ? "" : text(x(i), 366, day(date), { size: 12, fill: C.muted, anchor: "middle" }))).join("")}`, -3.5);
}

function languages(d) {
  const sum = d.langs.reduce((n, [, s]) => n + s, 0);
  if (!sum) return;
  const top = d.langs.slice(0, 5).map(([name, size]) => [name, (size / sum) * 100]);
  const rest = 100 - top.reduce((n, [, p]) => n + p, 0);
  if (rest > 0.05) top.push(["Other", rest]);
  let at = 34;
  const bar = top.map(([, p], i) => {
    const w = (p / 100) * 1132;
    const r = `<rect x="${at.toFixed(1)}" y="86" width="${Math.max(0, w - 3).toFixed(1)}" height="16" fill="${SHADES[i]}"/>`;
    at += w;
    return r;
  });
  save("languages.svg", 1200, 180, "Most used languages: " + top.map(([n, p]) => `${n} ${p.toFixed(1)}%`).join(", "),
    `${title(34, 54, "Most Used Languages")}${text(1166, 50, "public repositories", { size: 14, fill: C.muted, anchor: "end" })}
<clipPath id="bar"><rect x="34" y="86" width="1132" height="16" rx="8"/></clipPath><g clip-path="url(#bar)">${bar.join("")}</g>
${top.map(([name, p], i) => {
      const px = 34 + i * 190;
      return `<circle cx="${px + 6}" cy="136" r="6" fill="${SHADES[i]}"/>${text(px + 20, 141, esc(name), { size: 15, w: 600 })}${text(px + 20, 162, `${p.toFixed(1)}%`, { size: 13, fill: C.muted })}`;
    }).join("\n")}`, -5);
}

// draw only after all data arrived, so a failed request keeps the previous cards
const data = await collect();
mkdirSync(OUT, { recursive: true });
overview(data);
streakCard(data);
month(data);
languages(data);
console.log(`Stats cards written for ${USER}: ${data.calendar.length} days, ${data.repos} public repositories`);
