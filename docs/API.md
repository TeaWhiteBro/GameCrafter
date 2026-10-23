# API configuration and recovery

The built-in generation adapters target the Level Infinite gateway. The Tripo native public API is a different protocol; substituting only its base URL is not sufficient. Additional providers should implement the stage contract in [PLUGINS.md](PLUGINS.md).

```json
{
  "gateway": {
    "base_url": "https://gateway.ai.levelinfinite.com",
    "planner_model": "YOUR_VISION_CAPABLE_CHAT_MODEL",
    "image_model": "gpt-image-2",
    "key_env": "LEVELINFINITE_API_KEY"
  }
}
```

Set the named environment variable in the process launching Python/Codex. Do not put its value in a spec, CLI argument, Git commit, README or screenshot. `credential_file` remains available for an explicitly configured local Windows DPAPI credential; it is not portable and is excluded from public exports.

| Purpose | Endpoint | Authentication / body |
|---|---|---|
| Design and vision review | `POST /v1/chat/completions` | Bearer; messages, image data URLs, JSON response format |
| Concept generation | `POST /v1/images/generations` | Bearer; `model`, `prompt`, `n:1`, `size` |
| Reference-conditioned concept | `POST /v1/images/edits` | Bearer; multipart fields and binary `image[]` files |
| Text/image/multiview mesh | `POST /v1/3d/tasks` | Bearer; `model: tripo3d/v3.1-20260211`, task type and inputs |
| Task polling | `GET /v1/3d/tasks/{task_id}` | Bearer |
| Upload/download URL | `GET /rdec-lite-llm/v1/storage/presign_upload_url` or `presign_download_url` | `x-api-key`; query `file_name` or `file_id` |
| Binary upload/download | Presigned URL returned by gateway | Binary body for upload; no gateway Authorization forwarded |

Text-to-3D request body:

```json
{"model":"tripo3d/v3.1-20260211","type":"text_to_model","prompt":"A complete unarmed humanoid ..."}
```

An image source is uploaded first when local. Its storage identity becomes the Tripo image input. Four-view sources supply front, left, back and right in that order. The client persists the task ID, polls terminal status, waits for a usable artifact, refreshes expired download URLs and validates the resulting GLB. A progress value of 99% is not completion.

The native image adapter accepts `data[0].b64_json`, `url`, or `file_id`. It saves the response before downloading/decoding so a failed local download can resume without another POST. Standard concept size is 1024×1024. No installed Codex image skill or external image CLI is required.

## Paid-request recovery

POST requests are not blindly retried. `request_state.json` / `remote_task.json` and the SQLite journal preserve submission intent. If a POST response is lost, the stage enters `waiting_external`; recover the original task ID or image response through provider tools. Do not delete the marker merely to make the command proceed. If a source is definitely rejected and a new generation is needed, change the source intent explicitly and retain the failed request/evidence.

GET/download failures have bounded retries. A rerun never promises the same asset from a generative model; hashes establish provenance and same-run resumability only. Public PBR acquisition uses `api.polyhaven.com` and Poly Haven download hosts without the paid gateway key, checks provider MD5 and records SHA-256.

The supported gateway may require account-specific access. Offline tests mock paid endpoints; a passing `doctor` does not establish model entitlement or billing availability.
