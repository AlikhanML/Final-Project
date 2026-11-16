/* Pure timeline math: playback rate never changes route ETA. */
(function(root){
  function formatTime(seconds){
    const total=Math.max(0,Math.ceil(seconds));
    const minutes=Math.floor(total/60),s=total%60;
    return `${minutes}:${String(s).padStart(2,'0')}`;
  }
  function sample(path,times,seconds,turnDelays=[]){
    if(!path.length||path.length!==times.length)throw new Error('Invalid timeline');
    const t=Math.max(0,Math.min(seconds,times[times.length-1]));
    let lo=0,hi=times.length-1;
    while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(times[mid]<=t)lo=mid;else hi=mid-1;}
    const i=lo,j=Math.min(i+1,path.length-1),dt=times[j]-times[i];
    const delay=Math.max(0,Math.min(dt,Number(turnDelays?.[i]||0)));
    const moving=dt-delay;
    const fraction=moving>0?Math.max(0,(t-times[i]-delay)/moving):0;
    return {index:i,fraction,position:path[i].map((v,k)=>v+(path[j][k]-v)*fraction)};
  }
  function advance(current,wallSeconds,rate,total){
    return Math.min(total,Math.max(0,current)+Math.max(0,wallSeconds)*rate);
  }
  // Cache suffix distances once per immutable trip path, not once per frame.
  const distanceCache=new WeakMap();
  function remainingKm(path,motion){
    let suffix=distanceCache.get(path);
    if(!suffix){
      suffix=new Float64Array(path.length);
      const rad=Math.PI/180;
      for(let i=path.length-2;i>=0;i--){
        const [a,b]=path[i],[c,d]=path[i+1];
        const h=Math.sin((c-a)*rad/2)**2+Math.cos(a*rad)*Math.cos(c*rad)*Math.sin((d-b)*rad/2)**2;
        suffix[i]=suffix[i+1]+6371*2*Math.asin(Math.sqrt(Math.max(0,Math.min(1,h))));
      }
      distanceCache.set(path,suffix);
    }
    const i=motion.index;
    if(i>=path.length-1)return 0;
    return Math.max(0,suffix[i+1]+(suffix[i]-suffix[i+1])*(1-Math.max(0,Math.min(1,motion.fraction))));
  }
  // Measured callback cadence, not a guarantee that the GPU presented every frame.
  function frameMeter(){
    let start=null,last=null,count=0,slow=0;
    return {
      reset(){start=last=null;count=slow=0;},
      push(now){
        if(last===null){start=last=now;return null;}
        const dt=now-last;last=now;count++;if(dt>25)slow++;
        if(now-start<1000)return null;
        const result={fps:Math.round(count*1000/(now-start)),slow};
        start=now;count=slow=0;return result;
      }
    };
  }
  function frameRecording(durationMs=20000){
    let first=null,last=null;const intervals=[];
    return {push(now){
      if(first===null){first=last=now;return null;}
      const dt=now-last;last=now;if(dt>0)intervals.push(dt);
      if(now-first<durationMs&&intervals.length<20000)return null;
      const sorted=[...intervals].sort((a,b)=>a-b),elapsed=now-first;
      return {duration_ms:elapsed,frames:intervals.length,
        fps:intervals.length*1000/elapsed,p95_ms:sorted[Math.max(0,Math.ceil(sorted.length*.95)-1)]||0,
        max_ms:sorted.at(-1)||0,slow_frames:intervals.filter(t=>t>25).length};
    }};
  }
  // Heading in the north-up Web Mercator map, with stable direction at stops/end.
  function heading(path,index){
    const angle=i=>{
      if(i<0||i+1>=path.length)return null;
      const [a,b]=path[i],[c,d]=path[i+1];
      const rad=Math.PI/180;
      const merc=lat=>Math.log(Math.tan(Math.PI/4+Math.max(-85,Math.min(85,lat))*rad/2));
      const dx=(d-b)*rad,dy=merc(c)-merc(a);
      if(Math.abs(dx)+Math.abs(dy)<1e-12)return null;
      return (Math.atan2(dx,dy)*180/Math.PI+360)%360;
    };
    let value=angle(index);if(value!==null)return value;
    for(let i=Math.min(index-1,path.length-2);i>=0;i--){value=angle(i);if(value!==null)return value;}
    for(let i=index+1;i<path.length-1;i++){value=angle(i);if(value!==null)return value;}
    return null;
  }
  function unwrapHeading(previous,target){
    return previous===null?target:previous+((target-previous+540)%360+360)%360-180;
  }
  const api={formatTime,sample,advance,remainingKm,frameMeter,frameRecording,heading,unwrapHeading};root.QadamPlayback=api;
  if(typeof module!=='undefined')module.exports=api;
})(globalThis);
