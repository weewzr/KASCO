"""Leaflet map as one HTML string, so it renders the same on a server or in the browser."""
import json

from .data import Network

TEMPLATE = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"/>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<style>
html,body,#map{height:100%;margin:0;background:#0b1626;font-family:Inter,Segoe UI,Arial,sans-serif}
.leaflet-popup-content{font-size:13px;line-height:1.45;margin:10px 12px;min-width:190px}
.leaflet-popup-content b{color:#00205b}.pop-h{font-weight:700;font-size:14px;margin-bottom:3px;color:#00205b}
.pop-s{color:#5b6b80;font-size:12px;margin-bottom:6px}.pop-t{width:100%;border-collapse:collapse}
.pop-t td{padding:1px 0}.pop-t td:last-child{text-align:right;font-variant-numeric:tabular-nums}
.bar{height:6px;background:#e4e9f0;border-radius:3px;margin:6px 0 2px}.bar i{display:block;height:6px;border-radius:3px;background:#0a7c86}
.legend{background:rgba(11,22,38,.9);color:#e8eef6;padding:9px 11px;border-radius:6px;font-size:12px;line-height:1.7}
.legend .d{display:inline-block;width:11px;height:11px;margin-right:7px;vertical-align:-1px}
</style></head><body><div id="map"></div><script>
const D=__DATA__;
const map=L.map('map',{preferCanvas:false,zoomControl:true}).setView([-0.9,113.6],6);
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',{attribution:'&copy; OpenStreetMap &copy; CARTO',maxZoom:12,subdomains:'abcd'}).addTo(map);
const C={farm:'#3fb68b',depot:'#f2b84b',ref:'#ef6b6b',air:'#6db3f2',fd:'#3fb68b',dr:'#f2b84b',ra:'#6db3f2'};
const P=(k,v)=>`<tr><td>${k}</td><td>${v}</td></tr>`;
const bar=u=>`<div class="bar"><i style="width:${Math.min(100,100*u).toFixed(0)}%"></i></div>`;
const fmt=(x,d=1)=>Number(x).toLocaleString('en-GB',{minimumFractionDigits:d,maximumFractionDigits:d});
const mk={};const lay={farm:L.layerGroup(),depot:L.layerGroup(),ref:L.layerGroup(),air:L.layerGroup(),fd:L.layerGroup(),dr:L.layerGroup(),ra:L.layerGroup()};
const maxkt=Math.max(1e-9,...D.fd.map(f=>f.kt),...D.dr.map(f=>f.kt));
const w=(kt,m)=>Math.max(1,Math.min(7,0.8+6*Math.sqrt(kt/m)));
function line(f,c,g,leg,mx){const a=D.pos[f.src],b=D.pos[f.dst];if(!a||!b)return;
 L.polyline([a,b],{color:c,weight:w(f.kt,mx),opacity:.72}).bindPopup(`<div class="pop-h">${f.src} to ${f.dst}</div><div class="pop-s">${leg}</div><table class="pop-t">${P('Flow',fmt(f.kt,1)+' kt/yr')}${P('Road distance',fmt(f.km,0)+' km')}${P('Cost',' USD '+fmt(f.usd_m,2)+'M/yr')}</table>`).addTo(g);}
D.fd.forEach(f=>line(f,C.fd,lay.fd,'Biomass, site to depot',maxkt));
D.dr.forEach(f=>line(f,C.dr,lay.dr,'Pre-processed biomass, depot to refinery',maxkt));
const maxsaf=Math.max(1e-9,...D.ra.map(f=>f.kt));D.ra.forEach(f=>line(f,C.ra,lay.ra,'SAF, refinery to airport',maxsaf));
D.farms.forEach(s=>{L.circleMarker([s.lat,s.lon],{radius:2.5+s.kt/20,color:C.farm,weight:1,fillColor:C.farm,fillOpacity:s.used>0?.75:.18}).bindPopup(`<div class="pop-h">${s.id}</div><div class="pop-s">${s.district}, ${s.province}</div><table class="pop-t">${P('Biomass available',fmt(s.kt,1)+' kt/yr')}${P('Shipped',fmt(s.used,1)+' kt/yr')}</table>${bar(s.used/s.kt)}`).addTo(lay.farm);});
D.depots.forEach(d=>{const s=d.size==='large'?9:6;L.marker([d.lat,d.lon],{icon:L.divIcon({className:'',html:`<div style="width:${s*2}px;height:${s*2}px;background:${C.depot};border:1.5px solid #fff;transform:rotate(45deg)"></div>`,iconSize:[s*2,s*2],iconAnchor:[s,s]})}).bindPopup(`<div class="pop-h">${d.id} depot</div><div class="pop-s">${d.size==='large'?'Large':'Small'}, ${d.lat.toFixed(4)}, ${d.lon.toFixed(4)}</div><table class="pop-t">${P('Capacity',fmt(d.capacity,0)+' kt/yr')}${P('Throughput',fmt(d.throughput,1)+' kt/yr')}${P('Utilisation',fmt(100*d.utilisation,1)+'%')}</table>${bar(d.utilisation)}`).addTo(lay.depot);});
D.refs.forEach(r=>{const s=r.size==='large'?12:9;L.marker([r.lat,r.lon],{zIndexOffset:900,icon:L.divIcon({className:'',html:`<div style="width:${s*2}px;height:${s*2}px;border-radius:3px;background:${C.ref};border:2px solid #fff"></div>`,iconSize:[s*2,s*2],iconAnchor:[s,s]})}).bindPopup(`<div class="pop-h">${r.id} refinery</div><div class="pop-s">${r.size==='large'?'Large':'Small'}, ${r.lat.toFixed(4)}, ${r.lon.toFixed(4)}</div><table class="pop-t">${P('Capacity',fmt(r.capacity,0)+' kt/yr')}${P('Biomass in',fmt(r.biomass_in,1)+' kt/yr')}${P('SAF out',fmt(r.saf_kt,1)+' kt/yr')}${P('Utilisation',fmt(100*r.utilisation,1)+'%')}</table>${bar(r.utilisation)}`).addTo(lay.ref);});
D.air.forEach(a=>{L.marker([a.lat,a.lon],{zIndexOffset:1000,icon:L.divIcon({className:'',html:`<div style="width:26px;height:26px;border-radius:50%;background:${C.air};border:2px solid #fff;color:#00205b;font:700 9px/26px Arial;text-align:center">${a.id}</div>`,iconSize:[26,26],iconAnchor:[13,13]})}).bindPopup(`<div class="pop-h">${a.name}</div><div class="pop-s">${a.city}</div><table class="pop-t">${P('SAF demand',fmt(a.demand,2)+' kt/yr')}${P('SAF delivered',fmt(a.delivered,2)+' kt/yr')}${P('Jet uplift',fmt(a.uplift,1)+' kt/yr')}</table>`).addTo(lay.air);});
Object.values(lay).forEach(g=>g.addTo(map));
L.control.layers(null,{'Biomass sites':lay.farm,'Depots':lay.depot,'Refineries':lay.ref,'Airports':lay.air,'Site to depot flows':lay.fd,'Depot to refinery flows':lay.dr,'Refinery to airport flows':lay.ra},{collapsed:false,position:'topright'}).addTo(map);
const lg=L.control({position:'bottomleft'});lg.onAdd=()=>{const e=L.DomUtil.create('div','legend');e.innerHTML=`<span class="d" style="background:${C.farm};border-radius:50%"></span>Biomass site<br><span class="d" style="background:${C.depot};transform:rotate(45deg)"></span>Depot<br><span class="d" style="background:${C.ref};border-radius:2px"></span>Refinery<br><span class="d" style="background:${C.air};border-radius:50%"></span>Airport<br><span style="color:#9fb2c8">Lines are schematic. Costs use road km.</span>`;return e;};lg.addTo(map);
</script></body></html>"""


def build_map(sol: dict, net: Network, demand: dict, uplift: dict) -> str:
    """Render a solution. With no network it still shows sites and airports."""
    used = {}
    for f in sol.get("flows_fd", []):
        used[f["src"]] = used.get(f["src"], 0) + f["kt"]
    pos = {r.location_id: [r.latitude, r.longitude] for r in net.sites.itertuples()}
    pos.update({r.iata: [r.latitude, r.longitude] for r in net.airports.itertuples()})
    deliv = {}
    for f in sol.get("flows_ra", []):
        deliv[f["dst"]] = deliv.get(f["dst"], 0) + f["kt"]
    data = dict(
        pos=pos,
        farms=[
            dict(id=r.location_id, lat=r.latitude, lon=r.longitude, kt=r.production_kilotons, district=r.district, province=r.province, used=used.get(r.location_id, 0.0))
            for r in net.sites.itertuples()
        ],
        depots=sol.get("depots", []),
        refs=sol.get("refineries", []),
        air=[
            dict(id=r.iata, name=r.brief_name, city=r.city, lat=r.latitude, lon=r.longitude, demand=demand.get(r.iata, 0.0), delivered=deliv.get(r.iata, 0.0), uplift=uplift.get(r.iata, 0.0))
            for r in net.airports.itertuples()
        ],
        fd=sol.get("flows_fd", []),
        dr=sol.get("flows_dr", []),
        ra=sol.get("flows_ra", []),
    )
    return TEMPLATE.replace("__DATA__", json.dumps(data, default=float))
