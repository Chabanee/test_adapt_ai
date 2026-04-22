/**
 * Application de visualisation des parcelles cadastrales – Aisne (02)
 * Leaflet + OpenStreetMap + API Django/PostGIS
 */

const API_BASE = "/api";

// Centré sur l'Aisne (département 02)
const MAP_CENTER = [49.5, 3.5];
const MAP_ZOOM = 11;
// Zoom minimum pour charger les parcelles (évite de charger trop de données)
const MIN_ZOOM_LOAD = 14;

// ---- Initialisation de la carte ----
const map = L.map("map").setView(MAP_CENTER, MAP_ZOOM);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  maxZoom: 19,
}).addTo(map);

// Couche GeoJSON des parcelles
const parcellesLayer = L.geoJSON(null, {
  style: defaultStyle,
  onEachFeature: onEachFeature,
}).addTo(map);

let selectedLayer = null;
let loadTimeout = null;
let currentParcelleId = null;

// ---- Styles ----
function defaultStyle() {
  return {
    color: "#1a56db",
    weight: 1,
    opacity: 0.8,
    fillColor: "#93c5fd",
    fillOpacity: 0.25,
  };
}

function selectedStyle() {
  return {
    color: "#dc2626",
    weight: 2,
    opacity: 1,
    fillColor: "#fca5a5",
    fillOpacity: 0.5,
  };
}

// ---- Événements sur chaque feature ----
function onEachFeature(feature, layer) {
  layer.on({
    click: (e) => {
      L.DomEvent.stopPropagation(e);
      selectParcelle(feature, layer);
    },
    mouseover: (e) => {
      if (layer !== selectedLayer) {
        e.target.setStyle({ fillOpacity: 0.5, weight: 2 });
      }
    },
    mouseout: (e) => {
      if (layer !== selectedLayer) {
        parcellesLayer.resetStyle(e.target);
      }
    },
  });
}

// ---- Sélection d'une parcelle ----
function selectParcelle(feature, layer) {
  // Réinitialise l'ancienne sélection
  if (selectedLayer) {
    parcellesLayer.resetStyle(selectedLayer);
  }
  selectedLayer = layer;
  layer.setStyle(selectedStyle());

  const p = feature.properties;
  currentParcelleId = p.id;

  const infoPanel = document.getElementById("info-panel");
  infoPanel.innerHTML = `
    <table>
      <tr><td>IDU</td><td><strong>${p.idu || "—"}</strong></td></tr>
      <tr><td>Section</td><td>${p.section || "—"} – n° ${p.numero || "—"}</td></tr>
      <tr><td>Commune</td><td>${p.nom_com || p.code_com || "—"}</td></tr>
      <tr><td>Superficie</td><td>${p.contenance ? (p.contenance / 10000).toFixed(4) + " ha" : "—"}</td></tr>
    </table>
    <button id="btn-proprietaire" onclick="fetchProprietaire(${p.id})">
      Rechercher le propriétaire (SIREN)
    </button>
  `;

  // Cache le panneau propriétaire précédent
  document.getElementById("proprietaire-panel").classList.add("hidden");
}

// ---- Chargement des parcelles dans la bbox courante ----
function loadParcelles() {
  if (map.getZoom() < MIN_ZOOM_LOAD) {
    showHint(`Zoomez davantage pour afficher les parcelles (zoom ≥ ${MIN_ZOOM_LOAD}).`);
    parcellesLayer.clearLayers();
    return;
  }

  const bounds = map.getBounds();
  const bbox = [
    bounds.getWest().toFixed(6),
    bounds.getSouth().toFixed(6),
    bounds.getEast().toFixed(6),
    bounds.getNorth().toFixed(6),
  ].join(",");

  showLoading(true);

  fetch(`${API_BASE}/parcelles/?bbox=${bbox}`)
    .then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then((geojson) => {
      parcellesLayer.clearLayers();
      parcellesLayer.addData(geojson);
      showLoading(false);

      const count = geojson.count ?? geojson.features?.length ?? 0;
      if (count === 0) {
        showHint("Aucune parcelle dans cette zone. Déplacez ou zoomez la carte.");
      } else {
        showHint(`${count} parcelle(s) chargée(s). Cliquez sur une pour plus d'infos.`);
      }
    })
    .catch((err) => {
      showLoading(false);
      showHint(`Erreur de chargement : ${err.message}`);
    });
}

// ---- Récupération du propriétaire (SIREN) ----
window.fetchProprietaire = function (parcelleId) {
  const btn = document.getElementById("btn-proprietaire");
  if (btn) btn.disabled = true;

  showLoading(true);
  const panel = document.getElementById("proprietaire-panel");
  const content = document.getElementById("proprietaire-content");
  panel.classList.add("hidden");

  fetch(`${API_BASE}/parcelles/${parcelleId}/proprietaire/`)
    .then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then((data) => {
      showLoading(false);
      if (btn) btn.disabled = false;
      panel.classList.remove("hidden");
      content.innerHTML = renderProprietaire(data);
    })
    .catch((err) => {
      showLoading(false);
      if (btn) btn.disabled = false;
      panel.classList.remove("hidden");
      content.innerHTML = `<p class="no-siren">Erreur : ${err.message}</p>`;
    });
};

function renderProprietaire(data) {
  if (!data.siren) {
    return `<p class="no-siren">${data.message || "Aucun SIREN disponible pour cette parcelle."}</p>`;
  }

  const e = data.entreprise;
  let html = `
    <div class="prop-item">
      <div class="prop-label">SIREN</div>
      <div class="prop-value"><span class="siren-badge">${data.siren}</span></div>
    </div>
  `;

  if (e) {
    if (e.nom) html += propRow("Raison sociale", e.nom);
    if (e.siret_siege) html += propRow("SIRET siège", e.siret_siege);
    if (e.activite_principale) html += propRow("Activité (NAF)", e.activite_principale);
    if (e.adresse) html += propRow("Adresse", e.adresse);
    if (e.etat) {
      const actif = e.etat === "A";
      html += propRow("État", `<span style="color:${actif ? "#16a34a" : "#dc2626"}">${actif ? "Actif" : "Fermé"}</span>`);
    }
  }

  return html;
}

function propRow(label, value) {
  return `<div class="prop-item"><div class="prop-label">${label}</div><div class="prop-value">${value}</div></div>`;
}

// ---- UI helpers ----
function showHint(msg) {
  const p = document.getElementById("info-panel");
  // Ne remplace pas si une parcelle est sélectionnée
  if (!currentParcelleId) {
    p.innerHTML = `<p class="hint">${msg}</p>`;
  }
}

function showLoading(visible) {
  document.getElementById("loading").classList.toggle("hidden", !visible);
}

// ---- Déclenchement du chargement avec debounce ----
function scheduleLoad() {
  clearTimeout(loadTimeout);
  loadTimeout = setTimeout(loadParcelles, 400);
}

map.on("moveend", scheduleLoad);
map.on("zoomend", scheduleLoad);

// Chargement initial
scheduleLoad();
