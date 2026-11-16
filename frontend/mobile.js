/* Presentation only: never changes GPS, destination, routing or playback state. */
(() => {
 const screen=document.getElementById('screen');
 const panel=document.querySelector('.dispatch-panel');
 const title=document.getElementById('route-title');
 panel.id='mobile-route-panel';
 const toggle=document.createElement('button');
 toggle.type='button';toggle.className='mobile-panel-toggle';
 toggle.setAttribute('aria-controls',panel.id);toggle.setAttribute('aria-expanded','false');
 const label=document.createElement('span');toggle.appendChild(label);
 const updateLabel=()=>{label.textContent=p.b?title.textContent:document.getElementById("hint").textContent;screen.classList.toggle("mobile-empty",!p.b);};
 updateLabel();new MutationObserver(updateLabel).observe(title,{childList:true,characterData:true,subtree:true});
 panel.prepend(toggle);
 const originalRender=render;
 render=function(payload){originalRender(payload);updateLabel();};
 toggle.addEventListener('click',()=>{
  const expanded=screen.classList.toggle('mobile-expanded');
  toggle.setAttribute('aria-expanded',String(expanded));panel.scrollTop=0;
 });
 // Fit the embedded map to the phone viewport, including browser chrome changes.
 const originalResize=resize;
 resize=function(){
  if(window.innerWidth>=800){originalResize();return;}
  let available=window.innerHeight;
  try{available=(window.parent.visualViewport?.height||window.parent.innerHeight)-52;}catch(e){}
  const h=Math.max(320,Math.min(1200,Math.round(available)));
  lastHeight=h;lastWidth=window.innerWidth;document.body.style.height=h+'px';
  post('streamlit:setFrameHeight',{height:h});if(map)map.invalidateSize({pan:false});
 };
 window.addEventListener('resize',()=>resize());
 try{window.parent.visualViewport?.addEventListener('resize',()=>resize());}catch(e){}
 resize();
})();
