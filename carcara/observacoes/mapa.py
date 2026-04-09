"""
PROJETO CARCARÁ — View do Mapa Leaflet
========================================
Serve a página HTML do mapa interativo.
Equivalente ao endpoint GET /mapa do FastAPI.
"""

from django.http import HttpResponse


def mapa_view(request):
    """GET /caraca/mapa/ → página HTML completa com Leaflet."""
    return HttpResponse(MAP_HTML, content_type="text/html; charset=utf-8")


MAP_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CARCARÁ — Mapa de Focos</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Segoe UI', sans-serif; background: #0f1117; color: #e0e0e0;
         height: 100vh; display: flex; flex-direction: column; }
  header {
    background: #1a1d27; border-bottom: 2px solid #ff4d1c;
    padding: 10px 20px; display: flex; align-items: center; gap: 14px; z-index: 1000;
  }
  header h1 { font-size: 1.1rem; font-weight: 700; letter-spacing: 1px; color: #fff; }
  header h1 span { color: #ff4d1c; }
  .badge { background: #ff4d1c; color: #fff; font-size: 0.7rem; font-weight: 700;
           padding: 2px 8px; border-radius: 20px; letter-spacing: 1px; }
  .stats { margin-left: auto; display: flex; gap: 20px; font-size: 0.78rem; color: #aaa; }
  .stats b { color: #fff; }
  .btn-refresh { background: #ff4d1c; border: none; color: #fff; padding: 6px 14px;
    border-radius: 6px; cursor: pointer; font-size: 0.8rem; font-weight: 600; }
  .btn-refresh:hover { background: #e03a0e; }
  .btn-refresh.loading { background: #555; cursor: default; }
  .main { display: flex; flex: 1; overflow: hidden; }
  #map { flex: 1; }
  #painel { width: 280px; background: #1a1d27; border-left: 1px solid #2a2d3a;
            overflow-y: auto; display: flex; flex-direction: column; }
  .painel-titulo { padding: 12px 16px; font-size: 0.75rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 1px; color: #888;
    border-bottom: 1px solid #2a2d3a; }
  .legenda { padding: 14px 16px; border-bottom: 1px solid #2a2d3a; }
  .leg-item { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-size: 0.8rem; }
  .leg-cor { width: 16px; height: 16px; border-radius: 50%; flex-shrink: 0; }
  .leg-linha { width: 24px; height: 3px; flex-shrink: 0; }
  .foco-card { margin: 10px 12px; padding: 12px; border-radius: 8px;
    background: #22263a; border: 1px solid #2a2d3a; cursor: pointer;
    transition: border-color .2s; }
  .foco-card:hover { border-color: #ff4d1c; }
  .foco-card .titulo { font-size: 0.85rem; font-weight: 700; margin-bottom: 6px;
    display: flex; align-items: center; gap: 6px; }
  .foco-card .linha { font-size: 0.75rem; color: #aaa; margin-bottom: 3px; }
  .foco-card .linha b { color: #e0e0e0; }
  .conf-alto { color: #4caf50; } .conf-medio { color: #ffc107; } .conf-baixo { color: #f44336; }
  .coords-copy { margin-top: 8px; font-size: 0.7rem; color: #ff4d1c;
    cursor: pointer; text-decoration: underline; }
  .empty-state { padding: 30px 16px; text-align: center; color: #555; font-size: 0.82rem; }
  #toast { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
    background: #1e2030; border: 1px solid #ff4d1c; color: #fff;
    padding: 10px 20px; border-radius: 8px; font-size: 0.82rem;
    opacity: 0; transition: opacity .3s; pointer-events: none; z-index: 9999; }
  #toast.show { opacity: 1; }
  .leaflet-popup-content-wrapper { background: #1a1d27 !important; color: #e0e0e0 !important;
    border: 1px solid #2a2d3a !important; border-radius: 8px !important; }
  .leaflet-popup-tip { background: #1a1d27 !important; }
  .popup-titulo { font-weight: 700; font-size: 0.9rem; margin-bottom: 8px; }
  .popup-linha  { font-size: 0.78rem; color: #aaa; margin-bottom: 3px; }
  .popup-linha b { color: #fff; }
  .popup-link { font-size: 0.75rem; color: #ff4d1c; text-decoration: none; }
</style>
</head>
<body>
<header>
  <div class="badge">CARCARÁ</div>
  <h1>Mapa de <span>Focos de Incêndio</span></h1>
  <div class="stats">
    <span>Observadores: <b id="stat-obs">—</b></span>
    <span>Focos: <b id="stat-focos">—</b></span>
  </div>
  <button class="btn-refresh" id="btn-refresh" onclick="carregar()">↻ Atualizar</button>
</header>
<div class="main">
  <div id="map"></div>
  <div id="painel">
    <div class="painel-titulo">Legenda</div>
    <div class="legenda">
      <div class="leg-item"><div class="leg-cor" style="background:#ff4d1c;border:2px solid #fff"></div><span>Foco estimado</span></div>
      <div class="leg-item"><div class="leg-cor" style="background:#4caf50;opacity:.3;border:2px solid #4caf50"></div><span>Raio — Alta confiança</span></div>
      <div class="leg-item"><div class="leg-cor" style="background:#ffc107;opacity:.3;border:2px solid #ffc107"></div><span>Raio — Média confiança</span></div>
      <div class="leg-item"><div class="leg-cor" style="background:#f44336;opacity:.3;border:2px solid #f44336"></div><span>Raio — Baixa confiança</span></div>
      <div class="leg-item"><div class="leg-cor" style="background:#2196f3;border:2px solid #fff"></div><span>Observador</span></div>
      <div class="leg-item"><div class="leg-linha" style="background:#ff9800"></div><span>Linha de visão</span></div>
    </div>
    <div class="painel-titulo" style="margin-top:4px">Focos detectados</div>
    <div id="lista-focos"><div class="empty-state">Nenhum foco ainda.<br>Envie observações para começar.</div></div>
  </div>
</div>
<div id="toast"></div>
<script>
const map = L.map('map').setView([-10.89, -37.06], 10);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  maxZoom: 19
}).addTo(map);

const camadas = {
  focos: L.layerGroup().addTo(map),
  raios: L.layerGroup().addTo(map),
  observadores: L.layerGroup().addTo(map),
  linhas: L.layerGroup().addTo(map),
};
L.control.layers(null, {
  "🔥 Focos": camadas.focos, "⭕ Raios": camadas.raios,
  "👤 Observadores": camadas.observadores, "📐 Linhas de visão": camadas.linhas,
}, { collapsed: false }).addTo(map);

const iconeFoco = L.divIcon({ className: '',
  html: '<div style="background:#ff4d1c;width:22px;height:22px;border-radius:50%;border:3px solid #fff;box-shadow:0 0 12px #ff4d1c;display:flex;align-items:center;justify-content:center;font-size:12px">🔥</div>',
  iconSize: [22,22], iconAnchor: [11,11] });
const iconeObs = L.divIcon({ className: '',
  html: '<div style="background:#2196f3;width:14px;height:14px;border-radius:50%;border:2px solid #fff;box-shadow:0 0 6px #2196f388"></div>',
  iconSize: [14,14], iconAnchor: [7,7] });

const COR = { alto: '#4caf50', medio: '#ffc107', baixo: '#f44336' };

function toast(msg, ms=2500) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), ms);
}

let primeiraVez = true;

async function carregar() {
  const btn = document.getElementById('btn-refresh');
  btn.textContent = '↻ Carregando…'; btn.classList.add('loading');
  try {
    // URL relativa — funciona integrado ao Django existente
    const r = await fetch('/api/mapa/dados/');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const geo = await r.json();
    renderizar(geo);
    toast('Atualizado — ' + geo.meta.total_observacoes + ' obs / ' + geo.meta.total_focos + ' focos');
  } catch(e) {
    toast('Erro ao carregar: ' + e.message, 4000);
  } finally {
    btn.textContent = '↻ Atualizar'; btn.classList.remove('loading');
  }
}

function renderizar(geo) {
  Object.values(camadas).forEach(c => c.clearLayers());
  const focoF = geo.features.filter(f => f.properties.tipo === 'foco');
  const obsF  = geo.features.filter(f => f.properties.tipo === 'observador');
  const linF  = geo.features.filter(f => f.properties.tipo === 'linha_visao');

  document.getElementById('stat-obs').textContent   = obsF.length;
  document.getElementById('stat-focos').textContent = focoF.length;

  linF.forEach(f => {
    L.polyline(f.geometry.coordinates.map(c=>[c[1],c[0]]),
      { color:'#ff9800', weight:1.5, opacity:0.6, dashArray:'5,5' })
     .bindPopup(`<div class="popup-titulo">📐 Linha de Visão</div>
       <div class="popup-linha">Usuário: <b>${f.properties.usuario_id}</b></div>
       <div class="popup-linha">Azimute: <b>${f.properties.azimute?.toFixed(1)}°</b></div>`)
     .addTo(camadas.linhas);
  });

  obsF.forEach(f => {
    const [lon,lat] = f.geometry.coordinates;
    const p = f.properties;
    L.marker([lat,lon], {icon:iconeObs})
     .bindPopup(`<div class="popup-titulo">👤 ${p.usuario_id}</div>
       <div class="popup-linha">Azimute: <b>${p.azimute?.toFixed(1)}°</b></div>
       <div class="popup-linha">Elevação: <b>${p.elevacao!=null?p.elevacao.toFixed(1)+'°':'—'}</b></div>
       <div class="popup-linha">GPS: <b>${p.precisao_gps!=null?p.precisao_gps.toFixed(0)+' m':'—'}</b></div>
       ${p.foto_url?'<div style="margin-top:6px"><a class="popup-link" href="'+p.foto_url+'" target="_blank">📷 Ver foto</a></div>':''}`)
     .addTo(camadas.observadores);
  });

  focoF.forEach(f => {
    const [lon,lat] = f.geometry.coordinates;
    const p = f.properties;
    const cor = COR[p.nivel_confianca]||'#888';
    L.circle([lat,lon], { radius:p.raio_m, color:cor, weight:1.5,
      fillColor:cor, fillOpacity:0.12 }).addTo(camadas.raios);
    L.marker([lat,lon], {icon:iconeFoco})
     .bindPopup(`<div class="popup-titulo">🔥 Foco #${p.id}</div>
       <div class="popup-linha">Confiança: <b style="color:${cor}">${p.nivel_confianca}</b></div>
       <div class="popup-linha">Observações: <b>${p.n_observacoes}</b></div>
       <div class="popup-linha">Dist. média: <b>${p.distancia_media_m?(p.distancia_media_m/1000).toFixed(2)+' km':'—'}</b></div>
       <div style="margin-top:8px"><a class="popup-link" href="https://www.google.com/maps?q=${lat},${lon}" target="_blank">🗺 Abrir no Google Maps</a></div>`)
     .addTo(camadas.focos);
  });

  const lista = document.getElementById('lista-focos');
  lista.innerHTML = focoF.length ? focoF.map(f => {
    const p=f.properties, [lon,lat]=f.geometry.coordinates;
    const cor={alto:'conf-alto',medio:'conf-medio',baixo:'conf-baixo'}[p.nivel_confianca]||'';
    const label={alto:'🟢 Alta',medio:'🟡 Média',baixo:'🔴 Baixa'}[p.nivel_confianca]||'?';
    return `<div class="foco-card" onclick="map.setView([${lat},${lon}],13,{animate:true})">
      <div class="titulo">🔥 Foco #${p.id}<span class="${cor}" style="margin-left:auto;font-size:.75rem">${label}</span></div>
      <div class="linha">Observações: <b>${p.n_observacoes}</b></div>
      <div class="linha">Dist. média: <b>${p.distancia_media_m?(p.distancia_media_m/1000).toFixed(1)+' km':'—'}</b></div>
      <div class="coords-copy" onclick="event.stopPropagation();navigator.clipboard.writeText('${lat},${lon}').then(()=>toast('📋 Coordenadas copiadas!'))">
        📋 ${lat.toFixed(5)}, ${lon.toFixed(5)}</div>
    </div>`;
  }).join('') : '<div class="empty-state">Nenhum foco ainda.</div>';

  if (primeiraVez && geo.features.length > 0) {
    primeiraVez = false;
    const pts = geo.features.filter(f=>f.geometry.type==='Point')
      .map(f=>[f.geometry.coordinates[1],f.geometry.coordinates[0]]);
    if (pts.length) map.fitBounds(L.latLngBounds(pts).pad(0.15));
  }
}

carregar();
setInterval(carregar, 15000);
</script>
</body>
</html>"""