// Guard the CSS regression that shrank Leaflet's SVG renderer to icon size.
const fs=require('fs'),assert=require('node:assert/strict');
const css=fs.readFileSync(require.resolve('../frontend/style.css'),'utf8');
assert.ok(css.includes('svg[aria-hidden="true"]{width:25px;height:25px;'));
assert.ok(!/(?:^|\})\s*svg\s*\{/.test(css),'Global SVG rules must not resize the map renderer');
assert.ok(css.includes('.vehicle-ambulance svg{display:block;width:36px;height:50px;'));
const source=fs.readFileSync(require.resolve('../frontend/app.js'),'utf8');
assert.ok(source.includes('<svg viewBox="0 0 24 24" aria-hidden="true">'));
assert.ok(source.includes("L.svg({pane:'routeLines',padding:.5})"));
console.log('5 route SVG/icon style regression checks passed.');
