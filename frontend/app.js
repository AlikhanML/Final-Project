'use strict';
const $=id=>document.getElementById(id);
const icons={search:'<circle cx="10" cy="10" r="7"/><path d="m15 15 6 6"/>',mic:'<rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8"/>',menu:'<path d="M4 6h16M4 12h16M4 18h16"/>',layers:'<path d="m12 3 10 6-10 6L2 9Zm-9 11 9 5 9-5M3 18l9 5 9-5"/>',navigate:'<path d="m3 11 18-8-8 18-2-8Z" fill="currentColor"/>',bookmark:'<path d="M6 3h12v19l-6-5-6 5Z"/>',clock:'<circle cx="12" cy="12" r="9"/><path d="M12 6v7l4 2"/>',satellite:'<path d="m8 8 8 8M4 2l6 6-4 4-6-6Zm14 10 6 6-4 4-6-6ZM8 16a5 5 0 0 0 5 5M3 16a10 10 0 0 0 10 10"/>',grid:'<rect x="3" y="3" width="7" height="7" rx="1" fill="currentColor"/><rect x="14" y="3" width="7" height="7" rx="1" fill="currentColor"/><rect x="3" y="14" width="7" height="7" rx="1" fill="currentColor"/><rect x="14" y="14" width="7" height="7" rx="1" fill="currentColor"/>',route:'<circle cx="6" cy="5" r="3"/><circle cx="18" cy="19" r="3"/><path d="M9 5h6a4 4 0 0 1 0 8H9a4 4 0 0 0 0 6h6"/>',friends:'<circle cx="9" cy="7" r="4"/><path d="M2 22v-3a7 7 0 0 1 14 0v3M16 3a4 4 0 0 1 0 8M19 14a5 5 0 0 1 3 5v3"/>',places:'<path d="M3 22V3h10v19M13 9h8v13M6 7h4M6 11h4M6 15h4M6 19h4M16 13h2M16 17h2"/>',play:'<path d="m7 4 14 8-14 8Z" fill="currentColor"/>',pause:'<path d="M8 4v16M16 4v16" stroke-width="5"/>'};
function icon(name){return `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[name]||icons.navigate}</svg>`;}
icons.chat='<path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H5l1.4-3.1A7.5 7.5 0 1 1 20 11.5Z"/><path d="M9 10h7M9 13h5"/>';
icons.phone='<path d="M8 3H5a1 1 0 0 0-1 1c0 8.8 7.2 16 16 16a1 1 0 0 0 1-1v-3l-4.5-2-1.7 1.7a13 13 0 0 1-6.5-6.5L10 7.5 8 3Z"/>';
document.querySelectorAll('[data-icon]').forEach(e=>e.innerHTML=icon(e.dataset.icon));
function post(type,data={}){window.parent.postMessage({isStreamlitMessage:true,type,...data},'*');}
let p={},map,groups={},target='B',lastPair='',lastTrip=-1,step=0,timer=null,toastTimer,pending=null,light=false,offlineVersion=null;
let simTime=0,lastFrame=null,lastPaint=null,playbackRate=10,vehicleMarker=null,trail=null,trailBorder=null;
let routeDeviation=Infinity,drawnRoute=null,lastVisual='';
let searchTimer=null,selectionEnd=null,lastHeight=0,lastWidth=0,pendingType=null;
let callerEditor=null;
const flags={traffic:true,gps:false,hmm:false,base:true};
function emit(type,data={}){cancelSelection();const id=Date.now()+'-'+Math.random().toString(36).slice(2);pending=id;pendingType=type;if(['route','priority','pick','geocode'].includes(type))$('loading').hidden=false;post('streamlit:setComponentValue',{value:{id,type,...data},dataType:'json'});updateRouteAction();}
function toast(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,4200);}
function applyTheme(){
 const value=String(p.theme||'').trim().toLowerCase();
 const aurora=['aurora','polar','поляр шұғыласы','полярное сияние','northern lights'].includes(value);
 const theme=aurora?'aurora':value==='light'?'light':'dark';
 const nextLight=theme==='light';
 const changed=nextLight!==light;light=nextLight;
 document.body.setAttribute?.('data-theme',theme);
 document.body.style.colorScheme=light?'light':'dark';
 if(changed&&map?._qadamTiles&&(p.carto_key||'').trim()){
   map._qadamTiles.setUrl('https://{s}.basemaps.cartocdn.com/'+(light?'light_all':'dark_all')+'/{z}/{x}/{y}{r}.png?key='+encodeURIComponent(p.carto_key.trim()));
 }
}
function resize(){let h=800;try{h=window.parent.innerHeight-63;}catch(e){}h=Math.max(620,Math.min(960,h));
 const w=window.innerWidth;
 if(h===lastHeight&&w===lastWidth)return;
 lastHeight=h;lastWidth=w;document.body.style.height=h+'px';
 post('streamlit:setFrameHeight',{height:h});if(map)map.invalidateSize({pan:false});}
function cancelSelection(){if(selectionEnd&&map)map.off('moveend',selectionEnd);selectionEnd=null;}
function selectAddress(item){
 if(pending)return;
 cancelSelection();
 if(rejectCallExclusion(item.lat,item.lng))return;
 map.stop();stop();clearTimeout(searchTimer);closeSheet();$('search').blur();
 if(p.reduced_motion){map.setView([item.lat,item.lng],16,{animate:false});choose(item.lat,item.lng,'B',item.name);return;}
 const finish=()=>{cancelSelection();choose(item.lat,item.lng,'B',item.name);};
 selectionEnd=finish;
 // Attach before starting: Leaflet may complete synchronously for a tiny move.
 map.once('moveend',finish);
 const reduced=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
 const center=map.getCenter();
 if(map.getZoom()===16&&Math.abs(center.lat-item.lat)<1e-7&&Math.abs(center.lng-item.lng)<1e-7){finish();return;}
 map.flyTo([item.lat,item.lng],16,{animate:!reduced,duration:.8});
}

// Leaflet's stock marker rounds coordinates; retain fractional pixels for the vehicle.
function smoothVehicleMarker(position,options){
 const marker=L.marker(position,options);
 marker.update=function(){
   if(this._icon&&this._map){
     const point=this._map.project(this._latlng,this._map.getZoom()).subtract(this._map.getPixelOrigin());
     this._setPos(point);
   }
   return this;
 };
 return marker;
}
let frameProbe=null,performanceRecording=null;
let performanceResults=[];
try{
 const stored=JSON.parse(localStorage.getItem('qadam-frame-results-v1')||'[]');
 if(Array.isArray(stored))performanceResults=stored.filter(r=>r&&r.context&&Number.isFinite(r.fps)&&Number.isFinite(r.p95_ms)&&Number.isFinite(r.max_ms)&&Number.isFinite(r.slow_frames)).slice(-2);
}catch(e){} // Storage can be unavailable in embedded/private browser sessions.
function performanceContext(){
 return {build:'selective-layers-measure-v1',dataset:p.dataset_version,zoom:map.getZoom(),
 width:window.innerWidth,height:lastHeight,traffic:flags.traffic,gps:flags.gps,hmm:flags.hmm,
 trip:!!p.trip,rate:playbackRate};
}
function beginPerformanceCheck(){
 if(performanceRecording)return;
 performanceRecording={meter:QadamPlayback.frameRecording(),context:performanceContext()};
 closeSheet();toast('20 секунд: картаны бірдей бағытта алға-артқа жылжытыңыз. Вкладканы ауыстырмаңыз.');
}
function recordPerformanceFrame(now){
 if(!performanceRecording)return;
 const stats=performanceRecording.meter.push(now);if(!stats)return;
 if(JSON.stringify(performanceRecording.context)!==JSON.stringify(performanceContext())){
   performanceRecording=null;toast('Өлшеу баптаулары өзгерді. Бірдей масштаб пен қабаттарды сақтап, қайта бастаңыз.');return;
 }
 performanceResults.push({...stats,context:performanceRecording.context,created:new Date().toISOString()});
 performanceResults=performanceResults.slice(-2);performanceRecording=null;
 try{localStorage.setItem('qadam-frame-results-v1',JSON.stringify(performanceResults));}catch(e){}
 toast('Өлшеу дайын: qadam → Бірқалыптылықты тексеру.');
}
function performancePanel(){
 const c=sheet('Бірқалыптылықты тексеру');
 paragraph(c,'20 секунд бойы картаны бірдей аумақта алға-артқа жылжытыңыз. Екі өлшеуде масштаб, терезе өлшемі және қабаттар бірдей болсын. Бұл RAF шақыру жиілігі, GPU шығарған кадрлардың тікелей өлшемі емес.');
 action(c,performanceRecording?'Өлшеніп жатыр…':'20 секунд өлшеу',beginPerformanceCheck,false,!!performanceRecording);
 performanceResults.forEach((r,i)=>{
   paragraph(c,`${i===performanceResults.length-1?'Соңғы':'Алдыңғы'} өлшеу: RAF ${r.fps.toFixed(1)} /с · p95 ${r.p95_ms.toFixed(1)} мс · ең ұзақ ${r.max_ms.toFixed(1)} мс · 25 мс-тан ұзақ ${r.slow_frames} кадр аралығы.`);
   paragraph(c,`Масштаб: ${r.context.zoom} · Кептеліс: ${r.context.traffic?'қосулы':'өшірулі'} · ${r.context.width} × ${r.context.height}`);
 });
 if(performanceResults.length===2){
   const [a,b]=performanceResults;
   if(JSON.stringify(a.context)!==JSON.stringify(b.context))paragraph(c,'Шарттар әртүрлі: нәтижелерді тікелей салыстыруға болмайды. Бірдей баптаулармен қайта өлшеңіз.');
   else paragraph(c,`RAF айырмасы: ${(b.fps-a.fps).toFixed(1)} /с · p95 айырмасы: ${(b.p95_ms-a.p95_ms).toFixed(1)} мс (төмендегені жақсы). Бұл екі қолмен жасалған өлшеу, бұрынғы нұсқамен автоматты салыстыру емес.`);
 }
 paragraph(c,'p95 — кадр аралықтарының 95%-ы осы уақыттан аспайды. 60 Гц үшін қалыпты аралық шамамен 16,7 мс.');
}

function startFrameProbe(){
 if(frameProbe!==null)return;
 const badge=document.createElement('div');badge.id='frame-cadence';badge.hidden=true; // Diagnostics remain available in the performance panel.
 badge.textContent='RAF …';
 badge.title='Браузердің requestAnimationFrame жиілігі. Бұл GPU көрсеткен нақты кадр санын өлшемейді.';
 $('screen').appendChild(badge);
 const meter=QadamPlayback.frameMeter();
 const measure=now=>{
   recordPerformanceFrame(now);
   const result=meter.push(now);
   if(result)badge.textContent=`RAF ${result.fps} · ${result.slow} баяу`;
   frameProbe=requestAnimationFrame(measure);
 };
 document.addEventListener('visibilitychange',()=>{
   meter.reset();
   if(document.hidden){cancelAnimationFrame(frameProbe);frameProbe=null;badge.textContent='RAF —';
     if(performanceRecording){performanceRecording=null;toast('Вкладка жасырылды: өлшеу тоқтатылды. Қайта бастаңыз.');}
   }
   else if(frameProbe===null)frameProbe=requestAnimationFrame(measure);
 });
 frameProbe=requestAnimationFrame(measure);
}
let vehicleHeading=null,vehicleHeadingStep=-1;
// Both priorities use the same body and light bar. Only the lenses light up.
const ambulanceIcon=`
 <div class="vehicle vehicle-ambulance">
  <svg viewBox="0 0 40 56" role="img" aria-label="Жедел жәрдем">
   <rect x="4" y="10" width="5" height="10" rx="2" fill="#16283a"/>
   <rect x="31" y="10" width="5" height="10" rx="2" fill="#16283a"/>
   <rect x="4" y="36" width="5" height="10" rx="2" fill="#16283a"/>
   <rect x="31" y="36" width="5" height="10" rx="2" fill="#16283a"/>
   <rect x="8" y="2" width="24" height="52" rx="7" fill="#f5f8fc" stroke="#193953" stroke-width="2"/>
   <path d="M11 12h18l-2 10H13Z" fill="#70c9ed" stroke="#315e7c" stroke-width="1.5"/>
   <rect x="9" y="24" width="22" height="6" rx="2" fill="#17283c"/>
   <g class="emergency-light emergency-light-blue">
    <rect x="10" y="25" width="9" height="4" rx="1"/>
    <path class="emergency-light-core" d="M12 26h5v2h-5Z"/>
   </g>
   <g class="emergency-light emergency-light-red">
    <rect x="21" y="25" width="9" height="4" rx="1"/>
    <path class="emergency-light-core" d="M23 26h5v2h-5Z"/>
   </g>
   <path d="M8 32v13m24-13v13" stroke="#f05c56" stroke-width="3"/>
   <path d="M20 34v11m-5.5-5.5h11" stroke="#2785da" stroke-width="4"/>
   <rect x="13" y="48" width="14" height="3" rx="1" fill="#8daec2"/>
   <path d="M12 6h4m8 0h4" stroke="#ffde84" stroke-width="2"/>
  </svg>
 </div>`;
function orientVehicle(path,index,reset=false){
 const target=QadamPlayback.heading(path,index);
 const body=vehicleMarker?.getElement?.()?.querySelector('.vehicle-ambulance');
 if(!body||target===null)return;
 const snap=reset||index<vehicleHeadingStep||vehicleHeading===null;
 const next=QadamPlayback.unwrapHeading(snap?null:vehicleHeading,target);
 const reduced=!!p.reduced_motion||!!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
 if(snap||next!==vehicleHeading){
   body.style.transition=snap||reduced?'none':'transform 140ms linear';
   body.style.transform=`rotate(${next}deg)`;
 }
 vehicleHeading=next;vehicleHeadingStep=index;
}
function updateVehiclePriority(){
 const body=vehicleMarker?.getElement?.()?.querySelector('.vehicle-ambulance');
 if(!body)return;
 const urgent=(p.trip?.priority||p.priority)==='urgent';
 body.classList.toggle('vehicle-urgent',urgent);
 body.classList.toggle('vehicle-reduced-motion',!!p.reduced_motion);
 body.querySelector('svg')?.setAttribute('aria-label',urgent?'Шұғыл жедел жәрдем':'Қалыпты жедел жәрдем');
}
function clearGroup(name){groups[name]?.clearLayers();}
function init(){
 const reduced=!!p.reduced_motion||!!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
 map=L.map('map',{zoomControl:false,preferCanvas:true,zoomAnimation:!reduced,fadeAnimation:false,markerZoomAnimation:!reduced})
   .setView(p.city?[51.14,71.43]:[51.130,71.418],p.city?11:14);
 map.attributionControl?.setPrefix('<a href="https://leafletjs.com" target="_blank" rel="noopener">Leaflet</a>');
 // Fallback must be BELOW the opaque raster tiles, above the map background.
 const pane=map.createPane('roadFallback');pane.style.zIndex='150';pane.style.pointerEvents='none';
 const fallbackRenderer=L.canvas({pane:'roadFallback'});
 ['offline','coverage','traffic','hmm','gps','route','markers','vehicle','pendingCall'].forEach(n=>groups[n]=L.layerGroup().addTo(map));
 map._qadamFallbackRenderer=fallbackRenderer;
 const trafficPane=map.createPane('trafficFlow');trafficPane.style.zIndex='350';trafficPane.style.pointerEvents='none';
 map._qadamTrafficRenderer=L.canvas({pane:'trafficFlow',padding:.5});
 // Route paths use SVG so incremental drawing does not depend on canvas dirty regions.
 const routePane=map.createPane('routeLines');routePane.style.zIndex='420';routePane.style.pointerEvents='none';
 map._qadamRouteRenderer=L.svg({pane:'routeLines',padding:.5});
 const cartoKey=(p.carto_key||'').trim();
 const tileUrl=cartoKey
   ? 'https://{s}.basemaps.cartocdn.com/'+(light?'light_all':'dark_all')+'/{z}/{x}/{y}{r}.png?key='+encodeURIComponent(cartoKey)
   : 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
 const tiles=L.tileLayer(tileUrl,{
   subdomains:'abcd',className:cartoKey?'qadam-carto-tiles':'qadam-osm-tiles',
   maxZoom:cartoKey?20:19,updateWhenIdle:false,updateInterval:50,updateWhenZooming:false,keepBuffer:4,
   attribution:'© <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors'
     +(cartoKey?' · © <a href="https://carto.com/attribution/" target="_blank">CARTO</a>':'')
 });
 // A modest half-tile look-ahead at the current zoom, not an offline download.
 // keepBuffer retains old tiles but does not request unseen neighbouring tiles.
 map._qadamTiles=tiles;
 const viewportBounds=tiles._getTiledPixelBounds;
 tiles._getTiledPixelBounds=function(center){
   const bounds=viewportBounds.call(this,center);
   const margin=L.point(128,128);
   return L.bounds(bounds.min.subtract(margin),bounds.max.add(margin));
 };
 const retries=new Map(),attempts=new WeakMap();
 tiles.on('tileerror',event=>{
   const tile=event.tile;tile.style.visibility='hidden';
   const attempt=attempts.get(tile)||0;
   if(attempt>=2||retries.has(tile))return;
   attempts.set(tile,attempt+1);
   // Retry only this visible failed tile, never redraw/re-fetch the entire city.
   const url=tile.src;
   retries.set(tile,setTimeout(()=>{
     retries.delete(tile);
     if(tile.isConnected)tile.src=url;
   },attempt===0?1500:6000));
 });
 tiles.on('tileload',event=>{
   event.tile.style.visibility='';
   if(retries.has(event.tile))clearTimeout(retries.get(event.tile));
   retries.delete(event.tile);
 });
 tiles.on('tileunload',event=>{
   if(retries.has(event.tile))clearTimeout(retries.get(event.tile));
   retries.delete(event.tile);
 });
 tiles.addTo(map);
 map.on('unload',()=>{for(const timer of retries.values())clearTimeout(timer);retries.clear();});
 map.on('zoomend',updateTrafficStyle);
 map.on('moveend',drawCityTraffic);
 map.on('dragstart',()=>{cancelSelection();});
 map.on('click',e=>choose(e.latlng.lat,e.latlng.lng,'B'));
 startFrameProbe();
}
function offlineRoads(){
 if(!p.roads||!map)return;
 const version=p.dataset_version||p.roads;
 if(offlineVersion===version)return;
 clearGroup('offline');
 L.polyline(p.roads,{pane:'roadFallback',renderer:map._qadamFallbackRenderer,
   smoothFactor:1,color:'#677b84',weight:2,opacity:.65,interactive:false}).addTo(groups.offline);
 offlineVersion=version;
}

function pointInGeometry(lat,lng,geometry){
 if(!Number.isFinite(lat)||!Number.isFinite(lng)||!geometry)return false;
 function ringState(ring){
   let inside=false;
   for(let i=0,j=ring.length-1;i<ring.length;j=i++){
     const [x,y]=ring[i],[a,b]=ring[j];
     const cross=(lng-x)*(b-y)-(lat-y)*(a-x);
     if(Math.abs(cross)<1e-12&&lng>=Math.min(x,a)-1e-12&&lng<=Math.max(x,a)+1e-12&&lat>=Math.min(y,b)-1e-12&&lat<=Math.max(y,b)+1e-12)return 2;
     if((y>lat)!==(b>lat)&&lng<(a-x)*(lat-y)/(b-y)+x)inside=!inside;
   }
   return inside?1:0;
 }
 const polygons=geometry.type==='Polygon'?[geometry.coordinates]:geometry.type==='MultiPolygon'?geometry.coordinates:[];
 return polygons.some(rings=>{const outer=ringState(rings[0]);if(!outer)return false;if(outer===2)return true;
   for(const hole of rings.slice(1)){const state=ringState(hole);if(state===2)return true;if(state===1)return false;}return true;});
}
function rejectCallExclusion(lat,lng){
 if(!pointInGeometry(lat,lng,p.call_exclusion))return false;
 toast(p.call_exclusion_message);
 return true;
}
function choose(lat,lng,which,placeName=null){
 if(pending)return false;
 cancelSelection();
 if(!pointInGeometry(lat,lng,p.city_boundary)){
   toast(p.outside_city_message||'Тек Астанада қаласында шақырту нүктесің таңдай аласыз');return false;
 }
 if(rejectCallExclusion(lat,lng))return false;
 const [w,s,e,n]=p.bbox||[71.395,51.12,71.44,51.14];
 if(lat<s||lat>n||lng<w||lng>e){
   toast(p.city?'Астана жол базасының қамтуынан тыс.':'AI баптауларынан Астана жолдарын жүктеңіз.');return false;
 }
 stop();
 clearGroup('pendingCall');
 if(groups.pendingCall)pin([lat,lng],true,groups.pendingCall);
 emit('pick',{target:'B',lat,lng,place_name:placeName});target='B';closeSheet();hint();return true;
}
function hint(){$('hint').hidden=!!p.b;$('hint').textContent='Картадан шақырту орнын таңдаңыз';}
function pin(point,end=false,group=groups.markers){
 if(!point)return;
 const icon=end?'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/></svg>':'✚';
 const preview=group===groups.pendingCall;
 const title=preview?'Маршрут есептелуде…':end?'Шақырту орны':'Аурухана';
 L.marker(point,{title,alt:title,interactive:!preview,keyboard:!preview,opacity:preview ? .65 : 1,
   icon:L.divIcon({html:`<div class="pin ${end?'end':''}">${icon}</div>`,className:'',iconSize:[36,36],iconAnchor:[18,18]})}).addTo(group);
}
const trafficColors=['#46b77b','#ffd34f','#ee913e','#ff554f'];
// Free-flow roads recede so queues remain visible at city scale.
// Styling runs on zoomend only; geometry and routing never change here.
function trafficStyle(band){
 const zoom=map?.getZoom?.()??14;
 const width=zoom<=12?.65:zoom<=14?1:zoom<=16?1.5:2;
 return {color:trafficColors[band],
   weight:band===0?width*.7:width*1.2,
   opacity:band===0?(zoom<=12?.2:.4):(zoom<=12?.75:.94),
   lineCap:'round',lineJoin:'round'};
}
function updateTrafficStyle(){
 groups.traffic?.eachLayer(layer=>layer.setStyle(trafficStyle(layer._trafficBand)));
}
let trafficIndex=null,trafficSourceKey=null,trafficSource=null,trafficViewKey=null,trafficSourceDataset=null;
function drawCityTraffic(){
 if(!map)return;
 const source=p.traffic_packed||p.traffic_bands;
 const sourceKey=p.traffic_key?JSON.stringify([p.dataset_version,p.traffic_key]):null;
 const keepPrevious=!!trafficIndex&&trafficSourceDataset===p.dataset_version&&!!(p.traffic_pending||p.traffic_error);
 if(!keepPrevious&&(!trafficIndex||(sourceKey===null?trafficSource!==source:trafficSourceKey!==sourceKey))){
   const bands=p.traffic_packed?QadamTrafficView.unpack(p.traffic_packed):source||[[],[],[],[]];
   trafficIndex=QadamTrafficView.build(bands);trafficSource=source;trafficSourceKey=sourceKey;trafficViewKey=null;trafficSourceDataset=p.dataset_version;
 }
 const zoom=map.getZoom?.()??14;
 const key=JSON.stringify([zoom,flags.traffic]);
 if(key===trafficViewKey)return;
 trafficViewKey=key;clearGroup('traffic');
 if(!flags.traffic)return;
 // Keep the entire city geometry attached; Leaflet clips it to the canvas.
 const visible=trafficIndex.query(null);
 visible.forEach((lines,i)=>{
   if(!lines.length)return;
   const layer=L.polyline(lines,{
     pane:'trafficFlow',renderer:map._qadamTrafficRenderer,smoothFactor:zoom<=12?2.5:1,
     ...trafficStyle(i),interactive:false
   });
   layer._trafficBand=i;layer.addTo(groups.traffic);
 });
}

// Each layer has its own identity; unrelated updates keep existing Leaflet objects.
const layerKeys=new Map();
function layerChanged(name,parts){
 const key=JSON.stringify(parts);
 if(layerKeys.get(name)===key)return false;
 layerKeys.set(name,key);return true;
}
function draw(){
 if(!map)return;
 if(layerChanged('coverage',[p.dataset_version,p.city,p.bbox])){
   clearGroup('coverage');
   if(p.bbox&&!p.city){const[w,s,e,n]=p.bbox;L.rectangle([[s,w],[n,e]],{smoothFactor:0,color:'#46c97a',weight:1,dashArray:'5 7',fill:false,interactive:false,opacity:.6}).addTo(groups.coverage);}
 }
 if(layerChanged('markers',[p.a,p.b,p.snap_a,p.snap_b,p.hospital?.name])){
   clearGroup('markers');pin(p.a);pin(p.b,true);
   if(p.a&&p.hospital)L.tooltip({permanent:true,direction:'top',offset:[0,-20]}).setLatLng(p.a).setContent(document.createTextNode(p.hospital.name)).addTo(groups.markers);
   [[p.a,p.snap_a],[p.b,p.snap_b]].forEach(([a,b])=>{if(a&&b)L.polyline([a,b],{smoothFactor:0,color:'#c9dccf',weight:1,dashArray:'3 5',interactive:false}).addTo(groups.markers);});
 }
 const tripChanged=layerChanged('trip',[p.dataset_version,p.trip_id,!!p.trip]);
 const routeVisibilityChanged=layerChanged('planned-route',[flags.base]);
 drawCityTraffic();
 const sensorsChanged=layerChanged('sensors',[flags.gps,flags.hmm]);
 const endpointsChanged=layerChanged('empty-status',[p.a,p.b]);
 if(tripChanged||routeVisibilityChanged||sensorsChanged||(!p.trip&&endpointsChanged))drawStep(tripChanged);
 offlineRoads();
}
const sensorState={};
function drawSensor(name,points,enabled,index,reset){
 const previous=sensorState[name];
 let from=previous?.step??-1;
 if(reset||!previous||previous.enabled!==enabled||index<from){clearGroup(name);from=-1;}
 if(enabled)for(let i=from+1;i<=index;i++){
   L.circleMarker(points[i],{color:name==='hmm'?'#b891ff':'#f99759',radius:3,weight:1,fill:true,interactive:false}).addTo(groups[name]);
 }
 sensorState[name]={step:index,enabled};
}
// Report becomes visible only at the end of playback, including failed trips.
function updateTripReport(tr){
 const visible=!!tr&&simTime>=tr.elapsed_s;
 $('trip-report').hidden=!visible;
 if(!visible)return;
 const reasons={localization_stop:'GPS орны сенімді анықталмады',no_route:'Қолжетімді маршрут жоқ',no_valid_actions:'Рұқсат етілген бағыт жоқ',step_limit:'Қадам лимитіне жетті',compute_limit:'Есептеу уақытының лимитіне жетті'};
 $('report-status').textContent=tr.reached?'Мақсатқа жетті':'Мақсатқа жеткен жоқ · '+(reasons[tr.status]||'Сапар тоқтады');
 $('report-distance').textContent=Number.isFinite(tr.km)&&tr.km>=0?tr.km.toFixed(2)+' км':'—';
 $('report-time').textContent=Number.isFinite(tr.elapsed_s)&&tr.elapsed_s>=0?QadamPlayback.formatTime(tr.elapsed_s):'—';
}
function samePosition(a,b){
 return !!a&&!!b&&a[0]===b[0]&&a[1]===b[1];
}
function firstDeviation(path,plan){
 let planned=0;
 for(let i=0;i<path.length;i++){
   if(i>0&&samePosition(path[i],path[i-1]))continue;
   if(!samePosition(path[i],plan[planned++]))return i;
 }
 return Infinity;
}
function drawRoute(tr,motion,force){
 if(force||!trail){
   clearGroup('route');
   const options={renderer:map?._qadamRouteRenderer,pane:'routeLines',noClip:true,
     interactive:false,smoothFactor:0,lineCap:'round',lineJoin:'round'};
   trailBorder=L.polyline([],{...options,color:'#0f172a',weight:8}).addTo(groups.route);
   trail=L.polyline([],{...options,color:'#3B82F6',weight:5}).addTo(groups.route);
   routeDeviation=firstDeviation(tr.path,tr.base||[]);
   drawnRoute=null;
 }
 const {index,fraction,position}=motion;
 // Use the initial plan until the vehicle takes a different edge.
 const deviated=index>=routeDeviation||(index+1===routeDeviation&&fraction>0);
 const showSimulated=deviated||!tr.base?.length||simTime>=tr.elapsed_s;
 const fullPath=flags.base?(showSimulated?tr.path:tr.base):null;
 const key=flags.base?(showSimulated?'simulated':'planned'):(index+':'+fraction);
 if(key===drawnRoute)return;
 const geometry=fullPath||tr.path.slice(0,index+1);
 if(!fullPath&&!samePosition(tr.path[index],position))geometry.push(position);
 trailBorder.setLatLngs(geometry);
 trail.setLatLngs(geometry);
 drawnRoute=key;
}
function drawStep(force=false,updateUI=true){
 if(updateUI)updateRouteAction();
 const tr=p.trip;$('playback').hidden=!tr;
 if(updateUI)updateTripReport(tr);
 if(!tr){
   for(const name of ['route','hmm','gps','vehicle'])clearGroup(name);
   vehicleMarker=trail=trailBorder=drawnRoute=null;simTime=0;
   delete sensorState.gps;delete sensorState.hmm;vehicleHeading=null;vehicleHeadingStep=-1;
   $('route-title').textContent=p.a&&p.b?'Маршрутты есептеу':p.b?'Қолжетімді маршрут жоқ':'Шақырту бағыты';
   $('route-sub').textContent='Тек шақырту орнын таңдаңыз · Старт автоматты';$('distance').textContent='—';return;
 }
 simTime=Math.max(0,Math.min(simTime,tr.elapsed_s));
 if(tr.elapsed_s-simTime<1e-6)simTime=tr.elapsed_s;
 const motion=QadamPlayback.sample(tr.path,tr.timestamps_s,simTime,tr.stop_delays_s||tr.turn_delays_s);step=motion.index;
 drawRoute(tr,motion,force);
 drawSensor('hmm',tr.hmm,flags.hmm,step,force);
 drawSensor('gps',tr.gps,flags.gps,step,force);
 if(!vehicleMarker){
   vehicleMarker=smoothVehicleMarker(motion.position,{
     icon:L.divIcon({html:ambulanceIcon,className:'',iconSize:[36,50],iconAnchor:[18,25]}),
     title:'Жедел жәрдем',alt:'Жедел жәрдем көлігі'
   }).addTo(groups.vehicle);
 }
 vehicleMarker.setLatLng(motion.position);
 updateVehiclePriority();
 orientVehicle(tr.path,step,force);
 if(!updateUI)return;
 let phase=tr.phases[Math.min(step+1,tr.phases.length-1)]?'Q-learning':'A*';
 if(tr.fallback!==null&&step>=tr.fallback)phase='A* резерві';
 if(tr.path[step+1]&&tr.path[step][0]===tr.path[step+1][0]&&tr.path[step][1]===tr.path[step+1][1])phase='GPS орны нақтылануда';
 if((tr.recovery_events||[]).some(event=>event.index===step+1))phase='GPS қайта анықтау';
 if((tr.turn_delays_s?.[step]||0)>simTime-tr.timestamps_s[step]-(tr.signal_delays_s?.[step]||0))phase='Бұрылыс · '+({left:'солға',right:'оңға',uturn:'кері'}[tr.turn_kinds?.[step]]||'күту');
 if((tr.signal_delays_s?.[step]||0)>simTime-tr.timestamps_s[step])phase='Қызыл бағдаршам · күту';
 const finished=simTime>=tr.elapsed_s;
 $('route-title').textContent=finished?(tr.reached?'Мақсатқа жетті':({localization_stop:'GPS орны анық емес · қозғалыс тоқтады',no_route:'Қолжетімді маршрут жоқ',no_valid_actions:'Рұқсат етілген бағыт жоқ',step_limit:'Қадам лимиті аяқталды',compute_limit:'Есептеу лимиті · толық симуляция аяқталмады'}[tr.status]||'Сапар тоқтады')):'Жедел жәрдем · маршрут';
 $('route-sub').textContent=finished&&!tr.reached?'Мақсатқа жеткен жоқ · GPS шуын азайтып, қайта есептеңіз':tr.reached?`${phase} · ${QadamPlayback.remainingKm(tr.path,motion).toFixed(2)} км қалды`:`${phase} · Маршрут толық емес`;
 $('distance').textContent=tr.reached?QadamPlayback.remainingKm(tr.path,motion).toFixed(2)+' км':'—';
 $('progress').max=tr.elapsed_s;$('progress').value=simTime;$('progress').disabled=tr.elapsed_s===0;

 $('step').textContent=QadamPlayback.formatTime(simTime)+' / '+QadamPlayback.formatTime(tr.elapsed_s);
}
function stop(){if(timer!==null)cancelAnimationFrame(timer);timer=null;lastFrame=null;lastPaint=null;updateRouteAction();}
function tick(now){
 if(!p.trip){stop();return;}
 if(lastFrame!==null)simTime=QadamPlayback.advance(simTime,(now-lastFrame)/1000,playbackRate,p.trip.elapsed_s);
 lastFrame=now;
 // Animate at display cadence; text/progress need only 10 updates per second.
 const updateUI=lastPaint===null||now-lastPaint>=100||simTime>=p.trip.elapsed_s;
 drawStep(false,updateUI);if(updateUI)lastPaint=now;
 if(simTime>=p.trip.elapsed_s){stop();toast(p.trip.reached?'Мақсатқа жетті':'Мақсатқа жеткен жоқ · сапар тоқтатылды');return;}
 timer=requestAnimationFrame(tick);
}
function play(){
 if(!p.trip){openRoute();toast('Алдымен маршрутты есептеңіз.');return;}
 if(timer!==null){stop();return;}
 if(p.trip.elapsed_s===0){drawStep();return;}
 if(simTime>=p.trip.elapsed_s)simTime=0;
 lastFrame=null;timer=requestAnimationFrame(tick);updateRouteAction();
}
function closeSheet(){callerEditor=null;$('sheet').hidden=true;}
function sheet(title){callerEditor=null;$('sheet-title').textContent=title;$('sheet-content').replaceChildren();$('sheet').hidden=false;return $('sheet-content');}
function paragraph(parent,text){const e=document.createElement('p');e.textContent=text;parent.appendChild(e);}
function action(parent,text,fn,secondary=false,disabled=false){const b=document.createElement('button');b.className='big'+(secondary?' secondary':'');b.textContent=text;b.disabled=disabled;b.onclick=fn;parent.appendChild(b);return b;}
function routeActionState(){
 if(pending)return {label:'Өңделуде…',disabled:true};
 if(!p.b)return {label:'Шақырту орнын таңдаңыз',disabled:true};
 if(!p.hospital)return {label:'Қолжетімді маршрут жоқ',disabled:true};
 if(!p.trip)return {label:'Маршрутты есептеу',disabled:false};
 if(!(p.trip.elapsed_s>0))return {label:'Қозғалыс дерегі жоқ',disabled:true};
 return {label:timer!==null?'Кідірту':simTime>=p.trip.elapsed_s?'Симуляцияны қайта ойнату':simTime>0?'Қозғалысты жалғастыру':'Маршрутты бастау',disabled:false};
}
function formatEtaDuration(seconds){
 return seconds<60?`${seconds.toFixed(1)} с`:`${(seconds/60).toFixed(1)} мин`;
}
function etaExplanation(trip){
 const d=trip?.eta_breakdown;if(!d)return '';
 if(d.traffic_delay_s<.005&&!(d.normal_signal_delay_s>0))return 'Маршрутта кептеліс кідірісі жоқ: екі режимнің ETA-сы бірдей болуы мүмкін.';
 const delay=d.traffic_delay_s.toFixed(1);
 if(Number.isFinite(d.normal_same_path_s)&&Number.isFinite(d.urgent_same_path_s)){
   const saving=Math.max(0,d.normal_same_path_s-d.urgent_same_path_s);
   return `Осы маршрутта: қалыпты ${formatEtaDuration(d.normal_same_path_s)} · шұғыл ${formatEtaDuration(d.urgent_same_path_s)} · үнем ${formatEtaDuration(saving)}. Кептеліс кідірісі: +${formatEtaDuration(d.traffic_delay_s)} (модель).${d.normal_signal_delay_s>0?` Қалыпты режимдегі бағдаршам: +${formatEtaDuration(d.normal_signal_delay_s)} (модель).`:""}`;
 }
 return trip.priority==='urgent'
   ? `Кептеліс: +${delay} с · Осы жолда үнем: ${formatEtaDuration(d.same_path_saving_s)}`
   : `Кептеліс кідірісі: +${delay} с · Шұғыл режимде азаяды`;
}
function updatePriorityBadges(){
 for(const value of ['normal','urgent']){
   const button=$('priority-'+value);if(!button)continue;
   button.disabled=!p.b||!!pending;
   button.setAttribute?.('aria-pressed',String((p.priority==='urgent'?'urgent':'normal')===value));
 }
}
function updateRouteSummary(){
 updatePriorityBadges();
 updateVehiclePriority();
 // ETA is data, not a map layer: refresh even when the road geometry is unchanged.
 const eta=$('eta-chip'),hasEta=Number.isFinite(p.trip?.eta_plan_s);
 if(eta){eta.textContent=pending?'Есептелуде…':hasEta?'≈ '+formatEtaDuration(p.trip.eta_plan_s):'—';
 eta.title=hasEta?`${formatEtaDuration(p.trip.eta_plan_s)} · ${p.trip.priority==='urgent'?'Шұғыл':'Қалыпты'}`:'';}
 const explanation=$('eta-explanation');if(explanation)explanation.textContent=etaExplanation(p.trip);
 const priority=$('call-priority');if(priority){priority.value=p.priority==='urgent'?'urgent':'normal';
 priority.disabled=!p.b||!!pending;priority.setAttribute?.('data-priority',priority.value);}
 $('summary-hospital').textContent=p.hospital?.name||'Автоматты таңдалады';
 $('summary-destination').textContent=callAddressText();
}
function updateRouteAction(){
 updatePriorityBadges();
 updateCallerContact();
 const button=$('route-action'),state=routeActionState();
 if(button.textContent!==state.label)button.textContent=state.label;
 button.disabled=state.disabled;
 if($('call-priority'))$('call-priority').disabled=!p.b||!!pending;
}
function updateCallerContact(){
 const panel=$('caller-contact'),chat=$('caller-chat'),call=$('caller-call');
 if(!panel||!chat||!call)return;
 panel.hidden=!p.b;
 chat.disabled=call.disabled=!p.b||!!pending;
}
function formatCallerDigits(value){
 const digits=value.replace(/[^0-9]/g,'').slice(0,10);
 return [digits.slice(0,3),digits.slice(3,6),digits.slice(6)].filter(Boolean).join(' ');
}
function openCallerContact(mode){
 if(!p.b||pending)return;
 const chat=mode==='chat';
 const body=sheet(chat?'Шақырған адамға жазу':'Шақырған адамға қоңырау шалу');
 const contact={point:[...p.b],call_id:p.focus?.id??null};
 callerEditor=contact;
 const label=document.createElement('label');
 label.className='caller-form-label';
 label.htmlFor='caller-phone-input';
 label.textContent='Телефон нөмірі';
 const number=document.createElement('div');
 number.className='caller-number';
 const prefix=document.createElement('span');
 prefix.id='caller-phone-prefix';
 prefix.textContent='+7';
 const input=document.createElement('input');
 input.id='caller-phone-input';
 input.type='tel';
 input.inputMode='numeric';
 input.autocomplete='off';
 input.placeholder='775 755 0555';
 input.setAttribute('aria-describedby',prefix.id);
 input.value=formatCallerDigits((p.caller_phone||'').slice(2));
 number.append(prefix,input);
 body.append(label,number);
 let message=null;
 if(chat){
   const messageLabel=document.createElement('label');
   messageLabel.className='caller-form-label';
   messageLabel.htmlFor='caller-message';
   messageLabel.textContent='Хабарлама';
   message=document.createElement('textarea');
   message.id='caller-message';
   message.rows=4;
   message.maxLength=1000;
   body.append(messageLabel,message);
 }
 const launch=document.createElement('a');
 launch.className='caller-launch';
 launch.target='_blank';
 launch.rel='noopener noreferrer';
 launch.textContent=chat?'WhatsApp-та жалғастыру':'Қоңырау шалу';
 const refresh=()=>{
   const phone=input.value.replace(/[^0-9]/g,'');
   const draft=message?.value.trim()||'';
   const ready=phone.length===10&&(!chat||draft.length>0);
   launch.setAttribute('aria-disabled',String(!ready));
   if(!ready)launch.removeAttribute('href');
   else launch.href=chat?'https://wa.me/7'+phone+'?'+new URLSearchParams({text:draft}):'tel:+7'+phone;
 };
 input.addEventListener('beforeinput',event=>{
   if(event.inputType==='insertText'&&/[^0-9]/.test(event.data||''))event.preventDefault();
 });
 input.addEventListener('input',()=>{
   const cursor=input.selectionStart;
   const leftDigits=input.value.slice(0,cursor).replace(/[^0-9]/g,'').length;
   const formatted=formatCallerDigits(input.value);
   if(input.value!==formatted){
     input.value=formatted;
     let position=0, digits=0;
     while(position<formatted.length&&digits<leftDigits){
       if(formatted[position]!==' ')digits++;
       position++;
     }
     input.setSelectionRange(position,position);
   }
   refresh();
 });
 input.addEventListener('paste',event=>{
   const digits=event.clipboardData?.getData('text').replace(/[^0-9]/g,'')||'';
   if(digits.length===11&&/^[78]/.test(digits)){
     event.preventDefault();
     input.value=formatCallerDigits(digits.slice(1));
     refresh();
   }
 });
 message?.addEventListener('input',refresh);
 launch.onclick=event=>{
   if(pending||callerEditor!==contact||!launch.hasAttribute('href')){
     event.preventDefault();
     return;
   }
   emit('contact_save',{...contact,phone:'+7'+input.value.replace(/[^0-9]/g,'')});
 };
 body.append(launch);
 if(chat)paragraph(body,'Хабарлама WhatsApp-та ашылады. Жіберуді сол жерде растаңыз.');
 refresh();
 (p.caller_phone&&message?message:input).focus();
}
function primaryRouteAction(){
 if(routeActionState().disabled)return;
 closeSheet();
 if(p.trip)play();else {stop();emit('route');}
 updateRouteAction();
}
function routePoint(parent,label,value,kind){
 const row=document.createElement('div');row.className='journey-point '+kind;
 const dot=document.createElement('span');dot.className='journey-dot';dot.textContent=kind==='hospital'?'✚':'B';
 const copy=document.createElement('div');
 const caption=document.createElement('small');caption.textContent=label;
 const name=document.createElement('strong');name.textContent=value;
 copy.append(caption,name);row.append(dot,copy);parent.append(row);
}
function hasExactAddress(){
 return !!p.destination_label&&['found','manual'].includes(p.address_status)&&!p.address_nearby;
}
function callAddressText(){
 return p.b?p.destination_label:'Картадан нүкте таңдаңыз';
}
function syncOpenRouteAddress(){
 if($('sheet').hidden)return;
 const content=$('sheet-content');
 const value=content.querySelector?.('.journey-point.destination strong');
 if(!value)return;
 value.textContent=callAddressText();
 const note=content.querySelector('.route-address-note');
 if(note){
   note.textContent=p.b?(p.address_note||''):'';
   note.hidden=!note.textContent;
 }
 const lookup=content.querySelector('.route-address-lookup');
 if(lookup){
   const looking=p.address_status==='auto_pending'||pendingType==='address';
   lookup.hidden=!p.b||hasExactAddress()||p.address_status==='landmark';
   lookup.disabled=looking||!!pending;
   lookup.textContent=looking?'Мекенжай ізделуде…':'Осы нүктенің мекенжайын іздеу';
 }
}
function addressEditor(parent){
 const details=document.createElement('details'),summary=document.createElement('summary');
 details.className='address-editor';summary.textContent='Мекенжайды нақтылау';details.append(summary);
 const label=document.createElement('label');label.textContent='Көше және үй нөмірі';
 const input=document.createElement('input');input.type='text';input.maxLength=200;input.placeholder='Мысалы: Түркістан көшесі, 10';
 input.value=hasExactAddress()?(p.destination_label||''):'';
 label.append(input);details.append(label);
 paragraph(details,'Бұл мәтін шақырту нүктесін өзгертпейді. Басқа орын қажет болса, картадан қайта таңдаңыз.');
 const point=[...p.b];
 const save=()=>{
   if(pending)return;
   const address=input.value.trim();
   if(address.length<3){toast('Көше мен үй нөмірін енгізіңіз.');input.focus();return;}
   emit('address_save',{address,point});
 };
 action(details,'Мекенжайды сақтау',save,false,!!pending);
 input.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();if(!pending)save();}};
 parent.append(details);
}
function openRoute(){
 const c=sheet('Шақырту маршруты');
 paragraph(c,'Шақырту басымдығы: '+(p.priority==='urgent'?'Шұғыл':'Қалыпты'));
 const points=document.createElement('div');points.className='journey-points';
 routePoint(points,'СТАРТ · АВТОМАТТЫ',p.hospital?.name||'№1, №2 немесе №3 аурухана','hospital');
 routePoint(points,'ШАҚЫРТУ ОРНЫ',callAddressText(),'destination');
 c.append(points);
 if(p.b){
   const note=document.createElement('p');note.className='route-address-note';c.append(note);
   const lookup=action(c,'Осы нүктенің мекенжайын іздеу',()=>{
     if(pending||p.address_status==='auto_pending')return;
     emit('address');
     syncOpenRouteAddress();
   },true);
   lookup.className+=' route-address-lookup';
   addressEditor(c);
 }
 if(p.trip){
   paragraph(c,etaExplanation(p.trip));
   const metrics=document.createElement('div');metrics.className='journey-metrics';
   [['Болжамды уақыт',formatEtaDuration(p.trip.eta_plan_s)],['Маршрут ұзындығы',p.trip.km.toFixed(2)+' км']].forEach(([label,value])=>{
     const box=document.createElement('div'),small=document.createElement('small'),strong=document.createElement('strong');
     small.textContent=label;strong.textContent=value;box.append(small,strong);metrics.append(box);
   });c.append(metrics);
 }
 const state=routeActionState();
 action(c,state.label,primaryRouteAction,false,state.disabled);
 action(c,'Шақырту орнын өзгерту',()=>{closeSheet();toast('Картадан жаңа шақырту орнын басыңыз.');},true,!!pending);
 if(p.b)action(c,'Шақыртуды тазалау',()=>{stop();emit('reset');closeSheet();},true,!!pending);
 syncOpenRouteAddress();
}

function syncTrafficControls(){
 const checkbox=$('layer-traffic');if(checkbox)checkbox.checked=flags.traffic;
}
function setLayerVisibility(key,enabled){
 if(!Object.prototype.hasOwnProperty.call(flags,key))return;
 flags[key]=Boolean(enabled);syncTrafficControls();draw();
}
function layers(){
 const c=sheet('Карта қабаттары');
 const options=[
   ['traffic','Кептеліс',p.city?'Астана · ашық деректерге негізделген модель':'Жолдағы жасанды жүктеме деңгейі',trafficColors[0]],
   ['base','Маршрут','Жоспарланған жол','#779bd0']
 ];
 options.forEach(([key,title,description,color])=>{
   const row=document.createElement('label');row.className='layer-card';
   const mark=document.createElement('span');mark.className='layer-swatch '+(key==='gps'||key==='hmm'?'dot':'');mark.style.background=color;
   const copy=document.createElement('span');copy.className='layer-copy';
   const name=document.createElement('strong');name.textContent=title;
   const note=document.createElement('small');note.textContent=description;
   const box=document.createElement('input');box.id='layer-'+key;box.type='checkbox';box.checked=flags[key];
   box.onchange=()=>setLayerVisibility(key,box.checked);
   copy.append(name,note);row.append(mark,copy,box);c.append(row);
 });
 const legend=document.createElement('div');legend.className='traffic-scale';
 [[0,'Еркін'],[1,'Баяу'],[3,'Қатты']].forEach(([band,label])=>{
   const item=document.createElement('span'),line=document.createElement('i'),text=document.createElement('small');
   line.style.background=trafficColors[band];text.textContent=label;item.append(line,text);legend.append(item);
 });c.append(legend);
 syncTrafficControls();
}

function normalizeSearch(text){return String(text||'').normalize('NFKC').toLocaleLowerCase().replace(/ё/g,'е').replace(/\s+/g,' ').trim();}
let searchSource=null,searchEntries=[];
function matchingStreets(query){
 const source=p.streets||[];
 if(searchSource!==source){
   searchSource=source;
   searchEntries=source.map(item=>({item,keys:[item.name,...(item.aliases||[])].map(normalizeSearch)}));
 }
 const q=normalizeSearch(query),buckets=[[],[],[]];
 const tokens=q.split(' ').filter(Boolean);
 for(const {item,keys} of searchEntries){
   const matches=keys.filter(key=>tokens.every(token=>key.includes(token)));
   if(!matches.length)continue;
   const rank=matches.includes(q)?0:matches.some(key=>key.startsWith(q))?1:2;
   if(buckets[rank].length<15)buckets[rank].push(item);
 }
 return buckets.flat().slice(0,15);
}
function chooseOnMap(){clearTimeout(searchTimer);closeSheet();$('search').blur();toast('Картадағы нақты шақырту орнын басыңыз.');}
function results(title,list){
 const c=sheet(title);
 const intro=document.createElement('p');intro.className='search-note';
 intro.textContent='Нақты мекенжайды іздеу үшін Enter басыңыз. Төменде жергілікті көше ұсыныстары.';c.append(intro);
 const pick=action(c,'⌖  Картадан нүкте таңдау',chooseOnMap,true);pick.className+=' map-pick';
 if(!list.length){
   const empty=document.createElement('div');empty.className='search-empty';
   const heading=document.createElement('strong');heading.textContent='Көше табылмады';empty.append(heading);
   paragraph(empty,'Атауын қысқартып жазыңыз немесе картадан нүкте таңдаңыз.');c.append(empty);
 }
 list.forEach(item=>{
   const b=document.createElement('button');b.className='result search-result';
   const mark=document.createElement('span');mark.className='search-pin';mark.textContent='⌖';mark.setAttribute('aria-hidden','true');
   const copy=document.createElement('span');copy.className='search-result-copy';
   const name=document.createElement('strong');name.textContent=item.name;
   const note=document.createElement('small');note.textContent=p.city?'Астана · көше / орын':'Жүктелген аудан · көше / орын';
   copy.append(name,note);b.append(mark,copy);b.onclick=()=>selectAddress(item);c.append(b);
 });return c;
}
function syncSearchClear(){$('clear-search').hidden=!$('search').value;}
function search(){clearTimeout(searchTimer);syncSearchClear();const q=$('search').value;
 results(normalizeSearch(q)?'Іздеу нәтижелері':'Шақырту орнын іздеу',matchingStreets(q));}
function scheduleSearch(){clearTimeout(searchTimer);syncSearchClear();searchTimer=setTimeout(search,120);}
$('clear-search').onclick=()=>{$('search').value='';$('search').focus();search();};
$('search').onkeydown=e=>{
 if(e.key==='Escape'){clearTimeout(searchTimer);closeSheet();$('search').blur();}
 if(e.key==='Enter'&&normalizeSearch($('search').value)){
   e.preventDefault();if(pending)return;
   clearTimeout(searchTimer);stop();closeSheet();$('search').blur();
   emit('geocode',{query:$('search').value.trim()});
 }
};

function about(){const c=sheet('Qadam · Emergency Smart Route');paragraph(c,'Астана қаласындағы жедел жәрдем маршрутын жоспарлау.');paragraph(c,'Оқу жобасы · кептеліс пен бағдаршамдар модельденеді.');}
$('route-action').onclick=primaryRouteAction;
if($('caller-chat'))$('caller-chat').onclick=()=>openCallerContact('chat');
if($('caller-call'))$('caller-call').onclick=()=>openCallerContact('call');
// Older index.html may remain in browser cache after a partial update.
// Restore this newly added control before binding events so map startup survives.
function ensurePriorityControl(){
 if($('call-priority'))return;
 const host=document.querySelector('.dispatch-summary');
 if(!host)return;
 const label=document.createElement('label');label.className='call-priority';label.htmlFor='call-priority';
 const caption=document.createElement('span');caption.textContent='Шақырту басымдығы';
 const select=document.createElement('select');select.id='call-priority';select.disabled=true;
 for(const [value,text] of [['normal','Қалыпты жедел жәрдем'],['urgent','Шұғыл жедел жәрдем']]){
   const option=document.createElement('option');option.value=value;option.textContent=text;select.append(option);
 }
 label.append(caption,select);host.append(label);
}
ensurePriorityControl();
if($('call-priority'))$('call-priority').onchange=e=>{if(pending||!p.b)return;const priority=e.target.value;stop();closeSheet();emit('priority',{priority});updateRouteSummary();};
// Remove the previously saved home; location is requested afresh on every click.
try{localStorage.removeItem('qadam_home_v1');}catch(error){}
for(const value of ['normal','urgent']){
 const button=$('priority-'+value);
 if(button)button.onclick=()=>{
   if(pending||!p.b)return;
   const select=$('call-priority');select.value=value;
   select.onchange({target:select});
 };
}
let userLocationMarker=null,locationRequestPending=false;
function locateUser(){
 if(locationRequestPending||pending)return;
 if(!window.isSecureContext){toast('Геолокация қолжетімсіз. HTTPS немесе localhost арқылы ашып, браузер рұқсатын тексеріңіз.');return;}
 if(document.permissionsPolicy?.allowsFeature('geolocation')===false){toast('Геолокация осы бетте бұғатталған. Сайт рұқсаттарын тексеріңіз.');return;}
 if(!navigator.geolocation){toast('Геолокация бұл браузерде қолжетімсіз.');return;}
 cancelSelection();locationRequestPending=true;$('locate').disabled=true;
 toast('Орналасқан жеріңіз анықталуда…');
 let completed=false;
 const finish=()=>{if(completed)return false;completed=true;clearTimeout(watchdog);locationRequestPending=false;$('locate').disabled=false;return true;};
 const watchdog=setTimeout(()=>{if(finish())toast('Орныңызды анықтау уақыты аяқталды. Қайта көріңіз.');},25000);
 try{navigator.geolocation.getCurrentPosition(position=>{
   if(!finish())return;const {latitude:lat,longitude:lng,accuracy}=position?.coords||{};
   if(!Number.isFinite(lat)||!Number.isFinite(lng)){toast('Орналасқан жеріңіз анықталмады. Қайта көріңіз.');return;}
   if(!pointInGeometry(lat,lng,p.city_boundary)){toast('Сіз Астана қаласының сыртындасыз. Шақырту нүктесін тек Астанада таңдауға болады.');return;}
   if(choose(lat,lng,'B')===false)return;
   if(userLocationMarker)map.removeLayer(userLocationMarker);
   userLocationMarker=L.marker([lat,lng],{icon:L.divIcon({className:'user-location-marker',html:'<span style="display:block;width:18px;height:18px;border:3px solid white;border-radius:50%;background:#1479ed;box-shadow:0 1px 6px #0008"></span>',iconSize:[18,18],iconAnchor:[9,9]}),interactive:false}).addTo(map);
   map.setView([lat,lng],16,{animate:false});
   toast(Number.isFinite(accuracy)&&accuracy>200?'Орныңыз шамамен анықталды. Картадағы нүктені тексеріңіз.':'Қазіргі орныңыз картада көрсетілді.');
 },error=>{if(!finish())return;toast(error.code===1?'Геолокацияға рұқсат берілмеді. Браузер баптауларынан рұқсат беріңіз.':error.code===3?'Орныңызды анықтау уақыты аяқталды. Қайта көріңіз.':'Браузер координаттарды бере алмады. Wi-Fi мен орналасу қызметін тексеріңіз немесе картадан таңдаңыз.');},{enableHighAccuracy:true,timeout:20000,maximumAge:0});}
 catch(error){finish();toast('Геолокация қолжетімсіз. HTTPS немесе localhost арқылы ашып, браузер рұқсатын тексеріңіз.');}
}
$('plus').onclick=()=>{cancelSelection();map.zoomIn();};$('minus').onclick=()=>{cancelSelection();map.zoomOut();};$('layers').onclick=layers;$('locate').onclick=locateUser;$('brand').onclick=about;$('route-info').onclick=openRoute;$('close-sheet').onclick=closeSheet;$('progress').oninput=e=>{stop();simTime=Number(e.target.value);drawStep();};$('search').oninput=scheduleSearch;$('search').onfocus=search;

$('playback-rate').onchange=e=>{playbackRate=Number(e.target.value);};
document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();});
let lastFocusId=null;
function focusDestination(){
 const focus=p.focus;
 if(!focus||focus.id===lastFocusId||!Number.isFinite(focus.lat)||!Number.isFinite(focus.lng))return;
 lastFocusId=focus.id;map.setView([focus.lat,focus.lng],16,{animate:false});
}
function render(payload){const wasCity=p.city;p=payload||{};if(window.QadamI18n)window.QadamI18n.setLanguage(p.language||'kk');applyTheme();if(!map)init();if(p.city&&!wasCity)map.setView([51.14,71.43],11);const pair=JSON.stringify([p.a,p.b]);if(pair!==lastPair){lastPair=pair;target='B';stop();}if(p.trip_id!==lastTrip){lastTrip=p.trip_id;if(p.demo_scenario){flags.gps=flags.hmm=p.demo_scenario==='gps';}stop();step=0;simTime=0;}
 if(callerEditor&&(!p.b||JSON.stringify(p.b)!==JSON.stringify(callerEditor.point)||(p.focus?.id??null)!==callerEditor.call_id))closeSheet();
 if(pending&&p.ack===pending){
   clearGroup('pendingCall');
   const contactSave=pendingType==='contact_save';
   const addressSave=pendingType==='address_save';
   pending=null;pendingType=null;$('loading').hidden=true;
   if(p.error)toast(p.error);
   if(contactSave&&callerEditor){
     if(p.error)$('caller-phone-input')?.focus();
     else closeSheet();
   }
   if(addressSave&&!$('sheet').hidden){
     if(p.error)$('sheet-content').querySelector('.address-editor input')?.focus();
     else closeSheet();
   }
 }
 updateRouteAction();updateRouteSummary();syncOpenRouteAddress();applyTheme();const visual=JSON.stringify([p.dataset_version,p.a,p.b,p.snap_a,p.snap_b,p.hospital,p.city,p.bbox,p.sigma,p.trip_id,!!p.trip,p.traffic_key]);
 if(visual!==lastVisual){lastVisual=visual;hint();draw();}
 focusDestination();resize();}
window.addEventListener('message',event=>{if(event.source!==window.parent)return;if(event.data.type==='streamlit:render')render(event.data.args.payload);});window.addEventListener('resize',resize);
// Browsers suspend RAF in hidden tabs: resume without jumping ahead by minutes.
document.addEventListener('visibilitychange',()=>{lastFrame=null;lastPaint=null;});
post('streamlit:componentReady',{apiVersion:1});resize();
