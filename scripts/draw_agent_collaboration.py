"""Draw the collaboration view; no model, Blender or UE execution is needed."""
from pathlib import Path
from html import escape
import json

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
graph = json.loads((DOCS / 'workflow_graph.json').read_text(encoding='utf-8'))
known = {n['name'] for n in graph['nodes']}

roles = [
    {'id':'coordinator','title':'Executing agent / coordinator','kind':'Execution and recovery',
     'stages':[],
     'reads':['User objective, repository protocol and quality requirements','Current stage state, saved artifacts, failures and repair worklists'],
     'decides':['Sequence work through the stage executor and inspect blockers','Identify the responsible source, geometry, runtime or capture layer','Batch related repairs and resume only invalidated consumers'],
     'writes':['Scoped configuration or implementation revisions','Preserved diagnosis, new evidence and observed launch result'],
     'tools':['CLI / artifact DAG','Blender and UE adapters','Source receipts and run journal'],
     'boundary':'The executing Codex agent and deterministic scheduler cooperate. This is not a separate autonomous manager service inside the Python package.'},
    {'id':'design','title':'Game Design Agent','kind':'Model planning role','stages':['design'],
     'reads':['Prompt and optional scene / character reference images','Supported gameplay, character and scene contracts'],
     'decides':['Visual theme, character identities and playable scope','Combat / exploration intent and compact scene seed'],
     'writes':['game_spec.json: validated GameSpec','Character source prompts and concept-image direction'],
     'tools':['Vision-capable chat model','Schema validation'],
     'boundary':'Design writes bounded data. It does not invent executable commands or arbitrary new game mechanics.'},
    {'id':'asset','title':'Asset Planning Agent','kind':'Model planning role','stages':['asset_demands'],
     'reads':['Game brief and generated / edited concept image','Public material menu, asset budget and production lessons'],
     'decides':['Which distinctive objects need new Tripo generation','Which scalable or traversable structures Blender should author','Object dimensions, intended use and visible acceptance criteria'],
     'writes':['environment_demands.json','Generated-source requests, Blender construction requirements and PBR selections'],
     'tools':['Vision-capable chat model','Tripo and public-PBR requests through adapters'],
     'boundary':'Generated buildings are exterior landmarks. Traversable spaces are authored by Blender. Fresh runs do not require a previous case library.'},
    {'id':'art','title':'Art Direction Agent','kind':'Model planning role','stages':['art_plan'],
     'reads':['Concept image and source-resource demands','Actual available mesh descriptors and observed PBR albedo swatches'],
     'decides':['Shared material language and dominant / accent color hierarchy','Distinct regional functions, asset roles, exclusions and placement guidance'],
     'writes':['art_plan.json','Regional palette / material / composition constraints for world design'],
     'tools':['Vision-capable chat model','Material evidence preparation and resource validation'],
     'boundary':'This decision happens after resource preparation. Names alone cannot establish color, texture quality or suitability.'},
    {'id':'world','title':'World Design Agents','kind':'Layout planning plus conditional exploration refinement','stages':['scene_layout','exploration_plan'],
     'reads':['GameSpec, concept, art plan and available source resources','Supported Blender construction grammar and traversal requirements'],
     'decides':['Grounded architecture, terrain, encounter space and spawns','Branching route topology, destination function, enclosure and planting variation'],
     'writes':['scene_spec.json: metric construction and placement data','exploration_plan.json: itinerary and contract metrics'],
     'tools':['Scene-layout model call','Exploration validators and a conditional corrective planning call'],
     'boundary':'Exploration accepts a valid authored layout without another model call. Actual Blender geometry and UE route traversal still need separate validation.'},
    {'id':'source','title':'Source Review Agent','kind':'Vision role embedded in source preparation','stages':['rig_player','rig_boss','environment_assets'],
     'reads':['Current multi-view character / environment renders','Source dimensions, geometry summaries and requested identity'],
     'decides':['Whether a source is complete and usable for its declared purpose','For unskinned characters: anatomical landmarks and source forward axis'],
     'writes':['Source approval / defect reports','Character landmark and facing evidence consumed by rigging'],
     'tools':['Vision-capable chat model','Blender inspection, preparation and deformation checks'],
     'boundary':'Authored skin is preserved when applicable. Model judgments are followed by geometric, landmark and deformation checks; a model approval is not sufficient by itself.'},
    {'id':'preflight','title':'Visual Preflight Agent','kind':'Model visual-review role','stages':['scene_preflight'],
     'reads':['Current UE overview, full routes and centered destination views','Concept / visual identity and verified diagnostic evidence when needed'],
     'decides':['Whether actual architecture, materials and lighting preserve the requested identity','Which observed defects block progression to the expensive full acceptance suite'],
     'writes':['review.json and repair_worklist.json','Cited blockers, diagnostic requests and optional polish'],
     'tools':['UE evidence capture','Vision-capable chat model and review-memory checks'],
     'boundary':'Uncertain object identity requests grounded diagnostics. Identical rejected evidence retains its decision instead of being resampled for approval.'},
    {'id':'final','title':'Final Review Agent','kind':'Model review plus mandatory executable gates','stages':['review'],
     'reads':['Current normal-run art and character evidence','Gameplay, camera, geometry and five-channel validation results'],
     'decides':['Whether the delivered world is coherent and all required issues are resolved'],
     'writes':['Final review decision and concrete unresolved issues','Release eligibility only when every required gate also passes'],
     'tools':['Vision-capable chat model','Deterministic gate results and exact artifact provenance'],
     'boundary':'The reviewer cannot waive failed gameplay or data checks. Delivery and actual responsive launch are separate subsequent steps.'}
]
for role in roles:
    assert set(role['stages']) <= known, role['id']

P = []
INK, MUTED, LINE = '#173143','#526875','#91a7b4'
TEAL, PURPLE, BLUE, RED, GOLD = '#087769','#7553a4','#315fa9','#b05235','#996114'


def add(value):
    P.append(value)


def box(x,y,w,h,fill='white',stroke='#d3e0e5',r=12):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}"/>')


def txt(x,y,value,size=18,weight=400,color=INK,extra=''):
    add(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{color}" {extra}>{escape(value)}</text>')


def lines(x,y,values,size=18,gap=25,color=MUTED):
    for i,value in enumerate(values):
        txt(x,y+i*gap,value,size,color=color)


def edge(points,color=LINE,both=False,dashed=False):
    d=' '.join(('M' if i==0 else 'L')+str(x)+','+str(y) for i,(x,y) in enumerate(points))
    name={LINE:'normal',TEAL:'design',BLUE:'evidence',RED:'repair',PURPLE:'review'}[color]
    extra=(f' marker-start="url(#{name})"' if both else '')+(' stroke-dasharray="7 6"' if dashed else '')
    add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.1" stroke-linejoin="round" marker-end="url(#{name})"{extra}/>')


def role_start(name):
    item=next(r for r in roles if r['id']==name)
    add(f'<a href="#role-details" data-role="{name}" aria-label="Inspect {escape(item["title"])}"><title>{escape(item["title"]+": "+item["kind"])}</title>')


def role_card(name,x,title,read,decision,write):
    role_start(name)
    box(x,390,330,224)
    box(x,390,5,224,TEAL,TEAL,r=2)
    txt(x+18,417,'SPECIALIST DESIGN ROLE',13,650,TEAL,'letter-spacing="0.6"')
    txt(x+18,447,title,24,650)
    txt(x+18,478,'READ',13,650,TEAL)
    txt(x+18,500,read,16)
    lines(x+18,531,decision,17,24)
    txt(x+18,586,'WRITE  '+write,15,600,TEAL)
    add('</a>')


add('<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1300" viewBox="0 0 1920 1300" role="img" aria-labelledby="title desc">')
add('<title id="title">Agent collaboration and game design — GameCrafter </title>')
add('<desc id="desc">An executing agent coordinates specialist design roles through shared validated artifacts. Design, asset planning, art direction and world design guide image generation, Tripo, Blender and Unreal. Source and visual reviewers inspect current evidence and return structured issues for targeted repair. Executable gameplay, camera and data checks remain separate from model reviewers.</desc>')
add('<defs>')
for name,color in [('normal',LINE),('design',TEAL),('evidence',BLUE),('repair',RED),('review',PURPLE)]:
    add(f'<marker id="{name}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M1,1 L9,5 L1,9 Z" fill="{color}"/></marker>')
add('</defs><style>text{font-family:Inter,"Segoe UI",Arial,sans-serif}a{text-decoration:none}a:hover>rect:first-of-type,a:focus>rect:first-of-type{stroke:#087769;stroke-width:2}</style>')
box(0,0,1920,1300,'#f8fafb','none',r=0)
txt(40,65,'Agent Collaboration & Game Design',44,650)
txt(40,101,'GameCrafter / From design intent to a grounded, playable world',21,color=MUTED)
for x,color,label in [(40,TEAL,'Specialist design'),(340,PURPLE,'Evidence-based review'),(680,BLUE,'Software execution'),(1010,GOLD,'Executable validation'),(1360,RED,'Targeted repair')]:
    box(x,129,13,13,color,'none',r=3)
    txt(x+23,142,label,16,color=MUTED)

box(40,180,315,118)
txt(59,207,'USER INTENT',14,650,TEAL)
txt(59,239,'Prompt + references',25,650)
lines(59,267,['Theme · characters · play intent'],17)

role_start('coordinator')
box(395,180,1095,118,'#183646','#183646')
txt(417,209,'EXECUTING AGENT + WORKFLOW ORCHESTRATOR',15,650,'#8cdbc9','letter-spacing="0.5"')
txt(417,244,'Coordinate design, execution and repair',29,600,'white')
txt(417,276,'Sequence specialist work · route corrections · preserve task IDs / evidence · resume affected stages',19,color='#d3e4eb')
add('</a>')
edge([(355,239),(395,239)],TEAL)

box(1530,180,350,118,'#eaf6f1','#bdddcf')
txt(1549,207,'AFTER ALL REQUIRED GATES',13,650,TEAL)
txt(1549,239,'Playable world',25,650)
txt(1549,268,'2 activities · 3 views · 5 channels',17)

txt(40,345,'01  COOPERATIVE DESIGN',19,650)
txt(1100,345,'Specialists exchange validated artifacts',16,color=MUTED)
edge([(943,298),(943,365),(205,365),(205,390)],TEAL)
edge([(943,365),(578,365),(578,390)],TEAL)
edge([(943,365),(951,365),(951,390)],TEAL)
edge([(943,365),(1324,365),(1324,390)],TEAL)
role_card('design',40,'Game Design Agent','Prompt + reference images',
          ['Define theme, characters and scope','Specify combat / exploration intent'],'GameSpec')
role_card('asset',413,'Asset Planning Agent','GameSpec + concept image',
          ['Choose new Tripo identity assets','Assign scalable construction to Blender'],'Asset demands')
role_card('art',786,'Art Direction Agent','Concept + observed resources',
          ['Set palette and material hierarchy','Give each region a distinct visual role'],'Art plan')
role_card('world',1159,'World Design Agents','Art plan + supported resources',
          ['Compose encounter, routes and places','Layout → exploration refinement'],'Scene spec + itinerary')

txt(40,658,'02  SHARED RUN ARTIFACTS',19,650)
box(40,680,1450,108,'#edf4f1','#c5dcd4')
for x,label,content in [
    (60,'INTENT',['GameSpec · concept · asset demands']),
    (420,'PREPARED RESOURCES',['Meshes · PBR maps · rigs · provenance']),
    (793,'WORLD CONTRACT',['Art plan · metric layout · route itinerary']),
    (1166,'ACCEPTANCE RECORD',['Current evidence · checks · review issues'])]:
    txt(x,709,label,14,650,TEAL)
    lines(x,739,content,16)
txt(60,770,'Named dependencies + JSON / files + source hashes',15,color=MUTED)
txt(962,770,'No prior-case assets required in fresh mode',15,color=MUTED)
for x in (350,723,1096,1469):
    edge([(x,614),(x,680)],TEAL,both=True)

txt(40,842,'03  SOFTWARE EXECUTION',19,650)
tool_specs=[
    (40,'gpt-image-2','Concept generation / reference editing',['Visual design target'], 'Prompt ↔ concept'),
    (413,'Tripo + public PBR','New characters / distinctive objects',['Matched maps + source receipts'],'Requests ↔ sources'),
    (786,'Blender','Cleanup · rigging · world construction',['Detailed scene + structural whitebox'],'Specs ↔ geometry / rigs'),
    (1159,'Unreal Engine','Retargeting · lighting · gameplay',['Combat / exploration · three cameras'],'Import / play contracts')]
for x,title,body,tail,contract in tool_specs:
    edge([(x+310,788),(x+310,874)],BLUE,both=True)
    box(x,874,330,142,'#f0f5fc','#c7d7eb')
    txt(x+18,905,title,24,650,BLUE)
    txt(x+18,935,body,16)
    lines(x+18,961,tail,16)
    txt(x+18,994,contract,14,550,BLUE)

txt(40,1058,'04  CURRENT EVIDENCE + EXECUTABLE CHECKS',19,650)
box(40,1078,1450,88,'#f7f1e6','#e0d1b3')
txt(60,1110,'Source / deformation views · UE routes / destinations · early all-condition coverage · gameplay / camera QA',19,500)
txt(60,1139,'Calibrated five-channel outputs · exact verified export reuse · final pair validation · complete delivery',17,color=MUTED)
edge([(951,1016),(951,1078)],BLUE)
edge([(1324,1016),(1324,1078)],BLUE)

txt(1530,345,'OBSERVE & CRITIQUE',19,650,PURPLE)
box(1530,366,350,814,'#f3eef8','#dacfea')
review_specs=[
    ('source',390,'Source Review Agent',['Check anatomy, fused forms,','silhouette and source orientation'],['Approval / defects + landmarks']),
    ('preflight',614,'Visual Preflight Agent',['Compare actual UE views with','design identity and spatial intent'],['Cited defects / diagnostic requests']),
    ('final',838,'Final Review Agent',['Review current art together with','gameplay, camera and data checks'],['Approval only after required gates'])]
for name,y,title,body,out in review_specs:
    role_start(name)
    box(1548,y,314,176,'white','#dacfea')
    txt(1563,y+27,'VISION / REVIEW ROLE',13,650,PURPLE)
    txt(1563,y+59,title,21,650)
    lines(1563,y+88,body,17,25)
    lines(1563,y+153,out,15,color=PURPLE)
    add('</a>')
edge([(1490,1122),(1510,1122),(1510,477),(1548,477)],BLUE)
edge([(1510,701),(1548,701)],BLUE)
edge([(1510,925),(1548,925)],BLUE)
edge([(1862,477),(1873,477),(1873,1044),(1705,1044),(1705,1064)],RED,dashed=True)
edge([(1862,701),(1873,701)],RED,dashed=True)
edge([(1705,1014),(1705,1064)],RED,dashed=True)

box(1548,1064,314,96,'#fbede7','#dfbdaf')
txt(1563,1094,'STRUCTURED ISSUE → OWNER',13,650,RED)
lines(1563,1120,['Evidence · problem · repair','Verification for the next revision'],16,24)
edge([(1862,1113),(1907,1113),(1907,159),(1240,159),(1240,180)],RED,dashed=True)
edge([(1862,925),(1893,925),(1893,320),(1705,320),(1705,298)],TEAL)

txt(40,1213,'REPAIR LOOP',14,650,RED)
txt(205,1213,'Cited failure → responsible agent / adapter → scoped revision → new evidence → re-review',20,500,RED)
txt(40,1250,'Role collaboration is mediated by run artifacts; the local stage executor is sequential. Review does not replace deterministic validation.',17,color=MUTED)
txt(40,1278,'World design includes conditional exploration refinement. Structural repairs use the executing agent; only bounded lighting patches are CLI-automatic.',16,color=MUTED)
add('</svg>')

svg='\n'.join(P)+'\n'
(DOCS/'agent-collaboration.svg').write_text(svg,encoding='utf-8')

template='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Agent collaboration and game design · GameCrafter</title><style>
:root{--ink:#173143;--muted:#526875;--line:#d3e0e5;--green:#087769}*{box-sizing:border-box}body{margin:0;background:#f8fafb;color:var(--ink);font:16px/1.6 "Segoe UI",Arial,sans-serif}a{color:var(--green)}header{padding:18px 32px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}header strong{font-size:15px}nav{display:flex;gap:22px;font-size:14px;flex-wrap:wrap}main{max-width:1960px;margin:auto;padding:0 20px 40px}.figure{margin:0}.figure svg{display:block;width:100%;height:auto}.caption{margin:12px 20px 24px;font-size:14px;color:var(--muted)}h2{font-size:29px;letter-spacing:-.02em;line-height:1.25;margin:0 0 16px}h3{font-size:13px;letter-spacing:.08em;text-transform:uppercase;margin:22px 0 8px}#role-details{scroll-margin-top:20px;border-top:1px solid var(--line);padding:32px 20px}.inspect{display:grid;grid-template-columns:320px minmax(0,1fr);gap:44px}.role-buttons{display:flex;flex-direction:column;gap:7px}.role-buttons button{border:1px solid var(--line);background:white;border-radius:5px;padding:10px 12px;text-align:left;font:inherit;cursor:pointer;color:var(--ink)}.role-buttons button[aria-pressed=true]{background:var(--green);color:white;border-color:var(--green)}.eyebrow{font-size:12px;color:var(--green);font-weight:650;letter-spacing:.08em}.cols{display:grid;grid-template-columns:1fr 1fr;gap:26px}.list{margin:0;padding-left:20px}.code{font:13px ui-monospace,Consolas,monospace;color:var(--muted);overflow-wrap:anywhere}.boundary{border-left:3px solid var(--line);padding-left:15px;color:var(--muted);font-size:14px}.story{margin:10px 20px 0;border-top:1px solid var(--line);padding-top:28px}.story-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:28px}.story-grid strong{color:var(--green)}.story-grid p{font-size:15px;color:var(--muted)}footer{border-top:1px solid var(--line);padding:24px 32px;display:flex;gap:24px;flex-wrap:wrap;font-size:13px}@media(max-width:900px){.inspect,.cols{grid-template-columns:1fr}.role-buttons{flex-direction:row;flex-wrap:wrap}.story-grid{grid-template-columns:1fr 1fr}}@media(max-width:760px){main{padding:0 5px 25px}.figure{overflow-x:auto}.figure svg{min-width:1120px}.story-grid{grid-template-columns:1fr}}@media print{header,.caption,#role-details,.story,footer{display:none}main{padding:0}.figure svg{min-width:0;width:100%}@page{size:A3 landscape;margin:5mm}}
</style></head><body><header><strong>GAMECRAFTER / AGENT COLLABORATION</strong><nav><a href="agent-collaboration.svg" target="_blank">Full-size figure</a><a href="agent-collaboration.svg" download>Download SVG</a><a href="workflow.html">Complete execution workflow</a><a href="AGENT_COLLABORATION.md">Method notes</a></nav></header>
<main><figure class="figure">__SVG__</figure><p class="caption">Select an agent role to inspect what it reads, decides and writes. The arrows summarize artifact-mediated collaboration; they do not introduce autonomous worker processes or alter the production DAG.</p>
<section id="role-details"><div class="inspect"><div><span class="eyebrow">ROLE CONTRACTS</span><h2>Who designs what?</h2><div id="role-buttons" class="role-buttons"></div></div><article id="detail" aria-live="polite"></article></div></section>
<section class="story"><h2>How one design decision travels through the system</h2><p class="caption" style="margin-left:0">Illustrative handoff for a neon cyberpunk world; these are role responsibilities, not an additional benchmark result.</p><div class="story-grid"><div><strong>1 / Interpret the brief</strong><p>Game design specifies characters, the encounter and exploration intent. Asset planning translates the theme into recognizable objects, construction requirements and surface choices.</p></div><div><strong>2 / Ground the visual plan</strong><p>New sources are generated and reviewed. Art direction examines their actual colors and available materials before assigning palette, regional functions and composition rules.</p></div><div><strong>3 / Make a playable space</strong><p>World design places landmarks, connected streets and a clear encounter space. Blender realizes the metric plan; UE applies animation, rendering, collision and gameplay.</p></div><div><strong>4 / Correct the right cause</strong><p>If current UE views lose the intended neon identity, visual review cites the images and defect. The executing agent diagnoses the responsible asset, material or lighting layer, repairs it and collects new evidence.</p></div></div></section></main>
<footer><a href="workflow.html">All 26 production / bootstrap stages</a><a href="WORKFLOW.md">Workflow contract</a><a href="../AGENT_PROTOCOL.md">Agent repair protocol</a><a href="../QUALITY_GATES.md">Quality gates</a><a href="../README.md">README</a></footer>
<script>
const roles=__ROLES__;
const byId=new Map(roles.map(r=>[r.id,r]));
const buttons=document.getElementById('role-buttons'),detail=document.getElementById('detail');
function el(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
function list(parent,title,items){parent.append(el('h3',title));const ul=el('ul',undefined,'list');for(const item of items)ul.append(el('li',item));parent.append(ul);}
function select(id){const r=byId.get(id);if(!r)return;detail.replaceChildren();detail.append(el('span',r.kind.toUpperCase(),'eyebrow'),el('h2',r.title),el('div',r.stages.length?'Mapped stages: '+r.stages.join(' · '):'Executing-agent responsibilities outside the production DAG','code'));const grid=el('div',undefined,'cols'),left=el('div'),right=el('div');list(left,'Reads',r.reads);list(left,'Design / review decisions',r.decides);list(right,'Writes',r.writes);list(right,'Tools and checks',r.tools);grid.append(left,right);detail.append(grid,el('p',r.boundary,'boundary'));for(const b of buttons.children)b.setAttribute('aria-pressed',String(b.dataset.role===id));}
for(const r of roles){const b=el('button',r.title);b.type='button';b.dataset.role=r.id;b.onclick=()=>select(r.id);buttons.append(b);}
document.querySelectorAll('svg [data-role]').forEach(a=>a.addEventListener('click',()=>select(a.dataset.role)));
select('asset');
</script></body></html>'''
html=template.replace('__SVG__',svg).replace('__ROLES__',json.dumps(roles,ensure_ascii=False).replace('</','<\\/'))
(DOCS/'agent-collaboration.html').write_text(html,encoding='utf-8')
print(json.dumps({'version':graph['version'],'role_contracts':len(roles),'outputs':['docs/agent-collaboration.svg','docs/agent-collaboration.html']}))
