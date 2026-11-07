/* ===========================
   RESILIO — MAIN SCRIPT
   =========================== */

// ── Counter Animation ──────────────────────────────────────
function animateCounter(el, target) {
  if (!el) return;
  let start = 0;
  const step = target / (1800 / 16);
  const tick = () => {
    start += step;
    if (start < target) { el.textContent = Math.floor(start).toLocaleString(); requestAnimationFrame(tick); }
    else { el.textContent = target.toLocaleString(); }
  };
  requestAnimationFrame(tick);
}

// ── Resource Data ──────────────────────────────────────────
const resources = [
  { type:'water',   icon:'💧', name:'Drinking Water',    qty:'40L available', owner:'Node #1847', dist:'0.3km', updated:'2 min ago',  status:'urgent' },
  { type:'medical', icon:'💊', name:'First Aid Kits',    qty:'3 kits',        owner:'Node #2093', dist:'0.5km', updated:'5 min ago',  status:'available' },
  { type:'food',    icon:'🍱', name:'Food Rations',      qty:'120 packs',     owner:'Node #3301', dist:'0.8km', updated:'1 min ago',  status:'available' },
  { type:'shelter', icon:'🏠', name:'Emergency Tent',    qty:'2 spots',       owner:'Node #0991', dist:'1.2km', updated:'12 min ago', status:'urgent' },
  { type:'water',   icon:'💧', name:'Water Purification',qty:'Tablets x50',   owner:'Node #4472', dist:'1.5km', updated:'18 min ago', status:'offline' },
  { type:'medical', icon:'🩺', name:'Medical Volunteer', qty:'1 person',      owner:'Node #5503', dist:'0.9km', updated:'3 min ago',  status:'available' },
  { type:'food',    icon:'🥫', name:'Canned Goods',      qty:'80 units',      owner:'Node #1123', dist:'2.0km', updated:'25 min ago', status:'offline' },
  { type:'shelter', icon:'⛺', name:'Safe House',        qty:'5 rooms',       owner:'Node #7821', dist:'0.6km', updated:'7 min ago',  status:'urgent' },
];

function renderResources(filter) {
  filter = filter || 'all';
  const list = document.getElementById('resourceList');
  if (!list) return;
  const filtered = filter === 'all' ? resources : resources.filter(function(r){ return r.type === filter; });
  list.innerHTML = filtered.map(function(r){ return `
    <div class="resource-card ${r.status}">
      <div class="rc-top">
        <div class="rc-icon-name">${r.icon} ${r.name}</div>
        <span class="rc-badge ${r.status}">${r.status.toUpperCase()}</span>
      </div>
      <div class="rc-meta">
        <span>📦 ${r.qty}</span><span>👤 ${r.owner}</span>
        <span>📍 ${r.dist}</span><span>🕐 ${r.updated}</span>
      </div>
      <div class="rc-actions">
        <button class="rc-btn deliver" onclick="showToast('✓ Marked as delivered')">Mark Delivered</button>
        <button class="rc-btn request" onclick="showToast('📡 Assistance request sent')">Request Assist</button>
      </div>
    </div>`; }).join('');
}
renderResources();

document.querySelectorAll('.filter-btn').forEach(function(btn){
  btn.addEventListener('click', function(){
    document.querySelectorAll('.filter-btn').forEach(function(b){ b.classList.remove('active'); });
    btn.classList.add('active');
    renderResources(btn.dataset.filter);
  });
});

// ── MAP CANVAS — static pins ───────────────────────────────
var mapCanvas = document.getElementById('nodeMap');
var mapCtx = mapCanvas ? mapCanvas.getContext('2d') : null;
var mapNodes = [];

var MAP_POSITIONS = [
  [0.12,0.18],[0.28,0.11],[0.45,0.22],[0.61,0.08],[0.78,0.19],[0.90,0.14],
  [0.08,0.38],[0.22,0.45],[0.38,0.35],[0.55,0.42],[0.70,0.30],[0.85,0.40],
  [0.15,0.60],[0.32,0.68],[0.48,0.55],[0.64,0.62],[0.80,0.52],[0.94,0.60],
  [0.06,0.78],[0.20,0.85],[0.36,0.80],[0.52,0.75],[0.68,0.82],[0.84,0.72],
  [0.25,0.28],[0.42,0.48],[0.58,0.20],[0.74,0.46],[0.88,0.30],[0.16,0.52],
  [0.50,0.88],[0.72,0.65],[0.38,0.92],[0.60,0.50],[0.82,0.85],[0.10,0.90],
  [0.44,0.10],[0.68,0.95],[0.92,0.75],[0.28,0.72]
];
var MAP_COLORS = ['#FF3B30','#32D74B','#636366'];

function initMap() {
  if (!mapCanvas || !mapCtx) return;
  mapCanvas.width  = mapCanvas.offsetWidth  || 400;
  mapCanvas.height = mapCanvas.offsetHeight || 360;
  mapNodes = [];
  MAP_POSITIONS.forEach(function(pos){
    var fx = pos[0], fy = pos[1];
    mapNodes.push({
      fx: fx, fy: fy,
      x: fx * mapCanvas.width,
      y: fy * mapCanvas.height,
      r: 4 + Math.random() * 3,
      color: MAP_COLORS[Math.floor(Math.random() * MAP_COLORS.length)],
      phase: Math.random() * Math.PI * 2
    });
  });
}

function drawMap(ts) {
  if (!mapCanvas || !mapCtx) return;
  var W = mapCanvas.width, H = mapCanvas.height;
  if (!W || !H) { requestAnimationFrame(drawMap); return; }

  mapCtx.clearRect(0,0,W,H);
  mapCtx.fillStyle = '#0E0E18';
  mapCtx.fillRect(0,0,W,H);

  // Grid
  mapCtx.strokeStyle = 'rgba(255,255,255,0.04)';
  mapCtx.lineWidth = 1;
  for (var x=0; x<W; x+=40){ mapCtx.beginPath(); mapCtx.moveTo(x,0); mapCtx.lineTo(x,H); mapCtx.stroke(); }
  for (var y=0; y<H; y+=40){ mapCtx.beginPath(); mapCtx.moveTo(0,y); mapCtx.lineTo(W,y); mapCtx.stroke(); }

  // Connections
  for (var i=0; i<mapNodes.length; i++){
    for (var j=i+1; j<mapNodes.length; j++){
      var a=mapNodes[i], b=mapNodes[j];
      var dx=a.x-b.x, dy=a.y-b.y;
      var dist=Math.sqrt(dx*dx+dy*dy);
      if (dist<90){
        mapCtx.beginPath(); mapCtx.moveTo(a.x,a.y); mapCtx.lineTo(b.x,b.y);
        mapCtx.strokeStyle='rgba(255,255,255,'+(0.05*(1-dist/90))+')';
        mapCtx.lineWidth=1; mapCtx.stroke();
      }
    }
  }

  // Nodes
  var t = (ts||0) * 0.001;
  mapNodes.forEach(function(n){
    var pulse = Math.sin(t*2 + n.phase);
    var glowR = Math.max(2, n.r + pulse*2);
    var haloR = glowR * 3;

    // Ping ring for urgent
    if (n.color === '#FF3B30'){
      var pingPhase = ((t*0.5 + n.phase) % (Math.PI*2)) / (Math.PI*2);
      var pingR = n.r + pingPhase * 14;
      var alpha = Math.max(0, (1-pingPhase)*0.5);
      if (pingR > 0){
        mapCtx.beginPath(); mapCtx.arc(n.x,n.y,pingR,0,Math.PI*2);
        mapCtx.strokeStyle='rgba(255,59,48,'+alpha+')';
        mapCtx.lineWidth=1.5; mapCtx.stroke();
      }
    }

    // Glow
    if (haloR > 0){
      try {
        var grd = mapCtx.createRadialGradient(n.x,n.y,0, n.x,n.y,haloR);
        grd.addColorStop(0, n.color+'44');
        grd.addColorStop(1, 'rgba(0,0,0,0)');
        mapCtx.beginPath(); mapCtx.arc(n.x,n.y,haloR,0,Math.PI*2);
        mapCtx.fillStyle=grd; mapCtx.fill();
      } catch(e){}
    }

    // Core — FIXED, never moves
    mapCtx.beginPath(); mapCtx.arc(n.x,n.y,n.r,0,Math.PI*2);
    mapCtx.fillStyle=n.color; mapCtx.fill();
  });

  requestAnimationFrame(drawMap);
}

// ── NETWORK CANVAS ─────────────────────────────────────────
var netCanvas = document.getElementById('networkCanvas');
var netCtx = netCanvas ? netCanvas.getContext('2d') : null;
var netNodes = [];
var selectedNode = null;

var NET_TYPES = [
  {label:'Volunteer', color:'#32D74B', resources:'Food, Water'},
  {label:'Civilian',  color:'#FF9F0A', resources:'Requests water'},
  {label:'NGO',       color:'#0A84FF', resources:'Medical kits, Shelter'},
  {label:'Offline',   color:'#636366', resources:'Last seen 8 min ago'}
];

function initNetwork() {
  if (!netCanvas || !netCtx) return;
  netCanvas.width  = netCanvas.offsetWidth || 600;
  netCanvas.height = 480;
  netNodes = [];
  for (var i=0; i<32; i++){
    var t = NET_TYPES[Math.floor(Math.random()*NET_TYPES.length)];
    netNodes.push({
      id: 1000+i,
      x: 60 + Math.random()*(netCanvas.width-120),
      y: 60 + Math.random()*(netCanvas.height-120),
      r: 8 + Math.random()*5,
      color:t.color, label:t.label, resources:t.resources,
      vx:(Math.random()-0.5)*0.4, vy:(Math.random()-0.5)*0.4,
      phase:Math.random()*Math.PI*2,
      synced:(Math.floor(Math.random()*10)+1)+'min ago'
    });
  }
}

function drawNetwork(ts) {
  if (!netCanvas || !netCtx) return;
  var W=netCanvas.width, H=netCanvas.height;
  if (!W||!H){ requestAnimationFrame(drawNetwork); return; }

  netCtx.clearRect(0,0,W,H);
  netCtx.fillStyle='#111118'; netCtx.fillRect(0,0,W,H);

  var t = (ts||0)*0.001;

  for (var i=0; i<netNodes.length; i++){
    for (var j=i+1; j<netNodes.length; j++){
      var a=netNodes[i], b=netNodes[j];
      var dx=a.x-b.x, dy=a.y-b.y, dist=Math.sqrt(dx*dx+dy*dy);
      if (dist<120){
        var isSel = selectedNode && (a===selectedNode||b===selectedNode);
        netCtx.beginPath(); netCtx.moveTo(a.x,a.y); netCtx.lineTo(b.x,b.y);
        netCtx.strokeStyle = isSel ? 'rgba(255,255,255,0.3)' : 'rgba(255,255,255,'+(0.05*(1-dist/120))+')';
        netCtx.lineWidth = isSel ? 1.5 : 1; netCtx.stroke();
        if (isSel){
          netCtx.fillStyle='rgba(255,255,255,0.5)'; netCtx.font='9px monospace';
          netCtx.textAlign='center';
          netCtx.fillText(Math.floor(dist*0.8)+'ms',(a.x+b.x)/2,(a.y+b.y)/2);
          netCtx.textAlign='left';
        }
      }
    }
  }

  netNodes.forEach(function(n){
    n.x+=n.vx; n.y+=n.vy;
    if(n.x<20||n.x>W-20) n.vx*=-1;
    if(n.y<20||n.y>H-20) n.vy*=-1;
    var isSel=n===selectedNode;
    var size=Math.max(1, n.r+(isSel?4:Math.sin(t*2+n.phase)*1.5));
    var haloR=size*4;
    if(isSel){
      netCtx.beginPath(); netCtx.arc(n.x,n.y,size+6,0,Math.PI*2);
      netCtx.strokeStyle=n.color+'88'; netCtx.lineWidth=2; netCtx.stroke();
    }
    if(haloR>0){
      try{
        var grd=netCtx.createRadialGradient(n.x,n.y,0,n.x,n.y,haloR);
        grd.addColorStop(0,n.color+'44'); grd.addColorStop(1,'rgba(0,0,0,0)');
        netCtx.beginPath(); netCtx.arc(n.x,n.y,haloR,0,Math.PI*2);
        netCtx.fillStyle=grd; netCtx.fill();
      }catch(e){}
    }
    netCtx.beginPath(); netCtx.arc(n.x,n.y,size,0,Math.PI*2);
    netCtx.fillStyle=n.color; netCtx.fill();
    netCtx.fillStyle='rgba(255,255,255,0.45)'; netCtx.font='9px monospace';
    netCtx.textAlign='center';
    netCtx.fillText('#'+n.id, n.x, n.y+size+12);
    netCtx.textAlign='left';
  });

  requestAnimationFrame(drawNetwork);
}

if (netCanvas){
  netCanvas.addEventListener('click', function(e){
    var rect=netCanvas.getBoundingClientRect();
    var mx=e.clientX-rect.left, my=e.clientY-rect.top, hit=null;
    netNodes.forEach(function(n){
      var dx=n.x-mx, dy=n.y-my;
      if(Math.sqrt(dx*dx+dy*dy)<n.r+8) hit=n;
    });
    selectedNode=hit; renderNodeInfo(hit);
  });
}

function renderNodeInfo(node){
  var panel=document.getElementById('nodeInfo');
  if(!panel) return;
  if(!node){ panel.innerHTML='<p class="info-placeholder">← Tap a node to see details</p>'; return; }
  panel.innerHTML=`
    <div class="node-detail-title">NODE DETAILS</div>
    <div class="node-detail-item"><span class="node-detail-key">Node ID</span><span class="node-detail-val">#${node.id}</span></div>
    <div class="node-detail-item"><span class="node-detail-key">Type</span><span class="node-detail-val" style="color:${node.color}">${node.label}</span></div>
    <div class="node-detail-item"><span class="node-detail-key">Resources</span><span class="node-detail-val">${node.resources}</span></div>
    <div class="node-detail-item"><span class="node-detail-key">Last Sync</span><span class="node-detail-val">${node.synced}</span></div>
    <div class="node-detail-item"><span class="node-detail-key">Coords</span><span class="node-detail-val">${node.x.toFixed(0)}, ${node.y.toFixed(0)}</span></div>`;
}

// ── Bar Charts ─────────────────────────────────────────────
var barObserver = new IntersectionObserver(function(entries){
  entries.forEach(function(entry){
    if(entry.isIntersecting){
      entry.target.querySelectorAll('.bar-fill').forEach(function(bar){ bar.style.width=bar.dataset.target; });
      barObserver.unobserve(entry.target);
    }
  });
},{threshold:0.3});
document.querySelectorAll('.chart-card').forEach(function(c){ barObserver.observe(c); });

// ── Alerts ─────────────────────────────────────────────────
var alertData = [
  {type:'urgent', icon:'🆘', title:'Medical Emergency — Node #1847',       meta:'Zone 7 · 0.3km · 2 volunteers needed',  time:'Just now'},
  {type:'info',   icon:'✅', title:'Water delivery confirmed — Node #3301', meta:'40L delivered to Zone 4',               time:'3 min ago'},
  {type:'warning',icon:'⚠', title:'Low shelter capacity — Sector B',       meta:'Only 2 spots remaining',                time:'5 min ago'},
  {type:'info',   icon:'📡', title:'Node #2291 back online',                meta:'Was offline for 18 minutes',            time:'8 min ago'},
  {type:'urgent', icon:'🔴', title:'Critical: Medical shortage — Sector C', meta:'Request immediate volunteer dispatch',  time:'10 min ago'},
  {type:'info',   icon:'🟢', title:'Food surplus located — Node #5503',     meta:'120 packs available',                   time:'15 min ago'},
  {type:'warning',icon:'🔋', title:'Node #4472 low battery',                meta:'Expected disconnect in 30 min',         time:'20 min ago'},
];

function renderAlerts(data){
  var c=document.getElementById('alertsContainer'); if(!c) return;
  c.innerHTML=data.map(function(a){ return `
    <div class="alert-item ${a.type}">
      <span class="alert-icon">${a.icon}</span>
      <div class="alert-body"><div class="alert-title">${a.title}</div><div class="alert-meta">${a.meta}</div></div>
      <span class="alert-time">${a.time}</span>
    </div>`; }).join('');
}
renderAlerts(alertData);

setInterval(function(){
  var pool=[
    {type:'info',   icon:'📦', title:'New resource shared — Node #'+(Math.floor(Math.random()*8000)+1000), meta:'Water · Zone '+Math.floor(Math.random()*15+1), time:'Just now'},
    {type:'urgent', icon:'🆘', title:'Urgent request — Node #'+(Math.floor(Math.random()*8000)+1000),      meta:'Medical aid needed · '+(Math.random()*2).toFixed(1)+'km', time:'Just now'},
  ];
  var fresh=pool[Math.floor(Math.random()*pool.length)];
  alertData.unshift(fresh); if(alertData.length>12) alertData.pop();
  renderAlerts(alertData); showToast('🔔 '+fresh.title);
},8000);

// ── Crisis Mode ────────────────────────────────────────────
var crisisOverlay=document.getElementById('crisisOverlay');
var crisisToggle=document.getElementById('crisisToggle');
var crisisClose=document.getElementById('crisisClose');
if(crisisToggle) crisisToggle.addEventListener('click',function(){ crisisOverlay.classList.add('active'); document.body.style.overflow='hidden'; });
if(crisisClose)  crisisClose.addEventListener('click',function(){ crisisOverlay.classList.remove('active'); document.body.style.overflow=''; });
document.querySelectorAll('.crisis-action').forEach(function(btn){
  btn.addEventListener('click',function(){
    var type=[].slice.call(btn.classList).find(function(c){ return ['water','food','medical','shelter'].indexOf(c)>-1; })||'resource';
    showToast('📡 '+type.toUpperCase()+' request broadcast to mesh');
    btn.style.transform='scale(0.95)'; setTimeout(function(){ btn.style.transform=''; },200);
  });
});

// ── Toast ──────────────────────────────────────────────────
var toastTimer;
function showToast(msg){
  var toast=document.getElementById('toast'); if(!toast) return;
  toast.textContent=msg; toast.classList.add('show');
  clearTimeout(toastTimer); toastTimer=setTimeout(function(){ toast.classList.remove('show'); },3500);
}

// ── Shortage tags ──────────────────────────────────────────
document.querySelectorAll('.shortage-tag').forEach(function(el){
  el.addEventListener('click',function(){ showToast('📣 Volunteers alerted for this shortage'); });
});

// ── Nav scroll ─────────────────────────────────────────────
window.addEventListener('scroll',function(){
  var nav=document.getElementById('nav');
  if(nav) nav.style.background=window.scrollY>40?'rgba(10,10,15,0.98)':'rgba(10,10,15,0.92)';
});

// ── Smooth scroll ──────────────────────────────────────────
function scrollTo(id){ var el=document.getElementById(id); if(el) el.scrollIntoView({behavior:'smooth'}); }

// ── Resize ─────────────────────────────────────────────────
window.addEventListener('resize',function(){
  if(mapCanvas){
    mapCanvas.width=mapCanvas.offsetWidth||400;
    mapCanvas.height=mapCanvas.offsetHeight||360;
    mapNodes.forEach(function(n){ n.x=n.fx*mapCanvas.width; n.y=n.fy*mapCanvas.height; });
  }
  if(netCanvas){ netCanvas.width=netCanvas.offsetWidth||600; }
});

// ── Boot ───────────────────────────────────────────────────
window.addEventListener('load', function(){
  setTimeout(function(){
    animateCounter(document.getElementById('s1'),14820);
    animateCounter(document.getElementById('s2'),3241);
    animateCounter(document.getElementById('s3'),47);
    initMap();     requestAnimationFrame(drawMap);
    initNetwork(); requestAnimationFrame(drawNetwork);
  },100);
});