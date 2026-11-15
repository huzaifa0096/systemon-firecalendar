(() => {
  const byId = id => document.getElementById(id);
  const status = byId("liveStatus");
  if (!window.L) {
    status.textContent = "Map could not load. Check your connection and reload.";
    return;
  }
  const map = L.map("worldMap", {preferCanvas:true, minZoom:2, maxZoom:18, maxBounds:[[-85,-180],[85,180]], maxBoundsViscosity:1, scrollWheelZoom:true, touchZoom:true, doubleClickZoom:true});
  const streets = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',noWrap:true});
  const imagery = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {attribution:"Imagery © Esri and contributors",noWrap:true});
  imagery.addTo(map);
  const labelPane = map.createPane("placeLabels");
  labelPane.style.zIndex = 610;
  labelPane.style.pointerEvents = "none";
  const labels = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}", {
    pane:"placeLabels", maxNativeZoom:16, maxZoom:18, noWrap:true, attribution:"Place labels © Esri"
  }).addTo(map);
  map.on("baselayerchange", event => {
    if(event.layer === imagery) labels.addTo(map);
    else labels.remove();
  });
  const thermalStatus=byId("thermalStatus");
  thermalStatus.textContent="Archived fire observations over a current basemap.";
  L.control.layers({"Street map":streets,"Satellite imagery":imagery}).addTo(map);
  const panel=byId("worldMap").closest(".world");
  function expand(on){
    panel.classList.toggle("expanded",on);
    byId("expandMap").setAttribute("aria-pressed",String(on));
    byId("expandMap").textContent=on?"Close expanded map":"Expand map";
    byId("mapFullscreen").textContent=on?"Exit fullscreen":"Fullscreen";
    byId("mapFullscreen").setAttribute("aria-pressed",String(on));
    requestAnimationFrame(()=>map.invalidateSize());
  }
  async function toggleFullscreen(){
    if(document.fullscreenElement===panel){await document.exitFullscreen();return;}
    if(panel.classList.contains("expanded")){expand(false);return;}
    expand(true);
    try{if(panel.requestFullscreen)await panel.requestFullscreen();}catch{/* Expanded layout supports embedded browsers. */}
  }
  byId("expandMap").onclick=toggleFullscreen;
  byId("mapFullscreen").onclick=toggleFullscreen;
  document.addEventListener("fullscreenchange",()=>expand(document.fullscreenElement===panel));
  document.addEventListener("keydown",e=>{if(e.key==="Escape"&&panel.classList.contains("expanded")&&!document.fullscreenElement)expand(false);});
  L.control.scale({imperial:false}).addTo(map);
  const fires = L.layerGroup().addTo(map);
  const utc = value => new Date(value).toISOString().slice(0,16).replace("T"," ")+" UTC";
  function bounds(){
    const b=map.getBounds();
    return [Math.max(60,b.getWest()),Math.max(23,b.getSouth()),Math.min(79,b.getEast()),Math.min(38,b.getNorth())];
  }
  let selection, selecting=false, anchor, preview;
  let briefingData=null;
  const report=byId("watchReport"), draw=byId("drawArea");
  const surface=map.getContainer();
  function finishDrawing(){
    selecting=false;
    anchor=null;
    if(preview) preview.remove();
    preview=null;
    map.dragging.enable();
    surface.classList.remove("drawing");
    draw.textContent="Draw watch area";
  }
  draw.onclick=()=>{
    if(selecting){finishDrawing();schedule();return;}
    selecting=true;
    map.dragging.disable();
    surface.classList.add("drawing");
    draw.textContent="Cancel drawing";
    report.textContent="Drag across the map, or tap two opposite corners.";
  };
  function corner(event){
    return map.mouseEventToLatLng(event);
  }
  function outline(point){
    const box=L.latLngBounds(anchor,point);
    if(preview) preview.setBounds(box);
    else preview=L.rectangle(box,{color:"#edf7ff",weight:2,fillColor:"#407dae",fillOpacity:.13,interactive:false}).addTo(map);
    return box;
  }
  surface.addEventListener("pointerdown",event=>{
    if(!selecting || !event.isPrimary || event.button!==0 || event.target.closest(".leaflet-control"))return;
    event.preventDefault();
    event.stopPropagation();
    if(!allowedPoint(corner(event))){report.textContent="Select a point inside Pakistan.";return;}
    if(!anchor) anchor=corner(event);
    surface.setPointerCapture(event.pointerId);
  },true);
  surface.addEventListener("pointermove",event=>{
    if(selecting && anchor && event.isPrimary) outline(corner(event));
  });
  surface.addEventListener("pointerup",event=>{
    if(!selecting || !anchor || !event.isPrimary)return;
    const point=corner(event), delta=map.latLngToContainerPoint(point).subtract(map.latLngToContainerPoint(anchor));
    if(Math.min(Math.abs(delta.x),Math.abs(delta.y))<5)return;
    if(!allowedPoint(point)){report.textContent="Choose the opposite corner inside Pakistan.";return;}
    outline(point);
    if(selection)selection.remove();
    selection=preview;
    briefingData=null;
    preview=null;
    finishDrawing();
    byId("clearArea").hidden=false;
    document.dispatchEvent(new CustomEvent("archive-area",{detail:watchedBounds()}));
    schedule();
  });
  byId("clearArea").onclick=()=>{
    finishDrawing();
    selection?.remove();selection=null;
    byId("clearArea").hidden=true;
    schedule();
  };
  function watchedBounds(){
    if(!selection)return bounds();
    const b=selection.getBounds();
    return [b.getWest(),b.getSouth(),b.getEast(),b.getNorth()];
  }
  window.fireMap = {bounds, setArea:([w,s,e,n])=>map.fitBounds([[s,w],[n,e]],{maxZoom:16,animate:false})};
  let outlineRequest;
  function countryRings(){
    if(!outlineRequest) outlineRequest=fetch("assets/pakistan-boundary.json",{signal:AbortSignal.timeout(12000)})
      .then(async res=>{
        if(!res.ok)throw Error();
        const json=await res.json();
        const geometry=json;
        return geometry.type==="Polygon" ? [geometry.coordinates] : geometry.coordinates;
      }).catch(err=>{outlineRequest=null;throw err;});
    return outlineRequest;
  }
  function inRing(x,y,ring){
    let inside=false;
    for(let i=0,j=ring.length-1;i<ring.length;j=i++){
      const [ax,ay]=ring[i], [bx,by]=ring[j];
      if((ay>y)!==(by>y) && x<(bx-ax)*(y-ay)/(by-ay)+ax)inside=!inside;
    }
    return inside;
  }
  let ring;
  countryRings().then(polygons=>{
    ring=polygons[0][0];
  }).catch(()=>{report.textContent="Pakistan boundary unavailable. Reload to select an area.";});
  function allowedPoint(point){return ring && inRing(point.lng,point.lat,ring);}
  window.fireMap.acceptsArea = async ([w,s,e,n])=>{
    const [[boundary]]=await countryRings();
    if(!(60<=w && w<e && e<=79 && 23<=s && s<n && n<=38))return false;
    if([[w,s],[w,n],[e,s],[e,n]].some(([x,y])=>inRing(x,y,boundary)))return true;
    return boundary.some(([x,y],i)=>{
      if(x>=w && x<=e && y>=s && y<=n)return true;
      const [a,b]=boundary[(i+1)%boundary.length];
      return [w,e].some(edge=>{
        const t=(edge-x)/(a-x), cross=y+t*(b-y);
        return t>=0 && t<=1 && cross>=s && cross<=n;
      }) || [s,n].some(edge=>{
        const t=(edge-y)/(b-y), cross=x+t*(a-x);
        return t>=0 && t<=1 && cross>=w && cross<=e;
      });
    });
  };
  let generation=0,timer,activeRequest,playTimer,playing=false;
  const historyCache=new Map();
  const timeSlider=byId("mapTime"),timeLabel=byId("mapTimeLabel");
  const briefing=document.createElement("section");
  briefing.className="area-briefing";
  briefing.setAttribute("aria-label","Selected area briefing");
  briefing.setAttribute("aria-live","polite");
  briefing.hidden=true;
  byId("watchReport").after(briefing);
  function renderBriefing(){
    briefing.hidden=!selection;
    if(!selection)return;
    briefing.replaceChildren();
    const title=document.createElement("h3");title.textContent="Selected area";briefing.append(title);
    const matches=briefingData?.bbox?.every((value,i)=>Math.abs(value-watchedBounds()[i])<.0001);
    if(!matches){
      const note=document.createElement("p");note.textContent="Analyze this selected rectangle to load its historical briefing.";
      briefing.append(note);return;
    }
    const month=selectedMonth()||briefingData.rows.at(-1)?.month;
    const row=briefingData.rows.find(item=>item.month===month);
    const previous=month?(Number(month.slice(0,4))-1)+month.slice(4):null;
    const prior=briefingData.rows.find(item=>item.month===previous);
    const description=document.createElement("p");
    description.textContent=(selectedMonth()?"Archive month: ":"Latest historical reference: ")+(month||"Unavailable")+". Monthly values use the local historical archive.";
    briefing.append(description);
    const stats=document.createElement("dl");
    const number=value=>value==null?"Unavailable":value.toLocaleString("en",{maximumFractionDigits:1});
    const change=row&&!row.partial&&prior&&!prior.partial&&prior.harmonized>0?100*(row.harmonized/prior.harmonized-1):null;
    const fields=[
      ["Harmonized fire cell-days",number(row?.harmonized)],
      ["Same month, previous year",change==null?"Unavailable":(change>0?"+":"")+number(change)+"%"],
      ["Area held-out annual error",number(briefingData.validation?.loyo_error_pct)+(briefingData.validation?.loyo_error_pct==null?"":"%")],
      ["Sensor source",row?.source||"Outside selected date range"]
    ];
    for(const [label,value] of fields){const item=document.createElement("div"),term=document.createElement("dt"),definition=document.createElement("dd");term.textContent=label;definition.textContent=value;item.append(term,definition);stats.append(item);}
    briefing.append(stats);
    const coverage=document.createElement("p");coverage.className="briefing-coverage";
    coverage.textContent=(row?"Model date availability: "+(row.partial?"partial month":"full calendar month for the selected source")+". ":"Choose a timeline month within the analysis date range. ")+"Error uses "+(briefingData.validation?.years_tested||0)+" held-out years. Cloud-free observation coverage is unavailable; zero detections can include missed fires.";
    briefing.append(coverage);
  }
  document.addEventListener("archive-results",event=>{briefingData=event.detail;renderBriefing();});
  function updateTimelineControls(){
    const value=Number(timeSlider.value);
    timeSlider.style.setProperty("--timeline-progress",(value/Number(timeSlider.max)*100)+"%");
    byId("mapPrevious").disabled=value===0;
    byId("mapNext").disabled=value===Number(timeSlider.max);
  }
  updateTimelineControls();
  function stopPlayback(){
    playing=false;clearTimeout(playTimer);
    byId("mapPlay").textContent="\u25b6";
    byId("mapPlay").setAttribute("aria-label","Play timeline");
    byId("mapPlay").setAttribute("aria-pressed","false");
  }
  function advancePlayback(){
    clearTimeout(playTimer);
    if(!playing)return;
    if(Number(timeSlider.value)>=301){stopPlayback();return;}
    playTimer=setTimeout(()=>{if(playing&&!document.hidden){timeSlider.stepUp();updateTimeline();}else stopPlayback();},1000);
  }
  byId("mapPlay").onclick=()=>{
    if(playing){stopPlayback();return;}
    playing=true;
    byId("mapPlay").textContent="\u275a\u275a";
    byId("mapPlay").setAttribute("aria-label","Pause timeline");
    byId("mapPlay").setAttribute("aria-pressed","true");
    if(Number(timeSlider.value)>=301)timeSlider.value="0";
    updateTimeline();
  };
  function selectedMonth(){
    return new Date(Date.UTC(2000,10+Number(timeSlider.value),1)).toISOString().slice(0,7);
  }
  function updateTimeline(){
    updateTimelineControls();
    const month=selectedMonth();
    timeLabel.textContent=new Date(month+"-01T00:00:00Z").toLocaleDateString("en",{month:"long",year:"numeric",timeZone:"UTC"});
    timeSlider.setAttribute("aria-valuetext",timeLabel.textContent);
    panel.querySelector(".world-head p").textContent="Archived fire observations / "+timeLabel.textContent;
    panel.querySelectorAll(".fire-key > span").forEach(span=>span.hidden=Boolean(month));
    panel.querySelector(".fire-key > strong").textContent=month?"Archived detections":"Observation age";
    schedule();
  }
  timeSlider.addEventListener("input",()=>{stopPlayback();updateTimeline();});
  byId("mapPrevious").onclick=()=>{stopPlayback();timeSlider.stepDown();updateTimeline();};
  byId("mapNext").onclick=()=>{stopPlayback();timeSlider.stepUp();updateTimeline();};
  async function refresh(ticket){
    const month=selectedMonth();
    try {
      const polygons=await countryRings();
      if(ticket!==generation)return;
      const [west,south,east,north]=watchedBounds();
      if(!await window.fireMap.acceptsArea([west,south,east,north])){
        if(ticket!==generation)return;
        fires.clearLayers();
        byId("provider").textContent="Pakistan coverage";
        status.textContent="Pan to Pakistan to view satellite detections.";
        report.textContent="Fire analysis is available inside Pakistan.";
        return;
      }
      const historical=new URLSearchParams({month:month||"",west:Math.max(west,60),south:Math.max(south,23),east:Math.min(east,79),north:Math.min(north,38)});
      const url="/api/map/history?"+historical;
      let data=month?historyCache.get(url):null;
      if(!data){
        const controller=new AbortController();activeRequest=controller;
        const timeout=setTimeout(()=>controller.abort(),60000);
        try{
          const response=await fetch(url,{signal:controller.signal});
          data=await response.json();
          if(!response.ok || !Array.isArray(data.features))throw Error();
        }finally{clearTimeout(timeout);}
        if(month){
          if(historyCache.size>=18)historyCache.delete(historyCache.keys().next().value);
          historyCache.set(url,data);
        }
      }
      data.features=data.features.filter(({geometry:g})=>polygons.some(([outer,...holes])=>
        inRing(g.x,g.y,outer) && !holes.some(r=>inRing(g.x,g.y,r))));
      const source="NASA FIRMS archive / Pakistan";
      if(ticket!==generation)return;
      fires.clearLayers();
      byId("provider").textContent=source;

      let strongest = null;
      for(const {geometry,attributes} of data.features){
        const popup=document.createElement("div");
        const color="#ff871c";
        const power=attributes.frp==null||attributes.frp===""?null:Number(attributes.frp);
        const baseRadius=Number.isFinite(power)?Math.min(10,3+Math.sqrt(Math.max(0,power))*.45):4;
        const radius=baseRadius*Math.min(1,Math.max(.28,(map.getZoom()-3)/8));
        const title=document.createElement("strong");
        title.textContent="Thermal hotspot";
        popup.append(title);
        const details=[
          ["Observed",attributes.observation_date||utc(attributes.acq_time)],["Satellite",attributes.satellite],
          ["Detection confidence",({h:"High",n:"Nominal",l:"Low"})[attributes.confidence]||attributes.confidence],
          ["Radiative power",Number.isFinite(power)?power+" MW":"Unavailable"],
          ["Overpass",({D:"Day",N:"Night"})[attributes.daynight]||attributes.daynight||"Unavailable"],
          ["Location",geometry.y.toFixed(4)+", "+geometry.x.toFixed(4)]];
        for(const [label,value] of details){
          const line=document.createElement("div");line.textContent=label+" · "+value;popup.append(line);
        }
        const point = [geometry.y, geometry.x];
        L.circleMarker(point,{radius:radius*1.8,stroke:false,fillColor:color,fillOpacity:.08,interactive:false}).addTo(fires);
        const marker=L.circleMarker(point,{radius:radius+1,stroke:false,fillColor:color,fillOpacity:.5})
          .bindPopup(popup,{autoPan:false}).addTo(fires);
        if(Number.isFinite(power) && (!strongest || power > strongest.power)) strongest = {power,marker};
      }
      const inspect = byId("inspectPeak");
      inspect.hidden = !strongest;
      if(strongest){
        inspect.textContent = "Inspect strongest signal · " + strongest.power + " MW";
        inspect.onclick = () => strongest.marker.openPopup();
      }
      if(month)report.textContent=timeLabel.textContent+" · "+data.total.toLocaleString()+" archived vegetation fire detections in this area. These are satellite observations; incident confirmation is unavailable.";


      const count=data.features.length;
      status.textContent=(data.exceededTransferLimit?"Showing the 2,000 strongest detections of "+data.total.toLocaleString()+". Zoom in for more detail.":count+" archived detections shown.")+" Month: "+month+". Filtered vegetation fires from the local archive.";
    } catch {
      if(ticket===generation){stopPlayback();report.textContent="Historical observations could not load.";fires.clearLayers();byId("provider").textContent="Archive unavailable";status.textContent="Archive unavailable. Refresh to retry.";}
    } finally {
      if(ticket===generation){
        panel.classList.remove("map-loading");
        byId("worldMap").setAttribute("aria-busy","false");
        advancePlayback();
      }
    }
  }
  function schedule(){
    clearTimeout(timer);
    clearTimeout(playTimer);
    renderBriefing();
    activeRequest?.abort();
    panel.classList.add("map-loading");
    byId("worldMap").setAttribute("aria-busy","true");

    if(!selecting)report.textContent="Reading archived observations...";
    const ticket=++generation;
    byId("inspectPeak").hidden=true; byId("provider").textContent="Checking source...";
    status.textContent="Loading "+selectedMonth()+" observations...";
    timer=setTimeout(()=>refresh(ticket),80);
  }
  map.on("moveend",()=>{if(!selection && !selecting)schedule();});
  byId("refreshLive").onclick=schedule;
  document.addEventListener("visibilitychange",()=>{if(document.hidden)stopPlayback();});
  updateTimeline();
  let searchId=0;
  byId("placeForm").onsubmit=async event=>{
    event.preventDefault();
    const id=++searchId, results=byId("places");
    results.textContent="Searching places...";
    const params=new URLSearchParams({sourceCountry:"PAK",SingleLine:byId("place").value.trim(),f:"json",outSR:"4326",maxLocations:"5",outFields:"Addr_type,Region,Country"});
    try {
      const response=await fetch("https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates?"+params,{signal:AbortSignal.timeout(15000)});
      const data=await response.json();
      if(id!==searchId)return;
      if(!response.ok||!Array.isArray(data.candidates))throw Error();
      results.replaceChildren();
      data.candidates=data.candidates.filter(item=>allowedPoint({lng:item.location.x,lat:item.location.y}) && ["PAK","PK","PAKISTAN"].includes(String(item.attributes?.Country).toUpperCase()));
      if(!data.candidates.length)results.textContent="No matching place. Search for a place in Pakistan.";
      for(const item of data.candidates){
        const button=document.createElement("button");
        button.type="button"; button.textContent=[item.address,item.attributes?.Region,item.attributes?.Country,item.attributes?.Addr_type].filter(Boolean).join(" · ");
        button.onclick=()=>{
          results.replaceChildren();byId("place").value=item.address;
          if(item.extent){const e=item.extent;map.fitBounds([[e.ymin,e.xmin],[e.ymax,e.xmax]],{maxZoom:16});}
          else map.setView([item.location.y,item.location.x],12);
        };
        results.append(button);
      }
    } catch {if(id===searchId)results.textContent="Place search unavailable. Pan and zoom to your area.";}
  };
})();


