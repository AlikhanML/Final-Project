// Exercise production drawStep with a lightweight DOM/Leaflet adapter.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const elements=new Map();
const element=id=>{if(!elements.has(id))elements.set(id,{hidden:false,innerHTML:'',textContent:'',style:{}});return elements.get(id);};
let clears=0,sets=[];
const layer=points=>({points:[...points],addTo(g){g.items.push(this);return this;},
 addLatLng(p){this.points.push(p);return this;},setLatLngs(p){sets.push(p.length);this.points=[...p];return this;},setLatLng(){return this;}});
const context={console,setTimeout,clearTimeout,Math,JSON,Number,
 document:{getElementById:element,querySelectorAll:()=>[],body:{style:{}},addEventListener(){}},
 window:{parent:{innerHeight:800,postMessage(){}},addEventListener(){}},
 L:{polyline:(p,options)=>Object.assign(layer(p),{options}),circleMarker:p=>layer([p]),marker:p=>layer([p]),divIcon:x=>x},
 QadamTrafficView:require('../frontend/traffic_view.js'),QadamPlayback:require('../frontend/playback.js'),cancelAnimationFrame(){},requestAnimationFrame(){}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(require.resolve('../frontend/app.js'),'utf8'),context);
context.groupFactory=()=>({items:[],clearLayers(){clears++;this.items=[];}});
vm.runInContext(`
 groups=Object.fromEntries(['route','hmm','gps','vehicle'].map(k=>[k,groupFactory()]));
 const pts=[[0,0],[0,1],[1,1],[1,2]];
 p={trip:{path:pts,hmm:pts,gps:pts,timestamps_s:[0,10,20,30],elapsed_s:30,
 phases:[false,false,true,true],blocked:[[0,1],[1,1]],fallback:null,
 km:1,reached:true,status:'reached'}};
 flags.hmm=flags.gps=true;flags.base=false;
 simTime=5;drawStep(true);
`,context);
const read=s=>vm.runInContext(s,context);
read('const initialTrail=trail');
assert.equal(read('trail.points.length'),2);
assert.equal(read('trail.options.noClip'),true);
assert.equal(read('trail.options.pane'),'routeLines');
assert.equal(read('groups.route.items.length'),2);
assert.equal(read('trail.options.lineJoin'),'round');
assert.equal(read('JSON.stringify(trail.points)'),read('JSON.stringify(trailBorder.points)'));
let oldClears=clears;sets=[];
read('simTime=6;drawStep()');
assert.equal(clears,oldClears);
assert.deepEqual(sets,[2,2]);
read('simTime=25;drawStep()');
assert.equal(clears,oldClears);
assert.equal(read('trail.points.length'),4);
assert.equal(read('groups.hmm.items.length'),3);
read('simTime=2;drawStep()');
assert.equal(read('trail===initialTrail'),true);
assert.equal(read('trail.points.length'),2);
assert.equal(read('groups.gps.items.length'),1);
read('simTime=30;drawStep()');
assert.equal(read('trail.points.length'),4);
// A turn or detour replaces the geometry of the same blue stroke.
read(`
 const planned=[[0,0],[0,1],[0,2],[1,2]];
 p.trip.base=planned;flags.base=true;
 simTime=10;drawStep(true);
 const detourTrail=trail;
`);
assert.equal(read('JSON.stringify(trail.points)'),read('JSON.stringify(planned)'));
sets=[];
read('simTime=10;drawStep()');
assert.deepEqual(sets,[]);
read('simTime=12;drawStep()');
assert.equal(read('JSON.stringify(trail.points)'),read('JSON.stringify(pts)'));
assert.equal(read('trail===detourTrail&&groups.route.items.length===2'),true);
read('simTime=2;drawStep()');
assert.equal(read('JSON.stringify(trail.points)'),read('JSON.stringify(planned)'));
assert.equal(read('trail===detourTrail'),true);
console.log('Single route stroke, detour and seek assertions passed.');
// Unchanged Streamlit rerenders must not clear/redraw Leaflet layers.
read("map={invalidateSize(){},setView(){}};let redraws=0;draw=()=>{redraws++;};lastVisual='';");
read("const payload={dataset_version:'v1',trip_id:10,trip:p.trip,a:null,b:null,city:false};render(payload);render(payload);");
assert.equal(read('redraws'),1);
read("render({...payload,dataset_version:'v2'});");assert.equal(read('redraws'),2);
read("render({...payload,dataset_version:'v2',trip:null});");assert.equal(read('redraws'),3);
console.log('3 redundant-render assertions passed.');
// Address lookup updates the two labels in place, without restarting the trip.
read(`
 const addressNodes={
   '.journey-point.destination strong':{},
   '.route-address-note':{},
   '.route-address-lookup':{}
 };
 $('sheet').hidden=false;
 $('sheet-content').querySelector=selector=>addressNodes[selector];
 const addressPayload={...payload,b:[51.1,71.4],trip_id:11,address_status:'auto_pending',
                       destination_label:'Аңырақай көшесінің маңы'};
 render(addressPayload);
 const beforeAddress=redraws;
 simTime=18;
`);
assert.equal(read("addressNodes['.route-address-lookup'].disabled"),true);
assert.equal(element('summary-destination').textContent,'Аңырақай көшесінің маңы');
assert.equal(read("addressNodes['.journey-point.destination strong'].textContent"),'Аңырақай көшесінің маңы');
read("render({...addressPayload,address_status:'auto_unavailable'})");
assert.equal(read("addressNodes['.route-address-lookup'].disabled"),false);
assert.equal(element('summary-destination').textContent,'Аңырақай көшесінің маңы');
assert.equal(read("addressNodes['.journey-point.destination strong'].textContent"),'Аңырақай көшесінің маңы');
read("render({...addressPayload,address_status:'found',address_note:'OSM',destination_label:'Аңырақай көшесі, 37'})");
assert.equal(element('summary-destination').textContent,'Аңырақай көшесі, 37');
assert.equal(read("addressNodes['.journey-point.destination strong'].textContent"),'Аңырақай көшесі, 37');
assert.equal(read("addressNodes['.route-address-lookup'].hidden"),true);
assert.equal(read('redraws'),read('beforeAddress'));
assert.equal(read('simTime'),18);
read("$('sheet').hidden=true");
console.log('11 automatic address rendering assertions passed.');
// Selecting an address must not trigger a Python rerun during flyTo.
read(`
 let moveHandler=null,flyCalls=0,picks=[];
 $('search').blur=()=>{};
 window.parent.postMessage=message=>{if(message.value?.type==='pick')picks.push(message.value);};
 map={off(event,fn){if(moveHandler===fn)moveHandler=null;},stop(){},
 once(event,fn){moveHandler=fn;},getCenter(){return {lat:51,lng:71};},getZoom(){return 12;},
 flyTo(){flyCalls++;}};
 p={bbox:[70,50,73,53],city_boundary:{type:"Polygon",coordinates:[[[70,50],[73,50],[73,53],[70,53],[70,50]]]}};
 selectAddress({lat:51.1,lng:71.2});
`);
assert.equal(read('picks.length'),0);
assert.equal(read('flyCalls'),1);
read('moveHandler()');assert.equal(read('picks.length'),1);
assert.equal(read('moveHandler'),null);
read('pending=null;selectAddress({lat:51.2,lng:71.3});selectAddress({lat:51.3,lng:71.4});moveHandler()');
assert.equal(read('picks.length'),2);
assert.equal(read('picks[1].lat'),51.3);
read('pending=null;selectAddress({lat:51.4,lng:71.5});cancelSelection()');
assert.equal(read('moveHandler'),null);
read('pending=null;map.getZoom=()=>16;map.getCenter=()=>({lat:51.4,lng:71.5});selectAddress({lat:51.4,lng:71.5})');
assert.equal(read('picks.length'),3);
console.log('8 address-animation assertions passed.');
read(`p.trip={path:pts,hmm:pts,gps:pts,timestamps_s:[0,10,20,30],elapsed_s:30,
phases:[false,false,false,false],blocked:null,fallback:null,km:1,reached:false,status:'localization_stop'};
simTime=30;drawStep(true);`);
assert.ok(element('route-title').textContent.includes('қозғалыс тоқтады'));
assert.ok(element('route-sub').textContent.includes('Мақсатқа жеткен жоқ'));
console.log('2 incomplete-trip label assertions passed.');
// Production fast mode selects directly, without waiting for a fly animation.
read(`pending=null;let setViews=0;map.setView=()=>{setViews++;};p={bbox:[70,50,73,53],city_boundary:p.city_boundary,reduced_motion:true};
const picksBefore=picks.length;const flyBefore=flyCalls;
selectAddress({lat:51.2,lng:71.4});`);
assert.equal(read('setViews'),1);
assert.equal(read('picks.length-picksBefore'),1);
assert.equal(read('flyCalls-flyBefore'),0);
console.log('3 reduced-motion assertions passed.');
// Calls on the screenshot island are rejected before selecting or panning.
context.islandGeometry=JSON.parse(fs.readFileSync(require.resolve('../data/astana_call_exclusion.geojson'),'utf8')).geometry;
read(`pending=null;groups.pendingCall=groupFactory();p.call_exclusion=islandGeometry;p.call_exclusion_message='Choose a point on the riverbank.';
const beforeIsland=picks.length,beforeIslandView=setViews;
selectAddress({lat:51.099348,lng:71.482485});
`);
assert.equal(read('setViews'),read('beforeIslandView'));
assert.equal(read('picks.length'),read('beforeIsland'));
assert.equal(read("choose(51.099348,71.482485,'B')"),false);
assert.equal(read("choose(islandGeometry.coordinates[0][0][1],islandGeometry.coordinates[0][0][0],'B')"),false);
assert.equal(element('toast').textContent,'Choose a point on the riverbank.');
assert.equal(read('picks.length'),read('beforeIsland'));
assert.equal(read('groups.pendingCall.items.length'),0);
assert.equal(read("choose(51.101194,71.481884,'B')"),true);
assert.equal(read('picks.length'),read('beforeIsland')+1);
assert.equal(read('groups.pendingCall.items[0].points[0][0]'),51.101194);
read("render({...p,ack:'old-event',a:null,b:null})");
assert.equal(read('groups.pendingCall.items.length'),1);
read("render({...p,ack:pending,a:null,b:null,error:'Rejected'})");
assert.equal(read('groups.pendingCall.items.length'),0);
console.log('Island validation and immediate call marker assertions passed.');
read(`p.trip={path:pts,hmm:pts,gps:pts,timestamps_s:[0,10,20,30],elapsed_s:30,
phases:[true,true,true,true],blocked:[[0,1],[1,1]],fallback:null,km:1,reached:true,status:'reached'};
simTime=25;drawStep(true);`);
assert.equal(read('groups.route.items.length'),2);
console.log('1 removed-closure-overlay assertion passed.');
read(`groups.traffic=groupFactory();flags.traffic=true;p.traffic_bands=[[[[0,0],[0,1]]],[[[0,1],[0,2]]],[[[0,2],[0,3]]],[[[0,3],[0,4]]]];p.trip=null;drawCityTraffic();`);
assert.equal(read('groups.traffic.items.length'),4);
assert.equal(read('groups.traffic.items[3].points.length'),1);
read('groups.traffic.clearLayers();flags.traffic=false;drawCityTraffic()');
assert.equal(read('groups.traffic.items.length'),0);
console.log('3 citywide traffic rendering assertions passed.');
// Dispatch action must follow readiness and playback state, including pending requests.
read("pending=null;p={};timer=null;simTime=0;updateRouteAction()");
assert.equal(element('route-action').disabled,true);
read("p={b:[51,71]};updateRouteAction()");assert.equal(element('route-action').disabled,true);
read("p.hospital={name:'Hospital'};updateRouteAction()");assert.equal(element('route-action').textContent,'Маршрутты есептеу');
read("p.trip={elapsed_s:100};updateRouteAction()");assert.equal(element('route-action').textContent,'Маршрутты бастау');
read("timer=1;updateRouteAction()");assert.equal(element('route-action').textContent,'Кідірту');
read("timer=null;simTime=40;updateRouteAction()");assert.equal(element('route-action').textContent,'Қозғалысты жалғастыру');
read("simTime=100;updateRouteAction()");assert.equal(element('route-action').textContent,'Симуляцияны қайта ойнату');
read("pending='request';updateRouteAction()");assert.equal(element('route-action').disabled,true);
read("pending=null;p.trip.elapsed_s=0;updateRouteAction()");assert.equal(element('route-action').disabled,true);
console.log('9 dispatch action state assertions passed.');
// Ranking must prefer exact matches even after many partial matches.
read(`p.streets=[...Array.from({length:20},(_,i)=>({name:'Ескі Абай '+i})),{name:'Абай даңғылы'},{name:'Абай'},{name:'Берёзовая'}];`);
assert.equal(read("matchingStreets(' АБАЙ ')[0].name"),'Абай');
assert.equal(read("matchingStreets('Абай')[1].name"),'Абай даңғылы');
assert.equal(read("matchingStreets('Абай').length"),15);
assert.equal(read("matchingStreets('березовая')[0].name"),'Берёзовая');
assert.equal(read("matchingStreets('жоқ көше').length"),0);
read("p.streets=[{name:'Түркістан көшесі'}]");
assert.equal(read("matchingStreets('көшесі түркістан')[0].name"),'Түркістан көшесі');
read("p.streets=[{name:'Бәйтерек',aliases:['Байтерек','Bayterek']},{name:'Бәйтерек көшесі'}]");
assert.equal(read("matchingStreets('байтерек')[0].name"),'Бәйтерек');
assert.equal(read("matchingStreets('bayt')[0].name"),'Бәйтерек');
console.log('6 street search ranking assertions passed.');
// Layer toggles remain available in the sheet without extra map buttons.
read("const layerPicksBefore=picks.length;setLayerVisibility('traffic',false)");
assert.equal(element('layer-traffic').checked,false);
read("setLayerVisibility('traffic',true)");
assert.equal(element('layer-traffic').checked,true);
assert.equal(read('picks.length'),read('layerPicksBefore'));
read("p={};updateRouteSummary()");
assert.equal(element('summary-hospital').textContent,'Автоматты таңдалады');
assert.equal(element('summary-destination').textContent,'Картадан нүкте таңдаңыз');
read("p={b:[51,71],hospital:{name:'№2 аурухана'},destination_label:'Абай, 10',address_status:'found'};updateRouteSummary()");
assert.equal(element('summary-hospital').textContent,'№2 аурухана');
assert.equal(element('summary-destination').textContent,'Абай, 10');
console.log('7 compact interface state assertions passed.');

// Results distinguish playback completion, failed arrival and missing timings.
read("simTime=9;updateTripReport({elapsed_s:10,reached:true,km:1,compute_s:.23})");
assert.equal(element('trip-report').hidden,true);
read("simTime=10;updateTripReport({elapsed_s:10,reached:true,km:1.25,compute_s:.23})");
assert.equal(element('trip-report').hidden,false);
assert.equal(element('report-status').textContent,'Мақсатқа жетті');
assert.equal(element('report-distance').textContent,'1.25 км');
assert.equal(element('report-time').textContent,'0:10');
assert.ok(!fs.readFileSync(require.resolve('../frontend/index.html'),'utf8').includes('id="report-compute"'));
read("updateTripReport({elapsed_s:10,reached:false,status:'compute_limit',km:.12})");
assert.match(element('report-status').textContent,/Мақсатқа жеткен жоқ.*лимитіне/);
assert.equal(element('report-distance').textContent,'0.12 км');

read("simTime=0;updateTripReport({elapsed_s:0,reached:true,km:0,compute_s:0})");
assert.equal(element('report-distance').textContent,'0.00 км');
read("updateTripReport(null)");
assert.equal(element('trip-report').hidden,true);
read("simTime=2;updateTripReport({elapsed_s:10,reached:true})");
assert.equal(element('trip-report').hidden,true);
console.log('11 trip result report assertions passed.');
// Full city traffic is attached on first draw; panning needs no geometry reload.
read(`
 let west=0;
 map={getZoom:()=>14,getBounds:()=>({pad(){return this;},getSouth:()=>-1,getNorth:()=>1,getWest:()=>west,getEast:()=>west+1})};
 p={traffic_key:['test',1],traffic_bands:[[[[0,0],[0,.5]],[[0,10],[0,10.5]]],[],[],[]]};
 flags.traffic=true;drawCityTraffic();
`);
const before=clears;
read('drawCityTraffic()');assert.equal(clears,before);
assert.equal(read('groups.traffic.items[0].points[0][0][1]'),0);
assert.equal(read('groups.traffic.items[0].points.length'),2);
read('west=10;drawCityTraffic()');assert.equal(clears,before);
assert.equal(read('groups.traffic.items[0].points[1][0][1]'),10);
read('flags.traffic=false;drawCityTraffic()');assert.equal(read('groups.traffic.items.length'),0);
read('flags.traffic=true;drawCityTraffic()');assert.equal(read('groups.traffic.items.length'),1);
console.log('6 traffic refresh assertions passed.');
// Pending updates retain the last city overlay; explicit OFF and ready-empty win.
read(`p={dataset_version:'city-one',traffic_key:['a'],traffic_bands:[[[[0,10],[0,10.5]]],[],[],[]]};flags.traffic=true;drawCityTraffic();const stableIndex=trafficIndex;`);
const pendingClears=clears;
read("p={...p,traffic_key:['b'],traffic_pending:true,traffic_bands:[[],[],[],[]]};drawCityTraffic()");
assert.equal(read('trafficIndex===stableIndex'),true);assert.equal(clears,pendingClears);
read('flags.traffic=false;drawCityTraffic()');assert.equal(read('groups.traffic.items.length'),0);
read('flags.traffic=true;drawCityTraffic()');assert.equal(read('groups.traffic.items.length'),1);
read("p.traffic_pending=false;p.traffic_error='network';drawCityTraffic()");assert.equal(read('trafficIndex===stableIndex'),true);
read("p.traffic_error=null;drawCityTraffic()");assert.equal(read('groups.traffic.items.length'),0);
read("p.traffic_key=['c'];p.traffic_bands=[[[[0,10],[0,10.5]]],[],[],[]];drawCityTraffic();p={...p,dataset_version:'city-two',traffic_pending:true,traffic_bands:[[],[],[],[]]};drawCityTraffic()");assert.equal(read('groups.traffic.items.length'),0);
console.log('7 traffic persistence assertions passed.');
assert.match(read("etaExplanation({priority:'urgent',eta_breakdown:{traffic_delay_s:0,same_path_saving_s:0}})"),/бірдей/);
assert.match(read("etaExplanation({priority:'urgent',eta_breakdown:{traffic_delay_s:35,same_path_saving_s:65}})"),/1.1 мин/);
assert.match(read("etaExplanation({priority:'normal',eta_breakdown:{traffic_delay_s:100,same_path_saving_s:0}})"),/100.0 с/);
assert.equal(read('etaExplanation(null)'),'');
console.log('4 ETA explanation assertions passed.');
// Switching mode sends the chosen value, hides stale details, and refreshes ETA
// without relying on a map redraw or a changed route geometry.
read(`pending=null;p={b:[51,71],priority:'normal',trip:{priority:'normal',eta_plan_s:135}};updateRouteSummary();`);
assert.equal(element('eta-chip').textContent,'≈ 2.3 мин');
read(`let priorityMessages=[];window.parent.postMessage=m=>{if(m.value)priorityMessages.push(m.value);};$('call-priority').value='urgent';$('call-priority').onchange({target:$('call-priority')});`);
assert.equal(read('priorityMessages[0].priority'),'urgent');
assert.equal(element('sheet').hidden,true);
assert.equal(element('eta-chip').textContent,'Есептелуде…');
read(`pending=null;p={...p,priority:'urgent',trip:{priority:'urgent',eta_plan_s:70}};updateRouteSummary()`);
assert.equal(element('eta-chip').textContent,'≈ 1.2 мин');
assert.match(element('eta-chip').title,/1.2 мин.*Шұғыл/);
assert.match(read("etaExplanation({priority:'urgent',eta_breakdown:{traffic_delay_s:35,normal_same_path_s:135,urgent_same_path_s:70}})"),/қалыпты 2.3 мин.*шұғыл 1.2 мин.*1.1 мин/);
assert.match(read("etaExplanation({priority:'urgent',eta_breakdown:{traffic_delay_s:35,normal_same_path_s:135,urgent_same_path_s:70}})"),/Кептеліс кідірісі: \+35\.0 с/);
console.log('7 priority selection and ETA refresh assertions passed.');
// Beacon state follows the calculated trip on initial draw and subsequent mode changes.
read(`
 const beaconClasses=new Set(),beaconLabels={};
 const beaconBody={classList:{toggle(name,on){if(on)beaconClasses.add(name);else beaconClasses.delete(name);}},
 querySelector:()=>({setAttribute(name,value){beaconLabels[name]=value;}})};
 vehicleMarker={getElement:()=>({querySelector:()=>beaconBody})};
 p={priority:'urgent',trip:{priority:'urgent'}};updateRouteSummary();
`);
assert.equal(read("beaconClasses.has('vehicle-urgent')"),true);
assert.equal(read("beaconLabels['aria-label']"),'Шұғыл жедел жәрдем');
read("p={priority:'normal',trip:{priority:'normal'}};updateRouteSummary()");
assert.equal(read("beaconClasses.has('vehicle-urgent')"),false);
assert.equal(read("beaconLabels['aria-label']"),'Қалыпты жедел жәрдем');
read("p={priority:'urgent',trip:{priority:'urgent'},reduced_motion:true};updateRouteSummary()");
assert.equal(read("beaconClasses.has('vehicle-urgent')"),true);
assert.equal(read("beaconClasses.has('vehicle-reduced-motion')"),true);
read("p={priority:'urgent'};updateRouteSummary()");
assert.equal(read("beaconClasses.has('vehicle-urgent')"),true);
assert.equal(read("beaconClasses.has('vehicle-reduced-motion')"),false);
read('vehicleMarker=null;updateVehiclePriority()');
console.log('Emergency beacon state and mode switching passed.');
// Theme changes update map appearance without resetting route or playback.
read(`let themeAttrs={},themeUrls=[];document.body.setAttribute=(k,v)=>themeAttrs[k]=v;
map={_qadamTiles:{setUrl:url=>themeUrls.push(url)}};
p={theme:'light',carto_key:'test key',trip:{priority:'urgent'}};simTime=12;applyTheme();`);
assert.equal(read("themeAttrs['data-theme']"),'light');
assert.equal(read('document.body.style.colorScheme'),'light');
assert.match(read('themeUrls[0]'),/light_all.*test%20key/);
assert.equal(read('simTime'),12);
read('applyTheme()');assert.equal(read('themeUrls.length'),1);
read("p.theme='dark';applyTheme()");
assert.match(read('themeUrls[1]'),/dark_all/);
assert.equal(read("themeAttrs['data-theme']"),'dark');
read("p.theme='Aurora';applyTheme()");
assert.equal(read("themeAttrs['data-theme']"),'aurora');
assert.equal(read('document.body.style.colorScheme'),'dark');
assert.equal(read('themeUrls.length'),2);
read("p.theme='Поляр шұғыласы';applyTheme()");
assert.equal(read("themeAttrs['data-theme']"),'aurora');
assert.equal(read('simTime'),12);
read("p.theme='light';applyTheme()");
assert.equal(read("themeAttrs['data-theme']"),'light');
assert.match(read('themeUrls[2]'),/light_all/);
read("p.carto_key='';p.theme='light';applyTheme()");
assert.equal(read('themeUrls.length'),3); // OSM changes CSS, not tile source.
assert.equal(read('p.trip.priority'),'urgent');
console.log('Light, Dark and Aurora theme switching passed.');

// Simulated browser responses, not a physical location measurement.
context.navigator={geolocation:{getCurrentPosition(ok,fail,options){context.geoOK=ok;context.geoFail=fail;context.geoOptions=options;}}};
const timers=new Map();let timerId=0;
context.setTimeout=fn=>{timers.set(++timerId,fn);return timerId;};
context.clearTimeout=id=>timers.delete(id);
read(`window.isSecureContext=true;pending=null;let geoPicks=[],geoMessages=[];
const chooseFromMap=choose;
toast=msg=>geoMessages.push(msg);choose=(lat,lng,target)=>geoPicks.push({lat,lng,target});
map={items:[],setView(){},removeLayer(){}};
p={city_boundary:{type:'Polygon',coordinates:[[[70,50],[73,50],[73,53],[70,53],[70,50]]]}};
locateUser();`);
assert.equal(element('locate').disabled,true);
assert.equal(context.geoOptions.maximumAge,0);
context.geoOK({coords:{latitude:51.1,longitude:71.4,accuracy:30}});
assert.equal(read('geoPicks.length'),1);
assert.equal(read('geoPicks[0].target'),'B');
assert.equal(element('locate').disabled,false);
read('locateUser()');context.geoFail({code:1});
assert.match(read('geoMessages.at(-1)'),/рұқсат берілмеді/);
read('locateUser()');context.geoOK({coords:{latitude:40,longitude:71,accuracy:10}});
assert.equal(read('geoPicks.length'),1);
assert.match(read('geoMessages.at(-1)'),/сыртындасыз/);
read('locateUser()');const late=context.geoOK;
for(const fn of [...timers.values()])fn();
assert.equal(element('locate').disabled,false);
late({coords:{latitude:51.2,longitude:71.3,accuracy:20}});
assert.equal(read('geoPicks.length'),1);
assert.equal(read('locationRequestPending'),false);
console.log('11 simulated geolocation assertions passed.');
read(`choose=chooseFromMap;p.call_exclusion=islandGeometry;p.call_exclusion_message='Island selection unavailable.';
const markerBefore=userLocationMarker;locateUser();`);
context.geoOK({coords:{latitude:51.099348,longitude:71.482485,accuracy:20}});
assert.equal(read('userLocationMarker'),read('markerBefore'));
assert.equal(read('pending'),null);
assert.equal(read('geoMessages.at(-1)'),'Island selection unavailable.');
console.log('3 island geolocation assertions passed.');
// Visible priority badges use the same dispatch event as the original selector.
read(`pending=null;p={priority:'normal',b:[51,71]};let badgeMessages=[];
window.parent.postMessage=m=>{if(m.value)badgeMessages.push(m.value);};
for(const name of ['normal','urgent']){
 const button=$('priority-'+name);button.attrs={};button.setAttribute=(k,v)=>button.attrs[k]=v;
}
updatePriorityBadges();`);
assert.equal(element('priority-normal').attrs['aria-pressed'],'true');
assert.equal(element('priority-urgent').attrs['aria-pressed'],'false');
read("$('priority-urgent').onclick()");
assert.equal(read('badgeMessages[0].type'),'priority');
assert.equal(read('badgeMessages[0].priority'),'urgent');
assert.equal(element('priority-normal').disabled,true);
read("$('priority-normal').onclick()");
assert.equal(read('badgeMessages.length'),1);
read("pending=null;p.priority='urgent';updatePriorityBadges()");
assert.equal(element('priority-urgent').attrs['aria-pressed'],'true');
read("p.b=null;updatePriorityBadges()");
assert.equal(element('priority-urgent').disabled,true);
console.log('8 priority badge interaction assertions passed.');

// Enter performs an address lookup, rather than selecting a street centroid.
read(`pending=null;$('search').value='Мәңгілік Ел 55';let searchEvents=[];
window.parent.postMessage=m=>{if(m.value)searchEvents.push(m.value);};
$('search').onkeydown({key:'Enter',preventDefault(){}});`);
assert.equal(read('searchEvents[0].type'),'geocode');
assert.equal(read('searchEvents[0].query'),'Мәңгілік Ел 55');
read("$('search').onkeydown({key:'Enter',preventDefault(){}})");
assert.equal(read('searchEvents.length'),1);
read(`let focusMoves=[];map.setView=(coords,zoom)=>focusMoves.push({coords,zoom});
p.focus={id:'focus1',lat:51.13,lng:71.41};focusDestination();focusDestination();`);
assert.equal(read('focusMoves.length'),1);
assert.equal(read('focusMoves[0].zoom'),16);
assert.equal(read('focusMoves[0].coords[0]'),51.13);
read("p.focus={id:'focus2',lat:51.14,lng:71.42};focusDestination()");
assert.equal(read('focusMoves.length'),2);
console.log('7 geocoding and destination focus assertions passed.');
