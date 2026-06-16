import sys
import os
import json
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import plotly.graph_objects as go

sys.stdout.reconfigure(encoding="utf-8")

API_KEY     = os.getenv("TAC_API_KEY", "")
BASE_URL    = "https://api.taceconomics.io/"
DATASET     = "INFORM"
CACHE_FILE  = "inform_cache.json"
OUTPUT      = "inform_dashboard_2026.html"
MAX_WORKERS = 20

SESSION = requests.Session()
SESSION.headers.update({"Authorization": f"Bearer {API_KEY}"})

C_DARK   = "#1a1f4e"
C_MID    = "#2d3a8c"
C_ACCENT = "#00c2cb"
C_ORANGE = "#f4872b"
C_RED    = "#d64040"
C_GREY   = "#8892b0"
FONT     = "Poppins"

# 190 countries covered by INFORM 2026 (ISO 3166-1 alpha-3)
COUNTRIES = [
    "AFG", "ALB", "DZA", "AGO", "ATG", "ARG", "ARM", "AUS", "AUT", "AZE",
    "BHS", "BHR", "BGD", "BRB", "BLR", "BEL", "BLZ", "BEN", "BTN", "BOL", "BIH",
    "BWA", "BRA", "BRN", "BGR", "BFA", "BDI", "CPV", "KHM", "CMR", "CAN", "CAF",
    "TCD", "CHL", "CHN", "COL", "COM", "COD", "COG", "CRI", "CIV", "HRV", "CUB",
    "CYP", "CZE", "DNK", "DJI", "DMA", "DOM", "ECU", "EGY", "SLV", "GNQ", "ERI", "EST",
    "SWZ", "ETH", "FJI", "FIN", "FRA", "GAB", "GMB", "GEO", "DEU", "GHA", "GRC",
    "GRD", "GTM", "GIN", "GNB", "GUY", "HTI", "HND", "HUN", "ISL", "IND", "IDN", "IRN",
    "IRQ", "IRL", "ISR", "ITA", "JAM", "JPN", "JOR", "KAZ", "KEN", "KIR", "PRK", "KOR",
    "KWT", "KGZ", "LAO", "LVA", "LBN", "LSO", "LBR", "LBY", "LCA", "LIE", "LTU", "LUX",
    "MDG", "MWI", "MYS", "MDV", "MHL", "FSM", "MLI", "MLT", "MRT", "MUS", "MEX", "MDA", "MNG",
    "MNE", "MAR", "MOZ", "MMR", "NAM", "NPL", "NLD", "NZL", "NIC", "NER", "NGA", "NRU",
    "MKD", "NOR", "OMN", "PAK", "PAN", "PNG", "PRY", "PER", "PHL", "PLW", "POL", "PRT",
    "PSE", "QAT", "ROU", "RUS", "RWA", "WSM", "SAU", "SEN", "SRB", "SLE", "SGP", "SVK",
    "SVN", "SLB", "SOM", "ZAF", "SSD", "ESP", "LKA", "SDN", "SUR", "SWE", "SYC", "CHE",
    "SYR", "STP", "TJK", "TZA", "THA", "TLS", "TGO", "TON", "TTO", "TUN", "TUR", "TUV",
    "TKM", "UGA", "UKR", "ARE", "GBR", "USA", "URY", "UZB", "VCT", "VUT", "VEN", "VNM",
    "YEM", "ZMB", "ZWE",
]

# Tab layout: each entry defines the main indicator and its sub-columns grouped by theme.
# "color" applies to both the group header and the first sub-column; "light" to detail columns.
TAB_COLS = {
    "inform": {
        "main":   ("inform", "INFORM Risk"),
        "groups": [
            {"label": "", "color": "#2d5080", "light": "#4a78ab", "cols": [
                ("ha", "Hazard & Exposure"),
                ("vu", "Vulnerability"),
                ("cc", "Coping Capacity"),
            ]},
        ],
    },
    "ha": {
        "main":   ("ha", "H&E Index"),
        "groups": [
            {"label": "Natural Hazards", "color": "#c0392b", "light": "#d9736b", "cols": [
                ("ha_nat",           "Natural"),
                ("ha_nat_eq",        "Earthquake"),
                ("ha_nat_fl",        "River Flood"),
                ("ha_nat_ts",        "Tsunami"),
                ("ha_nat_tc",        "Tropical Cyclone"),
                ("ha_nat_cfl",       "Coastal Flood"),
                ("ha_nat_dr",        "Drought"),
                ("ha_nat_epi",       "Epidemic"),
            ]},
            {"label": "Human Hazards", "color": "#7d3c98", "light": "#a465c0", "cols": [
                ("ha_hum",           "Human"),
                ("ha_hum_con_gcri",  "Proj. Conflict"),
                ("ha_hum_con_gpi",   "Curr. Conflict"),
            ]},
        ],
    },
    "vu": {
        "main":   ("vu", "Vulnerability"),
        "groups": [
            {"label": "Socio-Economic Vulnerability", "color": "#d35400", "light": "#e8813a", "cols": [
                ("vu_sev",     "Socio-Econ."),
                ("vu_sev_pd",  "Dev. & Deprivation"),
                ("vu_sev_inq", "Inequality"),
                ("vu_sev_ad",  "Econ. Dependency"),
            ]},
            {"label": "Vulnerable Groups", "color": "#b7950b", "light": "#d4b030", "cols": [
                ("vu_vgr",               "Vuln. Groups"),
                ("vu_vgr_up",            "Uprooted People"),
                ("vu_vgr_og_he",         "Health Conditions"),
                ("vu_vgr_og_u5",         "Children U5"),
                ("vu_vgr_og_natdis-rel", "Recent Shocks"),
                ("vu_vgr_og_fs",         "Food Security"),
                ("vu_vgr_og",            "Other Vuln. Groups"),
            ]},
        ],
    },
    "cc": {
        "main":   ("cc", "Coping Capacity"),
        "groups": [
            {"label": "Institutional", "color": "#1a5276", "light": "#3d7aaa", "cols": [
                ("cc_ins",     "Institutional"),
                ("cc_ins_drr", "DRR"),
                ("cc_ins_gov", "Governance"),
            ]},
            {"label": "Infrastructure", "color": "#1d6a5a", "light": "#3d9080", "cols": [
                ("cc_inf",     "Infrastructure"),
                ("cc_inf_com", "Communication"),
                ("cc_inf_phy", "Physical Infra."),
                ("cc_inf_ahc", "Health Access"),
            ]},
        ],
    },
}

# Six axes of the radar chart: two sub-components per INFORM dimension
RADAR_SUBS = [
    ("ha_nat", "Natural Hazards"),
    ("ha_hum", "Human Hazards"),
    ("vu_sev", "Socio-Econ. Vulnerability"),
    ("vu_vgr", "Vulnerable Groups"),
    ("cc_ins", "Institutional"),
    ("cc_inf", "Infrastructure"),
]

# Full component tree for the country detail panel.
# Leading spaces in labels drive the visual indent (2 spaces = sub1, 4 spaces = sub2).
DETAIL_ROWS = [
    ("INFORM Risk Index",        "inform",                "top"),
    ("Hazard & Exposure",        "ha",                    "top"),
    ("  Natural Hazards",        "ha_nat",                "sub1"),
    ("    Earthquake",           "ha_nat_eq",             "sub2"),
    ("    River Flood",          "ha_nat_fl",             "sub2"),
    ("    Tsunami",              "ha_nat_ts",             "sub2"),
    ("    Tropical Cyclone",     "ha_nat_tc",             "sub2"),
    ("    Coastal Flood",        "ha_nat_cfl",            "sub2"),
    ("    Drought",              "ha_nat_dr",             "sub2"),
    ("    Epidemic",             "ha_nat_epi",            "sub2"),
    ("  Human Hazards",          "ha_hum",                "sub1"),
    ("    Proj. Conflict Prob.", "ha_hum_con_gcri",       "sub2"),
    ("    Curr. Conflict Int.",  "ha_hum_con_gpi",        "sub2"),
    ("Vulnerability",            "vu",                    "top"),
    ("  Socio-Econ. Vuln.",      "vu_sev",                "sub1"),
    ("    Dev. & Deprivation",   "vu_sev_pd",             "sub2"),
    ("    Inequality",           "vu_sev_inq",            "sub2"),
    ("    Econ. Dependency",     "vu_sev_ad",             "sub2"),
    ("  Vulnerable Groups",      "vu_vgr",                "sub1"),
    ("    Uprooted People",      "vu_vgr_up",             "sub2"),
    ("    Other Vuln. Groups",   "vu_vgr_og",             "sub2"),
    ("    Health Conditions",    "vu_vgr_og_he",          "sub2"),
    ("    Children U5",          "vu_vgr_og_u5",          "sub2"),
    ("    Recent Shocks",        "vu_vgr_og_natdis-rel",  "sub2"),
    ("    Food Security",        "vu_vgr_og_fs",          "sub2"),
    ("Lack of Coping Capacity",  "cc",                    "top"),
    ("  Institutional",          "cc_ins",                "sub1"),
    ("    DRR",                  "cc_ins_drr",            "sub2"),
    ("    Governance",           "cc_ins_gov",            "sub2"),
    ("  Infrastructure",         "cc_inf",                "sub1"),
    ("    Communication",        "cc_inf_com",            "sub2"),
    ("    Physical Infra.",      "cc_inf_phy",            "sub2"),
    ("    Health Access",        "cc_inf_ahc",            "sub2"),
]

# Collect all symbols referenced across tabs, detail rows and radar — deduplicated and ordered.
_syms = (
    ["inform", "ha", "vu", "cc"]
    + [s for tab in TAB_COLS.values() for g in tab["groups"] for s, _ in g["cols"]]
    + [s for _, s, _ in DETAIL_ROWS]
    + [s for s, _ in RADAR_SUBS]
)
ALL_SYMS   = list(dict.fromkeys(_syms))
ALL_SERIES = [(sym, geo) for geo in COUNTRIES for sym in ALL_SYMS]

COUNTRY_NAMES = {
    "AFG": "Afghanistan",       "ALB": "Albania",           "DZA": "Algeria",
    "AGO": "Angola",            "ATG": "Antigua & Barbuda", "ARG": "Argentina",
    "ARM": "Armenia",           "AUS": "Australia",         "AUT": "Austria",
    "AZE": "Azerbaijan",        "BHS": "Bahamas",           "BHR": "Bahrain",
    "BGD": "Bangladesh",        "BRB": "Barbados",          "BLR": "Belarus",
    "BEL": "Belgium",           "BLZ": "Belize",            "BEN": "Benin",
    "BTN": "Bhutan",            "BOL": "Bolivia",           "BIH": "Bosnia & Herz.",
    "BWA": "Botswana",          "BRA": "Brazil",            "BRN": "Brunei",
    "BGR": "Bulgaria",          "BFA": "Burkina Faso",      "BDI": "Burundi",
    "KHM": "Cambodia",          "CMR": "Cameroon",          "CAN": "Canada",
    "CAF": "C. African Rep.",   "TCD": "Chad",              "CHL": "Chile",
    "CHN": "China",             "COL": "Colombia",          "COM": "Comoros",
    "COD": "DR Congo",          "COG": "Congo",             "CRI": "Costa Rica",
    "CIV": "Cote d'Ivoire",     "HRV": "Croatia",           "CUB": "Cuba",
    "CYP": "Cyprus",            "CZE": "Czech Republic",    "DNK": "Denmark",
    "DJI": "Djibouti",          "DMA": "Dominica",          "DOM": "Dominican Rep.",
    "ECU": "Ecuador",           "EGY": "Egypt",             "SLV": "El Salvador",
    "GNQ": "Equatorial Guinea", "ERI": "Eritrea",           "EST": "Estonia",
    "SWZ": "Eswatini",          "ETH": "Ethiopia",          "FJI": "Fiji",
    "FIN": "Finland",           "FRA": "France",            "GAB": "Gabon",
    "GMB": "Gambia",            "GEO": "Georgia",           "DEU": "Germany",
    "GHA": "Ghana",             "GRC": "Greece",            "GRD": "Grenada",
    "GTM": "Guatemala",         "GIN": "Guinea",            "GNB": "Guinea-Bissau",
    "GUY": "Guyana",            "HTI": "Haiti",             "HND": "Honduras",
    "HUN": "Hungary",           "ISL": "Iceland",           "IND": "India",
    "IDN": "Indonesia",         "IRN": "Iran",              "IRQ": "Iraq",
    "IRL": "Ireland",           "ISR": "Israel",            "ITA": "Italy",
    "JAM": "Jamaica",           "JPN": "Japan",             "JOR": "Jordan",
    "KAZ": "Kazakhstan",        "KEN": "Kenya",             "KIR": "Kiribati",
    "PRK": "North Korea",       "KOR": "South Korea",       "KWT": "Kuwait",
    "KGZ": "Kyrgyzstan",        "LAO": "Laos",              "LVA": "Latvia",
    "LBN": "Lebanon",           "LSO": "Lesotho",           "LBR": "Liberia",
    "LBY": "Libya",             "LIE": "Liechtenstein",     "LTU": "Lithuania",
    "LUX": "Luxembourg",        "LCA": "Saint Lucia",       "MDG": "Madagascar",
    "MWI": "Malawi",            "MYS": "Malaysia",          "MDV": "Maldives",
    "MHL": "Marshall Islands",  "MLI": "Mali",              "MLT": "Malta",
    "MRT": "Mauritania",        "MUS": "Mauritius",         "MEX": "Mexico",
    "FSM": "Micronesia",        "MDA": "Moldova",           "MNG": "Mongolia",
    "MNE": "Montenegro",        "MAR": "Morocco",           "MOZ": "Mozambique",
    "MMR": "Myanmar",           "NAM": "Namibia",           "NPL": "Nepal",
    "NLD": "Netherlands",       "NZL": "New Zealand",       "NIC": "Nicaragua",
    "NER": "Niger",             "NGA": "Nigeria",           "NRU": "Nauru",
    "MKD": "North Macedonia",   "NOR": "Norway",            "OMN": "Oman",
    "PAK": "Pakistan",          "PAN": "Panama",            "PNG": "Papua New Guinea",
    "PRY": "Paraguay",          "PER": "Peru",              "PHL": "Philippines",
    "PLW": "Palau",             "POL": "Poland",            "PRT": "Portugal",
    "PSE": "Palestine",         "QAT": "Qatar",             "ROU": "Romania",
    "RUS": "Russia",            "RWA": "Rwanda",            "WSM": "Samoa",
    "SAU": "Saudi Arabia",      "SEN": "Senegal",           "SRB": "Serbia",
    "SLE": "Sierra Leone",      "SGP": "Singapore",         "SLB": "Solomon Islands",
    "SOM": "Somalia",           "ZAF": "South Africa",      "SSD": "South Sudan",
    "ESP": "Spain",             "LKA": "Sri Lanka",         "SDN": "Sudan",
    "SUR": "Suriname",          "SWE": "Sweden",            "SYC": "Seychelles",
    "CHE": "Switzerland",       "SYR": "Syria",             "STP": "Sao Tome & Principe",
    "TJK": "Tajikistan",        "TZA": "Tanzania",          "THA": "Thailand",
    "TLS": "Timor-Leste",       "TGO": "Togo",              "TON": "Tonga",
    "TTO": "Trinidad & Tobago", "TUN": "Tunisia",           "TUR": "Turkey",
    "TKM": "Turkmenistan",      "TUV": "Tuvalu",            "UGA": "Uganda",
    "UKR": "Ukraine",           "ARE": "United Arab Emirates",
    "GBR": "United Kingdom",    "USA": "United States",     "URY": "Uruguay",
    "UZB": "Uzbekistan",        "VCT": "St. Vincent & Gren.",
    "VUT": "Vanuatu",           "VEN": "Venezuela",         "VNM": "Vietnam",
    "YEM": "Yemen",             "ZMB": "Zambia",            "ZWE": "Zimbabwe",
}


def cname(iso):
    return COUNTRY_NAMES.get(iso, iso)


def fetch_series(sym, geo):
    url = f"{BASE_URL}data/{DATASET}/{sym}/{geo}"
    try:
        r = SESSION.get(url, timeout=15)
        if r.status_code == 200:
            return (sym, geo), r.json().get("data", [])
    except Exception:
        pass
    return (sym, geo), []


def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f)


def fetch_all():
    cache = load_cache()
    missing = [(s, g) for s, g in ALL_SERIES if f"{s}/{g}" not in cache]
    print(f"Series in cache: {len(cache)}, to fetch: {len(missing)}")
    if missing:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = {ex.submit(fetch_series, s, g): (s, g) for s, g in missing}
            done = 0
            for fut in as_completed(futures):
                (sym, geo), data = fut.result()
                cache[f"{sym}/{geo}"] = data
                done += 1
                if done % 100 == 0:
                    print(f"  {done}/{len(missing)} fetched...")
        save_cache(cache)
        print("Cache updated.")
    return cache


def latest(cache, sym, geo):
    data = cache.get(f"{sym}/{geo}") or []
    valid = [(d["timestamp"], d["value"]) for d in data if d["value"] is not None]
    return sorted(valid)[-1][1] if valid else None


def get_all_latest(cache, sym):
    return {
        geo: v
        for geo in COUNTRIES
        for v in [latest(cache, sym, geo)]
        if v is not None
    }


# INFORM official thresholds: Very High ≥7, High ≥5.4, Medium ≥3.6, Low ≥2.4, Very Low <2.4
def risk_label(v):
    if v is None: return "N/A"
    if v >= 7:    return "Very High"
    if v >= 5.4:  return "High"
    if v >= 3.6:  return "Medium"
    if v >= 2.4:  return "Low"
    return "Very Low"


def risk_color(v):
    if v is None: return C_GREY
    if v >= 7:    return "#d64040"
    if v >= 5.4:  return "#f4872b"
    if v >= 3.6:  return "#f9c74f"
    if v >= 2.4:  return "#90be6d"
    return "#43aa8b"


def fig_to_div(fig):
    return fig.to_html(full_html=False, include_plotlyjs=False,
                       config={"displayModeBar": False, "responsive": True})


def compute_kpis(d):
    if not d:
        return 0, 0, "N/D", "N/D", "N/D"
    n_high  = sum(1 for v in d.values() if v >= 5.4)
    n_vhigh = sum(1 for v in d.values() if v >= 7)
    top_iso = max(d, key=d.get)
    return n_high, n_vhigh, top_iso, f"{d[top_iso]:.2f}", f"{sum(d.values()) / len(d):.2f}"


# Stepped colorscale matching INFORM thresholds (score 0–10 mapped to 0–1)
COLORSCALE = [
    [0.0,   "#43aa8b"], [0.239, "#43aa8b"],
    [0.24,  "#90be6d"], [0.359, "#90be6d"],
    [0.36,  "#f9c74f"], [0.539, "#f9c74f"],
    [0.54,  "#f4872b"], [0.699, "#f4872b"],
    [0.70,  "#d64040"], [1.0,   "#d64040"],
]


def make_choropleth(cache, sym, label):
    d = get_all_latest(cache, sym)
    if not d:
        return go.Figure()
    isos  = list(d.keys())
    vals  = [d[iso] for iso in isos]
    names = [cname(iso) for iso in isos]
    fig = go.Figure(go.Choropleth(
        locations=isos, z=vals, text=names,
        customdata=[[iso, v] for iso, v in zip(isos, vals)],
        hovertemplate="<b>%{text}</b><br>" + label + ": %{customdata[1]:.2f}<extra></extra>",
        colorscale=COLORSCALE, zmin=0, zmax=10,
        marker_line_color="white", marker_line_width=0.4,
        colorbar=dict(
            title=dict(text="Score (0-10)", font=dict(size=10, color=C_DARK, family=FONT)),
            thickness=12, len=0.6,
            tickfont=dict(size=9, color=C_DARK, family=FONT),
        ),
    ))
    fig.update_layout(
        geo=dict(
            showframe=False, showcoastlines=True, coastlinecolor="#cccccc",
            showland=True, landcolor="#f0f0f0",
            showocean=False, showlakes=False,
            resolution=50, projection_type="natural earth",
            bgcolor="rgba(0,0,0,0)",
            lataxis=dict(range=[-58, 85]),
            lonaxis=dict(range=[-180, 180]),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=5, b=5),
        height=340,
        font=dict(family=FONT),
    )
    return fig


def cell_bar(v, level=2):
    fs = ["14px", "12px", "11px"][level]
    fw = ["700",  "600",  "500"][level]
    if v is None:
        return f'<td class="rank-cell" style="text-align:center;color:#bbb;font-size:{fs}">—</td>'
    c   = risk_color(v)
    pct = min(v / 10 * 100, 100)
    return (
        f'<td class="rank-cell">'
        f'<span class="rank-val" style="font-size:{fs};font-weight:{fw}">{v:.1f}</span>'
        f'<div class="rank-bar-wrap">'
        f'<div class="rank-bar" style="width:{pct:.0f}%;background:{c}"></div>'
        f'</div></td>'
    )


def make_html_rank_table(cache, tab_id):
    cfg = TAB_COLS[tab_id]
    main_sym, main_lbl = cfg["main"]
    groups = cfg["groups"]
    has_groups = any(g["label"] for g in groups)

    all_syms_in_tab = [main_sym] + [s for g in groups for s, _ in g["cols"]]
    col_data = {s: get_all_latest(cache, s) for s in all_syms_in_tab}
    main_d   = col_data[main_sym]
    if not main_d:
        return "<p>No data available</p>"

    all_isos = sorted(main_d.keys(), key=lambda x: main_d[x], reverse=True)
    bg0 = "#1a1f4e"

    h = '<div style="overflow-x:auto"><table class="rank-table">\n<thead>\n'

    if has_groups:
        h += '<tr>'
        h += f'<th rowspan="2" class="col-hdr" style="min-width:24px;background:{bg0}">#</th>'
        h += f'<th rowspan="2" class="col-hdr left" style="min-width:100px;background:{bg0}">Country</th>'
        h += f'<th rowspan="2" class="col-hdr" style="min-width:50px;background:{bg0}">{main_lbl}</th>'
        h += f'<th rowspan="2" class="col-hdr" style="min-width:54px;background:{bg0}">Level</th>'
        for g in groups:
            h += (f'<th colspan="{len(g["cols"])}" class="group-hdr" '
                  f'style="background:{g["color"]};color:white">{g["label"]}</th>')
        h += '</tr>\n<tr>'
        for g in groups:
            for i, (_, lbl) in enumerate(g["cols"]):
                bg = g["color"] if i == 0 else g["light"]
                h += f'<th class="col-hdr" style="min-width:38px;font-size:9px;background:{bg}">{lbl}</th>'
        h += '</tr>\n'
    else:
        g0 = groups[0]
        h += '<tr>'
        h += f'<th class="col-hdr" style="min-width:24px;background:{bg0}">#</th>'
        h += f'<th class="col-hdr left" style="min-width:100px;background:{bg0}">Country</th>'
        h += f'<th class="col-hdr" style="min-width:70px;background:{bg0}">{main_lbl}</th>'
        h += f'<th class="col-hdr" style="min-width:54px;background:{bg0}">Level</th>'
        for _, lbl in g0["cols"]:
            h += f'<th class="col-hdr" style="min-width:70px;background:{g0["color"]}">{lbl}</th>'
        h += '</tr>\n'

    h += '</thead>\n<tbody>\n'
    for i, iso in enumerate(all_isos):
        v   = main_d.get(iso)
        lc  = risk_color(v)
        tc  = "white" if v and v >= 5.4 else C_DARK
        lbl = risk_label(v)
        h += f'<tr class="rank-row" onclick="goToCountry(\'{iso}\')">'
        h += f'<td style="text-align:center;color:{C_GREY};font-size:10px;padding:2px 4px">{i + 1}</td>'
        h += f'<td style="font-weight:500;padding:3px 8px;font-size:11px;white-space:nowrap">{cname(iso)}</td>'
        h += cell_bar(v, level=0)
        h += (f'<td style="text-align:center;padding:3px 6px">'
              f'<span style="background:{lc};color:{tc};padding:2px 8px;border-radius:4px;'
              f'font-size:9px;font-weight:600;white-space:nowrap">{lbl}</span></td>')
        for g in groups:
            for j, (s, _) in enumerate(g["cols"]):
                h += cell_bar(col_data[s].get(iso), level=1 if j == 0 else 2)
        h += '</tr>\n'

    h += '</tbody>\n</table></div>'
    return h


def make_radar(cache, iso, world_avgs):
    syms = [s for s, _ in RADAR_SUBS]
    cats = [l for _, l in RADAR_SUBS]
    vals = [latest(cache, s, iso) or 0 for s in syms]
    avgs = [world_avgs[s] for s in syms]
    fig  = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=vals + [vals[0]], theta=cats + [cats[0]],
        fill="toself", name=cname(iso),
        line_color=C_MID, fillcolor="rgba(45,58,140,0.20)",
    ))
    fig.add_trace(go.Scatterpolar(
        r=avgs + [avgs[0]], theta=cats + [cats[0]],
        fill="toself", name="World average",
        line_color=C_GREY, line_dash="dot",
        fillcolor="rgba(136,146,176,0.10)",
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 10],
                            tickfont=dict(size=9, family=FONT), gridcolor="#d0d0d0"),
            angularaxis=dict(tickfont=dict(size=10, color=C_DARK, family=FONT),
                             gridcolor="#d0d0d0", linecolor="#d0d0d0"),
            bgcolor="rgba(0,0,0,0)",
        ),
        legend=dict(font=dict(size=10, family=FONT), orientation="h", y=-0.15),
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=40, t=20, b=60), height=380,
        font=dict(family=FONT),
    )
    return fig


def make_country_detail_table(cache, iso):
    h  = '<table class="detail-table">'
    h += ('<thead><tr>'
          '<th style="text-align:left;padding:4px 10px">Component</th>'
          '<th style="text-align:center;padding:4px 10px">Score</th>'
          '<th style="text-align:center;padding:4px 10px">Level</th>'
          '</tr></thead><tbody>')
    for label, sym, lvl in DETAIL_ROWS:
        v      = latest(cache, sym, iso)
        vs     = f"{v:.2f}" if v is not None else "N/D"
        rc     = risk_color(v)
        tc     = "white" if v and v >= 5.4 else C_DARK
        indent = label.count("  ") * 12
        clean  = label.strip()
        if lvl == "top":
            row_bg   = C_DARK
            name_sty = f"color:white;font-weight:700;font-size:12px;padding-left:{8 + indent}px"
            val_sty  = "color:white;font-weight:700;font-size:13px"
        elif lvl == "sub1":
            row_bg   = "#e8eaf6"
            name_sty = f"color:{C_DARK};font-weight:600;font-size:11px;padding-left:{8 + indent}px"
            val_sty  = f"color:{C_DARK};font-weight:600;font-size:12px"
        else:
            row_bg   = "#f8f9fc"
            name_sty = f"color:{C_DARK};font-weight:400;font-size:10px;padding-left:{8 + indent}px"
            val_sty  = f"color:{C_DARK};font-weight:500;font-size:11px"
        h += (f'<tr style="background:{row_bg};border-bottom:1px solid #dde">'
              f'<td style="{name_sty};padding-top:2px;padding-bottom:2px">{clean}</td>'
              f'<td style="text-align:center;padding:2px 8px">'
              f'<span style="{val_sty}">{vs}</span></td>'
              f'<td style="text-align:center;padding:2px 5px">'
              f'<span style="background:{rc};color:{tc};padding:1px 6px;border-radius:4px;'
              f'font-size:9px;font-weight:600;white-space:nowrap">{risk_label(v)}</span></td>'
              f'</tr>')
    h += '</tbody></table>'
    return h


def build_subtab_html(cache, tab_id, is_active=False):
    cfg = TAB_COLS[tab_id]
    main_sym, main_label = cfg["main"]
    d = get_all_latest(cache, main_sym)
    n_high, n_vhigh, top_iso, top_val, avg_val = compute_kpis(d)

    div_map   = fig_to_div(make_choropleth(cache, main_sym, main_label))
    div_table = make_html_rank_table(cache, tab_id)

    active_cls = " active" if is_active else ""
    h  = f'<div id="subtab-{tab_id}" class="subtab-content{active_cls}">\n'

    h += '<div class="kpi-row">'
    h += (f'<div class="kpi-card red"><div class="kpi-val">{n_vhigh}</div>'
          f'<div class="kpi-lbl">Countries at Very High risk<br>({main_label} &ge; 7)</div></div>')
    h += (f'<div class="kpi-card orange"><div class="kpi-val">{n_high}</div>'
          f'<div class="kpi-lbl">Countries at High or Very High risk<br>({main_label} &ge; 5.4)</div></div>')
    h += (f'<div class="kpi-card cyan"><div class="kpi-val">{cname(top_iso)}</div>'
          f'<div class="kpi-lbl">Highest score<br>({top_iso} &mdash; {top_val} / 10)</div></div>')
    h += (f'<div class="kpi-card"><div class="kpi-val">{avg_val}</div>'
          f'<div class="kpi-lbl">{main_label}<br>world average (0-10)</div></div>')
    h += '</div>\n'

    h += '<div class="legend-row">'
    for col, lbl in [
        ("#43aa8b", "Very Low (&lt;2.4)"),
        ("#90be6d", "Low (2.4-3.6)"),
        ("#f9c74f", "Medium (3.6-5.4)"),
        ("#f4872b", "High (5.4-7)"),
        ("#d64040", "Very High (&ge;7)"),
    ]:
        h += f'<div class="legend-item"><div class="legend-dot" style="background:{col}"></div>{lbl}</div>'
    h += ('<div class="legend-item" style="margin-left:auto;color:#8892b0;font-size:10px">'
          'Source: TAC ECONOMICS DataLab &mdash; INFORM 2026</div>')
    h += '</div>\n'

    h += f'<div class="card"><div class="card-title">{main_label} &mdash; World Map 2026</div>'
    h += div_map + '</div>\n'

    h += '<div class="section-title">World Ranking</div>'
    h += '<div class="card">' + div_table + '</div>\n'
    h += '</div>\n'
    return h


def build_html(cache):
    print("Building charts...")

    countries_with_data = [iso for iso in COUNTRIES if latest(cache, "inform", iso) is not None]
    print(f"  Countries with data: {len(countries_with_data)}")

    world_avgs = {}
    for s, _ in RADAR_SUBS:
        d = get_all_latest(cache, s)
        world_avgs[s] = sum(d.values()) / len(d) if d else 0

    print("  Rendering country charts...")
    radar_html  = ""
    detail_html = ""
    for iso in countries_with_data:
        r_div = fig_to_div(make_radar(cache, iso, world_avgs))
        d_div = make_country_detail_table(cache, iso)
        radar_html  += f'<div id="radar_{iso}" class="country-chart" style="display:none">{r_div}</div>\n'
        detail_html += f'<div id="detail_{iso}" class="country-chart" style="display:none">{d_div}</div>\n'

    country_options_html = "".join(
        f'<option value="{iso}">{cname(iso)} ({iso})</option>\n'
        for iso in sorted(countries_with_data, key=cname)
    )

    print("  Building subtabs...")
    subtabs_html = ""
    for i, tab_id in enumerate(["inform", "ha", "vu", "cc"]):
        subtabs_html += build_subtab_html(cache, tab_id, is_active=(i == 0))

    print("Building HTML...")

    css = """
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Poppins',Arial,sans-serif;background:#f5f6fa;color:#1a1f4e}
.header{background:#1a1f4e;padding:16px 32px;display:flex;align-items:center;
  justify-content:space-between;box-shadow:0 2px 12px rgba(0,0,0,0.22)}
.header-left{display:flex;flex-direction:column;gap:2px}
.header-main-title{color:white;font-size:20px;font-weight:700;letter-spacing:0.3px;line-height:1.2}
.header-subtitle{color:#a0aed0;font-size:12px;font-weight:400}
.header-right{text-align:right}
.header-source{color:#a0aed0;font-size:11px;line-height:1.6}
.tab-bar{background:#1a1f4e;display:flex;padding:0 32px}
.tab-btn{color:#a0aed0;background:none;border:none;padding:13px 24px;cursor:pointer;
  font-size:13px;font-weight:500;border-bottom:3px solid transparent;transition:all .2s;
  font-family:'Poppins',sans-serif}
.tab-btn:hover{color:white}
.tab-btn.active{color:#00c2cb;border-bottom-color:#00c2cb}
.tab-content{display:none;padding:24px 32px}
.tab-content.active{display:block}
.global-layout{display:flex;gap:20px;align-items:flex-start}
.global-sidebar{width:205px;flex-shrink:0;background:white;border-radius:8px;
  box-shadow:0 1px 6px rgba(0,0,0,0.07);padding:8px 0;position:sticky;top:16px}
.sidebar-label{font-size:10px;font-weight:700;color:#8892b0;text-transform:uppercase;
  letter-spacing:0.5px;padding:10px 18px 4px}
.sidebar-divider{height:1px;background:#e8eaf6;margin:6px 0}
.sidebar-btn{display:block;width:100%;text-align:left;padding:10px 18px;
  background:none;border:none;cursor:pointer;font-size:12px;font-weight:500;
  color:#8892b0;font-family:'Poppins',sans-serif;border-left:3px solid transparent;
  transition:all .2s;line-height:1.4}
.sidebar-btn:hover{color:#1a1f4e;background:#f0f2ff}
.sidebar-btn.active{color:#1a1f4e;background:#f0f2ff;border-left-color:#00c2cb;font-weight:600}
.global-main{flex:1;min-width:0}
.subtab-content{display:none}
.subtab-content.active{display:block}
.kpi-row{display:flex;gap:14px;margin-bottom:18px;flex-wrap:wrap}
.kpi-card{background:white;border-radius:8px;padding:14px 18px;flex:1;min-width:150px;
  box-shadow:0 1px 6px rgba(0,0,0,0.07);border-top:3px solid #2d3a8c}
.kpi-card.red{border-top-color:#d64040}
.kpi-card.orange{border-top-color:#f4872b}
.kpi-card.cyan{border-top-color:#00c2cb}
.kpi-val{font-size:22px;font-weight:700;color:#1a1f4e;line-height:1}
.kpi-lbl{font-size:10px;color:#8892b0;margin-top:5px;line-height:1.3}
.card{background:white;border-radius:8px;padding:18px;
  box-shadow:0 1px 6px rgba(0,0,0,0.07);margin-bottom:18px}
.card-title{font-size:13px;font-weight:600;color:#1a1f4e;margin-bottom:10px;
  padding-bottom:8px;border-bottom:2px solid #e8eaf6}
.section-title{font-size:13px;font-weight:700;color:#1a1f4e;margin:16px 0 8px 0;
  border-left:4px solid #00c2cb;padding-left:10px}
.legend-row{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px;align-items:center}
.legend-item{display:flex;align-items:center;gap:5px;font-size:10px;color:#555}
.legend-dot{width:11px;height:11px;border-radius:50%;flex-shrink:0}
.country-selector-wrap{background:white;border-radius:8px;padding:14px 18px;margin-bottom:18px;
  box-shadow:0 1px 6px rgba(0,0,0,0.07);display:flex;align-items:center;gap:14px}
.country-selector-wrap label{font-weight:600;font-size:13px;color:#1a1f4e;white-space:nowrap}
select#country-select{font-family:'Poppins',sans-serif;font-size:13px;padding:7px 12px;
  border:1px solid #d0d4e8;border-radius:6px;color:#1a1f4e;background:white;
  cursor:pointer;min-width:220px}
.country-name-display{font-size:18px;font-weight:700;color:#1a1f4e}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.source-note{font-size:10px;color:#8892b0;margin-top:5px}
.footer{background:#1a1f4e;color:#a0aed0;padding:16px 32px;font-size:11px;
  display:flex;justify-content:space-between;align-items:center;margin-top:28px}
.footer a{color:#00c2cb;text-decoration:none}
.rank-table{width:100%;border-collapse:collapse;font-family:'Poppins',sans-serif}
.rank-table thead th{padding:7px 5px;border:1px solid #2d3a8c;font-weight:600;
  font-size:9px;white-space:nowrap}
.rank-table th.col-hdr{background:#1a1f4e;color:white;text-align:center}
.rank-table th.col-hdr.left{text-align:left;padding-left:10px}
.rank-table th.group-hdr{text-align:center;font-size:10px;border:1px solid rgba(255,255,255,0.3)}
.rank-table tbody td{border-bottom:1px solid #f0f2ff;vertical-align:middle}
.rank-table tbody tr:nth-child(odd){background:#fafbff}
.rank-table tbody tr:nth-child(even){background:#ffffff}
.rank-row{cursor:pointer}
.rank-row:hover td{background:#dde8ff !important}
.rank-cell{text-align:center;padding:3px 5px;min-width:50px}
.rank-val{font-size:11px;font-weight:600;display:block;color:#1a1f4e}
.rank-bar-wrap{background:#e8eaf6;border-radius:2px;height:3px;margin-top:2px;min-width:36px}
.rank-bar{height:3px;border-radius:2px}
.radar-cat-legend{font-size:10px;padding:8px 4px 4px;display:flex;flex-wrap:wrap;
  align-items:center;gap:4px;border-top:1px solid #e8eaf6;margin-top:4px}
.radar-cat-items{color:#888;font-size:9px;margin-left:4px}
.detail-table{width:100%;border-collapse:collapse;font-family:'Poppins',sans-serif}
.detail-table thead th{background:#1a1f4e;color:white;font-size:10px;font-weight:600;
  border:1px solid #2d3a8c;white-space:nowrap}
.detail-table tbody tr:hover td{filter:brightness(0.95)}
@media(max-width:900px){.grid-2{grid-template-columns:1fr}.global-layout{flex-direction:column}
  .global-sidebar{width:100%;position:static}}
"""

    html  = '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
    html += '<meta charset="UTF-8">\n'
    html += '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
    html += '<title>INFORM Risk Index | TAC ECONOMICS DataLab</title>\n'
    html += '<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>\n'
    html += '<style>' + css + '</style>\n'
    html += '</head>\n<body>\n'

    html += '<div class="header">'
    html += ('<div class="header-left">'
             '<div class="header-main-title">INFORM Risk Index 2026</div>'
             '<div class="header-subtitle">DataLab &mdash; INFORM Risk Dataset &nbsp;|&nbsp; The Data Explorer &nbsp;|&nbsp; June 2026</div>'
             '</div>')
    html += ('<div class="header-right">'
             '<div class="header-source">Source: TAC ECONOMICS DataLab</div>'
             f'<div class="header-source">{len(countries_with_data)} countries &nbsp;|&nbsp; Scale 0 (low) to 10 (very high risk)</div>'
             '</div>')
    html += '</div>\n'

    html += '<div class="tab-bar">'
    html += '<button class="tab-btn active" onclick="showTab(\'global\',this)">World View</button>'
    html += '<button class="tab-btn" onclick="showTab(\'country\',this)">Country Focus</button>'
    html += '</div>\n'

    html += '<div id="tab-global" class="tab-content active">\n'
    html += '<div class="global-layout">\n'
    html += '<div class="global-sidebar">\n'
    html += '<div class="sidebar-label">Index</div>'
    html += '<button class="sidebar-btn active" onclick="showSubTab(\'inform\',this)">INFORM Risk Index</button>'
    html += '<div class="sidebar-divider"></div>'
    html += '<div class="sidebar-label">Dimensions</div>'
    html += '<button class="sidebar-btn" onclick="showSubTab(\'ha\',this)">Hazard &amp; Exposure</button>'
    html += '<button class="sidebar-btn" onclick="showSubTab(\'vu\',this)">Vulnerability</button>'
    html += '<button class="sidebar-btn" onclick="showSubTab(\'cc\',this)">Lack of Coping Capacity</button>'
    html += '</div>\n'
    html += '<div class="global-main">\n'
    html += subtabs_html
    html += '</div>\n</div>\n</div>\n'

    html += '<div id="tab-country" class="tab-content">\n'
    html += '<div class="country-selector-wrap">'
    html += '<label for="country-select">Select a country:</label>'
    html += f'<select id="country-select" onchange="updateCountry(this.value)">{country_options_html}</select>'
    html += '<div class="country-name-display" id="country-display">-</div>'
    html += '</div>\n'
    html += '<div class="grid-2">'
    html += '<div class="card"><div class="card-title">Risk Profile &mdash; 6 sub-components vs World Average</div>'
    html += f'<div id="radar-container">{radar_html}</div>'
    html += ('<div class="radar-cat-legend">'
             '<span style="color:#c0392b">&#9679;</span>&nbsp;'
             '<strong style="color:#c0392b">Hazard &amp; Exposure</strong>'
             '<span class="radar-cat-items">Natural Hazards &middot; Human Hazards</span>'
             '<span style="color:#d35400;margin-left:14px">&#9679;</span>&nbsp;'
             '<strong style="color:#d35400">Vulnerability</strong>'
             '<span class="radar-cat-items">Socio-Econ. &middot; Vulnerable Groups</span>'
             '<span style="color:#1a5276;margin-left:14px">&#9679;</span>&nbsp;'
             '<strong style="color:#1a5276">Coping Capacity</strong>'
             '<span class="radar-cat-items">Institutional &middot; Infrastructure</span>'
             '</div>')
    html += '</div>'
    html += f'<div class="card"><div class="card-title">Full Component Breakdown</div><div id="detail-container">{detail_html}</div></div>'
    html += '</div>\n'
    html += ('<div class="source-note" style="padding:0 0 14px 0">'
             'Source: TAC ECONOMICS DataLab &mdash; Dataset INFORM 2026 | '
             'Scale 0 (low risk) to 10 (very high risk)</div>\n')
    html += '</div>\n'

    html += '<div class="footer">'
    html += '<div>&copy; 2026 TAC ECONOMICS &mdash; <a href="https://app.taceconomics.com/datalab/data/INFORM" target="_blank">DataLab INFORM</a></div>'
    html += ('<div style="text-align:right">'
             '<a href="https://app.taceconomics.com/datalab/search" target="_blank">Web Platform</a>'
             ' &nbsp;|&nbsp; <a href="https://app.taceconomics.com/apidoc" target="_blank">API</a>'
             ' &nbsp;|&nbsp; <a href="https://app.taceconomics.com/download" target="_blank">Excel Add-in</a>'
             '</div>')
    html += '</div>\n'

    html += """<script>
function goToCountry(iso) {
  if (!document.getElementById("radar_" + iso)) return;
  document.querySelectorAll(".tab-content").forEach(el => el.classList.remove("active"));
  document.querySelectorAll(".tab-btn").forEach(el => el.classList.remove("active"));
  document.getElementById("tab-country").classList.add("active");
  document.querySelectorAll(".tab-btn").forEach(btn => {
    if (btn.textContent.trim() === "Country Focus") btn.classList.add("active");
  });
  updateCountry(iso);
  window.scrollTo({top: 0, behavior: "smooth"});
}

function showTab(name, btn) {
  document.querySelectorAll(".tab-content").forEach(el => el.classList.remove("active"));
  document.querySelectorAll(".tab-btn").forEach(el => el.classList.remove("active"));
  document.getElementById("tab-" + name).classList.add("active");
  if (btn) btn.classList.add("active");
  setTimeout(() => window.dispatchEvent(new Event("resize")), 100);
}

function showSubTab(name, btn) {
  document.querySelectorAll(".subtab-content").forEach(el => el.classList.remove("active"));
  document.querySelectorAll(".sidebar-btn").forEach(el => el.classList.remove("active"));
  document.getElementById("subtab-" + name).classList.add("active");
  if (btn) btn.classList.add("active");
  setTimeout(() => window.dispatchEvent(new Event("resize")), 100);
}

var currentCountry = null;
function updateCountry(iso) {
  if (currentCountry) {
    var pr = document.getElementById("radar_" + currentCountry);
    var pd = document.getElementById("detail_" + currentCountry);
    if (pr) pr.style.display = "none";
    if (pd) pd.style.display = "none";
  }
  currentCountry = iso;
  var r = document.getElementById("radar_" + iso);
  var d = document.getElementById("detail_" + iso);
  if (r) r.style.display = "block";
  if (d) d.style.display = "block";
  var sel = document.getElementById("country-select");
  for (var i = 0; i < sel.options.length; i++) {
    if (sel.options[i].value === iso) { sel.selectedIndex = i; break; }
  }
  document.getElementById("country-display").textContent =
    sel.options[sel.selectedIndex].text.split(" (")[0];
  setTimeout(() => window.dispatchEvent(new Event("resize")), 80);
}

window.addEventListener("DOMContentLoaded", function () {
  var sel = document.getElementById("country-select");
  if (sel && sel.options.length > 0) updateCountry(sel.options[0].value);
  document.querySelectorAll(".plotly-graph-div").forEach(function (mapDiv) {
    mapDiv.on("plotly_click", function (data) {
      if (data.points && data.points.length > 0) {
        var iso = data.points[0].customdata ? data.points[0].customdata[0] : null;
        if (iso && document.getElementById("radar_" + iso)) {
          showTab("country", document.querySelector(".tab-btn:nth-child(2)"));
          updateCountry(iso);
        }
      }
    });
  });
});
</script>
"""
    html += '</body>\n</html>\n'
    return html


if __name__ == "__main__":
    if not API_KEY:
        raise SystemExit("Set the TAC_API_KEY environment variable before running.")
    cache = fetch_all()
    html  = build_html(cache)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nDashboard generated: {OUTPUT}")
