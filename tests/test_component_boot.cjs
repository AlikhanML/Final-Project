const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(require.resolve('../frontend/index.html'),'utf8');
const source=fs.readFileSync(require.resolve('../frontend/app.js'),'utf8');
function boot(code,legacy){
 const elements=new Map(),messages=[];
 function element(){return {style:{},append(...nodes){for(const n of nodes)if(n.id)elements.set(n.id,n);}};}
 for(const match of html.matchAll(/\bid="([^"]+)"/g))if(!legacy||match[1]!=='call-priority')elements.set(match[1],element());
 const host=element();
 const context={console,setTimeout,clearTimeout,
 document:{getElementById:id=>elements.get(id)||null,querySelectorAll:()=>[],querySelector:()=>host,createElement:element,body:{style:{}},addEventListener(){}},
 window:{innerWidth:1200,parent:{innerHeight:800,postMessage:m=>messages.push(m)},addEventListener(){}}};
 vm.createContext(context);vm.runInContext(code,context);
 assert.ok(messages.some(m=>m.type==='streamlit:componentReady'));
 assert.equal(typeof elements.get('call-priority').onchange,'function');
}
boot(source,false);boot(source,true);
if(process.argv[2])assert.throws(()=>boot(fs.readFileSync(process.argv[2],'utf8'),true),/null/);
console.log('Component handshake passes with current and legacy HTML.');
