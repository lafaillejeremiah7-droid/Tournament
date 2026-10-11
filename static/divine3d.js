/* THE SYSTEM'S VERDICT: the same dependency-free, low-poly WebGL geometry
 * approach as city.js, rendered into an independent cinematic canvas. All neon
 * avatars, the giant mech arm, and its articulated plasma grip-claw are genuine
 * 3D meshes with normals, lighting, depth testing and a perspective camera.
 * Deep Sea: abyssal ruins, glowing coral and filtered ocean light with
 * wireframe, grid horizon, CRT scanline. The SYSTEM scans then DELETES. */
(function(){
 'use strict';
 const TAU=Math.PI*2,clamp=(n,a=0,b=1)=>Math.max(a,Math.min(b,n));
 const lerp=(a,b,t)=>a+(b-a)*t,vec=(a,b)=>a.map((v,i)=>v-b[i]);
 const add=(a,b)=>a.map((v,i)=>v+b[i]),mul=(a,k)=>a.map(v=>v*k);
 const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
 const dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0),unit=a=>mul(a,1/(Math.hypot(...a)||1));
 const positions=Array.from({length:10},(_,i)=>[(i%5-2)*5.8,0,i<5?-5.3:6.2]);
 // The overhead gate is a HORIZONTAL XZ ring suspended over the arena.
 // The palm descends along -Y, and the fragment shader clips everything
 // above its opening. A wrist can never float detached in front of the gate.
 const PORTAL_CENTER=[0,44,-12],PORTAL_RADIUS=23,HAND_SCALE=4.8;
 const PORTAL_LEAD=.45,EMERGENCE_SECONDS=2.85,PORTAL_PLANE=44;
 const ease=t=>t*t*(3-2*t);
 // Single source of truth for the slow "dramatic" one-by-one final cuts, so
 // plant(), hand() and _geometry() cannot drift apart. The five final cuts are
 // the only scene with cutIds.length===5, which for step>=3 is exactly step<5.
 const isDramatic=(step,cutIds)=>step>=3&&(cutIds?cutIds.length===5:step<5);
 // Shared blade-meet instant for a cutting step: ordinary 0.95s, dramatic
 // step-3 3.0s, dramatic step-4 4.30s. Used for the plant contact, the hand's
 // blade/finger touch and the exposed severed/close signals alike.
 const contactTime=(step,cutIds)=>isDramatic(step,cutIds)?(step===4?4.30:3.0):.95;
 const portalOpening=(step,age)=>step<0?ease(clamp(age/1.15)):1;
 const handEmergence=(step,age)=>step<0?ease(clamp((age-PORTAL_LEAD)/EMERGENCE_SECONDS)):1;
 const pseudoRand=n=>{const t=Math.sin(n*127.1+311.7)*43758.5453;return t-Math.floor(t);};
 function multiply(a,b){const c=new Float32Array(16);for(let j=0;j<4;j++)for(let i=0;i<4;i++)for(let k=0;k<4;k++)c[j*4+i]+=a[k*4+i]*b[j*4+k];return c;}
 function perspective(fov,aspect,near,far){const f=1/Math.tan(fov/2);return new Float32Array([f/aspect,0,0,0,0,f,0,0,0,0,(far+near)/(near-far),-1,0,0,2*far*near/(near-far),0]);}
 function lookAt(eye,target){const z=unit(vec(eye,target)),x=unit(cross([0,1,0],z)),y=cross(z,x);return new Float32Array([x[0],y[0],z[0],0,x[1],y[1],z[1],0,x[2],y[2],z[2],0,-dot(x,eye),-dot(y,eye),-dot(z,eye),1]);}
 const vertices=[[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1],[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1]];
 const sides=[[0,1,2,3],[5,4,7,6],[3,2,6,7],[4,5,1,0],[1,5,6,2],[4,0,3,7]];
 class Mesh{
  constructor(){this.data=[];this.triangles=0;}
  tri(a,b,c,col,kind=0){if([a,b,c,col].some(v=>!Array.isArray(v)||v.length!==3))throw Error('Invalid 3D triangle tuple '+JSON.stringify([a,b,c,col]));const n=unit(cross(vec(b,a),vec(c,a)));for(const p of [a,b,c])this.data.push(p[0],p[1],p[2],n[0],n[1],n[2],col[0],col[1],col[2],kind);this.triangles++;}
  quad(a,b,c,d,col,kind=0){this.tri(a,b,c,col,kind);this.tri(a,c,d,col,kind);}
  box(x,y,z,w,h,d,col,kind=0){const p=vertices.map(v=>[x+v[0]*w*.5,y+v[1]*h*.5,z+v[2]*d*.5]);for(const face of sides)this.quad(...face.map(i=>p[i]),col,kind);}
  gem(x,y,z,r,col,kind=0,stretch=1){const p=[[x+r,y,z],[x,y,z+r],[x-r,y,z],[x,y,z-r]],top=[x,y+r*stretch,z],bot=[x,y-r*stretch,z];for(let i=0;i<4;i++){this.tri(top,p[i],p[(i+1)%4],col,kind);this.tri(bot,p[(i+1)%4],p[i],col,kind);}}
  cylinder(a,b,r,col,other=r,segments=8,kind=0){
   const axis=unit(vec(b,a)),side=unit(cross(axis,Math.abs(axis[1])>.85?[1,0,0]:[0,1,0])),perp=cross(axis,side);
   const ring=(p,rad,t)=>add(p,add(mul(side,Math.cos(t)*rad),mul(perp,Math.sin(t)*rad)));
   for(let i=0;i<segments;i++){
    const t0=i*TAU/segments,t1=(i+1)*TAU/segments;
    const u=ring(a,r,t0),v=ring(a,r,t1),w=ring(b,other,t1),x=ring(b,other,t0);
    this.quad(u,x,w,v,col,kind);this.tri(a,v,u,col,kind);this.tri(b,x,w,col,kind);
   }
  }
  sphere(c,rx,ry,rz,col,kind=0,rings=5,slices=10){
   const pt=(phi,th)=>[c[0]+rx*Math.cos(th)*Math.sin(phi),c[1]+ry*Math.cos(phi),c[2]+rz*Math.sin(th)*Math.sin(phi)];
   for(let k=0;k<rings;k++)for(let i=0;i<slices;i++){
    const p=k*Math.PI/rings,q=(k+1)*Math.PI/rings,a=i*TAU/slices,b=(i+1)*TAU/slices;
    this.quad(pt(p,a),pt(p,b),pt(q,b),pt(q,a),col,kind);
   }
  }
  ring(center,r,tube,col,axis='xy',kind=0){
   const coord=(angle,rad)=>axis==='xy'?[center[0]+Math.cos(angle)*rad,center[1]+Math.sin(angle)*rad,center[2]]:
        [center[0]+Math.cos(angle)*rad,center[1],center[2]+Math.sin(angle)*rad];
   const N=20;
   for(let i=0;i<N;i++){
    const a=i*TAU/N,b=(i+1)*TAU/N;
    const p=coord(a,r),q=coord(b,r);
    this.cylinder(p,q,tube,col,tube,5,kind);
   }
  }
  // Smooth Gouraud-style meshes: PS2-era modeled skin, not cubes or gems.
  smoothTri(a,b,c,na,nb,nc,col,kind=7){
   for(const [p,n] of [[a,na],[b,nb],[c,nc]])this.data.push(...p,...unit(n),...col,kind);
   this.triangles++;
  }
  softSphere(center,rx,ry,rz,col,kind=7,rings=10,segments=16){
   const p=(v,t)=>[center[0]+rx*Math.sin(v)*Math.cos(t),center[1]+ry*Math.cos(v),center[2]+rz*Math.sin(v)*Math.sin(t)];
   const n=a=>[(a[0]-center[0])/(rx*rx),(a[1]-center[1])/(ry*ry),(a[2]-center[2])/(rz*rz)];
   for(let i=0;i<rings;i++)for(let j=0;j<segments;j++){
    const va=i*Math.PI/rings,vb=(i+1)*Math.PI/rings,ta=j*TAU/segments,tb=(j+1)*TAU/segments;
    const a=p(va,ta),b=p(va,tb),c=p(vb,tb),d=p(vb,ta);
    this.smoothTri(a,b,c,n(a),n(b),n(c),col,kind);
    this.smoothTri(a,c,d,n(a),n(c),n(d),col,kind);
   }
  }
  softTube(path,radii,col,kind=7,segments=12){
   const rings=path.map((center,i)=>{
    const tangent=unit(vec(path[Math.min(path.length-1,i+1)],path[Math.max(0,i-1)]));
    const basis=unit(cross(tangent,Math.abs(tangent[1])>.9?[0,0,1]:[0,1,0]));
    const next=unit(cross(tangent,basis));
    return Array.from({length:segments},(_,j)=>{
     const t=j*TAU/segments,normal=add(mul(basis,Math.cos(t)),mul(next,Math.sin(t)));
     return {p:add(center,mul(normal,radii[i])),n:normal};
    });
   });
   for(let i=0;i<rings.length-1;i++)for(let j=0;j<segments;j++){
    const k=(j+1)%segments,a=rings[i][j],b=rings[i][k],c=rings[i+1][k],d=rings[i+1][j];
    this.smoothTri(a.p,b.p,c.p,a.n,b.n,c.n,col,kind);
    this.smoothTri(a.p,c.p,d.p,a.n,c.n,d.n,col,kind);
   }
  }
  loopEllipse(c,rx,ry,col,tube=.13,kind=8){
   const path=Array.from({length:33},(_,i)=>[c[0]+Math.cos(i*TAU/32)*rx,c[1]+Math.sin(i*TAU/32)*ry,c[2]]);
   this.softTube(path,path.map(()=>tube),col,kind,8);
  }
 }

 // The same geometry style as the 3D grid city, rebuilt into a layered neon
 // skyline. Structural meshes are cached: dynamic action remains only the 10
 // living competitors, the vortex, drifting data-motes and the giant mech arm.
 function wall(m,x,y,z,w,d,h){
  // Basalt reef walls grow coral branches instead of masonry panels.
  const count=Math.ceil(Math.max(w,d)/2.5);
  for(let i=0;i<count;i++){
    const t=(i+.5)/count-.5,px=x+(w>d?t*w:0),pz=z+(w>d?0:t*d);
    const ht=h*(.75+pseudoRand(i*17+Math.abs(x)*5)*.5);
    m.gem(px,.35,pz,Math.max(.7,Math.min(1.35,w>d?d*.6:w*.6)),[.07,.17,.19],1,ht*.62);
    m.gem(px,ht*.72,pz,.46,[.20,.58,.51],2,1.35);
  }
 }
 function holoSign(m,x,y,z,tier=3,palette=0){
  // A tiny holographic sign post: emissive stalk crowned with a neon glyph.
  const tints=[[.17,.95,.92],[.31,.88,.78],[.60,.42,.98],[.98,.80,.32]];
  const col=tints[Math.floor(Math.abs(palette))%4];
  const height=.24+.11*tier;
  m.cylinder([x,y,z],[x,y+height,z],.065,[.20,.60,.80],.043,6);
  if(tier<2){m.gem(x,y+height,z,.14,[.24,.78,.92],2,1.2);return;}
  m.gem(x,y+height,z,.19,[.20,.95,.95],2,1.0);
  for(let i=0;i<5;i++){
   const a=i*TAU/5;
   m.gem(x+Math.cos(a)*.20,y+height+.055,z+Math.sin(a)*.20,.19,col,6,.85);
  }
 }
 function pylon(m,x,z,scale=1){
  // Street grid light pylon with a magenta lamp halo.
  m.box(x,1.55*scale,z,.18*scale,3.1*scale,.18*scale,[.14,.18,.26]);
  m.gem(x,3.15*scale,z,.48*scale,[.36,.86,.75],2,1.2);
  m.box(x,3.64*scale,z,.77*scale,.15*scale,.77*scale,[.20,.72,.90],2);
  m.gem(x,3.9*scale,z,.32*scale,[.40,.95,1],2,1.4);
 }
 function neonArch(m,x,z,wide=5.0){
  // Fossilized coral arches frame the entrance to the underwater arena.
  for(const side of [-1,1]){
    const xx=x+side*wide*.51;
    m.cylinder([xx,0,z],[xx-side*.45,5.6,z],.37,[.12,.35,.34],.22,7,1);
    for(let i=0;i<5;i++)m.gem(xx-side*(.3+i*.16),1.5+i*.89,z,.42,[.32,.82,.72],2,1.3);
  }
  m.ring([x,5.7,z],wide*.5,.21,[.32,.82,.72],'xy',2);
 }
 function dataSpire(m,x,z,height=7){
  // Clustered emissive data-node obelisk, a stand-in for a wireframe tree.
  const dark=[.05,.10,.18],light=[.20,.88,.92];
  m.cylinder([x,0,z],[x,height*.6,z],.36,[.10,.14,.22],.24,7);
  for(let j=0;j<3;j++){
   const y=height*(.43+j*.21),r=(1.6-j*.26);
   m.sphere([x,y,z],r,.85+j*.06,r,dark,5,5,9);
   m.gem(x,y+.66,z,r*.71,light,2,.54);
  }
  m.gem(x,height+.55,z,.35,[.45,.92,.72],2,1.4);
 }
 function dataWell(m,x,z){
  // A circular holo-fountain: concentric neon rings over a dark basin, with
  // light jets of cyan data arcing outward like spraying water.
  const base=[.06,.09,.16],ring=[.20,.74,.72],spray=[.55,.92,1];
  m.cylinder([x,.05,z],[x,.50,z],3.6,base,3.9,20);
  m.cylinder([x,.54,z],[x,.62,z],3.15,ring,3.12,20,2);
  m.cylinder([x,.15,z],[x,1.52,z],.61,base,.64,12);
  m.cylinder([x,1.48,z],[x,1.70,z],1.63,base,1.72,14);
  m.cylinder([x,1.71,z],[x,1.75,z],1.34,ring,1.34,14,2);
  m.gem(x,2.55,z,.49,[.58,.93,.74],2,1.45);
  for(let j=0;j<12;j++){
   const a=j*TAU/12,u=x+2.45*Math.cos(a),v=z+2.45*Math.sin(a);
   m.gem(u,.77,v,.17,spray,2,1.9);
  }
  for(let i=0;i<8;i++){
   const a=i*TAU/8;
   m.cylinder([x+Math.cos(a)*.85,1.72,z+Math.sin(a)*.85],
      [x+Math.cos(a)*2.55,.67,z+Math.sin(a)*2.55],.042,spray,.024,5,2);
  }
 }
 function holoPavilion(m,x,z){
  // Hovering holo-canopy on neon columns, a floating city kiosk.
  const strut=[.10,.16,.26],glow=[.95,.30,.76];
  m.cylinder([x,0,z],[x,.52,z],5.0,strut,5.0,12);
  for(let i=0;i<8;i++){
   const a=i*TAU/8,p=[x+Math.cos(a)*4.0,z+Math.sin(a)*4.0];
   m.cylinder([p[0],.52,p[1]],[p[0],6.8,p[1]],.34,strut,.34,8);
   m.gem(p[0],6.98,p[1],.5,glow,2,.45);
  }
  m.cylinder([x,7.10,z],[x,8,z],5.05,[.14,.76,.88],2.2,12,2);
  m.gem(x,9.4,z,2.9,[.18,.84,.92],2,1.08);
  m.gem(x,12.5,z,.58,[.55,.92,1],2,1.7);
 }
 function createField(){
  const m=new Mesh();
  // Painted sky triangle at the far depth plane, drawn with the city mesh.
  m.tri([-1,-1,0],[3,-1,0],[-1,3,0],[.07,.05,.16],9.5);
  const deck=[.04,.06,.12],plaza=[.06,.09,.17],
      slab=[.09,.13,.22],neon=[.16,.84,.92];
  m.box(0,-1.05,0,70,2.1,73,[.018,.08,.105],3);
  m.box(0,.012,0,64,.06,69,deck,3);
  // Glowing TRON grid floor: alternating dark tiles with emissive seam motes.
  for(let x=-30;x<=30;x+=5)for(let z=-30;z<=30;z+=5){
   const dark=(Math.round(x+z)/5)%2===0;
   m.box(x,.057,z,4.85,.04,4.85,dark?[.04,.12,.15]:[.05,.15,.17],3);
   const seed=(x+31)*571+(z+31)*43;
   for(let i=0;i<3;i++){
    const px=x+(pseudoRand(seed+i*3)-.5)*3.7,pz=z+(pseudoRand(seed+i*5+17)-.5)*3.8;
    m.gem(px,.16,pz,.085,[.20,.70,.85],2,.75);
   }
  }
  // Central concourse: straight light-strips with cyan-inlaid rims and a dais.
  m.box(0,.105,-.4,35,.12,28,plaza,3);
  for(const x of [-17.0,17.0])m.box(x,.19,-.4,.27,.17,29,neon,2);
  m.box(0,.20,.30,35,.20,3.45,slab,1);
  m.box(0,.315,.30,35,.04,.16,neon,2);
  for(const x of [-14.75,14.75])m.box(x,.20,-.4,1.05,.19,28,slab,1);
  for(let n=0;n<18;n++)m.box(-17.0+n*2,.329,.30,.035,.023,3.2,[.18,.86,.94],2);
  // Wide stepped ramp leading forward toward the viewer.
  for(let k=0;k<5;k++)m.box(0,.24-k*.035,16+k*1.9,31-k*.7,.23,1.65,slab,1);
  // Ten identical player nodes; a stage-specific neon avatar boots up above.
  for(let i=0;i<10;i++){
   const [x,,z]=positions[i];
   m.cylinder([x,.12,z],[x,.43,z],1.80,[.08,.12,.20],1.91,12,1);
   m.cylinder([x,.44,z],[x,.56,z],1.96,neon,1.96,12,2);
   m.cylinder([x,.57,z],[x,.70,z],1.80,slab,1.80,12,1);
   for(let j=0;j<6;j++){
    const a=j*TAU/6;
    m.gem(x+Math.cos(a)*1.57,.78,z+Math.sin(a)*1.57,.11,[.45,.92,.72],2,.9);
   }
  }
  // Symmetrical neon barrier lanes, raised data-rails and glowing edging.
  for(const s of [-1,1]){
   wall(m,s*21,0,-3,2.4,39,2.9);
   wall(m,s*28,0,2,1.4,48,3.7);
   wall(m,s*24,0,19,9,1.55,2.1);
   wall(m,s*24,0,-22,9,1.55,2.1);
   dataSpire(m,s*25,-14,8.2);
   dataSpire(m,s*25,12,7.0);
   holoPavilion(m,s*32,-29);
   dataWell(m,s*26,0);
   neonArch(m,s*22,-7,6.6);
   for(let k=0;k<32;k++){
    const z=-20+k*1.30,x=s*(22.8+(k%4)*1.11);
    holoSign(m,x,.1,z,3,k);
   }
   for(let k=0;k<4;k++)pylon(m,s*18,-13+k*9,.9);
  }
  wall(m,0,0,-26,55,1.7,3.9);
  wall(m,0,0,25,55,1.7,2.8);
  // Neon gateway arches behind the arena; light pylons flank the vortex.
  neonArch(m,-15,-23,6.3);neonArch(m,15,-23,6.3);
  for(let x=-14;x<=14;x+=4){
   holoSign(m,x,.1,-18.4,4,(x+20)/4);
   holoSign(m,x,.1,19.4,4,(x+24)/4);
  }
  // Distant painted vista: layered neon-magenta skyline ridges, a glowing
  // data-tower band and a flowing light-stream threading toward the horizon.
  // Kept far back and low on screen so the foreground avatars stay the focus.
  const ridgeTones=[[.06,.28,.33],[.04,.21,.27],[.03,.15,.22]];
  for(let ridge=0;ridge<3;ridge++){
   const depth=-58-ridge*9,baseH=15+ridge*5,tone=ridgeTones[ridge];
   let prevX=-56,prevY=.4;
   for(let step=0;step<=14;step++){
    const px=-56+step*8;
    const peak=baseH*(.55+pseudoRand(ridge*31+step*7)*.6);
    const foot=.4;
    m.tri([prevX,foot,depth],[px,foot,depth],[(prevX+px)*.5,peak,depth],tone,1);
    m.tri([prevX,foot,depth],[(prevX+px)*.5,peak,depth],[px,foot,depth],tone,1);
    prevX=px;prevY=peak;
   }
  }
  // Dense neon tower skyline sitting below the ridges in the mid distance.
  const tower=[.95,.24,.70],towerLit=[.30,.86,.95];
  for(let t=0;t<22;t++){
   const tz=-46-pseudoRand(t*5+3)*7,tx=-50+t*4.6+pseudoRand(t*9)*2.4;
   const th=3.2+pseudoRand(t*13+1)*2.6;
   m.cylinder([tx,.4,tz],[tx,.4+th*.3,tz],.26,[.08,.10,.18],.2,5,1);
   m.gem(tx,.4+th*.55,tz,th*.42,tower,2,1.7);
   m.gem(tx,.4+th*.82,tz,th*.26,towerLit,2,1.8);
  }
  // Flowing light-stream: a chain of cyan data-river segments catching the
  // skyline glow as it threads out of the far grid toward the concourse.
  const stream=[.13,.57,.67];
  let riverX=-4,riverZ=-50;
  for(let bend=0;bend<10;bend++){
   const nz=riverZ+5.2,nx=riverX+Math.sin(bend*.9)*6.0;
   const wNear=1.4+bend*.55,wFar=1.4+(bend-1)*.55;
   m.quad([riverX-wFar,.14,riverZ],[riverX+wFar,.14,riverZ],
     [nx+wNear,.15,nz],[nx-wNear,.15,nz],stream,2);
   riverX=nx;riverZ=nz;
  }
  // Half-buried temple columns, sponge towers and shoals replace server towers.
  for(const x of [-25,-17,-9,-1,7,15,23]){
    const height=9+3*pseudoRand(x+57);
    m.cylinder([x,0,-34],[x,height,-34],1.1,[.09,.22,.23],.64,10,1);
    m.gem(x,height+.3,-34,1.7,[.27,.75,.64],2,.70);
  }
  for(const x of [-25,25]){
    m.sphere([x,7,-40],5,9,4,[.10,.28,.30],1,8,12);
    m.gem(x,15,-40,3,[.30,.84,.69],2,1.1);
  }
  for(let i=0;i<18;i++){const x=-26+i*3.1,z=-28-(i%5)*.65,y=8+(i%4)*2.1;
    m.gem(x,y,z,.38,[.27,.66,.67],2,.52);
    m.tri([x-.45,y,z],[x-.98,y+.4,z],[x-.98,y-.4,z],[.19,.52,.53],2);
  }
  return m;
 }
 let baseField=null;
 function addFin(m,root,direction,y,len,width,col){
  // A flat emissive fin / data-wing jutting off the avatar frame.
  const x=root[0],z=root[2],p=[x,y,z],
      tip=[x+len*direction,y+len*.40,z+len*.22*direction],
      side=[x+len*.38*direction,y+len*.12,z+width];
  m.tri(p,tip,side,col,5);m.tri(p,side,tip,col,5);
  const back=[side[0],side[1],z-width];
  m.tri(p,back,tip,col,5);m.tri(p,tip,back,col,5);
 }
 function corona(m,center,scale,petals,col,prime=false){
  // The avatar's holographic crown: a glowing core wrapped in orbiting data
  // plates. `prime` adds the full data-ring halo for the top tiers.
  const [x,y,z]=center;
  m.gem(x,y,z,scale*.41,[.30,.95,1],2,1.2);
  for(let layer=0;layer<(prime?3:2);layer++){
   const ring=petals+(layer%2?2:0),r=scale*(.38+layer*.34);
   for(let j=0;j<ring;j++){
    const a=j*TAU/ring+layer*.26;
    const tone=col.map((c,i)=>clamp(c+(layer===0?.13:layer===2?-.12:0)));
    m.gem(x+Math.cos(a)*r,y+layer*.07+.08*Math.sin(a*2),z+Math.sin(a)*r,
      scale*(prime?.39:.44),tone,layer===0?2:6,.72);
   }
  }
  if(prime){
   m.ring([x,y+.18,z],scale*1.34,.055,[.58,.93,.74],'xz',2);
   for(let i=0;i<5;i++){
    const a=i*TAU/5;m.gem(x+Math.cos(a)*scale*1.26,y+.30,z+Math.sin(a)*scale*1.26,
      scale*.18,[.55,.95,1],2,1.65);
   }
  }
 }
 // One goal -> the first boot-up fins; by 21 goals a full neon-avatar corona.
 // Each tier has a distinct 3D silhouette, limbs, nodes and corona plate count.
 function plant(m,model,index,cutIds,step,age,elapsed){
  const [x,,z]=positions[index],tier=clamp(Math.floor(Number(model.tier)||0),0,6);
  const cutIndex=cutIds.indexOf(model.id),
   prior=!!model.priorPruned||cutIndex>=0&&cutIndex<step,cutting=cutIndex===step;
  const dramatic=isDramatic(step,cutIds);
  const contact=contactTime(step,cutIds);
  // `fall` drives the SEVERED TOP away once the blades meet; the lower stump
  // stays rooted. Before contact fall=0 so the whole plant reads upright/whole.
  const fall=prior?1:cutting?ease(clamp((age-(contact-.02))/.72)):0;
  const sway=prior?0:Math.sin(elapsed*1.4+index*1.31)*.055;
  const height=[.48,1.18,1.98,2.78,3.65,4.63,5.58][tier]*(prior?.64:1);
  const limbColor=prior?[.17,.29,.33]:tier>3?[.36,.85,.72]:[.28,.70,.74];
  const palette=[[.36,.86,.69],[.30,.92,.84],[.38,.70,.94],[.95,.80,.51]][index%4];
  // The avatar is split at `cutY`, just below the corona head. Anything below
  // stays an upright rooted base; anything at/above cutY is the deleted top
  // that tips, drops and drifts sideways as `fall` ramps 0->1 (power-down).
  const cutY=height*.78,dir=index%2?-1:1;
  const base=p=>[x+p[0]+sway*p[1],.75+p[1],z+p[2]];
  const map=p=>{
   if(fall<=0)return base(p);
   if(p[1]<cutY-1e-6)return base(p);
   const t=fall*1.95,dy=p[1]-cutY,drop=fall*fall*(2.8+height*.62)+fall*.55,drift=fall*(2.3+height*.34)*dir;
   return [x+p[0]*Math.cos(t)+dy*Math.sin(t)*dir+sway*cutY+drift,
     .75+cutY+dy*Math.cos(t)-p[0]*Math.sin(t)*dir-drop,z+p[2]+fall*.6];
  };
  m.cylinder([x,.71,z],[x,.95,z],.89,[.10,.14,.22],1.04,10);
  m.cylinder([x,.96,z],[x,1.01,z],1.05,[.20,.74,.72],1.05,10);
  // Core column: a single upright length when whole; once deleted it splits
  // into a rooted base (below cutY) and an upper length riding away powered-down.
  const severed=fall>0;
  if(severed){
   m.cylinder(base([0,.05,0]),base([0,cutY-fall*.12,0]),.10+tier*.016,[.20,.79,.69],.035+tier*.011,8);
   m.cylinder(map([0,cutY,0]),map([0,height,0]),.10+tier*.016,[.20,.79,.69],.035+tier*.011,8);
  }else{
   m.cylinder(base([0,.05,0]),base([0,height,0]),.10+tier*.016,[.20,.79,.69],.035+tier*.011,8);
  }
  // Growth stage 0 is a bare boot-up spark, not a formed avatar.
  if(tier===0){
   for(const d of [-1,1])addFin(m,map([0,.18,0]),d,.2,.20,.13,[.30,.86,.92]);
   m.gem(...map([0,height,0]),.20,[.34,.90,.95],2,1.18);
   return;
  }
  for(let j=0;j<Math.min(8,2+tier);j++){
   const a=j*TAU/3,y=.35+(height-.65)*(j/(3+tier));
   const dir=j%2?1:-1;
   const p=map([0,y,0]),q=map([dir*(.38+tier*.073),y+.20,Math.sin(a)*.30]);
   m.cylinder(p,q,.062,[.18,.70,.88],.025,6);
   m.gem(...q,.28+tier*.036,limbColor,2,.31);
   if(tier>=4)addFin(m,p,dir,p[1]+.16,.31,.18,[.26,.78,.90]);
  }
  if(tier===1){m.gem(...map([0,height,0]),.25,[.30,.88,.94],2,1.55);return;}
  if(tier===2){
   m.gem(...map([0,height,0]),.44,prior?[.28,.26,.32]:palette,2,1.6);
   m.gem(...map([0,height+.26,0]),.19,[.34,.90,.95],2,1.2);return;
  }
  const color=prior?[.30,.28,.34]:palette;
  // Fish-like body with fan tail, dorsal plates and a luminous eye.
  // The creature's body is anchored to its falling upper segment during a cut.
  const body=1+(tier-3)*.43;
  m.sphere(map([0,height,0]),body,body*.52,body*.45,color,2,7+tier,12+tier*2);
  m.tri(map([-body*.7,height,0]),map([-body*1.7,height+body*.55,0]),
        map([-body*1.7,height-body*.55,0]),color,2);
  m.gem(...map([body*.68,height+body*.13,0]),.14,[.02,.12,.18],2,.9);
  for(let fin=0;fin<Math.max(1,tier-2);fin++){
    const px=(fin/Math.max(1,tier-2)-.5)*body;
    m.gem(...map([px,height+body*.5,0]),.22+fin*.07,[.49,.94,.77],2,.8);
  }
  if(tier>=4){
   for(let k=0;k<(tier===4?2:tier===5?4:6);k++){
    const a=k*TAU/Math.max(2,tier===4?2:tier===5?4:6);
    const by=height*(.52+(k%3)*.13),reach=.45+(k%2)*.33+tier*.03;
    const p=map([0,by,0]),q=map([Math.cos(a)*reach,by+reach*.43,Math.sin(a)*reach]);
    m.cylinder(p,q,.058,[.16,.64,.84],.028,6);
    corona(m,q,tier===6?.34:.25,5,prior?[.26,.24,.30]:palette,false);
   }
  }
  // A neon halo-ring and node crown is earned, never present at 0 goals.
  if(tier>=5&&!prior){
   m.ring(map([0,height*.71,0]),tier===6?1.18:.80,.065,[.58,.93,.74],'xz',2);
   if(tier===6){
    for(let k=0;k<8;k++){
     const a=k*TAU/8;
     m.cylinder(map([Math.cos(a)*1.02,height*.55,Math.sin(a)*1.02]),
        map([Math.cos(a)*1.17,height*.94,Math.sin(a)*1.17]),.06,[.20,.84,.92],.05,5,2);
     m.gem(...map([Math.cos(a)*1.17,height*.96,Math.sin(a)*1.17]),.21,[.55,.95,1],2,1.6);
    }
   }
  }
  if(cutting&&age>contact-.01&&age<contact+.73){
   // Neon shards and data fragments burst outward and fall as the beam deletes.
   const sparkTones=[[.30,.90,.98],[.58,.93,.74],[.36,.67,.91],[.55,.95,1]];
   for(let j=0;j<12;j++){
    const a=j*TAU/12,spread=clamp((age-contact)/.75),drop=spread*spread*1.9;
    const lx=x+Math.cos(a)*spread*1.8,lz=z+Math.sin(a)*spread*1.8;
    const ly=height+Math.sin(j)*.3-drop;
    const tone=sparkTones[j%4];
    // Flattened, elongated emissive motes read as data shards shearing off.
    m.gem(lx,ly,lz,.17,tone,2,.26);
    m.gem(lx+Math.cos(a)*.12,ly-.14,lz+Math.sin(a)*.12,.11,tone,2,.4);
   }
  }
 }
 function portal(m,step,age,elapsed){
  const opening=portalOpening(step,age);
  if(opening<.008)return;
  const [x,y,z]=PORTAL_CENTER,r=PORTAL_RADIUS*opening,SEG=64;
  // The camera sees the UNDERSIDE of this horizontal XZ opening. The neon
  // vortex spins behind the arm; the ring always stays above the mech grip.
  const p=(a,rad,dy=0)=>[x+Math.cos(a)*rad,y+dy,z+Math.sin(a)*rad];
  const vortex=[[.05,.02,.14],[.22,.05,.30],[.52,.10,.52],[.14,.52,.72],[.26,.85,.78]];
  for(let band=0;band<5;band++){
   const low=band*r/5,high=(band+1)*r/5;
   for(let j=0;j<SEG;j++){
    const a=j*TAU/SEG+elapsed*(band%2?-.22:.30),b=(j+1)*TAU/SEG+elapsed*(band%2?-.22:.30);
    const col=vortex[band];m.quad(p(a,low,.2),p(b,low,.2),p(b,high,.2),p(a,high,.2),col,2);
   }
  }
  // Concentric neon whirlpool rings, cyan and magenta spiralling inward.
  for(let i=0;i<10;i++){
   const t=i/10,rad=r*(.27+t*.86);
   const tint=i%3===0?[.40,.96,1]:i%3===1?[.98,.34,.80]:[.52,.30,.86];
   const offset=.27*Math.sin(elapsed*(i%2?1:-1)+i);
   m.ring([x,y-.18+offset,z],rad,.18+.16*(i%3===0),tint,'xz',2);
  }
  for(const [size,tube,col] of [[1.00,.53,[.45,.98,1]],[1.12,.25,[.98,.40,.82]],[1.23,.12,[.40,.30,.80]]]){
   m.ring([x,y-.32,z],r*size,tube*opening,col,'xz',2);
  }
  // Swirling elongated data filaments; no square runes or fake halos.
  for(let arm=0;arm<8;arm++)for(let j=0;j<14;j++){
   const a=arm*TAU/8+elapsed*.62+j*.075,rad=r*(.16+j*.054);
   const q=p(a,rad,-.39),q2=p(a+.18,rad+r*.045,-.41);
   m.cylinder(q,q2,.055*opening,[.55,.95,1],.012*opening,4,2);
  }
  for(let j=0;j<26;j++){
   const a=j*TAU/26+elapsed*.3,rr=r*(1.07+Math.sin(j*5+elapsed)*.025);
   const q=p(a,rr,-.48);
   m.gem(...q,.13+(j%3)*.05,[.60,.96,1],2,1.6);
  }
  // Data-beams: emissive light shafts fanning down out of the neon vortex,
  // the SYSTEM casting scanning light across the grid around the gate.
  const shafts=9;
  for(let s=0;s<shafts;s++){
   const a=s*TAU/shafts+elapsed*.07,rad=r*(.5+(s%3)*.17);
   const top=[x+Math.cos(a)*rad*.3,y-.6,z+Math.sin(a)*rad*.3];
   const foot=[x+Math.cos(a)*rad,y-24-(s%2)*5,z+Math.sin(a)*rad];
   const beam=[.45,.92,1.0];
   m.cylinder(top,foot,.18*opening,beam,2.0*opening,4,2);
  }
 }
 function hand(m,position,elapsed,step,age,cutIds){
  const [x,y,z]=position,at=(a,b,c)=>[x+a,y+b,z+c];
  const chrome=[.52,.60,.72],shade=[.34,.40,.52],highlight=[.55,.95,1],
   stone=[.40,.46,.58],metal=[.12,.62,.78],edge=[.30,.86,.96],dark=[.04,.08,.16];
  // Soft-shaded mech forearm and knuckle housing, jointed grip-claw segments.
  // The forearm extends ABOVE the gate; the shader hides that portion.
  m.softTube([at(0,12,0),at(0,8.5,0),at(0,5.2,-.16),at(0,2.3,.02)],
    [1.24,1.42,1.30,1.01],chrome,7,16);
  m.softSphere(at(0,1.09,.06),1.60,1.84,.77,chrome,7,12,20);
  m.softSphere(at(0,-.55,.48),1.74,1.34,.91,chrome,7,12,20);
  m.softSphere(at(-.42,-.55,.83),.67,1.10,.51,shade,7,10,12);
  // Grip closure progress. The SAME `close` ease drives both the plasma
  // grip-blades and the claw digits, so the arm visibly clamps shut and reaches
  // full curl at the instant the blades meet (`touch`): finger-close,
  // blade-close, contact and the delete all coincide. close=0 is the open pose.
  const dramatic=isDramatic(step,cutIds);
  const touch=contactTime(step,cutIds);
  const close=step<0?0:ease(clamp((age-(touch-(dramatic?1.9:.33)))/(dramatic?1.9:.33)));
  // Claw digits curl inward/downward as `close` ramps 0->1, each joint bending
  // progressively toward the plasma emitters so the grip drives the delete.
  const spread=[-1.17,-.39,.41,1.16];
  for(let i=0;i<4;i++){
   const dx=spread[i],length=[2.30,2.82,2.68,2.14][i],
     curl=close*(1.0+(i===1||i===2?.16:0)),
     from=at(dx,-1.21,.97),
     knuckle=at(dx*(.99-.07*curl),-1.55-length*.34+length*.14*curl,1.42+.82*curl),
     joint=at(dx*(.89-.16*curl),-1.65-length*.71+length*.58*curl,2.05+1.46*curl*length*.34),
     tip=at(dx*(.79-.26*curl),-1.62-length+length*1.08*curl,2.22+2.08*curl*length*.34);
   m.softSphere(from,.40,.42,.40,chrome,7,8,12);
   m.softTube([from,knuckle,joint,tip],[.38,.36,.27,.12],chrome,7,12);
   m.softSphere(joint,.28,.28,.30,shade,7,7,10);
   m.softSphere(tip,.15,.17,.21,highlight,7,7,10);
   // Glowing emitter tips rather than organic nails: an emissive claw cap.
   m.softSphere(add(tip,[0,.075,.17]),.125,.064,.09,highlight,7,6,10);
  }
  // Opposing thumb-clamp presses in across the housing with the same closure.
  const thumb=[at(-1.42,.02,.74),
    at(-2.08+1.05*close,-.92-.55*close,1.45+.42*close),
    at(-1.53+1.35*close,-2.04-.30*close,2.07+.46*close)];
  m.softTube(thumb,[.57,.42,.24],chrome,7,12);
  m.softSphere(thumb[1],.43,.41,.43,shade,7,8,12);
  // Faint cable/conduit detail running down the alloy forearm.
  for(let i=-1;i<=1;i++){
   const u=i*.58;m.softTube([at(u,1.4,.77),at(u*.93,.55,.96),at(u*.9,-.7,1.09)],
    [.035,.048,.027],highlight,7,5);
  }
  // Emissive neon cuff bands and a glowing palm sigil on the mech housing.
  for(const yy of [5.45,7.35])m.ring(at(0,yy,-.05),1.40,.095,[.58,.93,.74],'xz',2);
  m.gem(...at(0,.10,1.03),.43,[.20,.88,.96],2,1.4);
  for(const sx of [-1,1])m.gem(...at(sx*.54,.30,.94),.15,[.40,.92,1],2,1.1);
  // Twin plasma grip-blades on a glowing pivot, with two ring mounts. The
  // emitters progressively close on the target avatar at exactly 0.95 s.
  // Blades share the `close` ease computed above with the claw digits.
  const pivot=at(.72,-2.69,2.22);
  const width=(1-close)*1.25;
  const left=at(.72-width,-5.55,2.38),right=at(.72+width,-5.55,2.38);
  function blade(tip,which){
   const base=add(pivot,[which*.34,-.28,-.05]),mid=add(mul(base,.56),mul(tip,.44));
   const wing=add(mid,[which*.45,.04,.19]);
   m.tri(base,wing,tip,metal,8);
   m.tri(base,tip,wing,edge,8);
   m.cylinder(base,tip,.045,edge,.022,5,8);
  }
  blade(left,-1);blade(right,1);
  m.softSphere(pivot,.26,.26,.24,[.18,.74,.90],8,8,12);
  const handleL=at(-.23,-2.50,2.24),handleR=at(1.62,-2.50,2.24);
  m.softTube([pivot,at(.08,-1.72,2.36),handleL],[.18,.15,.13],metal,8,10);
  m.softTube([pivot,at(1.38,-1.76,2.35),handleR],[.18,.15,.13],metal,8,10);
  m.loopEllipse(at(-.48,-2.34,2.25),.59,.72,dark,.13,8);
  m.loopEllipse(at(1.84,-2.28,2.25),.59,.73,dark,.13,8);
  m.gem(...pivot,.15,highlight,8,1.0);
 }
 // World-space scissor tips stay aligned with the selected player rather than
 // pointing to an unrelated pot. Action starts at the previous frame's position.
 function handPosition(models,cutIds,step,age,previous,elapsed=0){
  const emerged=[0,34,-12];
  if(step<0)return [0,lerp(78,emerged[1],handEmergence(step,age)),-12];
  const id=cutIds[step],index=models.findIndex(p=>p.id===id);
  if(index<0)return previous||emerged;
  const [x,,z]=positions[index],tier=Number(models[index].tier)||0;
  const bloomY=.75+[.48,1.18,1.98,2.78,3.65,4.63,5.58][Math.min(6,tier)];
  // At closure both shear tips converge at local [.72,-5.55,2.38].
  const target=[x-.72*HAND_SCALE,bloomY+5.55*HAND_SCALE,z-2.38*HAND_SCALE];
  const from=previous||emerged,t=ease(clamp(age/(cutIds.length===5&&step>=3?(step===4?3.7:2.45):.72)));
  const resting=from.map((v,i)=>lerp(v,target[i],t));
  if(coronation){
   const retreat=ease(clamp((elapsed-coronation.started)/3.4));
   return resting.map((v,i)=>lerp(v,[0,80,-12][i],retreat));
  }
  return resting;
 }
 function shotCamera(models,cuts,step,age,previous,elapsed=0){
  const wide={eye:[0,17,47],target:[0,24,-12],fov:68*Math.PI/180};
  const garden={eye:[0,17.5,27],target:[0,3.6,-.4],fov:54*Math.PI/180};
  if(step<0){
   const t=ease(clamp((age-3.10)/1.55));
   return {eye:wide.eye.map((v,i)=>lerp(v,garden.eye[i],t)),
    target:wide.target.map((v,i)=>lerp(v,garden.target[i],t)),
    fov:lerp(wide.fov,garden.fov,t),phase:t<.95?'arrival':'judgement'};
  }
  const index=models.findIndex(p=>p.id===cuts[step]);
  if(index<0)return {...garden,phase:'pruning'};
  const [x,,z]=positions[index],offset=x>0?3.4:-3.4;
  const close={eye:[x+offset,12.8,z+15.4],target:[x,3.5,z],fov:52*Math.PI/180};
  const from=previous||garden,t=ease(clamp(age/.72));
  const current={eye:from.eye.map((v,i)=>lerp(v,close.eye[i],t)),
   target:from.target.map((v,i)=>lerp(v,close.target[i],t)),
   fov:lerp(from.fov,close.fov,t),phase:'pruning'};
  if(!coronation)return current;
  const winner=models.findIndex(m=>m.id===coronation.id);
  if(winner<0)return current;
  const [cx,,cz]=positions[winner],u=ease(clamp((elapsed-coronation.started)/2.5));
  const crownCamera={eye:[cx+3,13.2,cz+19],target:[cx,5,cz],fov:51*Math.PI/180};
  return {eye:current.eye.map((v,i)=>lerp(v,crownCamera.eye[i],u)),
   target:current.target.map((v,i)=>lerp(v,crownCamera.target[i],u)),
   fov:lerp(current.fov,crownCamera.fov,u),phase:'coronation'};
 }
 function sceneGeometry(models,cutIds,step,age,elapsed,previous=null){
  if(!baseField)baseField=createField();
  const m=new Mesh();
  m.data=baseField.data.slice();m.triangles=baseField.triangles;
  for(let i=0;i<10;i++)if(models[i])plant(m,models[i],i,cutIds,step,age,elapsed);
  // Drifting neon data-motes rising through the arena air.
  for(let j=0;j<22;j++){
   const x=(pseudoRand(j+2)*2-1)*16.5,z=(pseudoRand(j+44)*2-1)*13;
   const y=.3+pseudoRand(j+13)*8;
   const p=[x+.6*Math.sin(elapsed*.4+j),y+(elapsed*.45+j)%7,z+.7*Math.cos(elapsed*.3+j)];
   m.gem(...p,.10,pseudoRand(j)>.5?[.57,.91,.69]:[.40,.92,1],2,.32);
  }
  portal(m,step,age,elapsed);
  if(coronation){
   const index=models.findIndex(p=>p.id===coronation.id);
   if(index>=0){
    const [x,,z]=positions[index],height=1.1+Math.min(6,Number(models[index].tier)||0)*.8;
    const t=clamp((elapsed-coronation.started)/2.8),beam=ease(t);
    m.softTube([[x,1.1,z],[x,4+height*beam,z],[x,12+height*beam,z]],
      [.05+beam*.2,.45+beam*.65,.08+beam*.1],[.30,.92,1],2,14);
    for(let k=0;k<12;k++){
     const angle=k*TAU/12+elapsed*.85,rad=1.35+beam*.65;
     m.gem(x+Math.cos(angle)*rad,1.3+height+Math.sin(elapsed*1.3+k)*.22,
       z+Math.sin(angle)*rad,.14+beam*.20,[.98,.36,.80],2,1.6);
    }
    for(let k=0;k<8;k++){
     const angle=k*TAU/8;const px=x+Math.cos(angle)*(1.4+beam*.3),pz=z+Math.sin(angle)*(1.4+beam*.3);
     m.gem(px,1.4+height+beam*(2.2+(k%2)*.9),pz,.25,[.45,.94,1],2,1.8);
    }
    m.ring([x,1.6+height+beam*2,z],1.5+beam*.7,.12+beam*.10,[.58,.93,.74],'xz',2);
   }
  }
  const [hx,hy,hz]=handPosition(models,cutIds,step,age,previous,elapsed);
  const start=m.data.length;
  if(step>=0||age>=PORTAL_LEAD){
   hand(m,[hx,hy,hz],elapsed,step,age,cutIds);
   for(let i=start;i<m.data.length;i+=10){
    m.data[i]=hx+(m.data[i]-hx)*HAND_SCALE;
    m.data[i+1]=hy+(m.data[i+1]-hy)*HAND_SCALE;
    m.data[i+2]=hz+(m.data[i+2]-hz)*HAND_SCALE;
    m.data[i+9]=m.data[i+9]===8?8:7;
   }
  }
  return m;
 }
 function compile(gl,type,source){
  const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);
  if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));
  return s;
 }
 function init(canvas){
  const gl=canvas.getContext('webgl',{alpha:false,antialias:true,powerPreference:'low-power'});
  if(!gl)return null;
  // Painted retro neon textures and light bands; no network texture files or
  // high-end GPU extensions. The giant mech arm and avatars remain actual 3D.
  const vertex=`
precision mediump float;
attribute vec3 a_pos,a_normal,a_color;
attribute float a_kind;
uniform mat4 u_vp;
varying vec3 v_normal,v_color,v_pos;
varying float v_kind;
void main(){
 v_pos=a_pos;v_normal=a_normal;v_color=a_color;v_kind=a_kind;
 if(a_kind>9.0)gl_Position=vec4(a_pos.xy,.99998,1.0);
 else gl_Position=u_vp*vec4(a_pos,1.0);
}`;
  // Kinds: 1 dark structure, 2 emissive neon/portal, 3 grid floor, 5 panel,
  // 6 avatar accent, 7 chrome mech alloy, 8 neon-chrome edges, 9.5 painted sky.
  const fragment=`
precision mediump float;
varying vec3 v_normal,v_color,v_pos;
varying float v_kind;
uniform vec3 u_eye,u_hand,u_crown;
float hash2(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.545);}
float painted(vec2 p){
 vec2 g=floor(p);
 return hash2(g)*.6+hash2(floor(p*.5)+vec2(3.,7.))*.4;
}
float cloudNoise(vec2 p){
 vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
 return mix(mix(hash2(i),hash2(i+vec2(1.,0.)),f.x),
            mix(hash2(i+vec2(0.,1.)),hash2(i+vec2(1.,1.)),f.x),f.y);
}
void main(){
 if(v_kind>9.0){
  // Deep ocean water with filtered shafts and suspended marine snow.
  vec2 uv=v_pos.xy*.5+.5;float t=smoothstep(.02,.98,uv.y);
  vec3 sky=mix(vec3(.003,.027,.068),vec3(.014,.17,.23),t);
  float waves=cloudNoise(uv*vec2(15.,7.))*.60+cloudNoise(uv*vec2(32.,18.))*.40;
  sky+=vec3(.03,.22,.18)*waves*t*.18;
  float shafts=0.;
  for(int k=0;k<7;k++){float x=(float(k)+.23)/7.;
    shafts+=exp(-abs(uv.x-x-uv.y*.17)*39.)*t*t;}
  sky+=vec3(.045,.22,.22)*shafts*.39;
  float snow=step(.997,hash2(floor(uv*vec2(140.,90.))));
  sky+=vec3(.31,.80,.74)*snow*.36;
  gl_FragColor=vec4(floor(sky*63.+.5)/63.,1.);return;
 }
 if(v_kind>6.5&&v_kind<8.5&&v_pos.y>44.0)discard;
 vec3 n=normalize(v_normal);
 vec3 sunDir=normalize(vec3(-.48,.83,.32));
 float nd=max(dot(n,sunDir),0.);
 float light=floor((.48+nd*.56)*7.+.5)/7.;
 vec3 warm=vec3(.79,1.03,.92),cool=vec3(.47,.83,1.04);
 vec3 col=v_color*mix(cool,warm,clamp(nd*.70+.22,0.,1.))*light;
 vec2 uv=v_pos.xz;
 float noise=painted(uv*2.4);
 if(v_kind>.5&&v_kind<1.5){
  // Dark structure panels: matte alloy with faint seam lines and a cool tint.
  uv=abs(n.y)>.60?v_pos.xz:v_pos.xy+v_pos.yz*.35;
  noise=painted(uv*3.5);
  vec2 p=uv*vec2(.43,.73);
  p.x+=floor(p.y)*.5;
  vec2 f=fract(p);
  float seam=(1.-step(.045,f.x))+(1.-step(.065,f.y));
  col*=.60+noise*.30;
  col+=vec3(.06,.22,.28)*min(seam,1.)*.5;
 }else if(v_kind>2.5&&v_kind<3.5){
  // Grid floor: dark tiles cut by glowing cyan seam lines.
  float cell=painted(uv*vec2(7.,11.));
  vec2 g=abs(fract(v_pos.xz*.172)-.5);
  float lineGlow=smoothstep(.46,.5,max(g.x,g.y));
  col*=.42+cell*.22;
  col+=vec3(.08,.42,.52)*lineGlow;
 }else if(v_kind>4.5&&v_kind<5.5){
  float panel=painted(v_pos.xz*5.5+v_pos.y*.8);
  col*=.60+panel*.55;
 }else if(v_kind>5.5&&v_kind<6.5){
  col*=.96+painted(v_pos.xy*13.)*.20;
 }else if(v_kind>6.5&&v_kind<7.5){
  // Chrome mech alloy: brushed metallic sheen with a cool rim and a crisp
  // specular glint, lit cyan-cool rather than warm ivory.
  vec3 eyeDir=normalize(u_eye-v_pos);
  float spec=pow(max(dot(reflect(-sunDir,n),eyeDir),0.),26.);
  float brush=painted(v_pos.xy*1.8+v_pos.z*.37);
  col=v_color*(.46+nd*.56)*vec3(.92,1.0,1.08);
  col*=.84+brush*.26;
  col+=vec3(.34,.70,.86)*spec*.6;
 }else if(v_kind>7.5&&v_kind<8.5){
  // Neon chrome / emissive mech alloy: bright emissive edge with a hot
  // specular highlight, reading as glowing plasma-lit metal rather than rust.
  vec3 eyeDir=normalize(u_eye-v_pos);
  float spec=pow(max(dot(reflect(-sunDir,n),eyeDir),0.),22.);
  float pit=painted(v_pos.xy*5.2+v_pos.z*.6);
  float glow=painted(v_pos.xy*2.1+vec2(4.,9.));
  col=v_color*(.70+nd*.46);
  col=mix(col,col*vec3(.60,1.1,1.2),glow*.55);
  col*=.78+pit*.34;
  col+=vec3(.30,.76,.92)*spec*.75;
 }else if(v_kind>1.5&&v_kind<2.5){
  col=v_color*(1.22+.08*nd);
 }else{
  col*=.84+noise*.24;
 }
 // Grounded contact shadows and the enormous hand's moving penumbra.
 if(v_pos.y<.9&&n.y>.55){
  float dx=abs(v_pos.x/5.8-floor(v_pos.x/5.8+.5))*5.8;
  float dz=min(abs(v_pos.z+5.3),abs(v_pos.z-6.2));
  float contact=1.-smoothstep(1.,3.7,length(vec2(dx,dz)));
  float handShadow=1.-smoothstep(2.,12.,length(v_pos.xz-u_hand.xz));
  handShadow*=1.-clamp((u_hand.y-9.)/80.,0.,1.);
  col*=1.-contact*.24-handShadow*.28;
 }
 if(u_crown.y>.5){
  float glow=1.-smoothstep(1.,10.,length(v_pos.xz-u_crown.xz));
  col+=glow*vec3(.08,.28,.34);
 }
 // Soft neon haze: a deep indigo that lets the distant skyline, data-towers
 // and light-stream vista fade gently into the painted night horizon.
 float fog=smoothstep(35.,145.,length(v_pos-u_eye))*.62;
 col=mix(col,vec3(.10,.08,.22),fog);
 float dither=(hash2(mod(gl_FragCoord.xy,4.))-.5)/85.;
 col=clamp(floor((col+dither)*63.+.5)/63.,0.,1.);
 gl_FragColor=vec4(col,1.);
}`;
  const program=gl.createProgram();
  gl.attachShader(program,compile(gl,gl.VERTEX_SHADER,vertex));gl.attachShader(program,compile(gl,gl.FRAGMENT_SHADER,fragment));gl.linkProgram(program);
  if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));
  const buffer=gl.createBuffer(),attrs=[];
  for(const [name,size,offset] of [['a_pos',3,0],['a_normal',3,12],['a_color',3,24],['a_kind',1,36]])attrs.push([gl.getAttribLocation(program,name),size,offset]);
  return {gl,program,buffer,attrs,uniform:gl.getUniformLocation(program,'u_vp'),eyeUniform:gl.getUniformLocation(program,'u_eye'),handUniform:gl.getUniformLocation(program,'u_hand'),crownUniform:gl.getUniformLocation(program,'u_crown')};
 }
 let active=null;
 let coronation=null;
 function stop(){
  if(!active)return;
  const instance=active;
  instance.stopped=true;
  if(typeof cancelAnimationFrame==='function'&&instance.raf)cancelAnimationFrame(instance.raf);
  instance.canvas.removeEventListener?.('webglcontextlost',instance.onLost);
  instance.canvas.removeEventListener?.('webglcontextrestored',instance.onRestored);
  const {gl,buffer,program}=instance;
  try{if(!gl.isContextLost?.()){gl.deleteBuffer(buffer);gl.deleteProgram(program);}}catch{}
  active=null;
 }
 function mount(canvas,models,cuts,step,labels){
  stop();
  if(!canvas||!canvas.getContext)return false;
  let renderer;
  try{renderer=init(canvas);}catch(e){console.warn('Divine 3D renderer unavailable:',e.message);return false;}
  if(!renderer)return false;
  const instance={...renderer,canvas,models,cuts,step,labels:Array.from(labels||[]),
    start:performance.now(),actionAt:performance.now(),raf:0,stopped:false,
    triangles:0,floats:0,actionFrom:null,cameraFrom:null,lastHand:null,lastCamera:null,phase:'arrival'};
  active=instance;coronation=null;
  instance.onLost=e=>{
   e.preventDefault();
   if(instance.stopped)return;
   if(instance.raf)cancelAnimationFrame(instance.raf);
   instance.raf=0;instance.contextLost=true;
  };
  instance.onRestored=()=>{
   if(instance.stopped||active!==instance)return;
   const saved={models:instance.models,cuts:instance.cuts,step:instance.step,labels:instance.labels};
   mount(canvas,saved.models,saved.cuts,saved.step,saved.labels);
  };
  canvas.addEventListener?.('webglcontextlost',instance.onLost);
  canvas.addEventListener?.('webglcontextrestored',instance.onRestored);
  const frame=()=>{
   if(instance.stopped||instance.contextLost||active!==instance)return;
   const rect=canvas.getBoundingClientRect();
   // Render at a PS2-like cinematic resolution, then let CSS scale the image.
   const retroScale=Math.min(1,960/Math.max(1,rect.width),540/Math.max(1,rect.height));
   const dpr=Math.min(window.devicePixelRatio||1,1.15)*retroScale;
   const w=Math.max(1,Math.floor(rect.width*dpr)),h=Math.max(1,Math.floor(rect.height*dpr));
   if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}
   const {gl,program,buffer,attrs,uniform,eyeUniform,handUniform,crownUniform}=instance;
   gl.viewport(0,0,w,h);gl.clearColor(.03,.03,.11,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
   gl.enable(gl.DEPTH_TEST);gl.disable(gl.CULL_FACE);
   const now=performance.now(),age=(now-(stepAgeStart(instance)))/1000,elapsed=(now-instance.start)/1000;
   const shot=shotCamera(instance.models,instance.cuts,instance.step,age,instance.cameraFrom,elapsed);
   instance.phase=shot.phase;instance.lastCamera=shot;
   const vp=multiply(perspective(shot.fov,w/h,.1,165),lookAt(shot.eye,shot.target));
   const mesh=sceneGeometry(instance.models,instance.cuts,instance.step,age,elapsed,instance.actionFrom);
   instance.lastHand=handPosition(instance.models,instance.cuts,instance.step,age,instance.actionFrom,elapsed);
   instance.triangles=mesh.triangles;instance.floats=mesh.data.length;
   gl.useProgram(program);gl.uniformMatrix4fv(uniform,false,vp);gl.uniform3fv(eyeUniform,shot.eye);
   gl.uniform3fv(handUniform,instance.lastHand);
   const crownIndex=coronation?instance.models.findIndex(p=>p.id===coronation.id):-1;
   gl.uniform3fv(crownUniform,crownIndex<0?[0,0,0]:[positions[crownIndex][0],1,positions[crownIndex][2]]);
   gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(mesh.data),gl.DYNAMIC_DRAW);
   for(const [loc,size,offset] of attrs)if(loc>=0){gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,size,gl.FLOAT,false,40,offset);}
   gl.drawArrays(gl.TRIANGLES,0,mesh.data.length/10);
   // Labels are a stable 5x2 HUD grid. World projection is deliberately not
   // used: at the wide portal camera, projected labels mathematically overlap.
   instance.raf=requestAnimationFrame(frame);
  };
  frame();
  return true;
 }
 function stepAgeStart(instance){return instance.step<0?instance.start:instance.actionAt;}
 function celebrate(id){
  if(!active||active.stopped||!active.models.some(p=>p.id===id))return false;
  coronation={id,started:(performance.now()-active.start)/1000};
  return true;
 }
 function setAction(step,models,cuts){
  if(!active||active.stopped||step<0||step===active.step)return false;
  const from=active.lastHand?.slice()||[0,34,-12],camera=active.lastCamera;
  active.models=models;active.cuts=cuts;active.step=step;
  active.actionAt=performance.now();active.actionFrom=from;
  active.cameraFrom=camera?{eye:camera.eye.slice(),target:camera.target.slice(),fov:camera.fov}:null;
  return true;
 }
 window.Divine3D={
  mount,stop,setAction,celebrate,
  // Nonmutating inspection for regression checks.
  _debug(){return active?{running:!active.stopped,triangles:active.triangles,floats:active.floats,plants:active.models.length,step:active.step,phase:active.phase,canvas:active.canvas,hand:active.lastHand,webgl:true}:null;},
  _geometry:(models,cuts,step,age=0)=>({triangles:sceneGeometry(models,cuts,step,age,0).triangles,positions:positions.map(x=>x.slice()),
   portalOpen:portalOpening(step,age),handScale:HAND_SCALE,portalCenter:PORTAL_CENTER.slice(),
   portalRadius:PORTAL_RADIUS,portalPlane:PORTAL_PLANE,portalAxis:'y',handEmergence:handEmergence(step,age),
   portalLead:PORTAL_LEAD,handPosition:handPosition(models,cuts,step,age),
   shearTipY:handPosition(models,cuts,step,age)[1]-5.55*HAND_SCALE,
   cameraPhase:shotCamera(models,cuts,step,age).phase,
   // Sever + finger/blade/contact coincidence, exposed for a browserless
   // regression check. `contact`/`touch` are the shared blade-meet instant for
   // the active cutting step (computed via the SAME contactTime/isDramatic
   // helpers plant()/hand() use, so they cannot drift); `close` is the single
   // ease that drives BOTH the shear blades and the hand fingers, so
   // fingerClose===bladeClose always and both reach 1 exactly at contact.
   // `severed` tracks the actual first-split instant plant() uses to start the
   // `fall` ramp (contact-.02), not the nominal contact, so the flag and the
   // visible stem split flip together.
   ...(()=>{const dramatic=isDramatic(step,cuts),contact=contactTime(step,cuts),
     close=step<0?0:ease(clamp((age-(contact-(dramatic?1.9:.33)))/(dramatic?1.9:.33)));
    return {contact,touch:contact,severed:step>=0&&age>=contact-.02,fingerClose:close,bladeClose:close};})(),
   gardenTriangles:baseField.triangles,plantStages:7,details:['grid floor','neon barriers','data wells','holo pavilions','neon arches','data spires','pylons','holo signs','megastructure']}),
  // Non-mutating access to the REAL assembled frame mesh (flat Float32 data,
  // 10 floats/vertex: x,y,z,nx,ny,nz,r,g,b,kind) so a browserless test can
  // inspect the actual vertices plant()/hand() emit, not a recomputed summary.
  _sceneMesh:(models,cuts,step,age=0)=>{const m=sceneGeometry(models,cuts,step,age,0);return {data:m.data.slice(),triangles:m.triangles};},
  // Just the hand+shears meshes at a given closure, so a test can read a real
  // finger-tip vertex and prove the fingers curl with `close`. Mirrors the
  // hand-scaling sceneGeometry applies, but builds nothing else.
  _handMesh:(step,age,cuts,position=[0,10,0])=>{
   const m=new Mesh();hand(m,position,0,step,age,cuts);
   for(let i=0;i<m.data.length;i+=10){
    m.data[i]=position[0]+(m.data[i]-position[0])*HAND_SCALE;
    m.data[i+1]=position[1]+(m.data[i+1]-position[1])*HAND_SCALE;
    m.data[i+2]=position[2]+(m.data[i+2]-position[2])*HAND_SCALE;
   }
   return {data:m.data.slice(),triangles:m.triangles};
  },
  // Just one plant's real meshes at a given cutting age, so a test can read
  // the actual stem vertices and prove the sever splits the stem (a rooted
  // stump capped near cutY plus a separated upper length) instead of only a
  // recomputed flag. index selects the plinth; cuts[step] must equal model.id
  // for that plant to be the one being cut.
  _plantMesh:(model,index,cuts,step,age)=>{
   const m=new Mesh();plant(m,model,index,cuts,step,age,0);
   return {data:m.data.slice(),triangles:m.triangles};
  },
  _growthMeshes:()=>Array.from({length:7},(_,tier)=>{
   const sample=new Mesh();
   plant(sample,{id:'seed',tier,priorPruned:false},0,[],-1,0,0);
   return {tier,triangles:sample.triangles};
  })
 };
})();
