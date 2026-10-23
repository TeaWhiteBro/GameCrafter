#!/usr/bin/env python3
"""Tripo gateway: submit / resume, poll, upload, and verified atomic download.

Python 3.10+, standard library only. Credentials never enter result manifests.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import http.client
import json
import mimetypes
import os
from pathlib import Path
import re
import struct
import sys
import time
from datetime import datetime, timezone
from urllib import error, parse, request
import zipfile

GATEWAY = 'https://gateway.ai.levelinfinite.com'
MODEL = 'tripo3d/v3.1-20260211'
SUCCESS = {'success', 'succeeded', 'completed', 'complete', 'done'}
FAILED = {'failed', 'failure', 'error', 'cancelled', 'canceled', 'expired', 'banned', 'unknown'}
RETRYABLE = {408, 425, 429, 500, 502, 503, 504}
DOWNLOAD_RETRYABLE = RETRYABLE | {401, 403, 404, 409}
NETWORK_ERRORS = (error.URLError, TimeoutError, ConnectionError, http.client.HTTPException)


class PipelineError(Exception):
    pass


class TemporaryError(PipelineError):
    pass


class RemoteError(PipelineError):
    def __init__(self, status: int):
        self.status = status
        super().__init__(f'HTTP {status}')


def log(message: str):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {message}', flush=True)


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.part')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, path)


def read_key(credential_file: str | None) -> str:
    if not credential_file:
        key = os.environ.get('TRIPO_API_KEY', '').strip()
        if not key:
            raise PipelineError('Set TRIPO_API_KEY or pass --credential-file (Windows DPAPI).')
        return key
    if os.name != 'nt':
        raise PipelineError('DPAPI credentials require the same Windows user and computer.')
    class Blob(ctypes.Structure):
        _fields_ = [('size', ctypes.c_ulong), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    encrypted = bytes.fromhex(Path(credential_file).read_text(encoding='utf-8-sig').strip())
    buffer = (ctypes.c_ubyte * len(encrypted)).from_buffer_copy(encrypted)
    source, target = Blob(len(encrypted), buffer), Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    crypt.CryptUnprotectData.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                                        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(Blob)]
    crypt.CryptUnprotectData.restype = ctypes.c_int
    if not crypt.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise PipelineError('Could not decrypt credential file for this Windows account.')
    try:
        return ctypes.string_at(target.data, target.size).decode('utf-16-le').strip()
    finally:
        kernel = ctypes.WinDLL('kernel32')
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree(ctypes.cast(target.data, ctypes.c_void_p))


class NoRedirect(request.HTTPRedirectHandler):
    """Do not forward gateway credentials through redirects."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, key: str, gateway=GATEWAY, timeout=45):
        self.key, self.gateway, self.timeout = key, gateway.rstrip('/'), timeout
        if parse.urlsplit(self.gateway).scheme != 'https':
            raise PipelineError('Gateway must use HTTPS.')
        self.auth_opener = request.build_opener(NoRedirect())

    def api(self, path: str, payload=None, storage=False, attempts=5):
        headers = {'Accept': 'application/json'}
        headers['x-api-key' if storage else 'Authorization'] = self.key if storage else 'Bearer ' + self.key
        body = None
        if payload is not None:
            body = json.dumps(payload).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        # Never retry POST blindly: an ambiguous timeout could create a second paid task.
        tries = 1 if payload is not None else attempts
        for attempt in range(tries):
            try:
                req = request.Request(self.gateway + path, data=body, headers=headers)
                with self.auth_opener.open(req, timeout=self.timeout) as response:
                    result = json.load(response)
                if not isinstance(result, dict):
                    raise PipelineError('Gateway returned an unexpected JSON structure.')
                if result.get('code', 0) not in (0, '0', None):
                    raise PipelineError(f'Gateway error code {result.get("code")}; inspect the task in the provider console.')
                if result.get('status') in {'error', 'failed', 'failure'}:
                    raise PipelineError('Gateway reported a failed request.')
                return result
            except error.HTTPError as exc:
                if exc.code not in RETRYABLE or attempt + 1 == tries:
                    raise RemoteError(exc.code) from None
                retry_after = exc.headers.get('Retry-After', '')
                delay = min(60, int(retry_after)) if retry_after.isdigit() else min(30, 2 ** (attempt + 1))
                log(f'Temporary gateway HTTP {exc.code}; retrying in {delay}s.')
            except NETWORK_ERRORS:
                if attempt + 1 == tries:
                    if payload is not None:
                        raise PipelineError('Submission response was lost. Do not resubmit automatically; recover the task ID from the provider first.') from None
                    raise TemporaryError('Gateway connection failed after retries; waiting to reconnect.') from None
                delay = min(30, 2 ** (attempt + 1))
                log(f'Temporary gateway connection error; retrying in {delay}s.')
            time.sleep(delay)

    def submit(self, payload):
        result = self.api('/v1/3d/tasks', payload=payload)
        task_id = (result.get('data') or result).get('task_id')
        if not task_id:
            raise PipelineError('Submission did not return task_id.')
        return task_id

    def task(self, task_id):
        result = self.api('/v1/3d/tasks/' + parse.quote(task_id, safe=''))
        data = result.get('data')
        if not isinstance(data, dict):
            raise PipelineError('Task response has no data object.')
        return data

    def download_url(self, file_id):
        query = parse.urlencode({'file_id': file_id})
        response = self.api('/rdec-lite-llm/v1/storage/presign_download_url?' + query, storage=True)
        data = response.get('data') if isinstance(response.get('data'), dict) else response
        url = data.get('presign_download_url')
        if not url:
            raise PipelineError('Storage did not return presign_download_url.')
        return url

    def upload(self, path: Path):
        if not path.is_file():
            raise PipelineError(f'Input file does not exist: {path.name}')
        mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        query = parse.urlencode({'file_name': path.name, 'accelerate': 'false'})
        response = self.api('/rdec-lite-llm/v1/storage/presign_upload_url?' + query, storage=True)
        data = response.get('data') if isinstance(response.get('data'), dict) else response
        url, file_id = data.get('presign_upload_url'), data.get('file_id')
        if not url or not file_id:
            raise PipelineError('Storage did not return file_id and presign_upload_url.')
        require_https(url)
        # A signed URL is its own authorization; never attach the gateway API key.
        for attempt in range(4):
            try:
                with path.open('rb') as stream:
                    req = request.Request(url, data=stream, method='PUT', headers={
                        'Content-Type': mime, 'Content-Length': str(path.stat().st_size)})
                    with request.build_opener(NoRedirect()).open(req, timeout=self.timeout) as result:
                        result.read()
                log(f'Uploaded {path.name} ({path.stat().st_size:,} bytes).')
                return {'file_id': file_id, 'mime_type': mime, 'name': path.name}
            except error.HTTPError as exc:
                if exc.code not in RETRYABLE or attempt == 3:
                    raise RemoteError(exc.code) from None
            except NETWORK_ERRORS:
                if attempt == 3:
                    raise PipelineError('Upload connection failed after retries.') from None
            time.sleep(min(20, 2 ** (attempt + 1)))


def require_https(url: str):
    if parse.urlsplit(url).scheme != 'https':
        raise PipelineError('Artifact URL must use HTTPS.')


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def validate(path: Path, extension=None):
    """Validate downloaded bytes, GLB structure/resources, and archive integrity."""
    size = path.stat().st_size
    if size == 0:
        raise PipelineError('Downloaded file is empty.')
    ext = (extension or path.suffix).lower()
    with path.open('rb') as stream:
        head = stream.read(512)
    if head.lstrip().lower().startswith((b'<!doctype html', b'<html', b'<?xml', b'<error')):
        raise PipelineError('Download returned an error page instead of an artifact.')
    info = {'bytes': size, 'sha256': sha256(path), 'format': ext.lstrip('.')}
    if ext == '.glb':
        with path.open('rb') as stream:
            header = stream.read(12)
            if len(header) != 12:
                raise PipelineError('GLB header is truncated.')
            magic, version, declared = struct.unpack('<4sII', header)
            if magic != b'glTF' or version != 2 or declared != size:
                raise PipelineError('GLB header/length check failed.')
            chunks = []
            document = None
            binary_length = 0
            while stream.tell() < size:
                chunk_header = stream.read(8)
                if len(chunk_header) != 8:
                    raise PipelineError('GLB chunk header is truncated.')
                length, kind = struct.unpack('<II', chunk_header)
                if length % 4 or stream.tell() + length > size:
                    raise PipelineError('GLB chunk length is invalid.')
                chunks.append(kind)
                if kind == 0x4E4F534A:
                    document = json.loads(stream.read(length).decode('utf-8').rstrip(' \x00'))
                else:
                    if kind == 0x004E4942:
                        binary_length += length
                    stream.seek(length, 1)
        if not document or chunks[0] != 0x4E4F534A:
            raise PipelineError('GLB has no leading JSON chunk.')
        buffers = document.get('buffers', [])
        for buffer in buffers:
            if not buffer.get('uri') and buffer.get('byteLength', 0) > binary_length:
                raise PipelineError('GLB binary buffer is truncated.')
        for view in document.get('bufferViews', []):
            index = view.get('buffer', 0)
            if index >= len(buffers) or view.get('byteOffset', 0) + view['byteLength'] > buffers[index]['byteLength']:
                raise PipelineError('GLB buffer view is outside its buffer.')
        external = [item['uri'] for item in buffers + document.get('images', [])
                    if item.get('uri') and not item['uri'].startswith('data:')]
        if external:
            raise PipelineError('GLB references external resources; source bundle is required.')
        primitives = [p for mesh in document.get('meshes', []) for p in mesh.get('primitives', [])]
        accessors = document.get('accessors', [])
        triangles = 0
        for primitive in primitives:
            if primitive.get('mode', 4) == 4:
                index = primitive.get('indices', primitive.get('attributes', {}).get('POSITION'))
                if index is not None:
                    triangles += accessors[index]['count'] // 3
        info.update({'glb_version': version, 'meshes': len(document.get('meshes', [])),
                     'primitives': len(primitives), 'triangles': triangles,
                     'materials': len(document.get('materials', [])),
                     'embedded_images': len(document.get('images', [])),
                     'skins': len(document.get('skins', [])), 'animations': len(document.get('animations', [])),
                     'self_contained': not external})
    elif ext == '.zip':
        with zipfile.ZipFile(path) as archive:
            bad = archive.testzip()
            if bad:
                raise PipelineError('ZIP integrity check failed.')
            info['archive_files'] = len(archive.infolist())
    elif ext == '.png' and not head.startswith(b'\x89PNG\r\n\x1a\n'):
        raise PipelineError('PNG signature check failed.')
    elif ext in {'.jpg', '.jpeg'} and not head.startswith(b'\xff\xd8\xff'):
        raise PipelineError('JPEG signature check failed.')
    elif ext == '.webp' and not (head[:4] == b'RIFF' and head[8:12] == b'WEBP'):
        raise PipelineError('WebP signature check failed.')
    return info


def download(url: str, path: Path, timeout=60):
    require_https(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.part')
    try:
        # New request, no Authorization / x-api-key headers on the storage host.
        with request.urlopen(request.Request(url, headers={'Accept': '*/*'}), timeout=timeout) as response:
            length = response.headers.get('Content-Length')
            with temporary.open('wb') as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
        if length and temporary.stat().st_size != int(length):
            raise PipelineError('Download length does not match Content-Length.')
        # This provider can label a PNG as .webp (including Content-Type).
        # Prefer actual image bytes over URL extensions and HTTP metadata.
        if path.suffix.lower() in {'.webp', '.png', '.jpg', '.jpeg'}:
            with temporary.open('rb') as stream:
                signature = stream.read(16)
            real_extension = None
            if signature.startswith(b'\x89PNG\r\n\x1a\n'):
                real_extension = '.png'
            elif signature.startswith(b'\xff\xd8\xff'):
                real_extension = '.jpeg'
            elif signature[:4] == b'RIFF' and signature[8:12] == b'WEBP':
                real_extension = '.webp'
            if real_extension and path.suffix.lower() != real_extension:
                log(f'Image format detected from bytes: {path.name} -> {path.stem + real_extension}')
                path = path.with_suffix(real_extension)
        info = validate(temporary, path.suffix)
        os.replace(temporary, path)
        info['file'] = path.name
        return info
    except error.HTTPError as exc:
        raise RemoteError(exc.code) from None
    except NETWORK_ERRORS:
        raise PipelineError('Download connection interrupted; retrying requires a fresh URL.') from None
    finally:
        temporary.unlink(missing_ok=True)


def artifacts(data):
    """Use the gateway's observed result/output schemas and deduplicate aliases."""
    found = []
    seen = set()
    def walk(value, label):
        if isinstance(value, dict):
            if isinstance(value.get('url'), str) or value.get('file_id'):
                add(label, value.get('url'), value.get('file_id'), value.get('type'))
                return
            for name, child in value.items():
                if name == 'file_id':
                    add(label, None, child, value.get('type'))
                else:
                    walk(child, name)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f'{label}_{index + 1}')
        elif isinstance(value, str) and value.startswith('https://'):
            add(label, value, None, None)
    def add(label, url, file_id, format_hint):
        identity = ('file', file_id) if file_id else ('url', url.split('?', 1)[0])
        if identity in seen:
            return
        seen.add(identity)
        clean_label = re.sub(r'[^A-Za-z0-9_-]+', '_', label).removesuffix('_url') or 'artifact'
        extension = Path(parse.urlsplit(url).path).suffix.lower() if url else ''
        if not re.fullmatch(r'\.[a-z0-9]{1,8}', extension):
            extension = '.' + format_hint.lower() if isinstance(format_hint, str) and re.fullmatch(r'[A-Za-z0-9]{1,8}', format_hint) else '.bin'
        # Stable readable names; multiple same-labelled artifacts get an index.
        filename = clean_label + extension
        if any(a['filename'] == filename for a in found):
            filename = f'{clean_label}_{len(found) + 1}{extension}'
        found.append({'label': clean_label, 'url': url, 'file_id': file_id,
                      'filename': filename, 'identity': identity})
    walk(data.get('result', {}), 'result')
    walk(data.get('output', {}), 'output')
    return found


def wait_and_download(client, task_id, output: Path, interval=15, max_wait=3600):
    output.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + max_wait if max_wait else float('inf')
    done = {}
    log(f'Task {task_id}; results: {output.resolve()}')
    while time.monotonic() < deadline:
        try:
            data = client.task(task_id)
        except RemoteError as exc:
            if exc.status not in RETRYABLE:
                raise
            log(f'Gateway HTTP {exc.status}; continuing to monitor the saved task.')
            time.sleep(min(interval, max(0, deadline - time.monotonic())))
            continue
        except TemporaryError as exc:
            log(str(exc))
            time.sleep(min(interval, max(0, deadline - time.monotonic())))
            continue
        status = str(data.get('status', '')).lower()
        state = {'task_id': task_id, 'gateway': client.gateway, 'status': status,
                 'progress': data.get('progress'), 'updated_at': datetime.now(timezone.utc).isoformat()}
        atomic_json(output / 'task_state.json', state)
        log(f'Generation {status or "unspecified"}; progress={data.get("progress", "?")}%')
        if status in FAILED:
            raise PipelineError(f'Task ended with status {status}; task ID: {task_id}')
        if status in SUCCESS:
            entries = artifacts(data)
            if not entries:
                log('Generation finished; waiting for output file references.')
            else:
                pending = False
                for item in entries:
                    identity = item['identity']
                    if identity in done:
                        continue
                    try:
                        url = client.download_url(item['file_id']) if item['file_id'] else item['url']
                        info = download(url, output / item['filename'], client.timeout)
                        done[identity] = {'role': item['label'], **info}
                        log(f'Validated {info["file"]}: {info["bytes"]:,} bytes.')
                    except RemoteError as exc:
                        if exc.status not in DOWNLOAD_RETRYABLE:
                            raise
                        pending = True
                        log(f'Artifact not ready (HTTP {exc.status}); refreshing references on next poll.')
                    except PipelineError as exc:
                        pending = True
                        log(str(exc))
                if not pending and all(item['identity'] in done for item in entries):
                    current_files = [done[item['identity']] for item in entries]
                    if not any(f['format'] in {'glb', 'gltf', 'fbx', 'obj', 'usdz', 'zip', 'blend'} for f in current_files):
                        log('Preview is ready; waiting for a model artifact.')
                    else:
                        state['updated_at'] = datetime.now(timezone.utc).isoformat()
                        manifest = {**state, 'status': 'downloaded', 'model': MODEL,
                                    'input': {k: v for k, v in data.get('input', {}).items()
                                              if k in {'prompt', 'pbr', 'texture', 'export_uv', 'model_version', 'geometry_quality', 'texture_alignment'}},
                                    'created_at': data.get('created_at'), 'completed_at': data.get('completed_at'),
                                    'credits_consumed': data.get('credits_consumed'), 'files': current_files}
                        atomic_json(output / 'manifest.json', manifest)
                        atomic_json(output / 'task_state.json', {**state, 'status': 'downloaded'})
                        log('Complete: generation, download, file validation, and manifest saved.')
                        return manifest
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(interval, remaining))
    raise PipelineError(f'Monitoring time limit reached; task continues on the server. Resume task {task_id}.')


def resolve_image(client, source: str):
    if source.startswith('https://'):
        mime = mimetypes.guess_type(parse.urlsplit(source).path)[0]
        if not mime or not mime.startswith('image/'):
            raise PipelineError('Image URL must end in a recognized image extension; alternatively pass a local image.')
        return {'type': mime, 'url': source}
    path = Path(source)
    mime = mimetypes.guess_type(path.name)[0]
    if not mime or not mime.startswith('image/'):
        raise PipelineError('Input must be a PNG/JPEG/WebP or another recognized image.')
    uploaded = client.upload(path)
    return {'type': uploaded['mime_type'], 'url': client.download_url(uploaded['file_id'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gateway', default=GATEWAY)
    parser.add_argument('--credential-file', help='Optional Windows DPAPI file; otherwise reads TRIPO_API_KEY')
    parser.add_argument('--timeout', type=int, default=45, help='Per-request timeout, seconds')
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ['text', 'resume', 'image', 'multiview']:
        cmd = sub.add_parser(name)
        cmd.add_argument('--out', type=Path, required=True)
        cmd.add_argument('--interval', type=int, default=15)
        cmd.add_argument('--max-wait', type=int, default=0, help='Maximum monitoring time, seconds; 0 waits until success/failure (default)')
        if name == 'text':
            cmd.add_argument('--prompt', required=True)
        elif name == 'resume':
            cmd.add_argument('--task-id', required=True)
        elif name == 'image':
            cmd.add_argument('--image', required=True, help='Local image path or HTTPS URL')
        else:
            for view in ['front', 'left', 'back', 'right']:
                cmd.add_argument('--' + view, required=True, help='Local image path or HTTPS URL')
    upload_parser = sub.add_parser('upload')
    upload_parser.add_argument('--file', type=Path, required=True)
    upload_parser.add_argument('--receipt', type=Path, required=True)
    dl_parser = sub.add_parser('download-file')
    dl_parser.add_argument('--file-id', required=True)
    dl_parser.add_argument('--out-file', type=Path, required=True)
    dl_parser.add_argument('--max-wait', type=int, default=600)
    dl_parser.add_argument('--interval', type=int, default=15)
    args = parser.parse_args()
    if args.timeout <= 0 or getattr(args, 'interval', 1) <= 0 or getattr(args, 'max_wait', 1) < 0:
        parser.error('Timeout and interval must be positive; maximum wait must be zero or positive.')
    client = Client(read_key(args.credential_file), args.gateway, args.timeout)
    if args.command == 'upload':
        receipt = client.upload(args.file)
        atomic_json(args.receipt, {**receipt, 'sha256': sha256(args.file)})
        log(f'Upload receipt saved: {args.receipt}')
        return
    if args.command == 'download-file':
        deadline = time.monotonic() + args.max_wait if args.max_wait else float('inf')
        while time.monotonic() < deadline:
            try:
                info = download(client.download_url(args.file_id), args.out_file, client.timeout)
                atomic_json(args.out_file.with_name(args.out_file.name + '.manifest.json'), info)
                log(f'Downloaded and validated {args.out_file.name} ({info["bytes"]:,} bytes).')
                return
            except RemoteError as exc:
                if exc.status not in DOWNLOAD_RETRYABLE:
                    raise
                log(f'Storage HTTP {exc.status}; waiting for file availability.')
            except PipelineError as exc:
                log(str(exc))
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(args.interval, remaining))
        raise PipelineError('File is not downloadable within the monitoring time limit.')
    if args.command == 'resume':
        task_id = args.task_id
    else:
        state_path = args.out / 'task_state.json'
        if state_path.exists():
            previous = json.loads(state_path.read_text(encoding='utf-8'))
            if previous.get('task_id') or previous.get('status') == 'submitting':
                raise PipelineError('This output directory already has a submitted or uncertain task. Use resume or choose a new output directory.')
        payload = {'model': MODEL}
        if args.command == 'text':
            payload.update(type='text_to_model', prompt=args.prompt)
        elif args.command == 'image':
            payload.update(type='image', image=resolve_image(client, args.image))
        else:
            payload.update(type='multiview_to_model', files=[resolve_image(client, getattr(args, view))
                                                           for view in ['front', 'left', 'back', 'right']])
        # Verify local destination before submitting a potentially paid task.
        atomic_json(args.out / 'task_state.json', {'status': 'submitting', 'model': MODEL})
        task_id = client.submit(payload)
        log(f'Submitted {payload["type"]}; task ID: {task_id}')
        atomic_json(args.out / 'task_state.json', {'task_id': task_id, 'status': 'submitted', 'gateway': client.gateway})
    wait_and_download(client, task_id, args.out, args.interval, args.max_wait)


if __name__ == '__main__':
    # Keep Chinese prompts/paths usable when launched through Windows pipes.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    try:
        main()
    except KeyboardInterrupt:
        log('Stopped locally. The server task continues; resume using the saved task ID.')
        sys.exit(130)
    except (PipelineError, OSError, ValueError, KeyError, IndexError) as exc:
        # Do not print request objects, response bodies, credentials, or signed URLs.
        if isinstance(exc, PipelineError):
            log('ERROR: ' + str(exc))
        else:
            log(f'ERROR: {type(exc).__name__}; check local paths or response/file structure.')
        sys.exit(1)
