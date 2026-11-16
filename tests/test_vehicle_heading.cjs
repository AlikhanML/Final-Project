const assert=require('node:assert/strict');
const {heading,unwrapHeading}=require('../frontend/playback.js');
assert.equal(heading([[51,71],[52,71]],0),0);
assert.equal(heading([[51,71],[51,72]],0),90);
assert.equal(heading([[51,71],[50,71]],0),180);
assert.equal(heading([[51,71],[51,70]],0),270);
const path=[[51,71],[51,72],[51,72],[52,72]];
assert.equal(heading(path,1),90); // stationary segment retains incoming direction
assert.equal(heading(path,2),0);
assert.equal(heading(path,3),0); // arrival retains last direction
assert.equal(heading([[51,71],[51,71],[51,72]],0),90);
assert.equal(heading([[51,71],[51,71]],0),null);
assert.equal(unwrapHeading(350,10),370);
assert.equal(unwrapHeading(10,350),-10);
assert.equal(unwrapHeading(null,270),270);
assert.equal(unwrapHeading(720,90),810);
console.log('13 vehicle heading assertions passed.');
