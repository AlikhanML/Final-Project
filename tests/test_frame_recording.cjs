const assert=require('node:assert/strict');
const {frameRecording}=require('../frontend/playback.js');
for(const hz of [30,60,120]){
 const meter=frameRecording(20000);let result;
 for(let i=0;i<=hz*20+1&&!result;i++)result=meter.push(i*1000/hz);
 assert.ok(result);assert.ok(Math.abs(result.fps-hz)<.01);
 assert.ok(Math.abs(result.p95_ms-1000/hz)<.01);
 assert.equal(result.slow_frames>0,hz===30);
}
const meter=frameRecording(1000);assert.equal(meter.push(0),null);
for(let t=10;t<900;t+=10)assert.equal(meter.push(t),null);
const stalled=meter.push(1100);
assert.equal(stalled.max_ms,210);assert.equal(stalled.slow_frames,1);
assert.ok(stalled.fps<100);assert.equal(stalled.p95_ms,10);
console.log('Frame recording: 30/60/120 Hz and long-stall statistics passed.');
