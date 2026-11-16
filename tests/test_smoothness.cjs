// Exercise the actual animation scheduler independently of Leaflet rendering.
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const events={},elements=new Map();let next=0;
const context={console,setTimeout,clearTimeout,
 document:{getElementById(id){if(!elements.has(id))elements.set(id,{style:{}});return elements.get(id);},querySelectorAll:()=>[],body:{style:{}},addEventListener(name,fn){events[name]=fn;}},
 window:{parent:{innerHeight:800,postMessage(){}},addEventListener(){}},
 requestAnimationFrame(){return ++next;},cancelAnimationFrame(){},
 QadamTrafficView:require('../frontend/traffic_view.js'),QadamPlayback:require('../frontend/playback.js')};
vm.createContext(context);
vm.runInContext(fs.readFileSync(require.resolve('../frontend/app.js'),'utf8'),context);
const run=s=>vm.runInContext(s,context);
run('let paints=[];drawStep=(force,ui)=>paints.push({time:simTime,ui});p={trip:{elapsed_s:100,reached:true}};playbackRate=1;');
for(let i=0;i<=60;i++)run(`tick(${i*1000/60})`);
assert.equal(run('paints.length'),61,'No dropped alternate frames at 60 Hz');
assert.ok(Math.abs(run('simTime')-1)<1e-9,'Wall time remains correct');
assert.ok(run('paints.filter(p=>p.ui).length')<=11,'Text updates are throttled');
events.visibilitychange();run('tick(60000)');
assert.ok(Math.abs(run('simTime')-1)<1e-9,'Hidden tab does not cause a jump');
run('simTime=99.99;tick(60020)');
assert.equal(run('simTime'),100);
assert.equal(run('timer'),null);
assert.equal(run('paints.at(-1).ui'),true,'Final state is always painted');
console.log('7 smooth playback assertions passed.');
const {frameMeter}=require('../frontend/playback.js');
for(const hz of [30,60,120]){
 const meter=frameMeter();let result;
 for(let i=0;i<=hz+1;i++)result=meter.push(i*1000/hz)||result;
 assert.equal(result.fps,hz,'Meter must distinguish 30/60/120 Hz');
 assert.equal(result.slow>0,hz===30);
 meter.reset();assert.equal(meter.push(100000),null);
}
run(`
 let projected;
 L={marker(){return {};}};
 const moving=smoothVehicleMarker([0,0],{});
 moving._icon={};moving._latlng=[0,0];
 moving._map={getZoom:()=>16,getPixelOrigin:()=>({x:100,y:200}),project:()=>({subtract:origin=>({x:100.25-origin.x,y:200.75-origin.y})})};
 moving._setPos=point=>{projected=point;};moving.update();
`);
assert.equal(run('projected.x'),.25);assert.equal(run('projected.y'),.75);
console.log('11 cadence and subpixel assertions passed.');
