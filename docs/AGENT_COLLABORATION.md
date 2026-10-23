# Agent collaboration and game design

The [collaboration figure](agent-collaboration.html) presents the method around decisions, handoffs and feedback. The [execution figure](workflow.html) presents the same implementation around its 26 named stages. They are complementary views of one system.

The central idea is **artifact-mediated design and evidence-driven revision**. Specialist model roles turn intent into progressively grounded specifications. Software adapters realize those specifications. Model reviewers inspect current results; executable validators check measurable properties. The executing agent routes a failure back to its responsible layer, preserves useful work and resumes affected consumers.

## Design is progressively grounded

| Role | Reads | Main decision | Writes |
|---|---|---|---|
| Game Design Agent | Prompt, optional references, supported contracts | Theme, characters, playable scope and scene seed | GameSpec |
| Asset Planning Agent | Brief, concept, public resource menu, budget | New distinctive Tripo objects versus scalable / traversable Blender construction | Asset demands, generation requests, dimensions and acceptance criteria |
| Art Direction Agent | Concept, prepared resource descriptors, actual albedo evidence | Palette hierarchy, regional functions, asset/material roles and exclusions | Art plan |
| World Design Agents | GameSpec, concept, art plan, supported resources | Metric architecture, encounter space, branching routes and differentiated destinations | Scene spec and exploration itinerary |

These roles do not design in isolation. Asset planning constrains what must be generated and what can be constructed. Art direction sees the resources that actually arrived, rather than assuming a prompt or filename guarantees their appearance. World design translates the agreed material and spatial intent into the supported Blender grammar. Exploration validation can accept a valid layout directly or request corrective planning.

Character source inspection is also a design handoff: current views and dimensions inform anatomical landmarks and forward direction before unskinned sources are bound. Existing skin is preserved when applicable. Landmark and deformation checks guard the model's estimates.

## Collaboration uses explicit artifacts

The shared run workspace contains named JSON results, images, source geometry, materials, tests and review evidence. Each stage receives its declared inputs and commits checked output files with hashes. The figure's shared artifact layer summarizes those handoffs; it is not an unimplemented general-purpose blackboard or an unrestricted peer-to-peer conversation bus.

The executing Codex agent cooperates with the deterministic stage scheduler. It follows the protocol, diagnoses failed work, changes the responsible configuration or implementation and resumes the run. Source IDs, paid task receipts and failed evidence are retained. This protects successful source generation from unnecessary repetition during local repairs.

## Review closes the design loop

Source review checks the actual generated characters and environment objects before downstream use. UE visual preflight checks current overview, route and destination views before expensive complete capture. Final review combines current art and anatomy evidence with the required gameplay, camera and multimodal checks.

A review issue names its severity, category, current images, concrete problem, proposed repair and verification. An unresolved interpretation requests additional grounded evidence. Repeating unchanged rejected images cannot create a new approval. The executing agent uses the issue to choose the repair owner; it does not rebuild every successful stage by default.

For example, fused character geometry returns to source preparation / rigging and deformation validation. A missing visual identity returns to asset allocation, art decisions or actual UE materials / lighting according to the evidence. A shifted depth or semantic frame returns to camera / capture / export implementation. These are illustrative routing examples, not promises that a model detects every defect automatically.

## Tools execute; validators measure

- gpt-image-2 generates or edits the visual target.
- Tripo generates source geometry; public PBR providers supply matched material maps.
- Blender prepares and rigs characters, builds detailed scenes and structural whitebox companions, and validates exported geometry.
- UE retargets installed motions, integrates rendering and gameplay, implements camera modes and emits synchronized observations.
- Deterministic checks validate anatomy bounds, deformation, traversal, facing, contact, camera behavior, calibration and native/export agreement.

Camera validation and capture planning are not additional independent LLM agents. In particular, the `agent.capture_plan` adapter name denotes deterministic condition planning. The local executor is sequential; independent environment source requests may overlap remotely. Model roles can share one configured model endpoint while using distinct prompts, inputs and output contracts.

Structural repair remains executing-agent work. The CLI automatically applies only bounded supported exposure / sky / fog patches. A review cannot waive a failed hard gate, and release still requires replay plus observed responsive launch.

Regenerate this figure and role inspector with `python scripts/draw_agent_collaboration.py`. No paid requests or game builds are performed. See [AGENT_PROTOCOL.md](../AGENT_PROTOCOL.md) for recovery rules and [WORKFLOW.md](WORKFLOW.md) for the exact implementation boundaries.
