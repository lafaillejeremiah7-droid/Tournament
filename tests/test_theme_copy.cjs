// Deep Sea theme, payout and visible copy regression checks.
// Run: node tests/test_theme_copy.cjs
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const index=read('static/index.html'),app=read('static/app.js');
const city=read('static/city.js'),style=read('static/style.css');
const cityStyle=read('static/city.css'),monuments=read('static/monuments.js');
const stages=['Know Your Depth','Adapt or Sink','The Abyssal Crown'];
assert(index.includes('<title>The Deep Sea - Brawl Hockey</title>'),'page title');
assert(index.includes('THE DESCENT BEGINS'),'opening countdown');
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
// STRENGTHENED garden-vocabulary blocklist. The retheme now covers BOTH index.html and
// app.js, so the user-facing copy in each must never regress to the old round names or the
// garden/flower vocabulary. We scrub ONLY the deliberately-preserved internal class/variable
// hooks (the cutscene art classes .divine-plant/.divine-plants, .garden-verdict, the gv-* art
// classes, the .fc-petal confetti class and its `petals` local) before scanning, so those hooks
// survive but any genuine user-visible garden word anywhere else still fails the suite.
const scrub=src=>src
 .replace(/divine-plants?/g,'')      // cutscene plant art class hooks
 .replace(/garden-verdict/g,'')      // verdict artwork container hook
 .replace(/gv-[\w-]+/g,'')           // every gv-* fallback art class (gv-rose-arch, gv-hedge, gv-gardener, ...)
 .replace(/fc-petal/g,'')            // confetti class hook
 .replace(/\bpetals\b/g,'');         // the local confetti variable name
const bannedCopy=[
 // The old nature round names must never reappear as user copy.
 'Know Thy Nature','Adapt or Wither','The Last Bloom',
 // The Royal Garden flora/pruning vocabulary.
 'garden','bloom','blooming','rose','petal','hedge','flower','wither',
 'will to live','take root','final garden','natural selection',
];
for(const [label,src] of [['index.html',index],['app.js',app]]){
 const scrubbed=scrub(src).toLowerCase();
 for(const word of bannedCopy){
  assert(!scrubbed.includes(word.toLowerCase()),
   label+' must not contain garden/old-round user copy: '+word);
 }
}
// The 'down' verdict caption must not regress to the garden-shears 'SNIP!' vocabulary.
// Match the user-visible caption word (uppercase with the bang) so the preserved
// internal 'gv-snip' art class hook and "audible snip" comments are left alone.
assert(!app.includes('SNIP!'),'verdict caption must not use garden-shears SNIP! wording in app.js');
// Positive deep-sea anchors so the test still fails if the copy is blanked.
for(const neon of ["THE DEEP SEA","REEF AWAKENING","ENTER AN OPEN DIVE CHAMBER","Ocean audio on","Pause ocean","THE ABYSS DECIDES"]){
 assert(index.includes(neon),'missing abyss interface anchor in index.html: '+neon);
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
assert(cityStyle.includes('#walkway-view{')&&cityStyle.includes('position:fixed;inset:0'),'full viewport reef');
assert(!style.includes('.garden-verdict'),'obsolete 2D garden verdict removed');
assert(city.includes('Hydrothermal vents')&&city.includes('coral arches')&&city.includes('stone temple'),'real submerged scene geometry must exist');
assert(style.includes('ABYSS INTERFACE'),'deep-sea CSS theme required');
assert(!app.includes('function playCutscene('),'unused name-based verdict removed');
assert(!city.includes('crownGate('),'unused gate ceremony removed');
assert(!index.includes('ceremony-hud'),'retired ceremony HUD removed');
assert(app.includes("stage==='final'?p.rank!==1:p.status==='CUT'"),'five losing finalists are pruned by the current cut-list function');
assert(app.includes('beginDivineJudgement(stage,cuts)')&&app.includes('strikeDivinePlant(stage,cuts,i)'),'active 3D cutscene owns the elimination sequence');
assert(!app.includes('hookSvg='),'removed obsolete hook artwork');
assert(!style.includes('.av-emperor'),'removed obsolete emperor styles');
assert(!style.includes('.fc-judgment'),'removed abandoned lineup animation');
const braces=text=>(text.match(/{/g)||[]).length-(text.match(/}/g)||[]).length;
assert.equal(braces(style),0,'style.css braces');
assert.equal(braces(cityStyle),0,'city.css braces');
console.log('PASS: Deep Sea copy, code rounds, $30 champion, viewport, scene, lean styles, and no garden/old-round regression.');
