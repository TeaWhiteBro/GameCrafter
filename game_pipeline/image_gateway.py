"""Native Level Infinite image adapter; never repeat an uncertain paid POST."""
import base64
import io
import json
import mimetypes
import uuid
from pathlib import Path
from urllib import request, error
from PIL import Image
from .core import StageError, PendingExternal, read_json, write_json, digest
from .tripo_client import NoRedirect, Client, require_https


def multipart(fields, paths):
    boundary = 'GamePipeline' + uuid.uuid4().hex
    chunks = []
    for key, value in fields.items():
        chunks.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n').encode())
    for index, source in enumerate(paths):
        path = Path(source)
        with Image.open(path) as im:
            im.verify()
        mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        # Generated ASCII names avoid injecting a user's filename into headers.
        header = f'--{boundary}\r\nContent-Disposition: form-data; name="image[]"; filename="reference_{index}{path.suffix.lower()}"\r\nContent-Type: {mime}\r\n\r\n'
        chunks.extend([header.encode(), path.read_bytes(), b'\r\n'])
    chunks.append(f'--{boundary}--\r\n'.encode())
    return b''.join(chunks), 'multipart/form-data; boundary=' + boundary


def image_bytes(response, machine, key):
    items = response.get('data', [])
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        raise StageError('Image response has no data[0] artifact.')
    item = items[0]
    if item.get('b64_json'):
        try:
            return base64.b64decode(item['b64_json'], validate=True)
        except (ValueError, TypeError):
            raise StageError('Image response contains invalid base64.') from None
    url = item.get('url')
    if not url and item.get('file_id'):
        from urllib.parse import urlencode
        data = Client(key, machine['gateway']['base_url']).api(
            '/rdec-lite-llm/v1/storage/presign_download_url?' + urlencode({'file_id':item['file_id']}), storage=True)
        url = data.get('presign_download_url') or data.get('data', {}).get('presign_download_url')
    if not url:
        raise StageError('Image response needs b64_json, url or file_id.')
    require_https(url)
    # Artifact downloads receive no gateway Authorization header.
    try:
        with request.build_opener(NoRedirect()).open(request.Request(url), timeout=120) as stream:
            data = stream.read(64 * 1024 * 1024 + 1)
    except (error.URLError, TimeoutError, OSError):
        raise StageError('Image artifact download failed; the response is saved. Resume without resubmitting.') from None
    if len(data) > 64 * 1024 * 1024:
        raise StageError('Image artifact exceeds 64 MiB.')
    return data


def generate(ctx, cfg):
    from .services import credential
    folder = ctx.directory
    out, state, response_path = folder/'concept.png', folder/'request_state.json', folder/'image_response.json'
    if state.exists():
        previous = read_json(state)
        if previous.get('status') == 'downloaded' and out.is_file() and digest(out) == previous.get('sha256'):
            return out
        if not response_path.exists():
            raise PendingExternal('Image POST outcome is unresolved. Recover its response/artifact; do not submit another paid request automatically.')
    key = credential(ctx.machine)
    if not response_path.exists():
        gateway = ctx.machine['gateway']
        base = gateway['base_url'].rstrip('/')
        require_https(base)
        fields = {'model':gateway.get('image_model','gpt-image-2'), 'prompt':cfg['prompt'], 'size':cfg.get('size','1024x1024')}
        refs = cfg.get('references', [])
        if refs:
            body, content_type = multipart(fields, refs)
            endpoint = '/v1/images/edits'
        else:
            body, content_type = json.dumps({**fields, 'n':1}).encode(), 'application/json'
            endpoint = '/v1/images/generations'
        ctx.spend('image_calls')
        write_json(state, {'status':'submitted_without_remote_id', 'model':fields['model'], 'endpoint':endpoint})
        req = request.Request(base + endpoint, data=body, headers={'Authorization':'Bearer ' + key, 'Content-Type':content_type})
        try:
            with request.build_opener(NoRedirect()).open(req, timeout=600) as stream:
                response = json.load(stream)
        except error.HTTPError as exc:
            raise PendingExternal(f'Image endpoint returned HTTP {exc.code}; inspect provider status before another submission.') from None
        except (error.URLError, TimeoutError, OSError, ValueError):
            raise PendingExternal('Image POST has an uncertain outcome; request marker preserved for recovery.') from None
        write_json(response_path, response)
    raw = image_bytes(read_json(response_path), ctx.machine, key)
    try:
        with Image.open(io.BytesIO(raw)) as im:
            im.load()
            temporary = out.with_suffix('.part')
            im.convert('RGB').save(temporary, format='PNG')
        temporary.replace(out)
    except (OSError, ValueError):
        raise StageError('Image endpoint returned invalid image bytes; saved response retained.') from None
    write_json(state, {'status':'downloaded', 'sha256':digest(out), 'adapter':'native_gateway_v1'})
    return out
