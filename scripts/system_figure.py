"""Vector-only system figure; model roles, software and measured gates are distinct."""
from html import escape


def render(graph):
    known={n['name']:n for n in graph['nodes']};drawn=set();p=[]
    ink='#183044';muted='#455c6b';line='#8da2af'
    colors={'agent':'#087f75','tool':'#4866a3','api':'#8054a4','gate':'#9a6b13','control':'#355166'}
    fills={'agent':'#ecf7f3','tool':'#edf2fb','api':'#f5effa','gate':'#fff7e8','control':'#eff4f7'}
    add=p.append
    def box(x,y,w,h,fill='white',stroke='#d4dfe5',r=14):
        add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}"/>')
    def text(x,y,t,size=19,color=ink,weight=400,extra=''):
        add(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" {extra}>{escape(t)}</text>')
    def lines(x,y,ls,size=19,gap=27,color=muted):
        for i,t in enumerate(ls):text(x,y+i*gap,t,size,color)
    def arrow(points,repair=False):
        d=' '.join(('M' if i==0 else 'L')+f'{x},{y}' for i,(x,y) in enumerate(points))
        extra=' stroke-dasharray="8 6"' if repair else ''
        add(f'<path d="{d}" fill="none" stroke="{"#b35640" if repair else line}" stroke-width="2.5" stroke-linejoin="round" marker-end="url(#{"repair" if repair else "arrow"})"{extra}/>')
    def section(x,y,num,title):
        box(x,y-25,34,34,ink,'none',9);text(x+9,y,num,17,'white',700)
        text(x+46,y,title,23,ink,650)
    def node(name,x,y,w,h,title,owner,body,artifact,kind='tool'):
        if name in known:
            if name in drawn:raise ValueError('Duplicate stage '+name)
            drawn.add(name)
            add(f'<a href="#stage-details" data-stage="{name}"><title>{escape(known[name]["detail"])}</title>')
        else:add('<g>')
        box(x,y,w,h)
        box(x,y,6,h,colors[kind],'none',3)
        text(x+20,y+25,owner,14,colors[kind],700)
        text(x+20,y+58,title,25,ink,650)
        lines(x+20,y+87,body,19,26)
        box(x+17,y+h-31,w-34,24,fills[kind],'none',5)
        text(x+25,y+h-14,artifact,14,colors[kind],500)
        add('</a>' if name in known else '</g>')
    add('<svg xmlns="http://www.w3.org/2000/svg" width="2600" height="2380" viewBox="0 0 2600 2380" role="img" aria-labelledby="title desc">')
    add('<title id="title">GameCrafter — complete agentic workflow</title>')
    add('<desc id="desc">Specialist agents coordinate fresh sources, Blender scene construction, Unreal gameplay, current visual review and synchronized observations. Twenty-five production stages plus design bootstrap. Evidence-bound repair preserves paid work and failed receipts.</desc>')
    add('<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10Z" fill="#8da2af"/></marker><marker id="repair" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10Z" fill="#b35640"/></marker></defs>')
    add('<style>text{font-family:Arial,"Helvetica Neue",sans-serif}a{text-decoration:none}a:hover>rect:first-of-type{stroke:#087f75;stroke-width:2}</style>')
    box(0,0,2600,2380,'#fbfcfe','none',0)
    text(48,86,'GameCrafter',58,ink,750)
    text(500,82,'An Agentic Framework for Scalable Multi-Gameplay Game World Generation',31,ink,500)
    text(48,130,'Reproducible process, fresh content  /  Specialist decisions → explicit artifacts → executable worlds → verified evidence',23,muted)
    for i,(kind,label) in enumerate([('agent','Model planning / review'),('api','Generation / resource API'),('tool','Software adapter'),('gate','Deterministic gate'),('control','Executing agent / scheduler')]):
        x=48+i*492;box(x,157,14,14,colors[kind],'none',4);text(x+24,171,label,18,muted)
    box(48,192,2504,36,'#edf3f6','none',7)
    text(65,216,'Before paid work: machine doctor · local credentials · tool versions · budgets · fresh run directory · installed motion dependencies',19,ink,500)

    node('input',48,258,420,173,'User intent','Input contract',
         ['Prompt + optional reference images','Scene / player / Boss references'], 'New run: no former case assets','control')
    node('design',498,258,550,173,'Game Design Agent','Model role · design bootstrap',
         ['Theme, player / Boss, world scope and constraints','Convert intent to supported metric contracts'], 'GameSpec + gameplay + scene seed','agent')
    node('concept',1078,258,510,173,'Visual target','gpt-image-2 · generation / reference edit',
         ['Create a new concept or edit scene references','Preserve original brief throughout review'], 'Concept image + generation receipt','api')
    node('asset_demands',1618,258,480,173,'Asset Planning Agent','Model role · software allocation',
         ['Distinctive objects → Tripo','Traversable, scalable structure → Blender'], 'Asset demands + dimensions + source gates','agent')
    for x in [468,1048,1588]:arrow([(x,345),(x+30,345)])
    text(50,468,'GameSpec supplies role-specific contracts. Prepared sources constrain later art and world design.',18,muted)

    box(48,490,650,638,'#edf2f9','none',18)
    box(728,490,1370,638,'#eef6f2','none',18)
    section(68,521,'1','Characters, skinning and motion')
    section(750,521,'2','Environment sources and grounded world design')
    arrow([(1858,431),(1858,537),(995,537),(995,550)])
    arrow([(1858,537),(1750,537),(1750,550)])
    node('mesh_player',68,550,294,140,'Player mesh','Tripo · text / image / multiview',
         ['Generate → poll → download'], 'New source + task receipt','api')
    node('mesh_boss',382,550,294,140,'Boss mesh','Tripo · text / image / multiview',
         ['Generate → poll → download'], 'New source + task receipt','api')
    node('rig_player',68,726,294,180,'Player cleanup + rig','Source vision + Blender',
         ['Complete, separated anatomy','Retain skin or bind weights','Semantic bones + 5 test poses'], 'Skinned mesh + deformation QA','tool')
    node('rig_boss',382,726,294,180,'Boss cleanup + rig','Source vision + Blender',
         ['Fused-limb and stretch checks','Verify evaluated deformation','Scale, forward and bone map'], 'Skinned mesh + deformation QA','tool')
    for x in [215,529]:arrow([(x,690),(x,726)])
    node('ue_project',68,960,266,143,'UE project','Unreal adapter',
         ['Runtime + engine motions'], 'Isolated project','tool')
    node('animations',370,960,306,143,'Motion retargeting','Unreal IK retargeter',
         ['14 slots · IK chains · stride'], 'Animations + semantic mapping','tool')
    arrow([(334,1032),(370,1032)])
    arrow([(215,906),(215,932),(522,932),(522,960)])
    arrow([(529,906),(529,932)])
    node('surface_assets',750,550,490,153,'Matched PBR resources','Public surface adapter + validation',
         ['Observed albedo / normal / roughness','License + checksums; download per run'], 'Run-local, matched material bundle','gate')
    node('environment_assets',1270,550,808,153,'Distinctive source generation and inspection','Tripo + Blender preparation + source-review model',
         ['Landmarks, plants and props; prepare scale, UVs and material slots','Inspect actual form and structural proxy; rejected sources stay outside layout'], 'Reviewed sources + descriptors + proxy meshes + preserved task IDs','api')
    arrow([(1240,626),(1270,626)])
    arrow([(1750,703),(1750,725),(950,725),(950,751)])
    node('art_plan',750,751,405,164,'Art Direction Agent','Model role',
         ['Observed resources → palette hierarchy','Regional material roles and exclusions'], 'Art plan + resource intent','agent')
    node('scene_layout',1185,751,420,164,'Scene Layout Agent','Model role + contract validation',
         ['Metric architecture, terrain and spawns','Combat court + supported construction'], 'Scene specification','agent')
    node('exploration_plan',1635,751,443,164,'Exploration Design','Model role / valid-plan reuse + checks',
         ['Branching routes and distinct destinations','Elevation, itinerary and encounter return'], 'Connected exploration plan','agent')
    arrow([(1155,834),(1185,834)]);arrow([(1605,834),(1635,834)])
    node('scene',750,960,1328,143,'Blender world construction + structural validation','Blender adapter · shared spatial contract',
         ['Build detailed world AND low-poly structural companion; grounded paving, terrain, architecture, planting and real openings'],
         'Scene exports + whitebox + shared transforms + portal / floor / terrain / route-clearance reports','tool')
    arrow([(1858,915),(1858,960)])
    arrow([(522,1103),(522,1150),(1098,1150),(1098,1191)])
    arrow([(1420,1103),(1420,1150),(1098,1150)])

    node('ue_assemble',48,1191,2050,150,'Unreal Engine: render, animate and play','3   Integration adapter · C++ runtime + original scene and characters',
         ['PBR / practical lights / Lumen / shadows · collision and grounding · animation-driven combat feedback',
          'Two gameplay modes: Boss combat + exploration   |   Three switchable views: first person · third person · isometric / 2.5D'],
         'Editable UE world + runtime reports + rendering policy shared by play, preflight and capture','tool')
    section(48,1391,'4','Current-world acceptance: inspect early, then measure gameplay')
    node('scene_preflight',48,1415,490,186,'Environmental visual preflight','Visual Review Agent + current UE views',
         ['Overview + routes + paired destination views','Ground / elevated / bounded oblique evidence','Judge geometry, materials, lighting and identity'],
         'Cited blockers / uncertainty / optional polish','agent')
    node('capture_probe',568,1415,490,186,'Early condition coverage','UE capture + deterministic validation',
         ['All 3 views × 2 activities; complete final clips','Player / Boss visibility + active opening + contact','Near plane + five-channel export checks'],
         'Immutable, per-sequence commits for later reuse','gate')
    node('playtest',1088,1415,490,186,'Gameplay regression','Executable UE validation',
         ['Movement, hit response, reset and Boss return','Full-map collision traversal + facing fault test','Valid moving samples + measured play FPS'],
         'Gameplay / traversal / anatomical facing reports','gate')
    node('camera_validation',1608,1415,490,186,'Camera-switch regression','Same-session executable UE validation',
         ['First → third → isometric → third','No teleport; travel, framing, owner visibility','Projection and perspective restoration'],
         '16 switching cases + actual input samples','gate')
    arrow([(1853,1341),(1853,1404),(293,1404),(293,1415)])
    for x in [538,1058,1578]:arrow([(x,1508),(x+30,1508)])

    section(48,1660,'5','Aligned observations: one post-animation camera and time per frame')
    node('capture_plan',48,1685,490,178,'Final condition plan','Deterministic adapter · not an LLM call',
         ['Match requested cameras, activities and duration','Default: 6 × 360 frames at 640 × 360','60 Hz simulation; distinct from measured FPS'],
         'Versioned job contracts + calibration jobs','gate')
    node('calibration',568,1685,490,178,'Independent calibration','UE calibration fixtures + raster checks',
         ['Known foreground / background geometry','Projection, metric depth and semantic visibility','Validate independently of exported matrices'],
         'Per-camera calibration evidence','gate')
    node('dataset',1088,1685,490,178,'Commit paired collections','UE capture / immutable export reuse',
         ['Reuse only exact source / job / exporter hashes','Otherwise capture or re-export in a new revision','No duplicate native work for unchanged jobs'],
         'Native buffers + PNG / NPY / JSON + videos','tool')
    node('pair_validation',1608,1685,490,178,'All-frame pair validation','Deterministic native / export comparison',
         ['Every frame: RGB, depth, IDs, bones, whitebox','Contact / subject visibility / motion from start','Lossless semantic IDs + complete viewing videos'],
         'Pairing report + cross-condition contact sheets','gate')
    arrow([(1853,1601),(1853,1674),(293,1674),(293,1685)])
    for x in [538,1058,1578]:arrow([(x,1774),(x+30,1774)])

    section(48,1923,'6','Final review, delivery and reproducible recovery')
    node('review',48,1947,650,162,'Final Visual Review Agent','Model review + every required acceptance report',
         ['Judge current art, anatomy, gameplay and all requested views','All required criteria pass; retained defects remain explicit'],
         'Accepted review tied to current evidence and source','agent')
    node('delivery',728,1947,660,162,'Release the accepted artifacts','Deterministic release gate',
         ['Exact editable UE project, launcher and provenance manifest','Preserve original case receipts and archived source version'],
         'Playable delivery + paired data + reproducible workflow source','gate')
    node('observation',1418,1947,680,162,'Replay and responsive launch','Executing agent · outside the production DAG',
         ['Verify cached replay and both emitted / public launch entries','Observe actual frames and switching; label offscreen-only checks'],
         'Launch evidence + total wall time + explicit limitations','control')
    arrow([(1853,1863),(1853,1936),(373,1936),(373,1947)])
    arrow([(698,2028),(728,2028)]);arrow([(1388,2028),(1418,2028)])

    box(48,2151,2050,165,'#193c4b','none',16)
    text(70,2185,'Playable world: explore + fight a Boss  /  3 views  /  5 paired output channels',25,'white',650)
    channels=[('RGB','Rendered appearance'),('Depth','Float32 metric depth'),('Skeleton','Animated joints + projection'),('Semantics','Lossless integer class IDs'),('Whitebox','Low-poly world + capsules')]
    for i,(name,detail) in enumerate(channels):
        x=70+i*403;box(x,2207,383,84,'#27505e','none',8)
        text(x+17,2237,name,24,'white',650);text(x+17,2267,detail,18,'#d3e5eb')

    # Persistent collaboration / recovery rail. This is control, not another LLM scheduler.
    box(2160,258,392,1851,'#eef3f7','#d3dfe6',18)
    text(2184,297,'Collaboration & control',25,ink,700)
    text(2184,327,'Executing agent + deterministic DAG',17,muted)
    box(2180,350,352,194,'#244556','none',12)
    text(2198,382,'Shared run artifacts',23,'white',650)
    lines(2198,415,['GameSpec → named stage inputs','JSON results + checked output files','SQLite states + one run writer','Source / tool / implementation hashes','Remote task IDs + cost reservations'],17,25,'#e0ebf0')
    text(2184,585,'Specialists cooperate through',20,ink,600)
    lines(2184,616,['declared artifacts, not hidden context.','Design roles propose bounded data.','Software adapters execute it.','Validators measure invariants.','Reviewers inspect current evidence.'],18,28)
    box(2180,782,352,169,'white','#cbd9e1',10)
    text(2198,816,'Resume without regeneration',22,ink,650)
    lines(2198,847,['Scope changes to affected consumers.','Keep paid submissions and valid files.','Do not reuse prior-case assets.','A cached replay is not a fresh run.'],17,27)
    text(2184,1001,'Evidence-driven repair',25,'#9b452e',700)
    lines(2184,1037,['A failed gate returns to its owner.','Unchanged evidence keeps its refusal.','Time pressure cannot waive a gate.'],18,28)
    repair_steps=[('01','Classify the cause',['Source / rig / geometry / material','Runtime / camera / capture / evidence']),
                  ('02','Resolve uncertainty first',['Capture the exact disputed location.','Keep current source and render hashes.']),
                  ('03','Batch one causal repair',['Inspect diagnose + impact reports.','Fix the owning layer in isolation.']),
                  ('04','Verify the changed revision',['New evidence → affected consumers.','Retain original failures and receipts.'])]
    for i,(number,title,body) in enumerate(repair_steps):
        y=1155+i*145;box(2180,y,352,124,'#fff6ef','#e5cabd',10)
        text(2196,y+30,number,17,'#9b452e',700);text(2231,y+30,title,20,ink,650)
        lines(2196,y+61,body,17,25)
        if i<3:arrow([(2356,y+124),(2356,y+145)],True)
    box(2180,1760,352,187,'#f6e6da','#ddbaa8',10)
    text(2198,1794,' convergence contract',22,'#8b3d29',700)
    lines(2198,1826,['After 3 distinct refused preflights:','bind the next repair plan to the refusal','and current source; cover every issue','with owner, cause, changes and','hashed verification evidence.'],17,25)
    lines(2184,1990,['Stop optional polish after required gates.','Report total user wall time, including','diagnosis, coding and manual intervention.'],17,28)
    arrow([(2098,1508),(2128,1508),(2128,1129),(2160,1129)],True)
    arrow([(2160,2050),(2138,2050),(2138,1150),(2098,1150),(2098,1191)],True)
    text(2160,2166,'Execution boundary',20,ink,650)
    lines(2160,2196,['Local DAG stages execute sequentially.','Independent remote sources may overlap.','This is not concurrent autonomous agents.'],17,27)
    lines(2160,2292,['25 production stages + design bootstrap.','Primary handoffs shown; exact DAG in HTML.'],16,24)
    text(48,2354,'Pairing is within each sequence. Different camera runs need not have identical trajectories. Whitebox shares camera / time but intentionally simplifies silhouettes.',18,muted)
    add('</svg>')
    if drawn!=set(known):raise ValueError('Figure stage coverage mismatch: '+repr(drawn^set(known)))
    return '\n'.join(p)
