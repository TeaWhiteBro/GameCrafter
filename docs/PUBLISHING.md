# Publishing GameCrafter source

Publish the complete allowlisted framework, not a machine workspace or a generated UE project. No remote repository URL or author identity is assumed by these instructions.

## Local release checks

```powershell
& .\.venv\Scripts\python.exe -B -m unittest discover -s tests
& .\.venv\Scripts\python.exe -B scripts\verify_repository.py
& .\.venv\Scripts\python.exe scripts\draw_workflow.py
& .\.venv\Scripts\python.exe scripts\draw_agent_collaboration.py
& .\.venv\Scripts\python.exe scripts\build_release.py --out ..\GameCrafter-source --zip ..\GameCrafter-source.zip
```

Choose a new export directory/archive; the exporter refuses overwrites. Test the exported tree independently and verify `SOURCE_MANIFEST.json` hashes. Keep the repository name GameCrafter and describe current capabilities only. The generated diagrams are derived from executable contracts.

Never include `machine.local.json`, `.env`, DPAPI credentials, keys, raw API responses, signed URLs, local journals, generated case assets, UE caches/binaries or vendor animation content. Review the actual staged changes with `git diff --cached` before pushing. A regex source check is a useful guard, not proof against every possible secret format. Read [SECURITY.md](../SECURITY.md) and [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

## Create the public repository

Create an empty repository named GameCrafter on your hosting account. In the checked clean source directory, use your own Git author configuration and actual remote URL:

```powershell
git init -b main
git add .
git diff --cached --stat
git diff --cached
git commit -m "Release GameCrafter framework"
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

Replace the placeholder URL; these commands publish externally only when executed deliberately by the maintainer. Do not invent author lists, paper identifiers, affiliations or project-page links. Add them only when confirmed. Keep license and third-party notices with the release.

The GitHub workflow runs Python 3.12 offline checks and checks the clean export. It does not install Unreal Engine or charge generation APIs. Native full-production acceptance needs the declared Windows toolchain, authorized API access and an executing agent; document it separately from source CI.
