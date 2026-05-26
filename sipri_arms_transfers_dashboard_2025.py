"""
SIPRI Arms Transfers Dashboard 2025
====================================
Generates a standalone interactive HTML dashboard from the
TAC ECONOMICS DataLab SIPRI dataset.

Data coverage: all bilateral arms transfer flows between
countries in the SIPRI Trade Register (ISO3 country list,
~10,000 supplier/recipient pairs tested).

Strategy:
  - Local JSON cache (sipri_cache.json) → instant on subsequent runs
  - Parallel API requests (20 threads) → ~8–10 min on first run
  - Single standalone HTML file, no server required

DEPENDENCIES
------------
    pip install plotly pandas requests

USAGE
-----
    python sipri_export_html.py
    → opens sipri_arms_transfers_dashboard_2025.html
"""

import os, json, time, requests
import concurrent.futures
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

API_KEY   = "MY_API_KEY"                   # ← your TAC ECONOMICS API key
BASE_URL  = "https://api.taceconomics.io/"
DATASET   = "SIPRI"
CACHE     = "sipri_cache.json"
OUTPUT    = "sipri_arms_transfers_dashboard_2025.html"
THREADS   = 20

# ─── Full ISO3 country list ───────────────────────────────────────────────────
ALL_COUNTRIES = {
    "Afghanistan":"AFG","Albania":"ALB","Algeria":"DZA","Angola":"AGO",
    "Argentina":"ARG","Armenia":"ARM","Australia":"AUS","Austria":"AUT",
    "Azerbaijan":"AZE","Bahrain":"BHR","Bangladesh":"BGD","Belarus":"BLR",
    "Belgium":"BEL","Bolivia":"BOL","Bosnia Herzegovina":"BIH","Brazil":"BRA",
    "Bulgaria":"BGR","Cambodia":"KHM","Cameroon":"CMR","Canada":"CAN",
    "Chile":"CHL","China":"CHN","Colombia":"COL","Congo":"COG",
    "Croatia":"HRV","Cuba":"CUB","Cyprus":"CYP","Czech Republic":"CZE",
    "Denmark":"DNK","Ecuador":"ECU","Egypt":"EGY","Estonia":"EST",
    "Ethiopia":"ETH","Finland":"FIN","France":"FRA","Georgia":"GEO",
    "Germany":"DEU","Ghana":"GHA","Greece":"GRC","Hungary":"HUN",
    "India":"IND","Indonesia":"IDN","Iran":"IRN","Iraq":"IRQ",
    "Ireland":"IRL","Israel":"ISR","Italy":"ITA","Japan":"JPN",
    "Jordan":"JOR","Kazakhstan":"KAZ","Kenya":"KEN","Kuwait":"KWT",
    "Kyrgyzstan":"KGZ","Latvia":"LVA","Lebanon":"LBN","Libya":"LBY",
    "Lithuania":"LTU","Malaysia":"MYS","Mexico":"MEX","Morocco":"MAR",
    "Mozambique":"MOZ","Myanmar":"MMR","Netherlands":"NLD",
    "New Zealand":"NZL","Nigeria":"NGA","North Korea":"PRK","Norway":"NOR",
    "Oman":"OMN","Pakistan":"PAK","Peru":"PER","Philippines":"PHL",
    "Poland":"POL","Portugal":"PRT","Qatar":"QAT","Romania":"ROU",
    "Russia":"RUS","Saudi Arabia":"SAU","Senegal":"SEN","Serbia":"SRB",
    "Singapore":"SGP","Slovakia":"SVK","South Africa":"ZAF",
    "South Korea":"KOR","Spain":"ESP","Sri Lanka":"LKA","Sudan":"SDN",
    "Sweden":"SWE","Switzerland":"CHE","Syria":"SYR","Taiwan":"TWN",
    "Tajikistan":"TJK","Thailand":"THA","Tunisia":"TUN","Turkey":"TUR",
    "Turkmenistan":"TKM","UAE":"ARE","Uganda":"UGA","Ukraine":"UKR",
    "United Kingdom":"GBR","United States":"USA","Uzbekistan":"UZB",
    "Venezuela":"VEN","Vietnam":"VNM","Yemen":"YEM","Zimbabwe":"ZWE",
    "Benin":"BEN",
    "Botswana":"BWA",
    "Brunei":"BRN",
    "Burkina Faso":"BFA",
    "Burundi":"BDI",
    "Central African Republic":"CAF",
    "Chad":"TCD",
    "DR Congo":"COD",
    "Djibouti":"DJI",
    "El Salvador":"SLV",
    "Eritrea":"ERI",
    "Gabon":"GAB",
    "Guatemala":"GTM",
    "Guinea":"GIN",
    "Honduras":"HND",
    "Iceland":"ISL",
    "Ivory Coast":"CIV",
    "Jamaica":"JAM",
    "Kosovo":"KSV",
    "Laos":"LAO",
    "Liberia":"LBR",
    "Luxembourg":"LUX",
    "Madagascar":"MDG",
    "Malawi":"MWI",
    "Mali":"MLI",
    "Malta":"MLT",
    "Mauritania":"MRT",
    "Mauritius":"MUS",
    "Moldova":"MDA",
    "Mongolia":"MNG",
    "Montenegro":"MNE",
    "Namibia":"NAM",
    "Nepal":"NPL",
    "Niger":"NER",
    "North Macedonia":"MKD",
    "Palestine":"PSE",
    "Panama":"PAN",
    "Paraguay":"PRY",
    "Rwanda":"RWA",
    "Sierra Leone":"SLE",
    "Somalia":"SOM",
    "South Sudan":"SSD",
    "Tanzania":"TZA",
    "Timor-Leste":"TLS",
    "Togo":"TGO",
    "Trinidad and Tobago":"TTO",
    "Uruguay":"URY",
    "Zambia":"ZMB",
    "Antigua and Barbuda":"ATG",
    "Aruba":"ABW",
    "Bahamas":"BHS",
    "Barbados":"BRB",
    "Belize":"BLZ",
    "Bhutan":"BTN",
    "Bosnia-Herzegovina":"BIH",
    "Cabo Verde":"CPV",
    "Comoros":"COM",
    "Costa Rica":"CRI",
    "Czechia":"CZE",
    "Dominican Republic":"DOM",
    "Equatorial Guinea":"GNQ",
    "Fiji":"FJI",
    "Gambia":"GMB",
    "Guinea-Bissau":"GNB",
    "Guyana":"GUY",
    "Haiti":"HTI",
    "Lesotho":"LSO",
    "Maldives":"MDV",
    "Nicaragua":"NIC",
    "Papua New Guinea":"PNG",
    "Saint Kitts and Nevis":"KNA",
    "Saint Vincent":"VCT",
    "Seychelles":"SYC",
    "Slovenia":"SVN",
    "Solomon Islands":"SLB",
    "Suriname":"SUR",
    "Tonga":"TON",
    "Turkiye":"TUR",
    "Viet Nam":"VNM",
    "United Arab Emirates":"ARE",
    "Vanuatu":"VUT",
}
ISO3_TO_NAME = {v: k for k, v in ALL_COUNTRIES.items()}

# ─────────────────────────────────────────────────────────────────────────────
# COLOUR PALETTE  — dark blue theme
# ─────────────────────────────────────────────────────────────────────────────

NAVY       = "#0A1628"      # deepest background
BLUE_DARK  = "#0D2B55"      # header / sidebar
BLUE_MID   = "#1A4A8A"      # primary accent
BLUE_LIGHT = "#2E6FD8"      # secondary accent
BLUE_PALE  = "#D6E4F7"      # soft background tint
GREY_BG    = "#F4F7FB"
GREY_LINE  = "#EBEBEB"
WHITE      = "#FFFFFF"
TEXT_MAIN  = "#0A1628"
TEXT_MUTED = "#5A7099"
RED_CHART  = "#E84545"
AMBER      = "#F5A623"
GREEN      = "#27AE60"

COLORS = [BLUE_MID, RED_CHART, AMBER, GREEN,
          "#9B59B6", BLUE_LIGHT, "#E67E22", "#1ABC9C",
          "#E91E8C", "#00BCD4", "#FF5722", "#607D8B"]

# ─────────────────────────────────────────────────────────────────────────────
# API — TAC ECONOMICS DataLab
# ─────────────────────────────────────────────────────────────────────────────
# Endpoint : {BASE_URL}/data/{DATASET}/{SYMBOL}/{GEO}
#   Bilateral series : SYMBOL = arms_exported{REC_ISO3}  e.g. arms_exportedFRA
#                      GEO    = {sup_iso3_lower}         e.g. usa
#   Aggregate series : SYMBOL = arms_exported             e.g. arms_exported
#                      GEO    = {ISO3}                   e.g. FRA
# Response format   : {"data": [{"timestamp": "YYYY-MM-DD", "value": float}, ...]}

SESSION = requests.Session()
SESSION.headers.update({"Authorization": f"Bearer {API_KEY}"})

def fetch_pair(sup_iso3: str, rec_iso3: str) -> list:
    symbol = f"arms_exported{rec_iso3.upper()}"
    geo    = sup_iso3.lower()
    url    = f"{BASE_URL}/data/{DATASET}/{symbol}/{geo}"
    try:
        r = SESSION.get(url, timeout=15)
        if r.status_code == 404:
            return []
        if r.status_code != 200:
            return []
        return r.json().get("data", [])
    except Exception:
        return []


def fetch_all_pairs() -> dict:
    isos  = sorted(ALL_COUNTRIES.values())
    pairs = [(s, r) for s in isos for r in isos if s != r]
    total = len(pairs)
    done  = {"n": 0}
    t0    = time.time()
    results = {}

    def worker(pair):
        sup, rec = pair
        data = fetch_pair(sup, rec)
        done["n"] += 1
        if done["n"] % 500 == 0:
            elapsed = time.time() - t0
            rate    = done["n"] / elapsed
            remain  = (total - done["n"]) / rate
            print(f"  {done['n']:,}/{total:,}  ({done['n']/total*100:.0f}%)"
                  f"  ~{remain/60:.0f} min remaining")
        return (sup, rec, data)

    print(f"Fetching {total:,} pairs with {THREADS} threads...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=THREADS) as ex:
        for sup, rec, data in ex.map(worker, pairs):
            if data:
                vals = [d["value"] for d in data if d.get("value")]
                if vals:
                    results[(sup, rec)] = data

    print(f"✓ {len(results):,} pairs with data "
          f"(out of {total:,} tested) — {time.time()-t0:.0f}s")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# CACHE
# ─────────────────────────────────────────────────────────────────────────────

def save_cache(raw: dict):
    serializable = {f"{s}|{r}": v for (s, r), v in raw.items()}
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(serializable, f)
    print(f"✓ Cache saved: {CACHE}  ({os.path.getsize(CACHE)//1024} KB)")

def load_cache() -> dict:
    with open(CACHE, encoding="utf-8") as f:
        raw = json.load(f)
    return {tuple(k.split("|")): v for k, v in raw.items()}


# ─────────────────────────────────────────────────────────────────────────────
# DATAFRAME
# ─────────────────────────────────────────────────────────────────────────────

def fetch_country_totals(isos: list) -> dict:
    """
    Fetches total export/import series per country using:
      arms_exported/{ISO3}  → total arms exported by that country
      arms_imported/{ISO3}  → total arms imported by that country
    Example URL: .../data/SIPRI/arms_exported/FRA
    Returns dict: {ISO3_UPPER: {"exp": {year: val}, "imp": {year: val}}}
    """
    results = {}
    total   = len(isos) * 2
    done    = 0
    print(f"Fetching {total} aggregate series (arms_exported/imported per country)...")

    def fetch_one(symbol, geo):
        """symbol = 'arms_exported' or 'arms_imported', geo = ISO3 upper"""
        url = f"{BASE_URL}/data/{DATASET}/{symbol}/{geo}"
        try:
            r = SESSION.get(url, timeout=15)
            if r.status_code == 404:
                return {}
            if r.status_code != 200:
                return {}
            data = r.json().get("data", [])
            return {int(obs["timestamp"][:4]): float(obs["value"])
                    for obs in data
                    if obs.get("value") is not None and obs.get("timestamp")}
        except Exception:
            return {}

    for iso in isos:
        iso_up = iso.upper()
        exp_d  = fetch_one("arms_exported", iso_up)
        imp_d  = fetch_one("arms_imported", iso_up)
        done  += 2
        if exp_d or imp_d:
            results[iso_up] = {"exp": exp_d, "imp": imp_d}
        if done % 40 == 0:
            print(f"  {done}/{total} aggregate series fetched...")
        time.sleep(0.08)

    n = len(results)
    print(f"✓ Country totals: {n} countries with data")
    return results


def build_dataframe(raw: dict) -> pd.DataFrame:
    rows = []
    for (sup_iso, rec_iso), data in raw.items():
        sup_name = ISO3_TO_NAME.get(sup_iso.upper(), sup_iso)
        rec_name = ISO3_TO_NAME.get(rec_iso.upper(), rec_iso)
        for obs in data:
            if obs.get("value") and obs.get("timestamp"):
                rows.append({
                    "year"        : int(obs["timestamp"][:4]),
                    "supplier"    : sup_name,
                    "recipient"   : rec_name,
                    "tiv"         : round(float(obs["value"]), 2),
                })
    df = pd.DataFrame(rows)
    print(f"✓ DataFrame: {len(df):,} rows | "
          f"{df['year'].min()}–{df['year'].max()} | "
          f"{df['supplier'].nunique()} exporters × {df['recipient'].nunique()} importers")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# FIGURES — shared layout helper
# ─────────────────────────────────────────────────────────────────────────────

def base_layout(title="", height=400, extra=None):
    l = dict(
        title_text=title,
        title_font=dict(size=14, color=BLUE_DARK, family="Poppins,Inter,Arial"),
        height=height,
        paper_bgcolor=WHITE,
        font=dict(family="Poppins,Inter,Arial", color=TEXT_MAIN, size=11),
        margin=dict(l=60, r=30, t=50, b=50),
        plot_bgcolor=WHITE,
        xaxis=dict(gridcolor=GREY_LINE, zerolinecolor=GREY_LINE),
        yaxis=dict(gridcolor=GREY_LINE, zerolinecolor=GREY_LINE),
    )
    if extra:
        l.update(extra)
    return l


# ─────────────────────────────────────────────────────────────────────────────
# FIGURES — Page 1: Global view
# ─────────────────────────────────────────────────────────────────────────────

def fig_world_annual(df, y0, y1, wld_series=None):
    # Use WLD API series if available, else fall back to bilateral sum
    if wld_series:
        w = pd.DataFrame(sorted(wld_series.items()), columns=["year", "tiv"])
    else:
        w = df.groupby("year")["tiv"].sum().reset_index()
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=w["year"], y=w["tiv"], name="Annual volume",
        marker_color=BLUE_MID,
        hovertemplate="%{x}<br><b>%{y:,.0f} M TIV</b><extra></extra>",
    ))
    fig.update_layout(**base_layout(
        f"Global Annual Volume of Arms Transfers ({y0}–{y1})", 400,
        dict(
            xaxis=dict(
                title="Year", gridcolor=GREY_LINE, dtick=5,
                zerolinecolor=GREY_LINE, range=[1950, y1+1],
            ),
            yaxis=dict(title="TIV (millions)", gridcolor=GREY_LINE,
                       zerolinecolor=GREY_LINE),
            margin=dict(l=65, r=30, t=55, b=30),
            showlegend=False,
        )
    ))
    return fig


def fig_top_exporters(exp_series, y0, y1, top_n=20):
    y_start = y1 - 4
    exp = exp_series.sort_values().tail(top_n)
    max_val = exp.values.max()
    fig = go.Figure(go.Bar(
        x=exp.values, y=exp.index, orientation="h",
        marker_color=BLUE_MID,
        text=[f"{v/1000:.1f}k" if v >= 1000 else f"{v:.0f}" for v in exp.values],
        textposition="outside",
        textfont=dict(size=9, color=TEXT_MAIN),
        hovertemplate="%{y}<br><b>%{x:,.0f} M TIV</b><extra></extra>",
        cliponaxis=False,
    ))
    fig.update_layout(**base_layout(
        f"Top {top_n} Exporters — cumulative TIV {y_start}–{y1}", 560,
        dict(xaxis=dict(title="TIV (millions)", gridcolor=GREY_LINE,
                        zerolinecolor=GREY_LINE,
                        range=[0, max_val * 1.35]),
             yaxis=dict(gridcolor=GREY_LINE),
             margin=dict(l=155, r=10, t=55, b=40),)
    ))
    return fig


def fig_top_importers(imp_series, y0, y1, top_n=20):
    y_start = y1 - 4
    imp = imp_series.sort_values().tail(top_n)
    max_val = imp.values.max()
    fig = go.Figure(go.Bar(
        x=imp.values, y=imp.index, orientation="h",
        marker_color=RED_CHART,
        text=[f"{v/1000:.1f}k" if v >= 1000 else f"{v:.0f}" for v in imp.values],
        textposition="outside",
        textfont=dict(size=9, color=TEXT_MAIN),
        hovertemplate="%{y}<br><b>%{x:,.0f} M TIV</b><extra></extra>",
        cliponaxis=False,
    ))
    fig.update_layout(**base_layout(
        f"Top {top_n} Importers — cumulative TIV {y_start}–{y1}", 560,
        dict(xaxis=dict(title="TIV (millions)", gridcolor=GREY_LINE,
                        zerolinecolor=GREY_LINE,
                        range=[0, max_val * 1.35]),
             yaxis=dict(gridcolor=GREY_LINE),
             margin=dict(l=155, r=10, t=55, b=40),)
    ))
    return fig
def fetch_world_total() -> dict:
    """
    Fetches global world totals directly from the Datalab:
      arms_exported/WLD → total arms exported worldwide (all countries)
      arms_imported/WLD → total arms imported worldwide (all countries)
    Returns dict: {"exp": {year: val}, "imp": {year: val}}
    More accurate than summing bilateral pairs (includes all SIPRI countries).
    """
    result = {"exp": {}, "imp": {}}
    for direction, key in [("arms_exported", "exp"), ("arms_imported", "imp")]:
        url = f"{BASE_URL}/data/{DATASET}/{direction}/WLD"
        try:
            r = SESSION.get(url, timeout=15)
            if r.status_code == 200:
                data = r.json().get("data", [])
                result[key] = {
                    int(obs["timestamp"][:4]): float(obs["value"])
                    for obs in data
                    if obs.get("value") is not None and obs.get("timestamp")
                }
                print(f"  ✓ {direction}/WLD — {len(result[key])} years")
            else:
                print(f"  ✗ {direction}/WLD [{r.status_code}] — fallback to bilateral sum")
        except Exception as e:
            print(f"  ✗ {direction}/WLD error: {e} — fallback to bilateral sum")
    return result


def build_country_data(df, country_totals=None) -> dict:
    # Build individual country data
    countries = sorted(set(df["supplier"].unique()) | set(df["recipient"].unique()))
    data = {}
    for country in countries:
        exp = df[df["supplier"] == country]
        imp = df[df["recipient"] == country]

        exp_by_year = exp.groupby("year")["tiv"].sum().reset_index().values.tolist()
        imp_by_year = imp.groupby("year")["tiv"].sum().reset_index().values.tolist()
        # Top partners: last 5 years only
        y_max   = int(df["year"].max())
        y_cut   = y_max - 4
        exp5    = exp[exp["year"] >= y_cut]
        imp5    = imp[imp["year"] >= y_cut]
        top_rec = (exp5.groupby("recipient")["tiv"].sum()
                      .sort_values(ascending=False).head(15)
                      .reset_index().values.tolist())
        top_sup = (imp5.groupby("supplier")["tiv"].sum()
                      .sort_values(ascending=False).head(15)
                      .reset_index().values.tolist())

        # Use API aggregate totals if available, otherwise fall back to bilateral sum
        iso = ALL_COUNTRIES.get(country, "").upper()
        api_totals = (country_totals or {}).get(iso, {})
        # Time series: use API aggregate if available, else bilateral sum
        if api_totals.get("exp"):
            exp_by_year_final = [[int(y), round(v, 1)]
                                 for y, v in sorted(api_totals["exp"].items())]
            # KPI total: sum of last 5 years from API series
            y_max_api = max(api_totals["exp"].keys()) if api_totals["exp"] else y_max
            y_cut_api = y_max_api - 4
            total_exp_final = round(sum(v for y, v in api_totals["exp"].items()
                                        if y >= y_cut_api), 1)
        else:
            exp_by_year_final = [[int(r[0]), round(r[1], 1)] for r in exp_by_year]
            total_exp_final   = round(float(exp5["tiv"].sum()), 1)

        if api_totals.get("imp"):
            imp_by_year_final = [[int(y), round(v, 1)]
                                 for y, v in sorted(api_totals["imp"].items())]
            y_max_api = max(api_totals["imp"].keys()) if api_totals["imp"] else y_max
            y_cut_api = y_max_api - 4
            total_imp_final = round(sum(v for y, v in api_totals["imp"].items()
                                        if y >= y_cut_api), 1)
        else:
            imp_by_year_final = [[int(r[0]), round(r[1], 1)] for r in imp_by_year]
            total_imp_final   = round(float(imp5["tiv"].sum()), 1)

        # Growth: last 5y vs prior 5y — use API aggregate when available
        if api_totals.get("exp"):
            exp5_sum  = sum(v for y, v in api_totals["exp"].items() if y >= y_cut)
            exp5p_sum = sum(v for y, v in api_totals["exp"].items()
                           if y_cut - 5 <= y < y_cut) or 0
        else:
            exp5_sum  = float(exp5["tiv"].sum())
            exp5p_df  = exp[exp["year"] < y_cut]
            exp5p_sum = float(exp5p_df[exp5p_df["year"] >= y_cut - 5]["tiv"].sum())

        if api_totals.get("imp"):
            imp5_sum  = sum(v for y, v in api_totals["imp"].items() if y >= y_cut)
            imp5p_sum = sum(v for y, v in api_totals["imp"].items()
                           if y_cut - 5 <= y < y_cut) or 0
        else:
            imp5_sum  = float(imp5["tiv"].sum())
            imp5p_df  = imp[imp["year"] < y_cut]
            imp5p_sum = float(imp5p_df[imp5p_df["year"] >= y_cut - 5]["tiv"].sum())

        g_exp_c = round((exp5_sum - exp5p_sum) / exp5p_sum * 100, 1) if exp5p_sum else None
        g_imp_c = round((imp5_sum - imp5p_sum) / imp5p_sum * 100, 1) if imp5p_sum else None

        data[country] = {
            "exp_year" : exp_by_year_final,
            "imp_year" : imp_by_year_final,
            "top_rec"  : [[r[0], round(r[1], 1)] for r in top_rec],
            "top_sup"  : [[r[0], round(r[1], 1)] for r in top_sup],
            "total_exp": total_exp_final,
            "total_imp": total_imp_final,
            "g_exp"    : g_exp_c,
            "g_imp"    : g_imp_c,
            "y_cut"    : y_cut,
            "y_max"    : y_max,
        }
    # ── Add regional aggregates ──────────────────────────────────────
    regions = {
        "Europe": [
            "France","Germany","United Kingdom","Italy","Spain","Netherlands",
            "Poland","Sweden","Norway","Belgium","Czech Republic","Czechia",
            "Denmark","Finland","Greece","Portugal","Austria","Switzerland",
            "Ukraine","Romania","Hungary","Bulgaria","Serbia","Croatia",
            "Slovakia","Slovenia","Estonia","Latvia","Lithuania","Belarus",
            "Russia","North Macedonia","Kosovo","Montenegro","Albania",
            "Luxembourg","Malta","Iceland","Cyprus","Moldova","Georgia",
            "Armenia","Azerbaijan",
        ],
        "Middle East": [
            "Saudi Arabia","UAE","United Arab Emirates","Israel","Iran","Iraq",
            "Qatar","Kuwait","Jordan","Bahrain","Oman","Lebanon","Syria",
            "Yemen","Palestine","Turkey","Turkiye",
        ],
        "Asia & Oceania": [
            "China","India","Japan","South Korea","Australia","Pakistan",
            "Indonesia","Malaysia","Singapore","Thailand","Vietnam","Viet Nam",
            "Philippines","New Zealand","Bangladesh","Myanmar","Taiwan",
            "Cambodia","Sri Lanka","Nepal","Mongolia","Brunei","Laos",
            "Timor-Leste","Kazakhstan","Uzbekistan","Kyrgyzstan","Tajikistan",
            "Turkmenistan","Afghanistan","North Korea","Papua New Guinea",
            "Fiji","Solomon Islands","Tonga","Vanuatu","Maldives","Bhutan",
            "Seychelles","Djibouti",
        ],
        "Americas": [
            "United States","Canada","Brazil","Mexico","Argentina","Chile",
            "Colombia","Peru","Ecuador","Venezuela","Bolivia","Paraguay",
            "Uruguay","Honduras","Guatemala","El Salvador","Panama","Jamaica",
            "Trinidad and Tobago","Cuba","Nicaragua","Dominican Republic",
            "Haiti","Guyana","Suriname","Barbados","Belize","Bahamas",
            "Antigua and Barbuda","Saint Kitts and Nevis","Saint Vincent","Aruba",
        ],
        "Africa": [
            "South Africa","Egypt","Algeria","Morocco","Nigeria","Ethiopia",
            "Kenya","Ghana","Cameroon","Mozambique","Senegal","Sudan","Uganda",
            "Tanzania","Zambia","Zimbabwe","Angola","Namibia","Botswana","Mali",
            "Niger","Chad","Burkina Faso","Guinea","Ivory Coast","Cote d'Ivoire",
            "DR Congo","Congo","Madagascar","Malawi","Rwanda","Burundi","Somalia",
            "Eritrea","Liberia","Sierra Leone","Togo","Benin","Gabon",
            "Mauritania","South Sudan","Central African Republic",
            "Equatorial Guinea","Guinea-Bissau","Cabo Verde","Gambia",
            "Lesotho","Mauritius",
        ],
    }
    for region_name, members in regions.items():
        reg_exp     = df[df["supplier"].isin(members)]
        reg_imp_ext = df[df["recipient"].isin(members) & ~df["supplier"].isin(members)]

        y_max_r  = int(df["year"].max())
        y_cut_r  = y_max_r - 4
        y_prev_r = y_cut_r - 5
        exp5_r   = reg_exp[reg_exp["year"] >= y_cut_r]
        imp5_r   = reg_imp_ext[reg_imp_ext["year"] >= y_cut_r]
        exp5p_r  = reg_exp[(reg_exp["year"] >= y_prev_r) & (reg_exp["year"] < y_cut_r)]
        imp5p_r  = reg_imp_ext[(reg_imp_ext["year"] >= y_prev_r) & (reg_imp_ext["year"] < y_cut_r)]

        exp_yr_r  = reg_exp.groupby("year")["tiv"].sum().reset_index().values.tolist()
        imp_yr_r  = reg_imp_ext.groupby("year")["tiv"].sum().reset_index().values.tolist()
        top_rec_r = (exp5_r.groupby("recipient")["tiv"].sum()
                     .sort_values(ascending=False).head(15).reset_index().values.tolist())
        top_sup_r = (imp5_r.groupby("supplier")["tiv"].sum()
                     .sort_values(ascending=False).head(15).reset_index().values.tolist())

        te5  = float(exp5_r["tiv"].sum())
        ti5  = float(imp5_r["tiv"].sum())
        te5p = float(exp5p_r["tiv"].sum())
        ti5p = float(imp5p_r["tiv"].sum())
        ge_r = round((te5 - te5p) / te5p * 100, 1) if te5p else None
        gi_r = round((ti5 - ti5p) / ti5p * 100, 1) if ti5p else None

        data[region_name] = {
            "exp_year" : [[int(r[0]), round(r[1], 1)] for r in exp_yr_r],
            "imp_year" : [[int(r[0]), round(r[1], 1)] for r in imp_yr_r],
            "top_rec"  : [[r[0], round(r[1], 1)] for r in top_rec_r],
            "top_sup"  : [[r[0], round(r[1], 1)] for r in top_sup_r],
            "total_exp": round(te5, 1),
            "total_imp": round(ti5, 1),
            "g_exp"    : ge_r,
            "g_imp"    : gi_r,
            "y_cut"    : y_cut_r,
            "y_max"    : y_max_r,
        }

    return data


# ─────────────────────────────────────────────────────────────────────────────
# HTML ASSEMBLY
# ─────────────────────────────────────────────────────────────────────────────

def to_div(fig, div_id=""):
    return pio.to_html(fig, full_html=False, include_plotlyjs=False,
                       div_id=div_id, config={"displayModeBar": False,
                                               "responsive": True})

def kpi(title, value, sub="", color=None):
    # color param kept for growth indicators (green/red), others use BLUE_DARK
    val_style = f"color:{color};" if color else f"color:{BLUE_DARK};"
    return f"""<div class="kpi-card">
      <div class="kpi-title">{title}</div>
      <div class="kpi-value" style="{val_style}">{value}</div>
      <div class="kpi-sub">{sub}</div>
    </div>"""


def build_html(df: pd.DataFrame) -> str:
    y0, y1 = int(df["year"].min()), int(df["year"].max())
    n_sup  = df["supplier"].nunique()
    n_rec  = df["recipient"].nunique()
    total  = df["tiv"].sum()
    top_s  = df.groupby("supplier")["tiv"].sum().idxmax()
    top_r  = df.groupby("recipient")["tiv"].sum().idxmax()
    fmt    = lambda v: f"{v/1000:.1f}B" if v >= 1000 else f"{v:,.0f}"

    print("Fetching world totals (WLD series)...")
    wld = fetch_world_total()

    print("Building Page 1 charts...")
    d_world = to_div(fig_world_annual(df, y0, y1, wld.get("exp") or None), "chart-world")

    # Rankings: build from aggregate API totals (arms_exported/{ISO}, arms_imported/{ISO})
    # Falls back to bilateral sum for countries without aggregate series
    isos_pre = list(ALL_COUNTRIES.values())
    country_totals_pre = fetch_country_totals(isos_pre)

    def _agg_series(totals, direction, y_start, y_end, iso_to_name):
        """Sum aggregate API series over [y_start, y_end] for each country."""
        rows = {}
        for iso, td in totals.items():
            series = td.get(direction, {})
            if not series:
                continue
            v = sum(val for yr, val in series.items() if y_start <= yr <= y_end)
            if v > 0:
                name = iso_to_name.get(iso, iso)
                rows[name] = v
        return pd.Series(rows)

    iso_to_name = {v.upper(): k for k, v in ALL_COUNTRIES.items()}
    y5s_pre = y1 - 4
    exp_agg = _agg_series(country_totals_pre, "exp", y5s_pre, y1, iso_to_name)
    imp_agg = _agg_series(country_totals_pre, "imp", y5s_pre, y1, iso_to_name)

    # Fallback: fill missing countries from bilateral df
    df5_pre = df[df["year"] >= y5s_pre]
    exp_bil = df5_pre.groupby("supplier")["tiv"].sum()
    imp_bil = df5_pre.groupby("recipient")["tiv"].sum()
    for name, val in exp_bil.items():
        if name not in exp_agg.index:
            exp_agg[name] = val
    for name, val in imp_bil.items():
        if name not in imp_agg.index:
            imp_agg[name] = val

    d_exp   = to_div(fig_top_exporters(exp_agg, y0, y1),  "chart-exp")
    d_imp   = to_div(fig_top_importers(imp_agg, y0, y1),  "chart-imp")

    # ── 5-year windows (needed for map and KPIs) ─────────────────
    y5s  = y1 - 4
    y5p  = y5s - 5
    df5  = df[df["year"] >= y5s]
    df5p = df[(df["year"] >= y5p) & (df["year"] < y5s)]

    print("Computing map data...")
    # Map data: use aggregate API totals (arms_exported/{ISO}) for accuracy
    # Growth rates: compare last 5y vs prior 5y from aggregate series
    map_data = []
    for iso, td in country_totals_pre.items():
        name = iso_to_name.get(iso.upper(), iso)
        iso3 = ALL_COUNTRIES.get(name, "")
        if not iso3:
            continue
        exp_s = td.get("exp", {})
        imp_s = td.get("imp", {})
        e5  = sum(v for yr, v in exp_s.items() if yr >= y5s_pre)
        i5  = sum(v for yr, v in imp_s.items() if yr >= y5s_pre)
        e5p = sum(v for yr, v in exp_s.items() if y5s_pre - 5 <= yr < y5s_pre)
        i5p = sum(v for yr, v in imp_s.items() if y5s_pre - 5 <= yr < y5s_pre)
        ge  = round((e5 - e5p) / e5p * 100, 1) if e5p else None
        gi  = round((i5 - i5p) / i5p * 100, 1) if i5p else None
        map_data.append({
            "country": name, "iso3": iso3,
            "exp5": round(e5, 1), "imp5": round(i5, 1),
            "g_exp": ge, "g_imp": gi,
        })
    map_json = json.dumps(map_data, ensure_ascii=False)

    print("Computing country data for Page 2...")
    # Reuse country_totals already fetched above
    country_data = build_country_data(df, country_totals_pre)
    country_json = json.dumps(country_data, ensure_ascii=False)
    country_list = sorted(country_data.keys())
    options_html = "\n".join(
        f'<option value="{c}">{c}</option>' for c in country_list
    )

    # ── 5-year window KPIs (df5/df5p already defined above) ──────

    # ── World totals from WLD series (all SIPRI countries) ────────
    def _sum_years(series_dict, y_from, y_to):
        return sum(v for y, v in series_dict.items() if y_from <= y <= y_to)

    wld_exp = wld.get("exp", {})
    wld_imp = wld.get("imp", {})

    if wld_exp:
        tot_exp5  = _sum_years(wld_exp, y5s, y1)
        tot_exp5p = _sum_years(wld_exp, y5p, y5s - 1)
        # y0/y1 from WLD (may be wider than bilateral df)
        y0 = min(y0, min(wld_exp.keys(), default=y0))
        y1 = max(y1, max(wld_exp.keys(), default=y1))
    else:
        # Fallback: bilateral sum
        tot_exp5  = float(df5["tiv"].sum())
        tot_exp5p = float(df5p["tiv"].sum())

    if wld_imp:
        tot_imp5  = _sum_years(wld_imp, y5s, y1)
        tot_imp5p = _sum_years(wld_imp, y5p, y5s - 1)
    else:
        tot_imp5  = float(df5["tiv"].sum())
        tot_imp5p = float(df5p["tiv"].sum())

    g_exp = round((tot_exp5 - tot_exp5p) / tot_exp5p * 100, 1) if tot_exp5p else None
    g_imp = round((tot_imp5 - tot_imp5p) / tot_imp5p * 100, 1) if tot_imp5p else None

    # Rankings (top exporter/importer) stay from bilateral df (by country)
    exp5_by_s  = df5.groupby("supplier")["tiv"].sum()
    exp5p_by_s = df5p.groupby("supplier")["tiv"].sum()
    imp5_by_r  = df5.groupby("recipient")["tiv"].sum()
    imp5p_by_r = df5p.groupby("recipient")["tiv"].sum()

    top_s5 = exp5_by_s.idxmax() if not exp5_by_s.empty else "—"
    top_r5 = imp5_by_r.idxmax() if not imp5_by_r.empty else "—"

    # Fastest growing exporter (min 50M TIV last 5y)
    exp_valid  = exp5_by_s[exp5_by_s >= 50]
    exp_prev_a = exp5p_by_s.reindex(exp_valid.index).fillna(1)
    g_exp_by   = ((exp_valid - exp_prev_a) / exp_prev_a * 100).sort_values(ascending=False)
    top_g_exp  = g_exp_by.index[0]    if not g_exp_by.empty else "—"
    top_g_expv = g_exp_by.iloc[0]     if not g_exp_by.empty else 0

    # Fastest growing importer
    imp_valid  = imp5_by_r[imp5_by_r >= 50]
    imp_prev_a = imp5p_by_r.reindex(imp_valid.index).fillna(1)
    g_imp_by   = ((imp_valid - imp_prev_a) / imp_prev_a * 100).sort_values(ascending=False)
    top_g_imp  = g_imp_by.index[0]    if not g_imp_by.empty else "—"
    top_g_impv = g_imp_by.iloc[0]     if not g_imp_by.empty else 0

    def fmt_pct(v): return "N/A" if v is None else (f"+{v:.0f}%" if v >= 0 else f"{v:.0f}%")
    clr_exp = GREEN if g_exp >= 0 else RED_CHART
    clr_imp = GREEN if g_imp >= 0 else RED_CHART
    period5 = f"{y5s}\u2013{y1}"
    priorp  = f"{y5p}\u2013{y5s-1}"

    # Total transfers = exports (exports == imports in TIV, use exp side)
    tot5   = tot_exp5
    tot5p  = tot_exp5p
    g_tot  = ((tot5 - tot5p) / tot5p * 100) if tot5p else 0
    clr_tot = GREEN if (g_tot is not None and g_tot >= 0) else RED_CHART

    n_countries = df["supplier"].nunique() + df[~df["recipient"].isin(df["supplier"].unique())]["recipient"].nunique()
    kpis_html = "".join([
        kpi("Total Transfers",        f"{fmt(tot5)} M TIV",           period5),
        kpi("Transfers Growth",       fmt_pct(g_tot),                 f"vs {priorp}"),
        kpi("Top Exporter",           top_s5,                         period5),
        kpi("Top Importer",           top_r5,                         period5),
        kpi("Fastest Export Growth",  f"{top_g_exp} ({fmt_pct(top_g_expv)})", "last 5y vs prior 5y"),
        kpi("Fastest Import Growth",  f"{top_g_imp} ({fmt_pct(top_g_impv)})", "last 5y vs prior 5y"),
    ])

    js_colors   = json.dumps(COLORS)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SIPRI Arms Transfers — TAC ECONOMICS DataLab</title>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Poppins',Inter,Arial,sans-serif;background:{GREY_BG};
     color:{TEXT_MAIN};min-width:900px}}

/* ── Header ── */
.header{{
  background:linear-gradient(135deg,{NAVY} 0%,{BLUE_DARK} 60%,{BLUE_MID} 100%);
  padding:0 40px;
  height:68px;
  display:flex;align-items:center;gap:24px;
}}
.header-title-block{{flex:1}}
.h-title{{
  font-size:17px;font-weight:700;
  color:{WHITE};line-height:1.3;letter-spacing:0.2px
}}
.h-sub{{
  font-size:11px;color:{BLUE_PALE};
  margin-top:2px;letter-spacing:0.5px;opacity:.85
}}
.tiv-tip{{
  cursor:help;
  border-bottom:1px dotted {BLUE_PALE};
  font-style:italic;
  opacity:.9;
}}
.h-meta{{
  text-align:right;font-size:11px;
  color:{BLUE_PALE};opacity:.7;line-height:1.9;
  flex-shrink:0;
}}

/* ── Force Poppins everywhere ── */
select,button,input,label{{font-family:'Poppins',Inter,Arial,sans-serif}}

/* ── Tabs ── */
.tabs{{
  background:{BLUE_DARK};
  padding:0 40px;
  display:flex;
  border-bottom:3px solid {BLUE_MID};
}}
.tab{{
  padding:12px 24px;font-size:13px;font-weight:600;
  font-family:'Poppins',Inter,Arial,sans-serif;
  color:rgba(255,255,255,.55);
  cursor:pointer;border:none;background:none;
  border-bottom:3px solid transparent;
  margin-bottom:-3px;transition:.2s;letter-spacing:0.3px;
}}
.tab:hover{{color:{WHITE};}}
.tab.active{{
  color:{WHITE};
  border-bottom:3px solid {BLUE_LIGHT};
  background:rgba(255,255,255,.06);
}}

/* ── Pages ── */
.page{{display:none;padding:28px 40px 40px}}
.page.active{{display:block}}

/* ── KPIs ── */
.kpi-row{{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:24px}}
.kpi-card{{
  background:{WHITE};border-radius:10px;flex:1;min-width:130px;
  padding:15px 18px 15px 20px;
  box-shadow:0 1px 6px rgba(10,22,40,.08),0 0 0 1px {GREY_LINE};
  border-left:3px solid {BLUE_MID};
}}
.kpi-title{{font-size:10px;color:{TEXT_MUTED};margin-bottom:4px;
            text-transform:uppercase;letter-spacing:.7px;font-weight:600}}
.kpi-value{{font-size:20px;font-weight:800;color:{BLUE_DARK};}}
.kpi-sub{{font-size:10px;color:{TEXT_MUTED};margin-top:3px}}

/* ── Cards ── */
.card{{
  background:{WHITE};border-radius:12px;
  box-shadow:0 1px 8px rgba(10,22,40,.07),0 0 0 1px {GREY_LINE};
  margin-bottom:18px;
}}
/* Fix: ensure Plotly charts inside cards are full width */
.card .js-plotly-plot,
.card .plotly-graph-div{{width:100% !important}}

.row{{display:flex;gap:18px;margin-bottom:18px}}
.row .card{{flex:1;margin-bottom:0}}

/* ── Section headers ── */
.sec{{
  font-size:11px;font-weight:700;color:{BLUE_MID};
  text-transform:uppercase;letter-spacing:1.2px;
  margin-bottom:12px;padding-bottom:8px;
  border-bottom:2px solid {BLUE_PALE};
}}

/* ── Country selector ── */
.country-bar{{
  display:flex;align-items:center;gap:16px;
  background:{WHITE};border-radius:12px;
  padding:14px 20px;
  box-shadow:0 1px 6px rgba(10,22,40,.08),0 0 0 1px {GREY_LINE};
  margin-bottom:20px;
}}
.country-bar label{{
  font-size:13px;font-weight:700;color:{BLUE_DARK};
  white-space:nowrap;
}}
.country-bar select{{
  flex:1;max-width:340px;padding:9px 14px;
  border:1px solid {GREY_LINE};border-radius:8px;
  font-size:13px;color:{TEXT_MAIN};background:{WHITE};
  outline:none;cursor:pointer;
  transition:border-color .2s;
}}
.country-bar select:focus{{border-color:{BLUE_MID};
  box-shadow:0 0 0 3px rgba(46,111,216,.15)}}

/* ── Country KPIs ── */
.ckpi-row{{display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap}}
.ckpi{{
  background:{WHITE};flex:1;min-width:130px;border-radius:10px;
  padding:14px 18px 14px 20px;
  box-shadow:0 1px 6px rgba(10,22,40,.08),0 0 0 1px {GREY_LINE};
  border-left:3px solid {BLUE_MID};
}}
.ckpi-label{{font-size:10px;color:{TEXT_MUTED};margin-bottom:3px;
             text-transform:uppercase;letter-spacing:.7px;font-weight:600}}
.ckpi-val{{font-size:18px;font-weight:800;color:{BLUE_DARK}}}
.ckpi-sub{{font-size:10px;color:{TEXT_MUTED};margin-top:2px}}

/* ── Placeholder ── */
.placeholder{{
  text-align:center;padding:70px 40px;
  color:{TEXT_MUTED};font-size:14px;
  background:{WHITE};border-radius:12px;
  box-shadow:0 1px 8px rgba(10,22,40,.07),0 0 0 1px {GREY_LINE};
}}
.placeholder span{{font-size:36px;display:block;margin-bottom:12px}}

/* ── Cursor pointer on bar charts ── */
#chart-exp .js-plotly-plot .bars g path,
#chart-imp .js-plotly-plot .bars g path,
#chart-rec .js-plotly-plot .bars g path,
#chart-sup .js-plotly-plot .bars g path {{cursor:pointer !important}}
/* ── Cursor pointer on map ── */
#chart-map .js-plotly-plot path.geo,
#chart-map svg g.trace path {{cursor:pointer !important}}

/* ── Period selector buttons ── */
.period-btns{{display:flex;gap:6px;margin-bottom:8px}}
.pbtn{{
  padding:4px 12px;font-size:11px;font-weight:600;
  font-family:'Poppins',Arial,sans-serif;
  border:1px solid {BLUE_MID};border-radius:5px;
  color:{BLUE_MID};background:white;cursor:pointer;
  transition:all .15s;
}}
.pbtn:hover{{background:{BLUE_PALE};}}
.pbtn.active{{background:{BLUE_MID};color:white;}}

/* ── Cursor pointer: target drag layers Plotly puts on top ── */
#chart-exp svg, #chart-imp svg,
#chart-rec svg, #chart-sup svg {{ cursor: pointer !important; }}
#chart-map svg {{ cursor: pointer !important; }}
#chart-exp .nsewdrag, #chart-imp .nsewdrag,
#chart-rec .nsewdrag, #chart-sup .nsewdrag {{ cursor: pointer !important; }}
#chart-map .nsewdrag {{ cursor: pointer !important; }}

/* ── Footer ── */
.footer{{
  background:{NAVY};color:{BLUE_PALE};
  font-size:11px;text-align:center;
  padding:14px 40px;opacity:.9;
  margin-top:20px;
}}
</style>
</head>
<body>

<!-- ════════ Header ════════ -->
<div class="header">
  <div class="header-title-block">
    <div class="h-title">SIPRI Arms Transfers Dashboard 2025</div>
    <div class="h-sub">DataLab — Bilateral Major Arms Transfers (unit: M TIV)
      <span class="tiv-tip" title="Trend Indicator Value: SIPRI unit measuring the volume of arms transfers based on known unit production costs. It reflects the volume of military resources transferred, not financial values.">(TIV ℹ)</span>
    </div>
  </div>
  <div class="h-meta">
    Source: SIPRI / TAC ECONOMICS DataLab<br>
    Period: 1950–{y1} &nbsp;|&nbsp; {n_sup} exporters × {n_rec} importers
  </div>
</div>

<!-- ════════ Tabs ════════ -->
<div class="tabs">
  <button class="tab active" onclick="showPage('world',this)">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:7px"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>Global View
  </button>
  <button class="tab" onclick="showPage('country',this)">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:7px"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>Country Focus
  </button>
</div>

<!-- ════════════════════════════════════════════════════════
     PAGE 1 — Global View
════════════════════════════════════════════════════════ -->
<div id="world" class="page active">

  <div class="kpi-row">{kpis_html}</div>

  <div class="sec">Global Trend</div>
  <div class="card" style="padding:12px 20px 8px">
    <div class="period-btns" id="world-period-btns">
      <button class="pbtn active" onclick="setWorldRange(1950,null,this)">All</button>
      <button class="pbtn" onclick="setWorldRange({y1}-9,null,this)">10y</button>
      <button class="pbtn" onclick="setWorldRange({y1}-19,null,this)">20y</button>
      <button class="pbtn" onclick="setWorldRange({y1}-29,null,this)">30y</button>
    </div>
    {d_world}
  </div>

  <div class="sec">World Map</div>
  <div class="card" style="padding:14px 20px 10px">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
      <label style="font-size:12px;font-weight:600;color:{BLUE_DARK}">Indicator:</label>
      <select id="map-indicator" onchange="renderMap()"
        style="padding:6px 12px;border:1px solid {GREY_LINE};border-radius:6px;
               font-family:'Poppins',Arial,sans-serif;font-size:12px;
               color:{TEXT_MAIN};cursor:pointer;outline:none">
        <option value="exp5">Exports — last 5 years (M TIV)</option>
        <option value="imp5">Imports — last 5 years (M TIV)</option>
        <option value="g_exp">Export Growth — last 5y vs prior 5y (%)</option>
        <option value="g_imp">Import Growth — last 5y vs prior 5y (%)</option>
      </select>
    </div>
    <div id="chart-map" style="width:100%;height:420px"></div>
  </div>

  <div class="sec">Rankings</div>
  <div class="row">
    <div class="card" style="padding:8px 4px 4px">{d_exp}</div>
    <div class="card" style="padding:8px 4px 4px">{d_imp}</div>
  </div>

</div>

<!-- ════════════════════════════════════════════════════════
     PAGE 2 — Country Focus  (JS-rendered)
════════════════════════════════════════════════════════ -->
<div id="country" class="page">

  <div class="country-bar">
    <label>Select a country or region:</label>
    <select id="country-select" onchange="renderCountry(this.value)">
      <option value="">— choose a country or region —</option>
      <optgroup label="── Regions ──">
        <option value="Europe">Europe</option>
        <option value="Middle East">Middle East</option>
        <option value="Asia &amp; Oceania">Asia &amp; Oceania</option>
        <option value="Americas">Americas</option>
        <option value="Africa">Africa</option>
      </optgroup>
      <optgroup label="── Countries ──">
      {options_html}
      </optgroup>
    </select>
  </div>

  <!-- Dynamic KPIs -->
  <div class="ckpi-row" id="ckpi-row" style="display:none">
    <div class="ckpi">
      <div class="ckpi-label">Total Exports</div>
      <div class="ckpi-val" id="ck-exp" style="color:{BLUE_DARK}">—</div>
      <div class="ckpi-sub" id="ck-exp-sub">last 5 years TIV</div>
    </div>
    <div class="ckpi">
      <div class="ckpi-label">Total Imports</div>
      <div class="ckpi-val" id="ck-imp" style="color:{BLUE_DARK}">—</div>
      <div class="ckpi-sub" id="ck-imp-sub">last 5 years TIV</div>
    </div>

    <div class="ckpi">
      <div class="ckpi-label">Export Growth</div>
      <div class="ckpi-val" id="ck-gexp">—</div>
      <div class="ckpi-sub" id="ck-gexp-sub">vs prior 5 years</div>
    </div>
    <div class="ckpi">
      <div class="ckpi-label">Import Growth</div>
      <div class="ckpi-val" id="ck-gimp">—</div>
      <div class="ckpi-sub" id="ck-gimp-sub">vs prior 5 years</div>
    </div>
    <div class="ckpi">
      <div class="ckpi-label">Top Customer</div>
      <div class="ckpi-val" id="ck-top-rec"
           style="font-size:14px;font-weight:800;color:{BLUE_DARK}">—</div>
      <div class="ckpi-sub" id="ck-rec-sub">main export destination</div>
    </div>
    <div class="ckpi">
      <div class="ckpi-label">Top Supplier</div>
      <div class="ckpi-val" id="ck-top-sup"
           style="font-size:14px;font-weight:800;color:{BLUE_DARK}">—</div>
      <div class="ckpi-sub" id="ck-sup-sub">main import origin</div>
    </div>
  </div>

  <!-- Dynamic charts -->
  <div id="country-charts" style="display:none">

    <div class="sec" id="sec-ts">Time Series</div>
    <div class="card" style="padding:12px 20px 8px">
      <div class="period-btns" id="ts-period-btns">
        <button class="pbtn active" onclick="setTsRange(1950,null,this)">All</button>
        <button class="pbtn" onclick="setTsRange({y1}-9,null,this)">10y</button>
        <button class="pbtn" onclick="setTsRange({y1}-19,null,this)">20y</button>
        <button class="pbtn" onclick="setTsRange({y1}-29,null,this)">30y</button>
      </div>
      <div id="chart-ts" style="height:380px;width:100%"></div>
    </div>

    <div class="row">
      <div style="flex:1">
        <div class="sec" id="sec-rec">Top Export Destinations</div>
        <div class="card" style="padding:8px 4px 4px">
          <div id="chart-rec" style="height:460px;width:100%"></div>
        </div>
      </div>
      <div style="flex:1">
        <div class="sec" id="sec-sup">Top Import Origins</div>
        <div class="card" style="padding:8px 4px 4px">
          <div id="chart-sup" style="height:460px;width:100%"></div>
        </div>
      </div>
    </div>

  </div>

  <div id="country-placeholder" class="placeholder">
    <span>🌐</span>
    Select a country or region above to explore arms transfer flows
  </div>

</div>

<!-- ════════ Footer ════════ -->
<div class="footer">
  TAC ECONOMICS — DataLab SIPRI Arms Transfers &nbsp;|&nbsp;
  Source: SIPRI Trend Indicator Values (TIV) &nbsp;|&nbsp; 1950–{y1} &nbsp;|&nbsp; Generated {pd.Timestamp.now().strftime('%B %Y')}
</div>

<script>
// ── Pre-computed data ──────────────────────────────────────────────────────
const COUNTRY_DATA = {country_json};
const MAP_DATA = {map_json};
const YEAR_MIN = {y0};
const YEAR_MAX = {y1};

// ── Colours ───────────────────────────────────────────────────────────────
const BLUE_MID  = "{BLUE_MID}";
const RED_CHART = "{RED_CHART}";
const BLUE_DARK = "{BLUE_DARK}";
const GREY_BG   = "{GREY_BG}";
const GREY_LINE = "{GREY_LINE}";
const TEXT_MAIN = "{TEXT_MAIN}";
const TEXT_MUTED= "{TEXT_MUTED}";
const WHITE     = "{WHITE}";

// ── Period range buttons ─────────────────────────────────────────────────────
function setWorldRange(start, end, btn) {{
  const chartDiv = document.getElementById('chart-world');
  if (!chartDiv) return;
  const y1 = YEAR_MAX;
  const newRange = [start, end || y1 + 1];
  Plotly.relayout(chartDiv, {{'xaxis.range': newRange}});
  // Update active button
  document.querySelectorAll('#world-period-btns .pbtn')
    .forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
}}

function setTsRange(start, end, btn) {{
  const chartDiv = document.getElementById('chart-ts');
  if (!chartDiv) return;
  const y1 = YEAR_MAX;
  const newRange = [start, end || y1 + 1];
  Plotly.relayout(chartDiv, {{'xaxis.range': newRange}});
  document.querySelectorAll('#ts-period-btns .pbtn')
    .forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
}}

// ── Tab navigation ─────────────────────────────────────────────────────────
function showPage(id, btn) {{
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(b  => b.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  btn.classList.add('active');
  // Force Plotly to resize all charts in the newly visible page
  setTimeout(function() {{
    document.querySelectorAll('#' + id + ' .plotly-graph-div').forEach(function(el) {{
      Plotly.Plots.resize(el);
    }});
  }}, 50);
}}

// Cursor via CSS on the draglayer (what mouse actually hits in Plotly)
function injectBarCursorStyle() {{
  // The draglayer sits on top of everything — target it per chart
  const barIds = ['chart-exp','chart-imp','chart-rec','chart-sup'];
  barIds.forEach(function(id) {{
    const div = document.getElementById(id);
    if (!div) return;
    // Target the nsewdrag overlay that captures mouse events
    div.querySelectorAll('.nsewdrag, .nwdrag, .nedrag, .swdrag, .sedrag, .drag')
       .forEach(function(el) {{ el.style.cursor = 'pointer'; }});
    // Also set on the SVG container itself
    const svg = div.querySelector('svg.main-svg');
    if (svg) svg.style.cursor = 'pointer';
  }});
  // Map: the geo drag layer
  const mapDiv = document.getElementById('chart-map');
  if (mapDiv) {{
    mapDiv.querySelectorAll('.nsewdrag, .drag, .geo')
          .forEach(function(el) {{ el.style.cursor = 'pointer'; }});
    const svg = mapDiv.querySelector('svg.main-svg');
    if (svg) svg.style.cursor = 'pointer';
  }}
}}

function startCursorInjection() {{
  [100, 300, 700, 1500, 3000].forEach(function(d) {{
    setTimeout(injectBarCursorStyle, d);
  }});
}}


// Render map immediately when DOM is ready
document.addEventListener('DOMContentLoaded', function() {{
  renderMap();
}});

// Trigger resize on initial load so bar charts render correctly
window.addEventListener('load', function() {{
  setTimeout(function() {{
    document.querySelectorAll('.plotly-graph-div').forEach(function(el) {{
      Plotly.Plots.resize(el);
    }});
    attachBarClickHandlers();
    startCursorInjection();
    // Re-render map in case it didn't initialize correctly
    renderMap();
  }}, 200);
}});

// ── World choropleth map ──────────────────────────────────────────────────
function renderMap() {{
  const ind    = document.getElementById('map-indicator').value;
  const labels = {{
    exp5 : 'Exports last 5y (M TIV)',
    imp5 : 'Imports last 5y (M TIV)',
    g_exp: 'Export Growth — last 5y vs prior 5y (%)',
    g_imp: 'Import Growth — last 5y vs prior 5y (%)',
  }};
  const isGrowth = ind.startsWith('g_');
  const vals   = MAP_DATA.map(d => d[ind]);

  // Growth: blue=low/negative, white=neutral, red=high/positive
  // Volume: white=low, red=high
  const colorscale = isGrowth
    ? [[0,'#1565C0'],[0.35,'#90CAF9'],[0.5,'#F5F5F5'],[0.65,'#EF9A9A'],[1,'#C62828']]
    : [[0,'#FFF5F5'],[0.25,'#FFCDD2'],[0.5,'#EF9A9A'],[0.75,'#E53935'],[1,'#7B0000']];

  // Shared percentile scale:
  // - Volumes (exp5/imp5): same scale across both indicators (P85 of all volume values)
  // - Growth: symmetric scale P15/P85 across both growth indicators
  const allVolumeVals = [...MAP_DATA.map(d=>d.exp5), ...MAP_DATA.map(d=>d.imp5)]
    .filter(v => v > 0).sort((a,b)=>a-b);
  const growthVals = [...MAP_DATA.map(d=>d.g_exp||0), ...MAP_DATA.map(d=>d.g_imp||0)]
    .sort((a,b)=>a-b);
  const volP85 = allVolumeVals[Math.floor(allVolumeVals.length * 0.85)] || 1;
  const gP15   = growthVals[Math.floor(growthVals.length * 0.15)];
  const gP85   = growthVals[Math.floor(growthVals.length * 0.85)];

  let plotVals = vals;
  const zmin = isGrowth ? Math.min(gP15, -gP85) : 0;
  const zmax = isGrowth ? Math.max(gP85, -gP15)  : volP85;

  const countryTab = document.querySelector('.tab:nth-child(2)');

  const trace = {{
    type: 'choropleth',
    locationmode: 'ISO-3',
    locations: MAP_DATA.map(d => d.iso3),
    z: vals,
    text: MAP_DATA.map(d => d.country),
    colorscale: colorscale,
    reversescale: false,
    autocolorscale: false,
    colorbar: {{
      title: {{ text: labels[ind],
               font: {{ size:11, family:'Poppins,Arial' }} }},
      thickness: 14,
      len: 0.7,
    }},
    customdata: MAP_DATA.map(d => d[ind]),
    hovertemplate: '<b>%{{text}}</b><br>' + labels[ind] + ': <b>%{{customdata:,.1f}}</b><extra></extra>',
    marker: {{ line: {{ color: '#AAAAAA', width: 0.4 }} }},
    zmin: zmin,
    zmax: zmax,
  }};

  const layout = {{
    geo: {{
      showframe: false,
      showcoastlines: true,
      coastlinecolor: '#BBBBBB',
      showborder: true,
      projection: {{ type: 'equirectangular' }},
      bgcolor: '#FFFFFF',
      showland: true,
      landcolor: '#F2F2F2',
      showocean: true,
      oceancolor: '#FFFFFF',
      showcountries: true,
      countrycolor: '#BBBBBB',
      countrywidth: 0.4,
      lataxis: {{ range: [-60, 85] }},
      lonaxis: {{ range: [-170, 180] }},
    }},
    paper_bgcolor: 'white',
    font: {{ family: 'Poppins,Arial', size: 11 }},
    margin: {{ l:0, r:0, t:0, b:0 }},
    height: 440,
  }};

  Plotly.react('chart-map', [trace], layout,
    {{ responsive:true, displayModeBar:false }});

  const mapDiv = document.getElementById('chart-map');
  if (mapDiv) {{
    // Cursor: pointer on hover over a country
    mapDiv.on('plotly_hover', function() {{
      const drag = mapDiv.querySelector('.nsewdrag, .drag');
      if (drag) drag.style.cursor = 'pointer';
    }});
    mapDiv.on('plotly_unhover', function() {{
      const drag = mapDiv.querySelector('.nsewdrag, .drag');
      if (drag) drag.style.cursor = 'default';
    }});

    // Click: navigate to Country Focus
    mapDiv.on('plotly_click', function(data) {{
      if (!data || !data.points || !data.points.length) return;
      const pt = data.points[0];
      const country = pt.text || pt.location;
      if (!country || !COUNTRY_DATA[country]) return;
      if (countryTab) showPage('country', countryTab);
      const sel = document.getElementById('country-select');
      if (sel) {{ sel.value = country; renderCountry(country); }}
      window.scrollTo({{top: 0, behavior: 'smooth'}});
    }});
  }}
}}

// Click on exporter/importer bar → navigate to Country Focus
function attachBarClickHandlers() {{
  const expDiv = document.getElementById('chart-exp');
  const impDiv = document.getElementById('chart-imp');
  const countryTab = document.querySelector('.tab:nth-child(2)');

  function onBarClick(data) {{
    if (!data || !data.points || !data.points.length) return;
    const country = data.points[0].label || data.points[0].y;
    if (!country || !COUNTRY_DATA[country]) return;
    // Switch to Country Focus tab
    if (countryTab) showPage('country', countryTab);
    // Set the select dropdown
    const sel = document.getElementById('country-select');
    if (sel) {{
      sel.value = country;
      renderCountry(country);
    }}
    // Scroll to top of page
    window.scrollTo({{top: 0, behavior: 'smooth'}});
  }}

  // Attach click + hover cursor to a chart div
  function attachToChart(div) {{
    if (!div) return;
    div.on('plotly_click', onBarClick);
    // Set cursor on all bar SVG elements directly after render
    function setCursorOnBars() {{
      div.querySelectorAll('g.trace path, .bars path, g.bar path, .point path')
         .forEach(function(el) {{ el.style.cursor = 'pointer'; }});
    }}
    setCursorOnBars();
    // Re-apply after any Plotly re-render via MutationObserver
    if (!div._cursorObserver) {{
      div._cursorObserver = new MutationObserver(setCursorOnBars);
      div._cursorObserver.observe(div, {{ childList: true, subtree: true }});
    }}
    div.on('plotly_hover', function() {{
      div.style.cursor = 'pointer';
      setCursorOnBars();
    }});
    div.on('plotly_unhover', function() {{ div.style.cursor = ''; }});
  }}

  attachToChart(expDiv);
  attachToChart(impDiv);

  const recDiv = document.getElementById('chart-rec');
  const supDiv = document.getElementById('chart-sup');
  attachToChart(recDiv);
  attachToChart(supDiv);
}}
// ── Format TIV ────────────────────────────────────────────────────────────
function fmtTIV(v) {{
  if (Math.abs(v) >= 1000) return (v/1000).toFixed(1) + 'B M TIV';
  return Math.round(v).toLocaleString() + ' M TIV';
}}

// ── Shared layout helper ──────────────────────────────────────────────────
function baseLayout(extra) {{
  return Object.assign({{
    paper_bgcolor: WHITE,
    plot_bgcolor : WHITE,
    font         : {{ family:'Poppins,Inter,Arial', color:TEXT_MAIN, size:11 }},
    xaxis        : {{ gridcolor:GREY_LINE, zerolinecolor:GREY_LINE }},
    yaxis        : {{ gridcolor:GREY_LINE, zerolinecolor:GREY_LINE }},
    margin       : {{ l:60, r:30, t:20, b:50 }},
  }}, extra || {{}});
}}

// ── Render country ────────────────────────────────────────────────────────
function renderCountry(country) {{
  if (!country) return;
  const d = COUNTRY_DATA[country];
  if (!d) return;

  // Show panels
  document.getElementById('ckpi-row').style.display        = 'flex';
  document.getElementById('country-charts').style.display  = 'block';
  document.getElementById('country-placeholder').style.display = 'none';

  // KPIs
  const y5s   = (d.y_max || YEAR_MAX) - 4;
  const y5p   = y5s - 5;
  const r5    = y5s + '–' + (d.y_max || YEAR_MAX);
  const rp    = y5p + '–' + (y5s - 1);

  document.getElementById('ck-exp').textContent  = fmtTIV(d.total_exp);
  document.getElementById('ck-imp').textContent  = fmtTIV(d.total_imp);
  document.getElementById('ck-exp-sub').textContent = 'TIV ' + r5;
  document.getElementById('ck-imp-sub').textContent = 'TIV ' + r5;

  // Growth KPIs
  const gExp = d.g_exp;
  const gImp = d.g_imp;
  const gExpEl = document.getElementById('ck-gexp');
  const gImpEl = document.getElementById('ck-gimp');
  if (gExpEl) {{
    gExpEl.textContent = (gExp === null || gExp === undefined)
      ? 'N/A'
      : (gExp >= 0 ? '+' : '') + gExp.toFixed(1) + '%';
    gExpEl.style.color = BLUE_DARK;
  }}
  if (gImpEl) {{
    gImpEl.textContent = (gImp === null || gImp === undefined)
      ? 'N/A'
      : (gImp >= 0 ? '+' : '') + gImp.toFixed(1) + '%';
    gImpEl.style.color = BLUE_DARK;
  }}
  document.getElementById('ck-gexp-sub').textContent = (gExp === null || gExp === undefined) ? 'no prior period data' : 'vs ' + rp;
  document.getElementById('ck-gimp-sub').textContent = (gImp === null || gImp === undefined) ? 'no prior period data' : 'vs ' + rp;

  document.getElementById('ck-top-rec').textContent = d.top_rec.length ? d.top_rec[0][0] : '—';
  document.getElementById('ck-top-sup').textContent = d.top_sup.length ? d.top_sup[0][0] : '—';
  document.getElementById('ck-rec-sub').textContent = 'main destination ' + r5;
  document.getElementById('ck-sup-sub').textContent = 'main origin ' + r5;
  document.getElementById('sec-ts').textContent     = 'Time Series — ' + country;

  const secRec = document.getElementById('sec-rec');
  const secSup = document.getElementById('sec-sup');
  // Titles now embedded in chart layout

  const cfg = {{ responsive:true, displayModeBar:false }};
  // Re-attach click handlers + cursor after charts re-render
  setTimeout(function() {{ attachBarClickHandlers(); injectBarCursorStyle(); }}, 400);

  // ── Chart 1: time series exports + imports ────────────────────────────
  Plotly.react('chart-ts',
    [
      {{
        x: d.exp_year.map(r=>r[0]), y: d.exp_year.map(r=>r[1]),
        name:'Exports', type:'bar', marker:{{color: BLUE_MID}},
        hovertemplate:'%{{x}}<br>Exports: <b>%{{y:,.0f}} M TIV</b><extra></extra>',
      }},
      {{
        x: d.imp_year.map(r=>r[0]), y: d.imp_year.map(r=>r[1]),
        name:'Imports', type:'bar', marker:{{color: RED_CHART}},
        hovertemplate:'%{{x}}<br>Imports: <b>%{{y:,.0f}} M TIV</b><extra></extra>',
      }}
    ],
    baseLayout({{
      barmode:'group',
      xaxis:{{
        title:'Year', gridcolor:GREY_LINE, dtick:5,
        zerolinecolor:GREY_LINE,
        range:[1950, (d.y_max || YEAR_MAX) + 1],
        rangeselector: {{
          buttons: [
            {{count:10, label:'10y', step:'year', stepmode:'backward'}},
            {{count:20, label:'20y', step:'year', stepmode:'backward'}},
            {{count:30, label:'30y', step:'year', stepmode:'backward'}},
            {{step:'all', label:'All'}},
          ],
          bgcolor: WHITE,
          activecolor: '#D6E4F7',
          bordercolor: GREY_LINE,
          font: {{family:'Poppins,Arial', size:10, color:BLUE_DARK}},
          x:0, y:1.02,
        }},
        type:'linear',
      }},
      yaxis:{{title:'TIV (millions)', gridcolor:GREY_LINE,
              zerolinecolor:GREY_LINE}},
      legend:{{orientation:'h', y:1.12, x:0,
               font:{{size:11, family:'Poppins,Arial'}}}},
      margin:{{l:65, r:20, t:55, b:40}},
    }}),
    cfg
  );

  // ── Chart 2: top destinations (exports) ──────────────────────────────
  const recL = d.top_rec.map(r=>r[0]).reverse();
  const recV = d.top_rec.map(r=>r[1]).reverse();
  // Helper: compute xaxis range with 40% label padding
  function xRangeWithPad(vals) {{
    const mx = Math.max(...vals);
    return [0, mx * 1.45];
  }}

  // Show message if no data
  const recCard = document.getElementById('chart-rec').parentElement;
  const supCard = document.getElementById('chart-sup').parentElement;

  if (!recV.length || Math.max(...recV) === 0) {{
    document.getElementById('chart-rec').innerHTML =
      '<div style="padding:60px;text-align:center;color:#5A7099;font-size:13px;">' +
      'No export data available for ' + country + ' in this period.</div>';
  }} else {{
  Plotly.react('chart-rec',
    [{{
      x:recV, y:recL, type:'bar', orientation:'h',
      marker:{{color:BLUE_MID}},
      text:recV.map(v => v >= 1000 ? (v/1000).toFixed(1)+'k' : v.toFixed(0)),
      textposition:'outside',
      cliponaxis: false,
      hovertemplate:'%{{y}}<br><b>%{{x:,.0f}} M TIV</b><extra></extra>',
    }}],
    baseLayout({{
      xaxis:{{title:'TIV (millions)',gridcolor:GREY_LINE,zerolinecolor:GREY_LINE,
              range: xRangeWithPad(recV)}},
      yaxis:{{gridcolor:GREY_LINE}},
      margin:{{l:145, r:20, t:30, b:45}},
      title: {{ text: 'Top Export Destinations — ' + country + ' (' + r5 + ')',
               font: {{size:13, color:BLUE_DARK, family:'Poppins,Arial'}} }},
    }}),
    cfg
  );
  }} // end if recV.length

  // ── Chart 3: top origins (imports) ───────────────────────────────────
  const supL = d.top_sup.map(r=>r[0]).reverse();
  const supV = d.top_sup.map(r=>r[1]).reverse();
  if (!supV.length || Math.max(...supV) === 0) {{
    document.getElementById('chart-sup').innerHTML =
      '<div style="padding:60px;text-align:center;color:#5A7099;font-size:13px;">' +
      'No import data available for ' + country + ' in this period.</div>';
  }} else {{
  Plotly.react('chart-sup',
    [{{
      x:supV, y:supL, type:'bar', orientation:'h',
      marker:{{color:RED_CHART}},
      text:supV.map(v => v >= 1000 ? (v/1000).toFixed(1)+'k' : v.toFixed(0)),
      textposition:'outside',
      cliponaxis: false,
      hovertemplate:'%{{y}}<br><b>%{{x:,.0f}} M TIV</b><extra></extra>',
    }}],
    baseLayout({{
      xaxis:{{title:'TIV (millions)',gridcolor:GREY_LINE,zerolinecolor:GREY_LINE,
              range: xRangeWithPad(supV)}},
      yaxis:{{gridcolor:GREY_LINE}},
      margin:{{l:145, r:20, t:30, b:45}},
      title: {{ text: 'Top Import Origins — ' + country + ' (' + r5 + ')',
               font: {{size:13, color:BLUE_DARK, family:'Poppins,Arial'}} }},
    }}),
    cfg
  );
  }} // end if supV.length
}}
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  SIPRI Arms Transfers — TAC ECONOMICS DataLab")
    print("=" * 60)

    if API_KEY == "MY_API_KEY":
        print("⚠  Please set your API key in API_KEY")
        raise SystemExit(1)

    # Load from cache or fetch from API
    if os.path.exists(CACHE):
        print(f"Cache found: {CACHE}  ({os.path.getsize(CACHE)//1024} KB)")
        raw = load_cache()
        print(f"✓ {len(raw):,} pairs loaded from cache")
    else:
        raw = fetch_all_pairs()
        if not raw:
            print("\n⚠  No data retrieved. Check your API key and SIPRI dataset access.")
            print(f"   Manual test: {BASE_URL}/data/{DATASET}/arms_exportedFRA/usa")
            raise SystemExit(1)
        save_cache(raw)

    df = build_dataframe(raw)
    if df.empty:
        print("⚠  Empty DataFrame after reconstruction.")
        raise SystemExit(1)

    print(f"\nGenerating HTML: {OUTPUT}")
    html = build_html(df)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)

    kb = os.path.getsize(OUTPUT) // 1024
    print(f"✓ File exported: {OUTPUT}  ({kb} KB)")
    print("  → Open it in your browser")
