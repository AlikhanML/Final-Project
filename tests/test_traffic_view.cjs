const assert=require('node:assert/strict');
const {build}=require('../frontend/traffic_view.js');
const bands=[[],[],[],[]];
for(let y=0;y<100;y++)for(let x=0;x<100;x++)bands[(x+y)%4].push([[51+y*.002,71+x*.002],[51+y*.002+.001,71+x*.002+.001]]);
// Crossing line: neither endpoint is inside viewport. Must remain visible.
bands[3].push([[50,70],[53,74]]);
const snapshot=JSON.stringify(bands),index=build(bands);
const box={south:51.05,west:71.05,north:51.07,east:71.07};
const begin=performance.now();const visible=index.query(box);const ms=performance.now()-begin;
const brute=bands.map(lines=>lines.filter(line=>Math.min(...line.map(p=>p[0]))<=box.north&&Math.max(...line.map(p=>p[0]))>=box.south&&Math.min(...line.map(p=>p[1]))<=box.east&&Math.max(...line.map(p=>p[1]))>=box.west));
assert.deepEqual(visible,brute);
assert.equal(JSON.stringify(bands),snapshot);
assert.deepEqual(index.query(null),bands);
assert.equal(index.query({south:-90,west:-180,north:90,east:180}).flat().length,index.count);
assert.equal(index.query({south:0,west:0,north:1,east:1}).flat().length,0);
assert.equal(build([[],[],[],[]]).query(box).flat().length,0);
console.log(JSON.stringify({source_lines:index.count,visible_lines:visible.flat().length,query_ms:ms,synthetic:true}));
console.log('6 traffic viewport assertions passed.');
