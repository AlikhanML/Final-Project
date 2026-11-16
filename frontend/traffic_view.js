/* Display-only spatial index. Never changes routing costs or source geometry. */
(function(root){
  function unpack(packed){
    return packed.map(band=>{
      const bytes=atob(band),lines=[];
      let offset=0;
      function read(){
        let value=0,factor=1;
        while(offset<bytes.length&&factor<=2**35){
          const byte=bytes.charCodeAt(offset++);
          value+=(byte&127)*factor;
          if(byte<128)return value;
          factor*=128;
        }
        throw new Error('Invalid Qadam traffic coordinates.');
      }
      const signed=value=>value%2?-(value+1)/2:value/2;
      while(offset<bytes.length){
        const count=read(),line=[];
        let lat=0,lon=0;
        if(count<2||count>(bytes.length-offset)/2)throw new Error('Invalid Qadam traffic line.');
        for(let i=0;i<count;i++){
          lat+=signed(read());lon+=signed(read());
          line.push([lat/1e7,lon/1e7]);
        }
        lines.push(line);
      }
      return lines;
    });
  }
  function build(bands){
    const size=.02,cells=new Map(),wide=[],items=[];
    bands.forEach((lines,band)=>lines.forEach(line=>{
      if(line.length<2)return;
      let south=Infinity,west=Infinity,north=-Infinity,east=-Infinity;
      for(const [lat,lon] of line){south=Math.min(south,lat);north=Math.max(north,lat);west=Math.min(west,lon);east=Math.max(east,lon);}
      if(![south,west,north,east].every(Number.isFinite))return;
      const id=items.length;items.push({line,band,south,west,north,east});
      const x0=Math.floor(west/size),x1=Math.floor(east/size),y0=Math.floor(south/size),y1=Math.floor(north/size);
      if((x1-x0+1)*(y1-y0+1)>256){wide.push(id);return;}
      for(let x=x0;x<=x1;x++)for(let y=y0;y<=y1;y++){
        const key=x+','+y;if(!cells.has(key))cells.set(key,[]);cells.get(key).push(id);
      }
    }));
    return {query(box){
      const result=[[],[],[],[]];
      if(!box){for(const item of items)result[item.band].push(item.line);return result;}
      const {south,west,north,east}=box;
      const x0=Math.floor(west/size),x1=Math.floor(east/size),y0=Math.floor(south/size),y1=Math.floor(north/size);
      const ids=new Set(wide);
      // A world-scale viewport must not iterate millions of empty grid cells.
      if((x1-x0+1)*(y1-y0+1)>4096){for(let i=0;i<items.length;i++)ids.add(i);}
      else for(let x=x0;x<=x1;x++)for(let y=y0;y<=y1;y++)for(const id of cells.get(x+','+y)||[])ids.add(id);
      for(const id of [...ids].sort((a,b)=>a-b)){
        const item=items[id];
        if(item.south<=north&&item.north>=south&&item.west<=east&&item.east>=west)result[item.band].push(item.line);
      }
      return result;
    },count:items.length};
  }
  root.QadamTrafficView={build,unpack};
  if(typeof module!=='undefined')module.exports={build,unpack};
})(globalThis);
