const el = id => document.getElementById(id);
const form = el("filters");
const coordinateNames = ["west", "south", "east", "north"];
const regions = {Pakistan:[60,23,79,38], Punjab:[69.3,27.7,75.4,34], Sindh:[66.6,23.6,71.2,28.6]};
const months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(" ");
const colors = ["#fff7ed","#ffedd5","#fed7aa","#fdba74","#fb923c","#f97316","#ea580c","#9a3412"];
const fmt = n => n == null ? "—" : n.toLocaleString("en",{maximumFractionDigits:1});
const percent = n => n == null ? "Unavailable" : (n>0?"+":"")+fmt(n)+"%";
const monthName = r => months[r.mon-1]+" "+r.year;
let rows = [], activeQuery, revision=0, comparison=0;
for(const field of document.querySelectorAll(".date-parts")){
  const input=field.querySelector("input");
  const caption=field.querySelector("legend").textContent;
  const [y,m,d]=input.value.split("-").map(Number);
  input.type="hidden";
  function dropdown(label,values,current){
    const select=document.createElement("select");
    select.setAttribute("aria-label",caption+" "+label);
    values.forEach(([value,text])=>select.add(new Option(text,value,false,value===current)));
    field.append(select);
    return select;
  }
  const years=Array.from({length:26},(_,i)=>[2000+i,2000+i]);
  const year=dropdown("year",years,y);
  const month=dropdown("month",months.map((name,i)=>[i+1,name]),m);
  const day=dropdown("day",[],d);
  function sync(preferredDay){
    for(const opt of month.options)opt.disabled=year.value==="2000" && Number(opt.value)<11;
    if(month.selectedOptions[0].disabled)month.value="11";
    const days=new Date(Number(year.value),Number(month.value),0).getDate();
    day.replaceChildren(...Array.from({length:days},(_,i)=>new Option(i+1,i+1)));
    day.value=String(Math.min(preferredDay,days));
    input.value=[year.value,month.value.padStart(2,"0"),day.value.padStart(2,"0")].join("-");
  }
  field.onchange=()=>sync(Number(day.value));
  sync(d);
}
for(const name of coordinateNames){
  const label=document.createElement("label");
  label.textContent=name[0].toUpperCase()+name.slice(1);
  const input=document.createElement("input");
  Object.assign(input,{type:"number",name,step:"any",min:["west","east"].includes(name)?60:23,max:["west","east"].includes(name)?79:38,required:true});
  label.append(input); el("coords").append(label);
  input.oninput=()=>{el("region").value="Custom bounds"; drawBox(coordinateNames.map(n=>Number(form.elements[n].value)));};
}
function drawBox(bounds){
  if(bounds.every(Number.isFinite) && bounds[0]<bounds[2] && bounds[1]<bounds[3]) window.fireMap?.setArea(bounds);
}
function setBox(bounds){
  coordinateNames.forEach((name,i)=>form.elements[name].value=bounds[i]);
  drawBox(bounds);
}
el("region").onchange=()=>{
  const box=regions[el("region").value];
  if(box)setBox(box);else form.querySelector("details").open=true;
};
setBox(regions.Punjab);
el("useExtent").onclick=async()=>{
  const b=window.fireMap?.bounds();
  if(!b){el("extentStatus").textContent="Map unavailable. Enter coordinates below.";return;}
  if(!await window.fireMap.acceptsArea(b)){
    el("extentStatus").textContent="This view is outside the Pakistan archive. Recent Pakistan detections are shown above.";return;
  }
  coordinateNames.forEach((name,i)=>form.elements[name].value=b[i].toFixed(4));
  el("region").value="Custom bounds";
  el("extentStatus").textContent="Visible bounds selected. Analyze to view the Pakistan archive.";
};
document.addEventListener("archive-area", event=>{
  coordinateNames.forEach((name,i)=>form.elements[name].value=event.detail[i].toFixed(5));
  el("region").value="Custom bounds";
  el("extentStatus").textContent="Selected watch area · Pakistan";
  form.requestSubmit();
});
document.querySelectorAll("nav button").forEach(button=>button.onclick=()=>{
  document.querySelectorAll("article").forEach(a=>a.hidden=a.id!==button.dataset.view);
  document.querySelectorAll("nav button").forEach(b=>b.setAttribute("aria-pressed",String(b===button)));
});
async function api(endpoint,query){
  const res=await fetch("/api/"+endpoint+"?"+query);
  if(!res.ok){let msg="Request failed ("+res.status+")";try{const data=await res.json();if(typeof data.detail==="string")msg=data.detail;}catch{}throw Error(msg);}
  return res.json();
}
document.querySelector("#calendar thead").innerHTML="<tr><th>Year</th>"+months.map(m=>"<th>"+m+"</th>").join("")+"</tr>";
function renderCalendar(data){
  rows=data.rows;
  const peak=rows.reduce((a,b)=>a.harmonized>=b.harmonized?a:b);
  const totals=new Map();
  for(const r of rows)totals.set(r.year,(totals.get(r.year)||0)+r.harmonized);
  el("total").textContent=fmt(rows.reduce((s,r)=>s+r.harmonized,0));
  el("peak").textContent=monthName(peak);
  el("peakYear").textContent=[...totals].sort((a,b)=>b[1]-a[1])[0][0];
  const body=document.querySelector("#calendar tbody");body.replaceChildren();
  const years=[...totals.keys()].reverse();
  const cells=new Map();
  for(const y of years){
    const tr=body.insertRow();const th=document.createElement("th");th.scope="row";th.textContent=y;tr.append(th);
    months.forEach((_,i)=>{const cell=tr.insertCell();cell.textContent="—";cells.set(y*12+i+1,cell);});
  }
  for(const r of rows){
    const b=document.createElement("button");
    const level=Math.min(7,Math.floor(8*r.harmonized/Math.max(1,peak.harmonized)));
    b.style.background=colors[level];b.style.color=level<7?"#000":"#fff";
    b.textContent=fmt(r.harmonized);
    const detail="MODIS "+fmt(r.modis)+" · VIIRS "+fmt(r.viirs)+" · "+monthName(r)+" · "+b.textContent+" fire cell-days · "+percent(r.anomaly_pct)+" vs. historical median · "+r.source+(r.partial?" · Partial month":"");
    b.setAttribute("aria-label",detail);
    b.onclick=()=>{body.querySelector('button[aria-pressed="true"]')?.setAttribute("aria-pressed","false"); b.setAttribute("aria-pressed","true"); el("detail").textContent=detail;};
    cells.get(r.year*12+r.mon).replaceChildren(b);
    if(r===peak)b.click();
  }
  el("year").replaceChildren(...years.map(y=>new Option(y,y)));anomalies();
  el("validation").textContent="Validation for this area: monthly correlation "+(data.validation.r??"unavailable")+" · median annual held-out error "+fmt(data.validation.loyo_error_pct)+"% · ratio source: "+data.k_source+". Same-unit national baseline annual error: "+fmt(data.validation.baseline?.annual_error_pct_median)+"%. Held-out years: "+fmt(data.validation.years_tested)+".";
}
function anomalies(){
  const list=rows.filter(r=>r.year===Number(el("year").value));
  const max=Math.max(1,...list.map(r=>Math.abs(r.anomaly_pct||0)));
  el("anomalies").innerHTML=list.map(r=>'<div class="bar"><span>'+months[r.mon-1]+'</span><i class="'+(r.anomaly_pct<0?"negative":"")+'" style="width:'+100*Math.abs(r.anomaly_pct||0)/max+'%"></i><span>'+percent(r.anomaly_pct)+'</span></div>').join("");
}
el("year").onchange=anomalies;
function renderTrust(data){
  el("flags").innerHTML="<h4>"+data.score+" trust · "+(data.latest_year??"No complete season")+"</h4>"+data.flags.map(f=>"<p><strong>"+f.title+"</strong><br>"+f.detail+"</p>").join("");
  for(const [title,series] of [["Morning share",data.terra_share],["Night share",data.night_share]]){
    const entries=Object.entries(series).filter(([year])=>Number(year)>=2012).sort(([a],[b])=>Number(a)-Number(b));
    if(entries.length<2)continue;
    const chart=document.createElement("div");chart.className="season-trend";
    const first=entries[0],last=entries.at(-1);
    chart.textContent=title+" · "+first[0]+" to "+last[0]+" · "+fmt(first[1]*100)+"% → "+fmt(last[1]*100)+"%";
    const bars=document.createElement("div");bars.className="trend-bars";
    for(const [year,value] of entries){
      const bar=document.createElement("i");bar.style.height=Math.max(2,value*100)+"%";
      bar.title=year+" · "+fmt(value*100)+"%";bars.append(bar);
    }
    chart.append(bars);el("flags").append(chart);
  }
  const years=[...new Set([...Object.keys(data.terra_share),...Object.keys(data.night_share)])].sort().reverse();
  const cell=v=>v==null?"—":'<i style="width:'+v*65+'px"></i>'+fmt(v*100)+"%";
  document.querySelector("#shares tbody").innerHTML=years.map(y=>"<tr><th>"+y+"</th><td>"+cell(data.terra_share[y])+"</td><td>"+cell(data.night_share[y])+"</td></tr>").join("");
}
async function compare(event){
  event?.preventDefault();if(!activeQuery)return;
  const current=++comparison;
  const q=new URLSearchParams(activeQuery);
  q.set("policy_year",el("policyYear").value);q.set("years",el("window").value);
  el("verdict").textContent="Comparing complete seasons…";
  try{
    const p=await api("policy_check",q);if(current!==comparison)return;
    el("verdict").innerHTML="<h4>"+p.verdict+"</h4><p>Before ("+(p.before_years.join(", ")||"none")+") · "+fmt(p.before_mean)+" average seasonal fire cell-days<br>After ("+(p.after_years.join(", ")||"none")+") · "+fmt(p.after_mean)+" average seasonal fire cell-days</p><p>Observed change: "+percent(p.change_pct)+" · Against historical median: "+percent(p.vs_median_pct)+"<br>Area seasonal held-out error: "+fmt(p.uncertainty_pct)+"% · After-period trust: "+p.trust.score+"</p>"+p.trust.flags.map(f=>"<p>"+f.detail+"</p>").join("");
    const selectedMonths = q.get("months").split(",").map(Number);
    const expected = Number(q.get("years"));
    const periods = [p.before_years,p.after_years].map(years =>
      rows.filter(row => years.includes(row.year) && selectedMonths.includes(row.mon)));
    const evidence = document.createElement("p");
    evidence.textContent = "Sensor cross-check requires complete before and after seasons with both sensors.";
    if(periods.every(period => period.length === expected * selectedMonths.length &&
        period.every(row => row.viirs != null && row.modis != null))){
      const changes = ["modis","viirs"].map(sensor => {
        const [before,after] = periods.map(period => period.reduce((sum,row) => sum + row[sensor],0));
        return before > 0 ? 100 * (after / before - 1) : null;
      });
      if(changes.every(Number.isFinite)){
        const agreement = Math.sign(changes[0]) === Math.sign(changes[1]);
        evidence.textContent = "Sensor cross-check · " + (agreement ? "Directions agree" : "Directions differ") +
          " · MODIS " + percent(changes[0]) + " · VIIRS " + percent(changes[1]) +
          ". Each change uses that sensor's own before-period count.";
      }
    }
    el("verdict").append(evidence);
    const groups = [p.before_years,p.after_years];
    if(groups.every(years => years.length === expected && years.length >= 2) && p.change_pct != null){
      const totals = new Map();
      for(const row of rows){
        if(selectedMonths.includes(row.mon)) totals.set(row.year,(totals.get(row.year) || 0) + row.harmonized);
      }
      const trials = groups.flat().map(omitted => {
        const [before,after] = groups.map(years => {
          const kept = years.filter(year => year !== omitted);
          return kept.reduce((sum,year) => sum + totals.get(year),0) / kept.length;
        });
        return {omitted,change:before > 0 ? 100 * (after/before - 1) : NaN};
      });
      if(trials.every(t => Number.isFinite(t.change))){
        const ordered = trials.sort((a,b) => a.change-b.change);
        const low = ordered[0], high = ordered[ordered.length-1];
        const section = document.createElement("section");
        const heading = document.createElement("h4");
        heading.textContent = "Does one season change the conclusion?";
        const result = document.createElement("p");
        result.textContent = "Leaving out one season at a time gives " + percent(low.change) +
          " (without " + low.omitted + ") to " + percent(high.change) + " (without " + high.omitted +
          "). " + (low.change < 0 && high.change > 0 ? "The direction reverses." : "The direction does not reverse.");
        section.append(heading,result);
        el("verdict").append(section);
      }
    }
    if(p.before_mean!=null && p.after_mean!=null){
      const scale=Math.max(p.before_mean,p.after_mean,1);
      for(const [label,value] of [["Before",p.before_mean],["After",p.after_mean]]){
        const line=document.createElement("div");line.className="compare-line";
        line.textContent=label+" · "+fmt(value)+" fire cell-days per season";
        const bar=document.createElement("i");bar.style.width=(100*value/scale)+"%";
        line.append(bar);el("verdict").append(line);
      }
    }
  }catch(e){if(current===comparison)el("verdict").textContent=e.message;}
}
el("policyForm").onsubmit=compare;
async function load(event){
  event?.preventDefault();
  const current=++revision;comparison++;activeQuery=null;
  const q=new URLSearchParams(new FormData(form));
  const region=el("region").value;
  el("results").hidden=true;el("status").textContent="Reading satellite observations…";
  try{
    if(window.fireMap && !await window.fireMap.acceptsArea(coordinateNames.map(name=>Number(q.get(name)))))throw Error("Choose a study area inside Pakistan.");
    if(current!==revision)return;
    const [data,evidence]=await Promise.all([api("calendar",q),api("trust",q)]);
    if(current!==revision)return;
    el("areaName").textContent=region;
    el("dates").textContent=q.get("start")+" — "+q.get("end");
    if(!data.archive_detections || !data.rows.length){el("status").textContent="No archived detections in this area. Select a rectangle within the Pakistan record.";return;}
    renderCalendar(data);renderTrust(evidence);
    document.dispatchEvent(new CustomEvent("archive-results",{detail:data}));
    el("download").href="/api/calendar.csv?"+q;el("raw").href="/api/hotspots.csv?"+q;
    activeQuery=q;el("results").hidden=false;el("status").textContent=data.rows.length+" months · "+(region==="Punjab"||region==="Sindh"?"Approximate province bounds":"Pakistan archive");
    compare();
  }catch(e){if(current===revision)el("status").textContent=e.message;}
}
form.onsubmit=load;load();

el("chartExport").onclick=function(){
  prepareChartExport();
};
function prepareChartExport(){
  if(!activeQuery || !rows.length)return;
  const years=[...new Set(rows.map(row=>row.year))].reverse();
  const width=960,height=164+years.length*30;
  const canvas=document.createElement("canvas");
  canvas.width=width*2;canvas.height=height*2;
  const ctx=canvas.getContext("2d");
  ctx.scale(2,2);
  ctx.fillStyle="#fff";ctx.fillRect(0,0,width,height);
  ctx.fillStyle="#203440";ctx.font="600 23px system-ui";
  ctx.fillText("FireCalendar  /  "+el("areaName").textContent,24,34);
  ctx.font="14px system-ui";
  ctx.fillText("Harmonized monthly fire cell-days   |   "+el("dates").textContent,24,58);
  ctx.fillText(coordinateNames.map(n=>n+" "+Number(activeQuery.get(n)).toFixed(4)).join("   "),24,80);
  const peak=Math.max(...rows.map(row=>row.harmonized),1);
  ctx.textAlign="center";
  months.forEach((m,i)=>ctx.fillText(m,115+72*i,106));
  years.forEach((y,i)=>ctx.fillText(String(y),45,133+i*30));
  for(const row of rows){
    const x=80+(row.mon-1)*72,y=114+years.indexOf(row.year)*30;
    const level=Math.min(7,Math.floor(8*row.harmonized/peak));
    ctx.fillStyle=colors[level];ctx.fillRect(x,y,70,28);
    ctx.fillStyle=level<7?"#000":"#fff";ctx.fillText(fmt(row.harmonized),x+35,y+19);
  }
  ctx.textAlign="left";ctx.fillStyle="#384e5d";
  ctx.fillText("NASA FIRMS · MODIS / VIIRS · Blank cells are outside the selected record.",24,height-18);
  const link=el("chartExport");
  link.download="FireCalendar-"+activeQuery.get("start")+"-"+activeQuery.get("end")+".png";
  link.href=canvas.toDataURL("image/png");
};
