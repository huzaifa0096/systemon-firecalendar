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
  const thermalDate = new Date(Date.now() - 86400000).toISOString().slice(0,10);
  const thermal = L.tileLayer.wms("https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi", {
    layers:"MODIS_Terra_Brightness_Temp_Band31_Day", time:thermalDate,
    format:"image/png", transparent:true, version:"1.1.1", maxNativeZoom:7,
    maxZoom:18, opacity:0.84, attribution:"Thermal imagery: NASA GIBS"
  });
  const thermalStatus = byId("thermalStatus");
  const toggle = byId("thermalView");
  toggle.onchange = () => {
    if(toggle.checked){
      thermalStatus.textContent = "Loading NASA thermal imagery for " + thermalDate + " UTC.";
      thermal.addTo(map);
    } else {
      thermal.remove();
      thermalStatus.textContent = "";
    }
  };
  let tileFailed = false;
  thermal.on("loading", () => { tileFailed = false; });
  thermal.on("tileerror", () => { tileFailed = true; });
  thermal.on("load", () => {
    if(toggle.checked) thermalStatus.textContent = tileFailed
      ? "Some NASA imagery tiles are unavailable. Disable thermal imagery to see the base map."
      : "Terra MODIS daytime brightness temperature · " + thermalDate + " UTC. Clear areas may lack coverage. Detection times are shown separately.";
  });
  L.control.layers({"Street map":streets,"Satellite imagery":imagery}).addTo(map);
  const panel=byId("worldMap").closest(".world");
  function expand(on){
    panel.classList.toggle("expanded",on);
    byId("expandMap").setAttribute("aria-pressed",String(on));
    byId("expandMap").textContent=on?"Close expanded map":"Expand map";
    map.invalidateSize();
  }
  byId("expandMap").onclick=()=>expand(!panel.classList.contains("expanded"));
  document.addEventListener("keydown",e=>{if(e.key==="Escape"&&panel.classList.contains("expanded"))expand(false);});
  L.control.scale({imperial:false}).addTo(map);
  const fires = L.layerGroup().addTo(map);
  const utc = value => new Date(value).toISOString().slice(0,16).replace("T"," ")+" UTC";
  function bounds(){
    const b=map.getBounds();
    return [Math.max(60,b.getWest()),Math.max(23,b.getSouth()),Math.min(79,b.getEast()),Math.min(38,b.getNorth())];
  }
  let selection, selecting=false, anchor, preview;
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
  function activity(features,partial){
    const readings=features.map(f=>f.attributes.frp).filter(v=>v!=null && v!=="").map(Number).filter(v=>Number.isFinite(v)&&v>=0).sort((a,b)=>a-b);
    const scope=selection?"Watch area":"Map view";
    let result="Too few power readings for outlier screening.";
    if(!features.length) result="No satellite detections returned.";
    if(readings.length>=8){
      const quantile=q=>readings[Math.floor((readings.length-1)*q)];
      const threshold=quantile(.75)+1.5*(quantile(.75)-quantile(.25));
      const flagged=readings.filter(v=>v>threshold);
      result=flagged.length ? "Activity alert: "+flagged.length+" unusually strong readings above "+threshold.toFixed(2)+" MW. Peak "+readings.at(-1)+" MW." : "No unusually strong readings in this sample.";
    }
    if(!selecting)report.textContent=scope+" · "+features.length+" detections in 24 h. "+result+
      (partial?" Latest 2,000 only.":"")+" Satellite screening only; incident confirmation unavailable.";
  }
  window.fireMap = {bounds, setArea:([w,s,e,n])=>map.fitBounds([[s,w],[n,e]],{maxZoom:16,animate:false})};
  const feed="https://services9.arcgis.com/RHVPKKiFTONKtxq3/arcgis/rest/services/Satellite_VIIRS_Thermal_Hotspots_and_Fire_Activity/FeatureServer/0/query";
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
  let generation=0,timer;
  async function refresh(ticket){
    const now=Date.now(), end=Math.floor(now/300000)*300000;
    const params=new URLSearchParams({f:"json",where:"1=1",geometry:watchedBounds().join(","),geometryType:"esriGeometryEnvelope",inSR:"4326",outSR:"4326",spatialRel:"esriSpatialRelIntersects",time:[end-86400000,end].join(","),outFields:"satellite,acq_time,confidence,frp,daynight",returnGeometry:"true",orderByFields:"acq_time DESC",resultRecordCount:"2000"});
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
      params.set("geometry",[Math.max(west,60),Math.max(south,23),Math.min(east,79),Math.min(north,38)].join(","));
      const response=await fetch(feed+"?"+params,{signal:AbortSignal.timeout(20000)});
      const data=await response.json();
      if(!response.ok || !Array.isArray(data.features))throw Error();
      data.features=data.features.filter(({geometry:g})=>polygons.some(([outer,...holes])=>
        inRing(g.x,g.y,outer) && !holes.some(r=>inRing(g.x,g.y,r))));
      const source="NASA FIRMS via Esri · Pakistan";
      if(ticket!==generation)return;
      fires.clearLayers();
      byId("provider").textContent=source;

      let strongest = null;
      for(const {geometry,attributes} of data.features){
        const popup=document.createElement("div");
        const hours=Math.max(0,(now-attributes.acq_time)/3600000);
        const color=hours<3?"#ff354e":hours<12?"#ff871c":"#ffd342";
        const power=attributes.frp==null||attributes.frp===""?null:Number(attributes.frp);
        const radius=Number.isFinite(power)?Math.min(10,3+Math.sqrt(Math.max(0,power))*.45):4;
        const title=document.createElement("strong");
        title.textContent="Thermal hotspot";
        popup.append(title);
        const details=[
          ["Observed",utc(attributes.acq_time)],["Satellite",attributes.satellite],
          ["Detection confidence",({h:"High",n:"Nominal",l:"Low"})[attributes.confidence]||attributes.confidence],
          ["Radiative power",Number.isFinite(power)?power+" MW":"Unavailable"],
          ["Overpass",({D:"Day",N:"Night"})[attributes.daynight]||attributes.daynight||"Unavailable"],
          ["Location",geometry.y.toFixed(4)+", "+geometry.x.toFixed(4)]];
        for(const [label,value] of details){
          const line=document.createElement("div");line.textContent=label+" · "+value;popup.append(line);
        }
        const point = [geometry.y, geometry.x];
        L.circleMarker(point,{radius:radius*1.8,stroke:false,fillColor:color,fillOpacity:.23,interactive:false}).addTo(fires);
        const marker=L.circleMarker(point,{radius:radius+1,stroke:false,fillColor:color,fillOpacity:.83})
          .bindPopup(popup,{autoPan:false}).addTo(fires);
        if(Number.isFinite(power) && (!strongest || power > strongest.power)) strongest = {power,marker};
      }
      const inspect = byId("inspectPeak");
      inspect.hidden = !strongest;
      if(strongest){
        inspect.textContent = "Inspect strongest signal · " + strongest.power + " MW";
        inspect.onclick = () => strongest.marker.openPopup();
      }
      activity(data.features,data.exceededTransferLimit);

      const count=data.features.length;
      status.textContent=(data.exceededTransferLimit?""+count+" Pakistan detections in a capped regional sample. Zoom in for more.":count+" detections in view.")+(count?" Latest observation: "+utc(data.features[0].attributes.acq_time)+".":"")+" Checked "+utc(now)+".";
    } catch {
      if(ticket===generation){report.textContent="Activity unknown. Satellite feed unavailable.";fires.clearLayers();byId("provider").textContent="Feed offline";status.textContent="Detection feed unavailable. Refresh to retry.";}
    }
  }
  function schedule(){
    clearTimeout(timer);

    if(!selecting)report.textContent="Checking satellite activity...";
    const ticket=++generation;
    byId("inspectPeak").hidden=true; byId("provider").textContent="Checking source...";
    status.textContent="Checking recent detections in this area...";
    timer=setTimeout(()=>refresh(ticket),300);
  }
  map.on("moveend",()=>{if(!selection && !selecting)schedule();});
  byId("refreshLive").onclick=schedule;
  setInterval(()=>{if(!document.hidden)schedule();},300000);
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


