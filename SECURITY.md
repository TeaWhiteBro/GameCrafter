# Credentials and local artifacts

Configure API credentials through the environment variable named by `gateway.key_env`. The CLI does not load `.env` files automatically. Keep credentials out of prompts, machine JSON values, screenshots, logs shared in issues, and Git history.

`machine.local.json`, reference inputs, generated runs, UE builds and credential files are ignored. The source export uses an explicit allowlist and rejects detected credential/private-user-path patterns. Run `python scripts/verify_repository.py` and inspect the staged Git diff before sharing a release.

When reporting a failure, provide the framework/distribution version, failing stage, error category and a sanitized reproduction. Provider task IDs, account responses, signed URLs and private references are not required in public issues. Use your hosting platform's private security reporting facility if enabled for sensitive findings; no public contact address is assumed by this distribution.

Generated text and reference images are treated as data. Only trusted code/configuration selects local tools and adapters. Inspect proposed executing-agent edits before granting unrelated system access. Uncertain paid POSTs retain their recovery markers; do not delete those markers to force resubmission.
