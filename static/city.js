/* Dependency-free Deep Sea 3D renderer. The submerged coral-reef scene, camera and
   visual effects never mutate tournament scoring. */
(function(){
 'use strict';
 const canvas=document.getElementById('city-canvas');
 if(!canvas)return;
 const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
 const mix=(a,b,t)=>a+(b-a)*t;
 const color=(a,b,t)=>a.map((v,i)=>mix(v,b[i],t));
 const add=(a,b)=>a.map((v,i)=>v+b[i]);
 const sub=(a,b)=>a.map((v,i)=>v-b[i]);
 const mul=(a,s)=>a.map(v=>v*s);
 const dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0);
 const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
 const norm=a=>mul(a,1/(Math.hypot(...a)||1));
 const rand=n=>{const x=Math.sin(n*127.1+311.7)*43758.5453;return x-Math.floor(x);};
 const smooth=t=>t*t*(3-2*t);
 const TAU=Math.PI*2,GRID_CENTER=[0,-62],GARDEN_CENTER=GRID_CENTER;
 function multiply(a,b){const out=new Float32Array(16);for(let c=0;c<4;c++)for(let r=0;r<4;r++)for(let k=0;k<4;k++)out[c*4+r]+=a[k*4+r]*b[c*4+k];return out;}
 function perspective(fov,aspect,near,far){const f=1/Math.tan(fov/2);return new Float32Array([f/aspect,0,0,0,0,f,0,0,0,0,(far+near)/(near-far),-1,0,0,2*far*near/(near-far),0]);}
 function lookAt(eye,target){const z=norm(sub(eye,target)),x=norm(cross([0,1,0],z)),y=cross(z,x);return new Float32Array([x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,-dot(x,eye),-dot(y,eye),-dot(z,eye),1]);}
 function project(p,m){const q=[0,0,0,0];for(let r=0;r<4;r++)q[r]=m[r]*p[0]+m[4+r]*p[1]+m[8+r]*p[2]+m[12+r];return [q[0]/q[3],q[1]/q[3],q[2]/q[3],q[3]];}
 const CORNERS=[[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1],[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1]];
 const FACES=[[0,1,2,3],[5,4,7,6],[3,2,6,7],[4,5,1,0],[1,5,6,2],[4,0,3,7]];
 class Mesh{
  constructor(){this.data=[];}
  tri(a,b,c,col,kind=0){const n=norm(cross(sub(b,a),sub(c,a)));for(const p of [a,b,c])this.data.push(...p,...n,...col,kind);}
  quad(a,b,c,d,col,kind=0){this.tri(a,b,c,col,kind);this.tri(a,c,d,col,kind);}
  // A quad whose winding is flipped when needed so its normal faces `want`.
  oquad(a,b,c,d,want,col,kind=0){if(dot(cross(sub(b,a),sub(c,a)),want)<0)this.quad(a,d,c,b,col,kind);else this.quad(a,b,c,d,col,kind);}
  box(x,y,z,w,h,d,col,kind=0,roll=0){
   const co=Math.cos(roll),si=Math.sin(roll);
   const p=CORNERS.map(v=>{
    const vx=v[0]*w/2,vy=v[1]*h/2;return [x+vx*co-vy*si,y+vx*si+vy*co,z+v[2]*d/2];
   });
   for(const f of FACES)this.quad(...f.map(i=>p[i]),col,kind);
  }
  gem(x,y,z,r,col,kind=0,stretch=1){
   const p=[[x+r,y,z],[x,y,z+r],[x-r,y,z],[x,y,z-r]],a=[x,y+r*stretch,z],b=[x,y-r*stretch,z];
   for(let i=0;i<4;i++){this.tri(a,p[i],p[(i+1)%4],col,kind);this.tri(b,p[(i+1)%4],p[i],col,kind);}
  }
  // Flat ring in the plane of unit vectors a and b, facing cross(a,b). Like ring(), the annulus
  // runs from r-width to r, so r is the outer radius.
  loop(c,a,b,r,width,col,kind=0,seg=16){
   const want=cross(a,b),at=(t,rr)=>add(c,add(mul(a,Math.cos(t)*rr),mul(b,Math.sin(t)*rr)));
   for(let i=0;i<seg;i++){const t0=i*TAU/seg,t1=(i+1)*TAU/seg;this.oquad(at(t0,r),at(t1,r),at(t1,r-width),at(t0,r-width),want,col,kind);}
  }
 }
 let tournament=[],unlocks={},routeTime=0;
 let monuments=null,podiumSites=[],podiumTime=0,riseAt=null;
 const roomKeys=['settings','round1','round2','final','overview'];
 // Neon node palette: registration, introspection, adaptation, final, leaderboard.
 const roomColors=[[.30,.89,.78],[.27,.73,.94],[.51,.88,.67],[.96,.78,.40],[.33,.79,.88]];
 const ROMAN=['I','II','III','IV','V'];
 // Data-mote spark colors (cyan / magenta / amber) for the drifting dynamic mesh.
 const SPARKS=[[.30,.90,.78],[.24,.67,.96],[.75,.91,.56]];
 const media=window.matchMedia('(prefers-reduced-motion: reduce)');
 // Calm-morning ambience: birds are fully present near progress 0 and gone by this
 // threshold. The audio chirps in BrawlAudio use the same cutoff so the sky birds and
 // their song appear and disappear together.
 const BIRD_THRESHOLD=.2;
 let settings={},state={progress:0,phase:'DEPTHS DORMANT'},width=1,height=1,rooms=[],gates=[],dirty=true,geometryDirty=true;
 let bloomLevel=0,gardenFlowers=0,gardenHedges=0;
 let staticMesh=new Mesh(),staticArray=new Float32Array();
 let elapsed=0,lastFrame=0,lastSample=0,paused=false,suspended=false,inside=false,transition=null,lastBuild='',needsLayout=true;
 let dusk=0,duskTarget=0;
 let surgeAt=null,surgeBig=false,surgeEnv=0;
 let partTris={},rebuilds=0,dynamicTriangles=0,lastDynamic=[];
 // Elevated first-person overview above the neon grid avenues.
 const baseCamera={eye:[0,56,25],target:[0,2,-54]};
 let sceneView='street',returnRoute=[];
 let camera={eye:baseCamera.eye.slice(),target:baseCamera.target.slice()},vp;
 let gl=null,ctx=null,program,skyProgram,staticBuffer,dynamicBuffer,skyBuffer,uniforms,skyUniforms;
 const fov=66*Math.PI/180;
 // Synthwave night-sky colors shared by the sky shader, the fog and the static
 // fallback gradient: near-black indigo at the top, a hot magenta/orange sunset
 // band along the horizon that deepens as dusk settles.
 const skyStops=d=>({top:color([.014,.17,.24],[.008,.08,.15],d),bottom:color([.004,.035,.084],[.003,.025,.062],d)});
 const fogColor=(d,p)=>color(skyStops(d).bottom,[.018,.17,.23],p*.55);
 function shader(type,code){
  const s=gl.createShader(type);gl.shaderSource(s,code);gl.compileShader(s);
  if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s;
 }
 function link(v,f){const p=gl.createProgram();gl.attachShader(p,shader(gl.VERTEX_SHADER,v));gl.attachShader(p,shader(gl.FRAGMENT_SHADER,f));gl.linkProgram(p);if(!gl.getProgramParameter(p,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(p));return p;}
 // No uniform is shared between the vertex and fragment stages: their default float
 // precisions differ (highp vs mediump), and GLSL ES 1.00 fails the link on a mismatch.
 const VERTEX_SRC='attribute vec3 a_pos,a_normal,a_color;attribute float a_kind;uniform mat4 u_vp;uniform float u_wtime,u_wheat,u_surge;uniform vec2 u_center;varying vec3 v_pos,v_normal,v_color;varying float v_kind;void main(){float wave=0.;if(a_kind>1.5&&a_kind<2.5){float ang=atan(a_pos.z-u_center.y,a_pos.x-u_center.x);float bob=max(0.,sin(u_wtime*5.+a_pos.x*.35+a_pos.z*.27));float mex=pow(max(0.,cos(ang-u_wtime*.9)),24.);wave=bob*.12*(.3+u_wheat)+mex*.9*u_wheat+u_surge*bob*.5;}vec3 p=a_pos+vec3(0.,wave,0.);v_pos=p;v_normal=a_normal;v_color=a_color;v_kind=a_kind;gl_Position=u_vp*vec4(p,1.);}';
 // Neon wireframe towers, glowing grid floor and synthwave signage, with the
 // banded light steps and subtle quantization of CRT / retro-futurist materials.
 const FRAGMENT_SRC=`
precision mediump float;
varying vec3 v_pos,v_normal,v_color;
varying float v_kind;
uniform vec3 u_eye,u_fog;
uniform float u_heat,u_dusk,u_time;
float grit(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5);}
void main(){
 vec3 n=normalize(v_normal);
 float sun=max(dot(n,normalize(vec3(-.4,.85,.45))),0.);
 float band=floor((.43+sun*.59)*7.+.5)/7.;
 vec3 daylight=mix(vec3(.54,.84,.93),vec3(.82,1.07,.94),sun*.72+.18);
 vec3 c=v_color*daylight*band*mix(vec3(1.),vec3(.72,.93,1.04),u_dusk*.75);
 float noise=grit(floor(v_pos.xz*3.5))*.63+grit(floor(v_pos.xz*1.6))*.37;
 if(v_kind<.5){
  c*=.78+noise*.36;
  c+=vec3(.014,.020,.004)*step(.93,grit(floor(v_pos.xz*12.)));
 }
 if(v_kind>.5&&v_kind<1.5){
  vec2 uv=abs(n.y)>.56?v_pos.xz:v_pos.xy;
  vec2 course=uv*vec2(.5,.85);
  course.x+=floor(course.y)*.5;
  vec2 f=fract(course);
  float mortar=1.-step(.045,f.x)*step(.072,f.y);
  c*=.79+grit(floor(uv*4.5))*.28;
  c*=1.-mortar*.22;
 }
 if(v_kind>1.5&&v_kind<2.5)c*=.82+grit(floor(v_pos.xy*7.+v_pos.z))*.34;
 if(v_kind>2.5&&v_kind<3.5)c=v_color*(1.19+sin(u_time*2.+v_pos.x)*.05);
 float fog=clamp(1.-exp(-length(v_pos-u_eye)*(.003+u_heat*.0015)),0.,.86);
 c=mix(c,u_fog,fog*(v_kind>2.5?.45:1.));
 float alpha=1.;
 if(v_kind>3.5){
  vec2 uv=v_normal.xy;
  float rr=length(uv);
  if(v_kind<4.5){
   alpha=(1.-smoothstep(.05,1.,rr))*.38;
   c=mix(v_color,u_fog,.24);
  }else{
   float sway=sin(u_time*4.+uv.y*5.+v_pos.x)*.13*(uv.y+1.);
   float width=(1.-uv.y)*.4+.05;
   float core=clamp(1.-abs(uv.x+sway)/width,0.,1.);
   alpha=core*(1.-smoothstep(.3,1.,uv.y))*smoothstep(-1.,-.6,uv.y);
   c=mix(vec3(.03,.36,.43),vec3(.48,1.,.78),pow(core,2.)*(1.-uv.y)*.65);
  }
  if(alpha<.01)discard;
 }
 if(v_kind<3.5){
  float dither=(grit(mod(gl_FragCoord.xy,4.))-.5)/90.;
  c=floor(clamp(c+dither,0.,1.)*63.+.5)/63.;
 }
 gl_FragColor=vec4(c,alpha);
}`;
 const SKY_VERTEX_SRC='attribute vec2 a_pos;varying vec2 v_uv;void main(){v_uv=a_pos*.5+.5;gl_Position=vec4(a_pos,0.,1.);}';
 // Dark underwater water column with light shafts and marine snow.
 const SKY_FRAGMENT_SRC=`precision mediump float;varying vec2 v_uv;uniform float u_heat,u_dusk,u_time;
 float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5);}
 void main(){
 vec2 uv=v_uv;
 vec3 c=mix(vec3(.002,.021,.053),mix(vec3(.014,.17,.24),vec3(.008,.075,.144),u_dusk),smoothstep(.04,1.,uv.y));
 float shafts=0.;
 for(int k=0;k<6;k++){
 float center=(float(k)+.30)/6.+sin(u_time*.085+float(k)*2.1)*.014;
 shafts+=exp(-abs(uv.x-center-uv.y*.14)*48.)*pow(uv.y,1.65);
 }
 c+=vec3(.016,.14,.155)*shafts*(.22+u_heat*.48);
 float snow=step(.997,hash(floor(uv*vec2(270.,170.)+vec2(u_time*.18,-u_time*.32))));
 c+=vec3(.32,.88,.73)*snow*(.26+u_heat*.55);
 float ripple=.5+.5*sin(uv.x*62.+sin(uv.y*39.+u_time*.27)*3.);
 c+=vec3(.008,.052,.056)*ripple*uv.y*(.3+u_heat*.35);
 gl_FragColor=vec4(c,1.);
 }`;
 function initGL(){
  gl=canvas.getContext('webgl',{alpha:false,antialias:true,powerPreference:'low-power'});
  if(!gl)return false;
  program=link(VERTEX_SRC,FRAGMENT_SRC);
  uniforms={};for(const name of ['vp','wtime','wheat','surge','center','eye','fog','heat','dusk','time'])uniforms[name]=gl.getUniformLocation(program,'u_'+name);
  skyProgram=link(SKY_VERTEX_SRC,SKY_FRAGMENT_SRC);
  skyUniforms={};for(const name of ['heat','dusk','time'])skyUniforms[name]=gl.getUniformLocation(skyProgram,'u_'+name);
  staticBuffer=gl.createBuffer();dynamicBuffer=gl.createBuffer();skyBuffer=gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER,skyBuffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,3,-1,-1,3]),gl.STATIC_DRAW);
  return true;
 }
 let mode='webgl';
 try{if(!initGL())mode='static';}catch(error){console.warn('Deep Sea renderer uses static projection:',error.message);mode='static';}
 if(mode==='static'){
  // A fresh canvas can obtain 2D even if an attempted WebGL setup already claimed one.
  const fallback=document.createElement('canvas');fallback.id=canvas.id;fallback.setAttribute('aria-hidden','true');canvas.replaceWith(fallback);ctx=fallback.getContext('2d');
 }
 const surface=mode==='static'?document.getElementById('city-canvas'):canvas;
 const isMoving=()=>!paused&&!media.matches&&!suspended&&!inside&&mode==='webgl';
 // Front face vertical layout of a gate, all heights from y=0 at the gate (s = gate size).
 
 function layout(){
  // Five neon entrance nodes standing along the avenues of the neon grid city.
  const sites=[[-26,-35],[-14,-68],[0,-42],[14,-68],[26,-35]];
  rooms=roomKeys.map((key,i)=>{
   const [x,z]=sites[i],size=i===4?9:8,N=[0,0,1],pos=[x,0,z];
   return {key,pos,front:[x,0,z+size*.6],N,size,color:roomColors[i],
    laurelAt:[x,size*1.55,z],face:{keystoneTop:size*1.5,bannerBottom:size*.8,bannerTop:size*1.2,
     bannerHalfW:size*.25,bannerCenter:size*1.1,bannerFrontN:0,blockTop:size*1.6,
     tunnelCeiling:size*.8,openTop:size*.8,archR:size*.2,tunnelLen:size*.6,laurelR:.9,laurelN:0}};
  });
  gates=rooms;
  podiumSites=[{place:1,pos:[0,0,-99],size:3.2}];
  geometryDirty=true;needsLayout=false;positionLabels();
 }
 function resize(){
  const box=document.getElementById('world').getBoundingClientRect();width=Math.max(1,box.width);height=Math.max(1,box.height);
  const dpr=Math.min(window.devicePixelRatio||1,mode==='static'?1:1.5);
  surface.width=Math.round(width*dpr);surface.height=Math.round(height*dpr);
  if(gl&&mode==='webgl')gl.viewport(0,0,surface.width,surface.height);
  needsLayout=true;geometryDirty=true;dirty=true;
 }
 function gateState(key){
  const stage=tournament.find(t=>t.key===key);
  if(stage?.status==='sealed')return 'sealed';
  if(['round1','round2','final'].includes(key)&&stage?.status==='complete')return 'crowned';
  return 'open';
 }
 function rebuildGrid(){
  // Build the fixed neon skyline and the countdown-driven charge nodes of the
  // full-viewport synthwave city scene.
  const m=new Mesh(),still=mode==='static';partTris={};rebuilds++;
  const part=(name,fn)=>{const before=m.data.length;fn();partTris[name]=(m.data.length-before)/30;};
  const seabed=[.04,.10,.12];
  const litNodes=Math.floor(bloomLevel*112);
  const nodeColors=[[.22,.91,.78],[.36,.74,.96],[.59,.93,.64],[.95,.82,.51]];
  gardenFlowers=0;gardenHedges=0;
  part('grid-floor',()=>{
   // Basalt sea floor, scattered stones and pale silt winding into the trench.
   m.box(0,-.7,-61,180,1.4,182,[.013,.047,.064]);
   m.box(0,.03,-62,70,.12,137,[.036,.092,.093]);
   for(let k=0;k<44;k++){const x=(rand(k+90)-.5)*158,z=-12-rand(k+133)*126;
     m.gem(x,.12,z,1+rand(k+53)*2.8,[.06,.14,.14],0,.28);}
 });
 part('skyline',()=>{
   // Two walls of jagged coral, sponge towers and anemone-like branching growth.
   for(const side of [-1,1])for(let k=0;k<45;k++){
     const x=side*(21+rand(k*7+side*13)*32),z=-10-k*2.91+rand(k*19+3)*2;
     const h=2.4+rand(k*17+7)*6.6;
     const dark=k%3===0?[.12,.33,.35]:k%3===1?[.10,.39,.31]:[.24,.29,.36];
     m.gem(x,.60,z,1.6+rand(k+31),[.06,.14,.15],0,.47);
     m.box(x,h*.44,z,.56,h*.88,.62,dark,0,(rand(k+8)-.5)*.6);
     for(const dir of [-1,1]){
       const ax=x+dir*1.45,ay=h*.63;
       m.box(ax,ay,z,.54,h*.40,.5,dark,0,dir*.55);
       m.gem(ax+dir*.5,ay+h*.21,z,.54,[.38,.84,.67],3,1.2);
     }
     m.gem(x,h,z,.8,[.26,.77,.66],3,1.1);gardenHedges++;
   }
 });
 part('charge-nodes',()=>{
   // 112 soft-bodied bioluminescent polyps awaken ONLY from countdown progress.
   for(let i=0;i<112;i++){
     const lane=i%8,rank=Math.floor(i/8),side=lane<4?-1:1;
     const x=side*(5+(lane%4)*8)+Math.sin(i*13.1)*1.4,z=-19-rank*7.3;
     const col=nodeColors[i%4],lit=(i*37)%112<litNodes;
     m.gem(x,.06,z,1.2,[.055,.12,.14],0,.25);
     const h=lit?1.5+bloomLevel*3.6:1;
     m.box(x,h*.5,z,.28,h,.28,lit?[.10,.38,.39]:[.05,.12,.14]);
     if(lit){
       gardenFlowers++;
       for(let p=0;p<5;p++){const angle=p*TAU/5;
         m.gem(x+Math.cos(angle)*.64,h*.75,z+Math.sin(angle)*.64,.44,col,3,1.45);}
       m.gem(x,h+.25,z,.67,[.61,.95,.80],3,1.5);
       if(bloomLevel>=1){
         for(let p=0;p<5;p++){const angle=p*TAU/5+.3;
           m.gem(x+Math.cos(angle)*1.23,h+.25,z+Math.sin(angle)*1.23,.56,[.64,.98,.78],3,1.55);}
         m.loop([x,h+.5,z],[1,0,0],[0,0,-1],1,.16,[.64,.98,.78],3,6);
       }
     }
   }
 });
 part('nodes',()=>{
   // Five active expedition chambers marked by pearl beacons.
   for(const g of rooms){
     const [x,,z]=g.pos,r=g.size,sealed=gateState(g.key)==='sealed';
     m.box(x,.20,z,r*2,.4,r*1.75,[.04,.10,.14]);
     m.loop([x,.5,z],[1,0,0],[0,0,-1],r*.77,.35,sealed?[.08,.19,.21]:g.color,3,16);
     for(const dx of [-r*.6,r*.6])for(const dz of [-r*.5,r*.5]){
       m.gem(x+dx,2.7,z+dz,.74,[.09,.30,.31],0,3.4);
       m.gem(x+dx,5.2,z+dz,.6,sealed?[.06,.17,.19]:g.color,3,1.8);
     }
     m.gem(x,7.5,z,r*.63,sealed?[.09,.16,.19]:g.color,3,.70);
     m.gem(x,9,z,.5,sealed?[.07,.11,.14]:[.79,1,.81],3,1.2);
     if(sealed)for(let k=0;k<5;k++)m.box(x+(k-2)*r*.27,2.5,z+r*.68,.16,4.8,.17,[.07,.15,.19]);
     else m.loop([x,2.5,z+r*.7],[1,0,0],[0,1,0],r*.61,.21,g.color,3,16);
   }
 });
 part('megastructure',()=>{
   // Ancient, half-buried stone temple with a great luminous pearl at its heart.
   const z=-133,stone=[.07,.17,.19],shell=[.13,.34,.31],light=[.53,.94,.75];
   for(let step=0;step<6;step++)m.box(0,1.1+step*.9,z-step*.7,55-step*5,2,20-step*1.5,stone);
   for(const x of [-18,-12,-6,0,6,12,18]){
     const h=10+5*(1-Math.abs(x)/22);
     m.box(x,6+h*.5,z-4,1.8,h,2,shell);
     m.gem(x,6+h,z-4,1.4,light,3,.65);
   }
   m.loop([0,14,z+3],[1,0,0],[0,1,0],12,1.2,[.31,.79,.68],3,24);
   m.gem(0,14,z+3,9,[.045,.14,.17],0,.85);
   m.gem(0,16,z+4,5,[.55,.97,.78],3,.72);
   for(const x of [-26,26]){
     m.gem(x,9,z,4,[.12,.27,.29],0,3.1);
     for(let p=0;p<5;p++)m.gem(x+(p-2)*1.4,13+Math.abs(p-2),z,1.1,[.23,.68,.54],3,1.5);
   }
 });
 part('holo-signs',()=>{
   // Hydrothermal vents breathe luminous plumes beside the coral path.
   for(const [x,z,r] of [[0,-22,5],[0,-113,6],[-46,-66,4],[46,-66,4]]){
     m.gem(x,.42,z,r*.7,[.035,.105,.13],0,.47);
     for(let v=0;v<5;v++){const xx=x+(v-2)*r*.2,h=1.2+(v%3)*.7;
       m.box(xx,h*.5,z,.6,h,.7,[.10,.25,.25]);m.gem(xx,h+.5,z,.32,[.33,.86,.75],3,1.3);}
   }
 });
 part('neon-arches',()=>{
   // Organic coral arches frame the seven transitions into the abyss.
   for(let n=0;n<7;n++){
     const z=-19-n*15,x=n%2?-2:2;
     for(const side of [-1,1]){
       m.box(x+side*5,3,z,.55,6,.67,[.13,.35,.32],0,side*.35);
       m.gem(x+side*3.1,6,z,1.3,[.31,.73,.60],3,1.2);
     }
     m.loop([x,4.7,z],[1,0,0],[0,1,0],4.4,.33,[.21,.62,.53],3,14);
     m.gem(x,7.4,z,.75,bloomLevel>(n%3)/3?nodeColors[n%4]:[.09,.18,.20],3,1.4);
   }
 });
  staticMesh=m;staticArray=new Float32Array(m.data);
  if(mode==='webgl'){gl.bindBuffer(gl.ARRAY_BUFFER,staticBuffer);gl.bufferData(gl.ARRAY_BUFFER,staticArray,gl.STATIC_DRAW);}
  geometryDirty=false;lastBuild=state.progress+'|'+duskTarget+'|'+bloomLevel;dirty=true;
 }
 // Draw a handful of ambient drone glyphs across the night sky. They only appear while
 // the grid is calm (progress<BIRD_THRESHOLD) and no round is settled yet (dusk 0), and
 // fade out as the system energizes. Under reduced motion or the static fallback they are
 // drawn in fixed poses with no animation, and when the world is paused the shared frozen
 // `t` keeps them still like the rest.
 
 function effects(t){
  const m=new Mesh(),still=media.matches||mode==='static';
  // Energy fountains sparking up from the holo-sign pads, independent of round results.
  for(const [x,z,r] of [[0,-22,5],[0,-113,6],[-46,-66,4],[46,-66,4]]){
   const count=still?5:10;
   for(let i=0;i<count;i++){
    const angle=i*TAU/count,u=still?.45:(t*.57+i*.113)%1;
    const radius=r*.65*Math.sin(Math.PI*u),h=.5+Math.sin(Math.PI*u)*3.3;
    m.gem(x+Math.cos(angle)*radius,h,z+Math.sin(angle)*radius,.12,[.40,.95,1.0],3,1.1);
   }
  }
  // Drifting data motes / sparks rise through the city as the grid charges.
  const motes=8+Math.round(bloomLevel*55);
  for(let i=0;i<motes;i++){
   const x=(rand(i+201)-.5)*78,z=-17-rand(i+304)*99,u=still?.3:(t*(.03+rand(i+399)*.018)+rand(i+521))%1;
   m.gem(x+Math.sin(t*.54+i)*.4,still?.2:17*(1-u)+.2,z,.16,SPARKS[i%SPARKS.length],3,.46);
  }
  // Tournament podium stays bound to actual saved rank/results.
  if(monuments)for(const site of podiumSites){
   const slot=monuments.slots.find(s=>s.place===site.place);if(!slot)continue;
   const [x,,z]=site.pos,w=site.size,rise=monuments.complete?(still||riseAt===null?1:smooth(clamp((podiumTime-riseAt)/2.4))):0;
   const h=w*(.4+(4-site.place)*.28+rise*.9);
   const medal=site.place===1?[.98,.80,.28]:site.place===2?[.70,.85,1.0]:[.98,.40,.60];
   m.box(x,h/2,z,w*1.6,h,w*1.3,slot.tied?[.20,.24,.34]:medal);
   m.box(x,h+.07,z,w*1.75,.15,w*1.45,[.70,.90,1.0],3);
   if(monuments.complete)m.loop([x,h+.2,z],[1,0,0],[0,0,-1],w*.62,.15,[.98,.78,.30],3);
  }
  return m;
 }
 function bindMesh(buffer,array){
  gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
  if(array)gl.bufferData(gl.ARRAY_BUFFER,array,gl.DYNAMIC_DRAW);
  for(const [name,size,offset] of [['a_pos',3,0],['a_normal',3,12],['a_color',3,24],['a_kind',1,36]]){
   const a=gl.getAttribLocation(program,name);gl.enableVertexAttribArray(a);gl.vertexAttribPointer(a,size,gl.FLOAT,false,40,offset);
  }
 }
 function drawGL(){
  gl.disable(gl.DEPTH_TEST);gl.useProgram(skyProgram);gl.bindBuffer(gl.ARRAY_BUFFER,skyBuffer);
  const a=gl.getAttribLocation(skyProgram,'a_pos');gl.enableVertexAttribArray(a);gl.vertexAttribPointer(a,2,gl.FLOAT,false,0,0);
  gl.uniform1f(skyUniforms.heat,state.progress);gl.uniform1f(skyUniforms.dusk,dusk);gl.uniform1f(skyUniforms.time,elapsed);gl.drawArrays(gl.TRIANGLES,0,3);
  gl.enable(gl.DEPTH_TEST);gl.clear(gl.DEPTH_BUFFER_BIT);gl.useProgram(program);
  gl.uniformMatrix4fv(uniforms.vp,false,vp);
  gl.uniform1f(uniforms.wtime,elapsed%(Math.PI*200));gl.uniform1f(uniforms.wheat,state.progress);gl.uniform1f(uniforms.surge,surgeEnv);gl.uniform2f(uniforms.center,GARDEN_CENTER[0],GARDEN_CENTER[1]);
  gl.uniform3fv(uniforms.eye,camera.eye);gl.uniform3fv(uniforms.fog,fogColor(dusk,state.progress));
  gl.uniform1f(uniforms.heat,state.progress);gl.uniform1f(uniforms.dusk,dusk);gl.uniform1f(uniforms.time,elapsed);
  bindMesh(staticBuffer);gl.drawArrays(gl.TRIANGLES,0,staticArray.length/10);
  lastDynamic=effects(elapsed).data;dynamicTriangles=lastDynamic.length/30;
  const dynamic=new Float32Array(lastDynamic);
  gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);gl.depthMask(false);
  bindMesh(dynamicBuffer,dynamic);gl.drawArrays(gl.TRIANGLES,0,dynamic.length/10);
  gl.depthMask(true);gl.disable(gl.BLEND);
 }
 function drawStatic(){
  if(!ctx)return;
  const sky=skyStops(dusk);
  const rgb=c=>'rgb('+c.map(v=>Math.round(clamp(v)*255)).join(',')+')';
  const gradient=ctx.createLinearGradient(0,0,0,height);gradient.addColorStop(0,rgb(sky.top));gradient.addColorStop(1,rgb(sky.bottom));ctx.fillStyle=gradient;ctx.fillRect(0,0,width,height);
  lastDynamic=effects(5).data;dynamicTriangles=lastDynamic.length/30;
  const tris=[],data=staticMesh.data.concat(lastDynamic);
  for(let i=0;i<data.length;i+=30){
   const vertices=[0,10,20].map(k=>project(data.slice(i+k,i+k+3),vp));
   if(vertices.some(v=>v[3]<=0)||vertices.every(v=>Math.abs(v[0])>1.2||Math.abs(v[1])>1.2))continue;
   const n=data.slice(i+3,i+6),lit=.42+Math.max(0,dot(n,norm([-.4,.85,.45])))*.64;
   tris.push({vertices,z:vertices.reduce((s,v)=>s+v[2],0),col:rgb(data.slice(i+6,i+9).map(v=>v*(data[i+9]>2.5?1.2:lit)))});
  }
  tris.sort((a,b)=>b.z-a.z);
  for(const tri of tris){ctx.beginPath();tri.vertices.forEach((v,i)=>{const x=(v[0]+1)*width/2,y=(1-v[1])*height/2;i?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.closePath();ctx.fillStyle=tri.col;ctx.fill();}
 }
 function positionLabels(){
  const host=document.getElementById('door-labels');if(!host||!vp)return;
  const names=['Players & rules','Know Your Depth','Adapt or Sink','The Abyssal Crown','Leaderboard'];
  const labelAt=g=>add(add(g.pos,[0,g.size*1.05+.6,0]),mul(g.N,.4));
  const items=sceneView==='podium'&&monuments?podiumSites.map(site=>({id:'place'+site.place,pos:add(site.pos,[0,6,0]),label:site.place+'. '+(monuments.slots.find(s=>s.place===site.place)?.names.join(' · ')||'Awaiting finalist')})):
   [...rooms.map((g,i)=>({id:g.key,pos:labelAt(g),label:ROMAN[i]+' / '+names[i],locked:gateState(g.key)==='sealed'})),
    ...(sceneView==='street'?gates.filter(g=>g.decor).map(g=>({id:g.key,pos:labelAt(g),label:g.label,decor:true})):[])];
  const signature=items.map(i=>i.id+':'+i.label+':'+!!i.locked+':'+!!i.decor).join('|');
  if(host.dataset.signature!==signature){host.replaceChildren(...items.map(i=>{const e=document.createElement('span');e.textContent=i.label;e.className='door-marker'+(i.locked?' locked':'')+(i.decor?' decor':'');return e;}));host.dataset.signature=signature;}
  const forward=norm(sub(camera.target,camera.eye));
  items.forEach((item,i)=>{const e=host.children[i],point=project(item.pos,vp),depth=dot(sub(item.pos,camera.eye),forward);e.hidden=inside||!!transition||depth<1||point[0]<-1||point[0]>1||point[1]<-.95||point[1]>.95;
   e.style.left=((point[0]+1)*width/2)+'px';e.style.top=((1-point[1])*height/2)+'px';e.style.opacity=String(clamp(1-depth/170,.5,1));
  });
 }
 function updateBloomHud(){
  const label=document.getElementById('city-status'),pct=document.getElementById('city-damage'),bar=document.getElementById('city-progress');
  if(label)label.textContent=bloomLevel>=1?'THE REEF IS FULLY AWAKE':bloomLevel>0?'BIOLUMINESCENCE RISING':state.phase;
  if(pct)pct.textContent=Math.floor(bloomLevel*100)+'% AWAKE';
  if(bar)bar.style.width=(bloomLevel*100)+'%';
 }
 function sample(now){
  const next=window.CityTimeline.sample(settings,now),arrived=next.remaining===0;
  if(next.progress!==state.progress)dirty=true;
  state=next;
  // The saved countdown is the only charge source. Scores and round status never
  // affect it; zero remaining time fully charges the grid, even before any match starts.
  bloomLevel=next.progress;
  if(!suspended&&!paused){
   // Low synth hum and power-up chimes follow the countdown charge.
   const ev=window.BrawlAudio?.ambience?.(next.progress,arrived);
   if((ev==='roar'||ev==='big'||ev==='begin')&&isMoving()){surgeAt=elapsed;surgeBig=ev!=='roar';}
   // Ambient synth / drone glyphs: on while the grid is calm and no round is settled, off once it energizes.
   window.BrawlAudio?.ambientBirds?.(next.progress<BIRD_THRESHOLD&&!arrived&&dusk===0);
  }else window.BrawlAudio?.ambientBirds?.(false);
  document.body.style.setProperty('--arena-heat',String(state.progress));
  updateBloomHud();
 }
 function updateCamera(now,moving){
  if(transition){
   const u=clamp((now-transition.at)/transition.duration),scaled=u*(transition.nodes.length-1),index=Math.min(transition.nodes.length-2,Math.floor(scaled)),s=smooth(scaled-index),from=transition.nodes[index],to=transition.nodes[index+1];
   camera={eye:from.eye.map((v,i)=>mix(v,to.eye[i],s)),target:from.target.map((v,i)=>mix(v,to.target[i],s))};
   if(u===1){const done=transition.done;transition=null;done();}
   return;
  }
  if(inside||sceneView!=='street')return;
  camera={eye:baseCamera.eye.slice(),target:baseCamera.target.slice()};
  // Hovering aerial camera. The tiny motion suggests flight above the neon skyline.
  if(moving){const hover=Math.sin(elapsed*.62)*.14;camera.eye[1]+=hover;camera.target[1]+=hover;}
  if(moving&&surgeEnv>0){camera.eye[0]+=Math.sin(elapsed*43)*surgeEnv*(surgeBig?.06:.03);camera.eye[1]+=Math.cos(elapsed*37)*surgeEnv*.03;}
 }
 function frame(now){
  requestAnimationFrame(frame);
  if(document.hidden){lastFrame=now;return;}
  if(now-lastFrame<(mode==='static'?300:width<600?40:32))return;
  const routeDelta=(now-lastFrame)/1000,dt=Math.min(.1,routeDelta);lastFrame=now;
  if(now-lastSample>950){sample(Date.now());lastSample=now;}
  const moving=isMoving();
  if(moving){
   elapsed+=dt;routeTime+=routeDelta;
   if(sceneView==='podium')podiumTime+=routeDelta;
  }
  // The sun lowers smoothly while the arena moves and snaps when it is still. Uniforms only, no rebuild.
  if(dusk!==duskTarget){dusk=moving?(dusk<duskTarget?Math.min(duskTarget,dusk+.3*dt):Math.max(duskTarget,dusk-.3*dt)):duskTarget;dirty=true;}
  surgeEnv=surgeAt===null?0:clamp(1-(elapsed-surgeAt)/1.6);
  if(needsLayout)layout();
  if(geometryDirty||lastBuild!==state.progress+'|'+duskTarget+'|'+bloomLevel)rebuildGrid();
  if(!moving&&!transition&&!dirty)return;
  updateCamera(now,moving);
  vp=multiply(perspective(fov,width/height,.3,900),lookAt(camera.eye,camera.target));
  if(mode==='webgl')drawGL();else drawStatic();
  positionLabels();dirty=false;
 }
 function travel(nodes,nextInside){
  inside=nextInside;dirty=true;
  if(transition){const finish=transition.done;transition=null;finish();}
  const route=[{eye:camera.eye.slice(),target:camera.target.slice()},...nodes];
  if(media.matches||mode==='static'){
   const to=nodes[nodes.length-1];camera={eye:to.eye.slice(),target:to.target.slice()};return Promise.resolve();
  }
  return new Promise(done=>{transition={at:performance.now(),duration:Math.min(4200,route.length*680),nodes:route,done};});
 }
 function home(){sceneView='street';return travel([{eye:[camera.eye[0],Math.max(camera.eye[1],30),camera.eye[2]+6],target:[0,0,GARDEN_CENTER[1]]},baseCamera],false);}
 const lifted=(p,y)=>[p[0],p[1]+y,p[2]];
 window.CityWorld={
  setMonuments(value){
   if(monuments){
    if(value.complete&&!monuments.complete)riseAt=podiumTime;
    if(!value.complete)riseAt=null;
   }
   monuments=value;needsLayout=true;dirty=true;
  },
  setTournament(stages){
   const signature=items=>JSON.stringify(items.map(s=>[s.key,s.status]));
   if(signature(stages)===signature(tournament))return;
   for(const stage of stages){
    const previous=tournament.find(s=>s.key===stage.key);
    if(stage.status==='sealed')delete unlocks[stage.key];
    else if(previous?.status==='sealed')unlocks[stage.key]=routeTime;
   }
   const first=!tournament.length;
   tournament=stages.map(s=>({...s}));
   duskTarget=.08;
   if(first)dusk=duskTarget;
   geometryDirty=true;dirty=true;
  },
  setSettings(value){settings={...value};sample(Date.now());dirty=true;},
  refreshRooms(){needsLayout=true;dirty=true;},
  setPaused(value){paused=!!value;dirty=true;},
  setSuspended(value){suspended=!!value;dirty=true;},
  enterRoom(key){
   if(needsLayout)layout();
   const gate=rooms.find(r=>r.key===(key==='sitout'?'round2':key));if(!gate)return Promise.resolve();
   const {front,N}=gate,gx=gate.pos[0];
   const route=[{eye:[gx*.28,35,-12],target:lifted(front,4)},{eye:lifted(add(front,mul(N,18)),13),target:lifted(front,5)},{eye:lifted(add(front,mul(N,5)),3.8),target:lifted(sub(front,mul(N,4)),3)}];
   returnRoute=route.slice(0,2).reverse();sceneView='street';return travel(route,true);
  },
  leaveRoom(){sceneView='street';return travel([...returnRoute,baseCamera],false);},
  visit(place){
   sceneView=place;
   return travel([{eye:[18,30,GARDEN_CENTER[1]+30],target:[0,0,GARDEN_CENTER[1]]},{eye:[0,12,GARDEN_CENTER[1]+18],target:[0,3,GARDEN_CENTER[1]]}],false);
  },
  home,
  getStatus(){
   return {mode,progress:state.progress,phase:state.phase,dusk,duskTarget,bloomLevel,gardenFlowers,gardenHedges,rooms:rooms.length,
    gates:gates.map(g=>({key:g.key,state:gateState(g.key)})),paused,inside,sceneView,cameraEye:camera.eye.slice(),traveling:!!transition,
        debug:{staticTriangles:staticArray.length/30,dynamicTriangles,rebuilds,parts:{...partTris}}};
  },
  // Read-only test hooks (deep copies); app.js never uses them.
  _debugLayout(){
   return JSON.parse(JSON.stringify({
    pavilions:rooms.map(g=>({key:g.key,pos:g.pos,front:g.front,size:g.size,color:g.color})),
    championPedestal:podiumSites.map(p=>({...p}))
   }));
  },
  _debugDynamic(){return Array.from(lastDynamic);}
 };
 window.addEventListener('resize',resize);
 if(window.ResizeObserver){const observer=new ResizeObserver(resize);observer.observe(document.body);}
 if(media.addEventListener)media.addEventListener('change',()=>{dirty=true;});
 surface.addEventListener('webglcontextlost',e=>{e.preventDefault();paused=true;});
 surface.addEventListener('webglcontextrestored',()=>{try{initGL();geometryDirty=true;paused=false;resize();}catch{location.reload();}});
 resize();requestAnimationFrame(frame);
})();
