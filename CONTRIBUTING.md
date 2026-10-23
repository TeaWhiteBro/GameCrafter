# Contributing

Read AGENTS.md and the stage contracts before changes. Keep content outside runtime logic. Add meaningful negative controls for new validators, declare helper implementation scopes and preserve old task IDs during local preparation changes.

Run `python -m unittest discover -s tests -v` from the repository root. Python-only tests must use temporary fixtures, not our former scenes, machine config, credentials or network. UE/Blender integration checks require the documented installed tools and are reported separately. Changes to capture or gameplay require a complete affected integration acceptance run before advertising them as tested in-game.

Public docs and examples are English. Never commit machine.local.json, .env, credentials, signed URLs, paid responses, generated runs, private screenshots, engine binaries or third-party asset files. `scripts/build_release.py` exports only an allowlisted source tree and rejects obvious secret/private-path patterns. Review its manifest and run the suite from the exported directory.

Describe the problem, final behavior and validation in a change request. Distinguish model/agent judgments from deterministic measurements and executing-agent interventions. Report total case wall time as well as closed-stage timing. Do not rename old results to the current framework version.
