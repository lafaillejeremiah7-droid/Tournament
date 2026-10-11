// Royal Garden theme, payout and visible copy regression checks.
// Run: node tests/test_theme_copy.cjs
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const index=read('static/index.html'),app=read('static/app.js');
const city=read('static/city.js'),style=read('static/style.css');
const cityStyle=read('static/city.css'),monuments=read('static/monuments.js');
const stages=['Know Thy Nature','Adapt or Wither','The Last Bloom'];
assert(index.includes('<title>The Neon Grid - Brawl Hockey</title>'),'page title');
assert(index.includes('THE GRID BOOTS'),'opening countdown');
for(const name of stages){
 assert(index.includes(name),'home missing '+name);
 assert(app.includes(name),'game navigation missing '+name);
}
for(const old of ['Face Your Weakness','Abandon Your Comfort','Prove Your Resolve','COLISEUM DIVISION']){
 assert(!index.includes(old)&&!app.includes(old),'obsolete displayed label: '+old);
}
// The Royal Garden chrome has been replaced entirely: no garden/rose/pavilion wording
// survives in the index.html scaffold (fails if the reskin regresses to garden copy or goes blank).
// Compare case-insensitively so lowercase leftovers (e.g. "royal garden"/"pavilions") are caught too.
const indexLower=index.toLowerCase();
for(const garden of ['ROYAL GARDEN','ROYAL HEDGE MAZE','ROSE BLOOM','ROSES WAITING','Pause garden','Garden sound on','BACK TO GARDEN','THE GARDENER','PAVILION','PRUNED']){
 assert(!indexLower.includes(garden.toLowerCase()),'garden chrome must be reskinned out of index.html: '+garden);
}
// The 'down' verdict caption must not regress to the garden-shears 'SNIP!' vocabulary.
// Match the user-visible caption word (uppercase with the bang) so the preserved
// internal 'gv-snip' art class hook and "audible snip" comments are left alone.
assert(!app.includes('SNIP!'),'verdict caption must not use garden-shears SNIP! wording in app.js');
// Positive cyberpunk anchors so the test still fails if the copy is blanked.
for(const neon of ["THE NEON GRID","GRID CHARGE","JACK INTO AN OPEN NODE","Grid audio on","Pause grid","THE SYSTEM'S VERDICT"]){
 assert(index.includes(neon),'missing neon chrome anchor in index.html: '+neon);
}
assert(index.includes('ONE $30 CHAMPION'),'single champion on home screen');
assert(app.includes('Winner-take-all prize'),'settings show fixed prize');
assert(!app.includes("inp('settings.prizes."),'payouts must not be editable');
assert(app.includes("prizes:[30,0,0]"),'reset-all keeps $30/0/0');
assert(monuments.includes('const slots=[1].map(place=>'),'only one trophy pedestal');
assert(monuments.includes('$30'),'only $30 champion');
for(const geometry of ["part('skyline'","part('charge-nodes'","part('nodes'","part('holo-signs'","part('megastructure'","part('neon-arches'"]){
 assert(city.includes(geometry),'missing 3D scenery: '+geometry);
}
assert(cityStyle.includes('#walkway-view{')&&cityStyle.includes('position:fixed;inset:0'),'full viewport garden');
assert(style.includes('.garden-verdict'),'garden verdict artwork');
for(const token of ['gv-shears','gv-compost','gv-pruning-count','gv-snip','gv-pruned','gv-fling']){
 assert(style.includes(token),'missing pruning visual: '+token);
}
assert(app.includes("stage==='final'?p.rank!==1:p.status==='CUT'"),'five losing finalists are pruned by the current cut-list function');
assert(app.includes('runReducedFinalPruning(cuts)'),'reduced-motion finalists also get individual scenes');
assert(!app.includes('hookSvg='),'removed obsolete hook artwork');
assert(!style.includes('.av-emperor'),'removed obsolete emperor styles');
assert(!style.includes('.fc-judgment'),'removed abandoned lineup animation');
const braces=text=>(text.match(/{/g)||[]).length-(text.match(/}/g)||[]).length;
assert.equal(braces(style),0,'style.css braces');
assert.equal(braces(cityStyle),0,'city.css braces');
console.log('PASS: Royal Garden copy, nature rounds, $30 champion, viewport, scene, lean styles.');
