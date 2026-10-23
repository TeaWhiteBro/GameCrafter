"""Render the complete agentic system and offline exact-stage inspector."""
from pathlib import Path
import hashlib,json
from system_figure import render
ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/'docs'
graph=json.loads((DOCS/'workflow_graph.json').read_text(encoding='utf-8'))
stages={n['name']:n for n in graph['nodes']}
drawn=set(stages)
svg=render(graph)
(DOCS/'workflow.svg').write_text(svg+'\n',encoding='utf-8')

template = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Complete system · GameCrafter</title>
<style>
:root{--ink:#152f40;--muted:#526775;--line:#d6e1e7;--green:#087566}*{box-sizing:border-box}body{margin:0;color:var(--ink);background:#f8fafb;font:16px/1.6 "Segoe UI",Arial,sans-serif}a{color:var(--green)}button{font:inherit;cursor:pointer}header{padding:18px 32px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap}header strong{font-size:15px}nav{display:flex;align-items:center;gap:22px;font-size:14px}main{max-width:1840px;margin:auto;padding:0 20px 36px}.figure{margin:0}.figure svg{width:100%;height:auto;display:block}.instructions{font-size:14px;color:var(--muted);margin:0 20px 28px}#stage-details{scroll-margin-top:20px;border-top:1px solid var(--line);padding:30px 20px}.detail-layout{display:grid;grid-template-columns:minmax(260px,.85fr) minmax(0,1.6fr);gap:36px}h2{font-size:29px;margin:0 0 12px;letter-spacing:-.02em}h3{font-size:14px;text-transform:uppercase;letter-spacing:.07em;margin:22px 0 10px}.stage-list{display:flex;gap:7px;flex-wrap:wrap}.stage-list button,.deps button{border:1px solid var(--line);border-radius:5px;background:white;padding:6px 9px;font-size:12px;color:var(--ink)}.stage-list button[aria-pressed=true]{background:var(--green);color:white;border-color:var(--green)}.deps{display:flex;flex-wrap:wrap;gap:8px}.eyebrow{font-size:12px;font-weight:600;letter-spacing:.08em;color:var(--green)}.code{font:13px ui-monospace,Consolas,monospace;color:var(--muted);overflow-wrap:anywhere}#detail p{max-width:840px}#detail .boundary{font-size:14px;color:var(--muted);border-left:3px solid var(--line);padding-left:16px}footer{padding:24px 32px;border-top:1px solid var(--line);font-size:13px;color:var(--muted);display:flex;gap:24px;flex-wrap:wrap}.columns{display:grid;grid-template-columns:1fr 1fr;gap:28px}.notes{margin:0 20px;border-top:1px solid var(--line);padding-top:20px;font-size:14px;color:var(--muted)}.notes strong{color:var(--ink)}.notes p{margin:6px 0 18px}@media(max-width:760px){header{padding:16px 20px}nav{gap:13px;flex-wrap:wrap}main{padding:0 6px 24px}.detail-layout,.columns{grid-template-columns:1fr}.figure{overflow-x:auto}.figure svg{min-width:1080px}.instructions{margin-top:12px}}@media print{header,.instructions,#stage-details,.notes,footer{display:none}main{padding:0;max-width:none}.figure svg{width:100%;min-width:0}@page{size:A3 portrait;margin:5mm}}
</style></head><body>
<header><strong>GAMECRAFTER</strong><nav><a href="agent-collaboration.html">Agent collaboration</a><a href="workflow.svg" target="_blank">Open full-size figure</a><a href="workflow.svg" download>Download SVG</a><a href="#stage-details">Inspect all 26 stages</a><a href="../README.md">README</a></nav></header>
<main><figure class="figure">__SVG__</figure>
<p class="instructions">Select a stage to inspect its adapter and exact dependencies. The main figure compresses evidence fan-in so the production path stays readable.</p>
<section id="stage-details"><div class="detail-layout"><div><span class="eyebrow">SOURCE-DERIVED STAGE INDEX</span><h2>26 named stages</h2><p class="code">Design bootstrap + 25 production DAG nodes</p><div id="stage-list" class="stage-list" aria-label="Select a pipeline stage"></div></div><article id="detail" aria-live="polite"></article></div></section>
<section class="notes columns"><div><strong>Fresh production and scoped recovery</strong><p>New runs generate new case content. Public PBR downloads and installed UE motions are declared dependencies. An explicit provided-mode replacement can keep the surrounding world while affected consumers are revalidated. Same-run resume retains paid task IDs and valid artifacts.</p><strong>Evidence-driven repair</strong><p>The executing agent handles structural diagnoses. Only bounded exposure / sky / fog patches are automatically applied by the CLI. Unchanged rejected images cannot be resampled for approval; three distinct refused preflights require a source-bound repair plan with hashed verification evidence before another capture/review.</p></div><div><strong>Software boundaries</strong><p>Tripo provides source geometry. Blender prepares characters and builds detailed / structural scenes. UE retargets installed motion, implements gameplay and renders the world. Model planning, model review and deterministic validation are separate responsibilities.</p><strong>Current scope</strong><p>Upright humanoids, one melee Boss and connected exploration. The standard profile has six 360-frame sequences at 640 × 360. A source release and its offline tests are distinct from a new clean-machine integrated game acceptance.</p></div></section>
</main><footer><a href="WORKFLOW.md">Full workflow contract</a><a href="workflow_graph.json">Source graph JSON</a><a href="workflow_dag.md">Exact DAG / Mermaid</a><a href="../QUALITY_GATES.md">Quality gates</a><a href="../DATASET.md">Five-channel contract</a><a href="LIMITATIONS.md">Tested limits</a><span>Graph SHA-256: __HASH__</span></footer>
<script>
const stages=__STAGES__;
const byName=new Map(stages.map(s=>[s.name,s]));
const index=document.getElementById('stage-list');
const detail=document.getElementById('detail');
function element(tag, content, className){const el=document.createElement(tag);if(content!==undefined)el.textContent=content;if(className)el.className=className;return el;}
function dependencyGroup(title,names,empty){detail.append(element('h3',title));const row=element('div',undefined,'deps');if(!names.length)row.append(element('span',empty,'code'));for(const name of names){const b=element('button',name);b.type='button';b.onclick=()=>select(name);row.append(b);}detail.append(row);}
function select(name){const s=byName.get(name);if(!s)return;detail.replaceChildren();detail.append(element('span',s.owner.toUpperCase(),'eyebrow'),element('h2',s.title),element('div',s.name+' · '+s.adapter,'code'),element('p',s.detail));
dependencyGroup('Declared upstream dependencies',s.dependencies,s.name==='design'?'Prompt / references and machine configuration':'Run GameSpec / explicit inputs or installed dependencies');
dependencyGroup('Declared downstream consumers',stages.filter(x=>x.dependencies.includes(name)).map(x=>x.name),s.name==='design'?'GameSpec is written before the production DAG is created.':'Final accepted stage output');
if(s.name==='design')detail.append(element('p','Bootstrap dependency is conceptual: all production nodes receive the run specification. It is not a production-DAG edge.','boundary'));
if(s.name==='capture_plan')detail.append(element('p','The adapter identifier starts with agent., but this stage uses deterministic condition planning.','boundary'));
if(s.name==='delivery')detail.append(element('p','The executing agent verifies replay and actual responsive launch after this release gate. These observations are outside the production DAG.','boundary'));
for(const b of index.children)b.setAttribute('aria-pressed',String(b.dataset.name===name));}
for(const s of stages){const b=element('button',s.name);b.type='button';b.dataset.name=s.name;b.onclick=()=>select(s.name);index.append(b);}
document.querySelectorAll('svg [data-stage]').forEach(a=>a.addEventListener('click',()=>select(a.dataset.stage)));
select('asset_demands');
</script></body></html>
'''
html = (template.replace('__SVG__', svg)
        .replace('__STAGES__', json.dumps(graph['nodes'], ensure_ascii=False).replace('</', '<\\/'))
        .replace('__HASH__', hashlib.sha256((DOCS / 'workflow_graph.json').read_bytes()).hexdigest()[:16]))
(DOCS / 'workflow.html').write_text(html, encoding='utf-8')

mermaid = ['# Exact stage dependencies', '',
           'Generated from `workflow_graph.json`. Solid edges are declared production dependencies. Dashed bootstrap edges supply the run specification and are not production-DAG edges.', '',
           '```mermaid', 'flowchart TD']
for stage in graph['nodes']:
    mermaid.append(f'  {stage["name"]}["{stage["title"]}<br/>{stage["adapter"]}"]')
for stage in graph['nodes']:
    if stage['name'] != 'design' and not stage['dependencies']:
        mermaid.append(f'  design -. GameSpec .-> {stage["name"]}')
    for parent in stage['dependencies']:
        mermaid.append(f'  {parent} --> {stage["name"]}')
mermaid += ['```', '', 'Prerequisite machine checks and executing-agent replay / launch observation are outside this DAG.', '']
(DOCS / 'workflow_dag.md').write_text('\n'.join(mermaid), encoding='utf-8')
print(json.dumps({'version':graph['version'], 'diagram_stages':len(drawn),
                  'declared_edges':sum(len(s['dependencies']) for s in stages.values()),
                  'outputs':['docs/workflow.html','docs/workflow.svg','docs/workflow_dag.md']}))
