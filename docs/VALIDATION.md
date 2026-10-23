# Validation scope

Public source checks cover pinned-dependency installation, offline unit/regression tests, current production DAGs, clean export, source syntax, required files, documentation links and credential/private-path scans. The [release verification report](source_verification.json) records the actual checks for this distribution: a fresh Python 3.12 environment, pinned dependency installation and 473 passing tests from a clean source export. Source/DAG checks and CLI help also pass. Some pinned dependency deprecation warnings remain; they are not test failures.

Offline tests mock paid endpoints and native jobs. They exercise request persistence, schema rejection, scoped invalidation, deformation/geometry helpers, rendering policies, gameplay QA parsing, condition planning and pairing failure controls. They do not prove model entitlement, real MSVC/UE compilation, GPU performance or new clean-machine end-to-end game acceptance.

Full native acceptance requires the declared Windows toolchain and APIs, actual scene/art review, runtime gameplay/cameras, calibration, complete native/export checks and responsive launcher observation. See [REPRODUCING.md](REPRODUCING.md) and [QUALITY_GATES.md](../QUALITY_GATES.md). No production-time improvement is inferred from cache replay or offline tests.
