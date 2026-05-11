"""
TAC ECONOMICS – DataLab DVF
Carte interactive des prix immobiliers au m² par code postal / département / région
Auteur : TAC ECONOMICS
Prérequis : pip install requests pandas plotly
"""
import os
import json
import requests
import pandas as pd
from pyproj import Transformer

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

API_KEY    = "MY_API_KEY"          # à remplacer
BASE_URL   = "https://api.taceconomics.io/"
DATASET_ID = "DVF"
SYMBOL     = "RESIDENT_PRICESM"
 
# Période : 2025T4=2025-10-01 | 2025T3=2025-07-01 | 2025T2=2025-04-01 | 2025T1=2025-01-01
TIMESTAMP     = "2025-10-01"
QUARTER_LABEL = "2025T4"
 


# Fichiers cache — evite de refaire les appels API si deja telecharges
CACHE_GEOJSON  = "geojson_cp_wgs84.json"    # GeoJSON converti
CACHE_SERIES   = "all_series.json"           # Series historiques
CACHE_DF       = "df_dvf.csv"               # Valeurs carte

# ─────────────────────────────────────────────
# 1. GEOJSON — telechargement + conversion Lambert93 -> WGS84
# ─────────────────────────────────────────────

def convert_coords(coords, transformer):
    if isinstance(coords[0], list):
        return [convert_coords(c, transformer) for c in coords]
    lon, lat = transformer.transform(coords[0], coords[1])
    return [lon, lat]

if os.path.exists(CACHE_GEOJSON):
    print(f"[1/3] GeoJSON charge depuis le cache ({CACHE_GEOJSON})")
    with open(CACHE_GEOJSON, encoding="utf-8") as f:
        geojson_wgs84 = json.load(f)
else:
    print("[1/3] Telechargement et conversion du GeoJSON...")
    r = requests.get(
        "https://catalogue.atlasante.fr/api/data/65f0a9e6-89ff-48e2-a2c1-a3aba4b06ed1",
        timeout=120
    )
    geo_raw = r.json()
    print(f"      -> {len(geo_raw['features'])} features brutes")

    transformer = Transformer.from_crs("EPSG:2154", "EPSG:4326", always_xy=True)
    features_wgs84 = []
    for feat in geo_raw["features"]:
        code = feat["properties"]["id"].strip()
        nom  = feat["properties"]["lib"].strip().replace("\n", " ").replace("\r", " ")
        features_wgs84.append({
            "type": "Feature",
            "properties": {
                "code_postal": code,
                "nom": nom,
                "dep": feat["properties"]["dep"].strip()
            },
            "geometry": {
                "type": feat["geometry"]["type"],
                "coordinates": convert_coords(feat["geometry"]["coordinates"], transformer)
            }
        })

    geojson_wgs84 = {"type": "FeatureCollection", "features": features_wgs84}

    with open(CACHE_GEOJSON, "w", encoding="utf-8") as f:
        json.dump(geojson_wgs84, f, ensure_ascii=False)
    print(f"      -> {len(features_wgs84)} features converties et sauvegardees")

# ─────────────────────────────────────────────
# 2. APPELS API — series historiques completes
# ─────────────────────────────────────────────

def get_full_series(country_id):
    url = f"{BASE_URL}/data/{DATASET_ID}/{SYMBOL}/{country_id}"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 404:
            return []
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception as e:
        print(f"  Erreur {country_id} : {e}")
        return []

if os.path.exists(CACHE_SERIES) and os.path.exists(CACHE_DF):
    print(f"[2/3] Series chargees depuis le cache")
    with open(CACHE_SERIES, encoding="utf-8") as f:
        all_series = json.load(f)
    df = pd.read_csv(CACHE_DF, dtype={"code": str})
    print(f"      -> {len(df)} zones")
else:
    features = geojson_wgs84["features"]
    print(f"[2/3] Interrogation de l'API ({len(features)} codes postaux)...")
    print(f"      Duree estimee : 30-60 minutes")

    records    = []
    all_series = {}

    for i, feat in enumerate(features):
        code = feat["properties"]["code_postal"]
        nom  = feat["properties"]["nom"]
        country_id = f"FRA_CP{code}"

        if (i + 1) % 100 == 0 or i == 0:
            print(f"      [{i+1}/{len(features)}] {country_id}...")

        series = get_full_series(country_id)
        if not series:
            continue

        val_carte = None
        for obs in series:
            if obs.get("timestamp") == TIMESTAMP:
                val_carte = obs.get("value")
                break

        if val_carte is not None:
            records.append({"code": code, "nom": nom, "prix_m2": round(val_carte)})

        dates  = [obs["timestamp"][:7] for obs in series]
        values = [round(obs["value"]) if obs["value"] else None for obs in series]

        # Convertir les dates en etiquettes trimestrielles lisibles
        def to_quarter(ym):
            year, month = ym.split('-')
            q = {'01':'T1','04':'T2','07':'T3','10':'T4'}.get(month, '??')
            return f"{q} {year}"

        labels = [to_quarter(d) for d in dates]
        # Echapper les apostrophes pour eviter les erreurs JS
        nom_safe = nom.replace("'", "\u2019").replace('"', '\u201c')
        all_series[code] = {"labels": labels, "values": values, "nom": nom_safe}

    df = pd.DataFrame(records)
    taux = len(df) / len(features) * 100
    print(f"      -> {len(df)} zones chargees ({taux:.1f}% de couverture)")
    print(df.sort_values("prix_m2", ascending=False).head(5).to_string(index=False))

    # Sauvegarde cache
    with open(CACHE_SERIES, "w", encoding="utf-8") as f:
        json.dump(all_series, f, ensure_ascii=False)
    df.to_csv(CACHE_DF, index=False)
    print(f"      Cache sauvegarde : {CACHE_SERIES}, {CACHE_DF}")

# ─────────────────────────────────────────────
# 3. GENERATION DU HTML AUTONOME
# ─────────────────────────────────────────────

print("[3/3] Generation du fichier HTML...")

# Filtrer le GeoJSON sur les zones chargees
codes_ok = set(df["code"].astype(str))
geojson_filtered = {
    "type": "FeatureCollection",
    "features": [
        f for f in geojson_wgs84["features"]
        if f["properties"]["code_postal"] in codes_ok
    ]
}
print(f"      -> {len(geojson_filtered['features'])} zones dans la carte")

# Serialisation des donnees pour le JS
series_json  = json.dumps(all_series, ensure_ascii=False)
geojson_json = json.dumps(geojson_filtered, ensure_ascii=False)
df_json      = df.to_json(orient="records")
current_ym   = TIMESTAMP[:7]

zmin = int(df["prix_m2"].quantile(0.05))
zmax = int(df["prix_m2"].quantile(0.95))

html = (
"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DVF \u2014 Prix immobilier """
+ QUARTER_LABEL +
"""</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: Arial, sans-serif; background: #f0f2f5; overflow: hidden; }

  header {
    background: #1a2535;
    color: white;
    padding: 0 20px;
    height: 54px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  header .left h1 { font-size: 15px; font-weight: 700; letter-spacing: 0.2px; }
  header .left p  { font-size: 11px; opacity: 0.6; margin-top: 2px; }

  .container { display: flex; height: calc(100vh - 54px); }

  #map-panel { flex: 1; min-width: 0; position: relative; }
  #map { width: 100%; height: 100%; }

  #chart-panel {
    width: 420px;
    background: white;
    border-left: 1px solid #dce1e9;
    display: flex;
    flex-direction: column;
    box-shadow: -2px 0 8px rgba(0,0,0,0.06);
  }

  #chart-header {
    padding: 16px 18px 10px;
    border-bottom: 1px solid #f0f0f0;
  }
  #chart-title {
    font-size: 14px;
    font-weight: 700;
    color: #1a2535;
    margin-bottom: 2px;
  }
  #chart-subtitle { font-size: 11px; color: #9aa3b0; }

  #chart-body { flex: 1; display: flex; flex-direction: column; padding: 12px; }

  #chart-placeholder {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: #c5ccd8;
    font-size: 13px;
    text-align: center;
    gap: 12px;
  }
  #chart-placeholder svg { opacity: 0.3; }

  #chart-div { flex: 1; }

  #stats-bar {
    display: flex;
    gap: 0;
    border-top: 1px solid #f0f0f0;
  }
  .stat-box {
    flex: 1;
    padding: 10px 12px;
    border-right: 1px solid #f0f0f0;
    text-align: center;
  }
  .stat-box:last-child { border-right: none; }
  .stat-label { font-size: 10px; color: #9aa3b0; text-transform: uppercase; letter-spacing: 0.5px; }
  .stat-value { font-size: 14px; font-weight: 700; color: #1a2535; margin-top: 2px; }
  .stat-name  { font-size: 10px; color: #b0b8c4; margin-top: 1px; }

  /* Barre de recherche */
  #search-bar {
    position: absolute;
    top: 12px;
    left: 12px;
    z-index: 1000;
    display: flex;
    gap: 6px;
    background: white;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.15);
    padding: 8px 10px;
    width: 300px;
  }
  #search-input {
    flex: 1;
    border: none;
    outline: none;
    font-size: 13px;
    color: #1a2535;
    background: transparent;
  }
  #search-input::placeholder { color: #b0b8c4; }
  #search-btn {
    background: #1a2535;
    color: white;
    border: none;
    border-radius: 5px;
    padding: 4px 10px;
    font-size: 12px;
    cursor: pointer;
  }
  #search-btn:hover { background: #2c3e50; }
  #search-dropdown {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    background: white;
    border-radius: 0 0 8px 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.12);
    max-height: 220px;
    overflow-y: auto;
    display: none;
    z-index: 1001;
  }
  .search-item {
    padding: 8px 12px;
    font-size: 12px;
    cursor: pointer;
    border-bottom: 1px solid #f5f5f5;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .search-item:hover { background: #f0f4f8; }
  .search-item .cp   { font-weight: 700; color: #1a2535; }
  .search-item .nom  { color: #6b7a8d; }
  .search-item .prix { color: #e74c3c; font-weight: 600; font-size: 11px; }
</style>
</head>
<body>

<header>
  <div class="left">
    <h1>Prix immobilier r\u00e9sidentiel moyen au m\u00b2 \u2014 """
+ QUARTER_LABEL +
"""</h1>
    <p>Source\u00a0: TAC ECONOMICS\u00a0/ DVF (moyenne mobile 4 trimestres) \u00a0|\u00a0 Cliquez sur une zone pour afficher l\u2019historique</p>
  </div>

</header>

<div class="container">
  <div id="map-panel">
    <div id="search-bar">
      <input id="search-input" type="text" placeholder="Rechercher un code postal ou une commune..." autocomplete="off">
      <button id="search-btn">&#128269;</button>
      <div id="search-dropdown"></div>
    </div>
    <div id="map"></div>
  </div>

  <div id="chart-panel">
    <div id="chart-header">
      <div id="chart-title">Historique des prix</div>
      <div id="chart-subtitle">S\u00e9lectionnez un code postal sur la carte</div>
    </div>
    <div id="chart-body">
      <div id="chart-placeholder">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M3 3h18v18H3zM3 9h18M9 21V9"/>
        </svg>
        Cliquez sur un code postal<br>pour afficher son historique de prix
      </div>
      <div id="chart-div" style="display:none;"></div>
    </div>
    <div id="stats-bar">
      <div class="stat-box">
        <div class="stat-label">Code postal</div>
        <div class="stat-value" id="stat-code">\u2014</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">"""
+ QUARTER_LABEL +
"""</div>
        <div class="stat-value" id="stat-prix">\u2014</div>
        <div class="stat-name">\u20ac/m\u00b2</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Var. 1 an</div>
        <div class="stat-value" id="stat-var">\u2014</div>
      </div>
    </div>
  </div>
</div>

<script>
const ALL_SERIES = """
+ series_json +
""";
const GEOJSON    = """
+ geojson_json +
""";
const DF         = """
+ df_json +
""";
const CURRENT_YM = '"""
+ current_ym +
"""';
const QUARTER    = '"""
+ QUARTER_LABEL +
"""';
const ZMIN = """
+ str(zmin) +
""";
const ZMAX = """
+ str(zmax) +
""";

// ── Carte choroplèthe
const mapData = [{
  type: 'choroplethmapbox',
  geojson: GEOJSON,
  locations: DF.map(d => d.code),
  z: DF.map(d => d.prix_m2),
  featureidkey: 'properties.code_postal',
  colorscale: [
    [0.0,  '#2d6a2d'],
    [0.20, '#74c476'],
    [0.38, '#d4e85a'],
    [0.50, '#ffffb2'],
    [0.62, '#fecc5c'],
    [0.74, '#fd8d3c'],
    [0.86, '#e31a1c'],
    [1.0,  '#67001f'],
  ],
  reversescale: false,
  zmin: ZMIN,
  zmax: ZMAX,
  marker: { opacity: 0.78, line: { width: 0.3, color: 'white' } },
  colorbar: {
    title: { text: '\u20ac/m\u00b2', side: 'right', font: { size: 11 } },
    tickformat: ',.0f',
    thickness: 13,
    len: 0.7,
  },
  customdata: DF.map(d => [d.code, d.nom, d.prix_m2]),
  hovertemplate:
    '<b>%{customdata[1]}</b><br>' +
    'Code\u00a0: %{customdata[0]}<br>' +
    'Prix\u00a0: <b>%{customdata[2]:,}\u00a0\u20ac/m\u00b2</b>' +
    '<extra></extra>',
}];

const mapLayout = {
  mapbox: {
    style: 'carto-positron',
    center: { lat: 46.8, lon: 2.3 },
    zoom: 5,
  },
  margin: { t: 0, b: 0, l: 0, r: 0 },
  paper_bgcolor: '#e8e8e8',
};

Plotly.newPlot('map', mapData, mapLayout, {
  responsive: true,
  scrollZoom: true,
  displayModeBar: true,
  modeBarButtonsToRemove: ['toImage', 'sendDataToCloud', 'select2d', 'lasso2d'],
  displaylogo: false,
});

// ── Fonction commune : afficher historique pour un code
function showHistory(code) {
  const serie = ALL_SERIES[code];
  if (!serie) return;

  document.getElementById('chart-title').textContent    = serie.nom;
  document.getElementById('chart-subtitle').textContent =
    'Code postal\u00a0' + code + '\u00a0\u2014\u00a0historique trimestriel';
  document.getElementById('stat-code').textContent = code;

  const xdata = serie.labels || serie.dates.map(d => {
    const [year, month] = d.split('-');
    return ({'01':'T1','04':'T2','07':'T3','10':'T4'}[month] || '??') + ' ' + year;
  });

  const currentIdx = xdata.indexOf('T4 2025');
  const prix = currentIdx >= 0 ? serie.values[currentIdx] : null;
  document.getElementById('stat-prix').textContent =
    prix ? prix.toLocaleString('fr-FR') : '\u2014';

  const idx1an = currentIdx - 4;
  if (currentIdx >= 0 && idx1an >= 0 && serie.values[idx1an]) {
    const varPct = ((serie.values[currentIdx] - serie.values[idx1an]) / serie.values[idx1an] * 100);
    const varEl  = document.getElementById('stat-var');
    varEl.textContent = (varPct >= 0 ? '+' : '') + varPct.toFixed(1) + '\u00a0%';
    varEl.style.color = varPct >= 0 ? '#27ae60' : '#e74c3c';
  } else {
    document.getElementById('stat-var').textContent = '\u2014';
    document.getElementById('stat-var').style.color = '#1a2535';
  }

  document.getElementById('chart-placeholder').style.display = 'none';
  document.getElementById('chart-div').style.display = 'block';

  const traceLine = {
    x: xdata, y: serie.values, type: 'scatter', mode: 'lines',
    line: { color: '#1a2535', width: 2 },
    fill: 'tozeroy', fillcolor: 'rgba(26,37,53,0.07)',
    hovertemplate: '%{x}<br><b>%{y:,}\u00a0\u20ac/m\u00b2</b><extra></extra>',
    showlegend: false,
  };

  const tracePoint = currentIdx >= 0 ? {
    x: [xdata[currentIdx]], y: [serie.values[currentIdx]],
    type: 'scatter', mode: 'markers+text',
    marker: { color: '#e74c3c', size: 9, line: { color: 'white', width: 1.5 } },
    text: [serie.values[currentIdx].toLocaleString('fr-FR') + '\u00a0\u20ac'],
    textposition: 'top center',
    textfont: { size: 11, color: '#e74c3c', family: 'Arial' },
    hovertemplate: QUARTER + '<br><b>%{y:,}\u00a0\u20ac/m\u00b2</b><extra></extra>',
    showlegend: false,
  } : null;

  const shapes = currentIdx >= 0 ? [{
    type: 'line',
    x0: xdata[currentIdx], x1: xdata[currentIdx],
    y0: 0, y1: 1, yref: 'paper',
    line: { color: '#e74c3c', width: 1, dash: 'dot' },
  }] : [];

  Plotly.react('chart-div',
    tracePoint ? [traceLine, tracePoint] : [traceLine],
    {
      margin: { t: 15, b: 60, l: 58, r: 12 },
      xaxis: {
        type: 'category', showgrid: true, gridcolor: '#f3f4f6',
        tickmode: 'array',
        tickvals: xdata.filter((d, i) => i % 4 === 0),
        ticktext: xdata.filter((d, i) => i % 4 === 0),
        tickangle: -45, tickfont: { size: 9 },
      },
      yaxis: {
        showgrid: true, gridcolor: '#f3f4f6',
        tickformat: ',.0f', ticksuffix: '\u00a0\u20ac', tickfont: { size: 10 },
      },
      shapes: shapes,
      paper_bgcolor: 'white', plot_bgcolor: 'white',
      showlegend: false, font: { family: 'Arial', size: 11 },
    },
    { responsive: true, displayModeBar: false }
  );
}

// ── Clic sur la carte
document.getElementById('map').on('plotly_click', function(data) {
  const code = data.points[0].location;
  showHistory(code);
});

// ── Barre de recherche
const searchInput    = document.getElementById('search-input');
const searchDropdown = document.getElementById('search-dropdown');

// Index de recherche : code + nom -> liste triee
const searchIndex = DF.map(d => ({
  code: d.code,
  nom: d.nom,
  prix: d.prix_m2,
  key: (d.code + ' ' + d.nom).toLowerCase()
}));

searchInput.addEventListener('input', function() {
  const q = this.value.trim().toLowerCase();
  searchDropdown.innerHTML = '';
  if (q.length < 2) { searchDropdown.style.display = 'none'; return; }

  const results = searchIndex
    .filter(d => d.key.includes(q))
    .sort((a, b) => {
      // Priorite aux codes postaux qui commencent par la query
      const aStarts = a.code.startsWith(q) ? 0 : 1;
      const bStarts = b.code.startsWith(q) ? 0 : 1;
      return aStarts - bStarts || a.code.localeCompare(b.code);
    })
    .slice(0, 12);

  if (results.length === 0) { searchDropdown.style.display = 'none'; return; }

  results.forEach(d => {
    const item = document.createElement('div');
    item.className = 'search-item';
    item.innerHTML =
      '<span><span class="cp">' + d.code + '</span> ' +
      '<span class="nom">' + d.nom + '</span></span>' +
      '<span class="prix">' + d.prix.toLocaleString('fr-FR') + '\u00a0\u20ac/m\u00b2</span>';
    item.addEventListener('click', function() {
      searchInput.value = d.code + ' \u2014 ' + d.nom;
      searchDropdown.style.display = 'none';
      selectCode(d.code);
    });
    searchDropdown.appendChild(item);
  });
  searchDropdown.style.display = 'block';
});

// Fermer dropdown si clic ailleurs
document.addEventListener('click', function(e) {
  if (!document.getElementById('search-bar').contains(e.target)) {
    searchDropdown.style.display = 'none';
  }
});

// Selectionner un code : zoom + historique
function selectCode(code) {
  // Trouver le centroide de la zone dans le GeoJSON
  const feat = GEOJSON.features.find(f => f.properties.code_postal === code);
  if (feat) {
    // Calculer le centre approximatif
    let lons = [], lats = [];
    const collectCoords = (coords) => {
      if (typeof coords[0] === 'number') { lons.push(coords[0]); lats.push(coords[1]); }
      else coords.forEach(c => collectCoords(c));
    };
    collectCoords(feat.geometry.coordinates);
    const centerLon = lons.reduce((a,b) => a+b, 0) / lons.length;
    const centerLat = lats.reduce((a,b) => a+b, 0) / lats.length;

    // Zoomer sur la zone
    Plotly.relayout('map', {
      'mapbox.center': { lat: centerLat, lon: centerLon },
      'mapbox.zoom': 11
    });
  }
  // Afficher l historique
  showHistory(code);
}

// Touche Entree dans la barre de recherche
searchInput.addEventListener('keydown', function(e) {
  if (e.key === 'Enter') {
    const first = searchDropdown.querySelector('.search-item');
    if (first) first.click();
  }
  if (e.key === 'Escape') { searchDropdown.style.display = 'none'; }
});
</script>
</body>
</html>"""
)

output_file = f"dvf_carte_cp_{QUARTER_LABEL}_avec_historique.html"
with open(output_file, "w", encoding="utf-8") as f:
    f.write(html)

print(f"\nTermine !")
print(f"Carte exportee : {os.path.abspath(output_file)}")
print(f"Ouvrez ce fichier dans votre navigateur.")
