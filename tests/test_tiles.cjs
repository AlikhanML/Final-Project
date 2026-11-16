const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const elements=new Map(),timers=new Map(),tileEvents={},mapEvents={};let mapOptions;let timerId=0,tileOptions,tileUrl,view,panes={},polylines=0,clears=0;
const element=id=>{if(!elements.has(id))elements.set(id,{style:{},appendChild(){}});return elements.get(id);};
const fakeMap={setView(center,zoom){view={center,zoom};return this;},createPane(name){return panes[name]={style:{}};},on(name,fn){mapEvents[name]=fn;return this;}};
const point=(x,y)=>({x,y,subtract(p){return point(x-p.x,y-p.y);},add(p){return point(x+p.x,y+p.y);}});
let boundsCalls=0;
const originalBounds=function(center){assert.equal(this,tiles);assert.equal(center,'center');boundsCalls++;return {min:point(100,200),max:point(900,800)};};
const tiles={_getTiledPixelBounds:originalBounds,on(name,fn){tileEvents[name]=fn;return this;},addTo(){return this;}};
const context={console,Math,JSON,Number,Map,WeakMap,
setTimeout(fn){timers.set(++timerId,fn);return timerId;},clearTimeout(id){timers.delete(id);},
document:{createElement:()=>({}),getElementById:element,querySelectorAll:()=>[],body:{style:{}},addEventListener(){}},
window:{parent:{innerHeight:800,postMessage(){}},addEventListener(){}},
L:{map:(_id,options)=>{mapOptions=options;return fakeMap;},canvas:options=>({options}),svg:options=>({options,type:"svg"}),point,bounds:(min,max)=>({min,max}),tileLayer(url,options){tiles._getTiledPixelBounds=originalBounds;tileUrl=url;tileOptions=options;return tiles;},
layerGroup:()=>({addTo(){return this;},clearLayers(){clears++;}}),polyline(points,options){polylines++;assert.equal(options.pane,'roadFallback');return {addTo(){}};}},
QadamTrafficView:require('../frontend/traffic_view.js'),QadamPlayback:require('../frontend/playback.js'),cancelAnimationFrame(){},requestAnimationFrame(){}};
vm.createContext(context);vm.runInContext(fs.readFileSync(require.resolve('../frontend/app.js'),'utf8'),context);
const run=s=>vm.runInContext(s,context);
run("p={city:true,dataset_version:'v1',roads:[[[51,71],[51.1,71.1]]]};init();offlineRoads();");
assert.equal(view.zoom,11);assert.equal(tileOptions.updateWhenIdle,false);
assert.equal(tileOptions.updateInterval,50);assert.equal(tileOptions.keepBuffer,4);
assert.equal(panes.roadFallback.style.zIndex,'150');assert.equal(polylines,1);
const tile={style:{},src:'https://tile.openstreetmap.org/11/1/1.png',isConnected:true};
tileEvents.tileload({tile});run('offlineRoads()');assert.equal(polylines,1);assert.equal(clears,1);
function fireTimer(){const [id,fn]=timers.entries().next().value;timers.delete(id);fn();}
tileEvents.tileerror({tile});assert.equal(tile.style.visibility,'hidden');assert.equal(timers.size,1);
fireTimer();tileEvents.tileerror({tile});assert.equal(timers.size,1);
fireTimer();tileEvents.tileerror({tile});assert.equal(timers.size,0);
tileEvents.tileload({tile});assert.equal(tile.style.visibility,'');
const other={...tile,style:{}};tileEvents.tileerror({tile:other});assert.equal(timers.size,1);
tileEvents.tileunload({tile:other});assert.equal(timers.size,0);
run("p.dataset_version='v2';offlineRoads()");assert.equal(polylines,2);
console.log('16 tile-loading assertions passed.');

assert.equal(tileOptions.className,'qadam-osm-tiles');
run("p.carto_key='test key&value';init()");
assert.ok(tileUrl.includes('/dark_all/'));
assert.ok(tileUrl.endsWith('?key=test%20key%26value'));
assert.equal(tileOptions.className,'qadam-carto-tiles');
assert.equal(tileOptions.maxZoom,20);
assert.ok(tileOptions.attribution.includes('CARTO'));
console.log('6 basemap configuration assertions passed.');

assert.equal(mapOptions.zoomAnimation,true);assert.equal(mapOptions.markerZoomAnimation,true);
run('p.reduced_motion=true;init()');assert.equal(mapOptions.zoomAnimation,false);
console.log('3 zoom animation assertions passed.');

const buffered=tiles._getTiledPixelBounds('center');
assert.equal(boundsCalls,1);
assert.deepEqual([buffered.min.x,buffered.min.y,buffered.max.x,buffered.max.y],[-28,72,1028,928]);
assert.equal(tileOptions.updateWhenZooming,false,'Do not request intermediate flyTo zoom levels');
console.log('3 bounded tile look-ahead assertions passed.');

assert.equal(fakeMap._qadamRouteRenderer.type,"svg");
assert.equal(fakeMap._qadamRouteRenderer.options.pane,"routeLines");
