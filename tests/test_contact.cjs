const fs = require('fs');
const vm = require('vm');
const assert = require('node:assert/strict');
const buttons = {};
for (const id of ['contact-call', 'contact-chat']) {
  buttons[id] = {addEventListener(event, handler) { this.click = handler; }};
}
const events = [];
const context = {
  document: {getElementById: id => buttons[id], referrer: 'http://localhost:8501/'},
  window: {parent: {location: {href: 'http://localhost:8501/'}}},
  p: {}, pending: null,
  render(payload) { context.p = payload; },
  emit(type, data) { events.push({type, ...data}); context.pending = 'request'; }
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(require.resolve('../frontend/contact.js'), 'utf8'), context);
assert.equal(buttons['contact-call'].disabled, true);
buttons['contact-chat'].click();
assert.equal(events.length, 0);
context.render({b: [51.1, 71.4]});
assert.equal(buttons['contact-chat'].disabled, false);
buttons['contact-chat'].click();
assert.equal(events[0].mode, 'chat');
assert.equal(events[0].page_url, 'http://localhost:8501/');
buttons['contact-call'].click();
assert.equal(events.length, 1);
context.pending = null;
context.render({b: [51.1, 71.4]});
buttons['contact-call'].click();
assert.equal(events[1].mode, 'call');
context.pending = null;
context.render({b: null});
assert.equal(buttons['contact-call'].disabled, true);
console.log('Contact actions respect selection, pending events and both contact modes.');

const frames = {children:[], replaceChildren(){this.children=[];}, appendChild(frame){this.children.push(frame);}};
const dialog = {open:false, showModal(){this.open=true;}, close(){this.open=false;}};
Object.assign(buttons, {'quick-frames':frames, 'quick-contact':dialog, 'quick-close':{}, 'quick-title':{}});
context.document.createElement = () => ({dataset:{}});
context.location = {origin:'http://localhost:8501'};
context.URL=URL;
vm.runInContext(fs.readFileSync(require.resolve('../frontend/contact.js'),'utf8'),context);
const selected = {b:[51.1,71.4],theme:'dark',contact_room:{dispatcher:'dispatcher-token',caller:'caller-token'}};
context.render(selected);
const prepared = [...frames.children];
assert.equal(prepared.length,2);
context.render(selected);
assert.equal(frames.children[0],prepared[0]);
for (const mode of ['chat','call']) {
  buttons['contact-'+mode].click();
  assert.equal(dialog.open,true);
  assert.equal(frames.children.filter(frame=>!frame.hidden)[0].dataset.mode, mode);
  buttons['quick-close'].onclick();
}
assert.equal(events.length,2);
context.render({b:null});
assert.equal(frames.children.length,0);
