const assert=require('node:assert/strict');
const {sample,advance,formatTime}=require('../frontend/playback.js');
const path=[[0,0],[0,1],[1,1]],times=[0,10,30];
assert.deepEqual(sample(path,times,5).position,[0,.5]);
assert.deepEqual(sample(path,times,20).position,[.5,1]);
assert.deepEqual(sample(path,times,10).position,[0,1]);
assert.deepEqual(sample(path,times,100).position,[1,1]);
assert.deepEqual(sample([[1,2]],[0],20).position,[1,2]);
assert.equal(advance(10,1,1,100),11);
assert.equal(advance(10,1,10,100),20);
assert.equal(advance(10,20,10,100),100);
assert.deepEqual(sample([[0,0],[0,1],[0,1]],[0,10,20],15).position,[0,1]);
assert.equal(formatTime(125),'2:05');
console.log('10 playback assertions passed.');
assert.deepEqual(sample(path,[0,10,45],15,[0,15]).position,[0,1]);
assert.deepEqual(sample(path,[0,10,45],25,[0,15]).position,[0,1]);
assert.deepEqual(sample(path,[0,10,45],35,[0,15]).position,[.5,1]);
assert.deepEqual(sample(path,[0,10,45],45,[0,15]).position,[1,1]);
console.log('4 turn-pause playback assertions passed.');
// Remaining distance follows geometry and holds steady during a turn pause.
{
 const q=require('../frontend/playback.js');
 const path=[[51,71],[51,71.01],[51.01,71.01]],times=[0,20,40];
 const start=q.remainingKm(path,q.sample(path,times,0,[10,0]));
 assert.ok(start>1.7&&start<1.9);
 assert.equal(q.remainingKm(path,q.sample(path,times,5,[10,0])),start);
 const mid=q.remainingKm(path,q.sample(path,times,15,[10,0]));
 assert.ok(mid<start&&mid>1.1);
 assert.equal(q.remainingKm(path,q.sample(path,times,40,[10,0])),0);
 assert.equal(q.remainingKm(path,q.sample(path,times,0,[10,0])),start);
 console.log('5 remaining-distance assertions passed.');
}
