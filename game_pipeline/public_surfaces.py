"""Acquire matched public PBR maps into the current run, without a private library."""
import hashlib
import json
import time
from pathlib import Path
from urllib import request, error, parse
from PIL import Image
from .core import ROOT, StageError, read_json, write_json, digest


def menu():
    return read_json(ROOT/'config/public_surfaces.json')['materials']


def validate_selection(plan, maximum=6):
    ids = plan.get('surface_materials')
    if not isinstance(ids, list) or not 2 <= len(ids) <= maximum:
        raise StageError('Choose 2 to max_materials distinct public surface_materials.')
    if any(not isinstance(name, str) or name not in menu() for name in ids):
        raise StageError('surface_materials must be an array of available public material ID strings, not objects.')
    if len(set(ids)) != len(ids):
        raise StageError('Choose distinct public surface_materials.')
    return ids


def fetch(url, maximum=128*1024*1024):
    parsed = parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in ('api.polyhaven.com', 'dl.polyhaven.org', 'dl.polyhaven.com'):
        raise StageError('Public PBR download must use a Poly Haven HTTPS endpoint.')
    for attempt in range(4):
        try:
            req = request.Request(url, headers={'User-Agent':'AgenticGamePipeline/1.0 public-PBR'})
            with request.urlopen(req, timeout=90) as stream:
                data = stream.read(maximum + 1)
            if len(data) > maximum:
                raise StageError('Public PBR response exceeds the download limit.')
            return data
        except error.HTTPError as exc:
            if exc.code not in (408,429,500,502,503,504) or attempt == 3:
                raise StageError(f'Public PBR HTTP {exc.code}; resume this stage after resolving source availability.') from None
        except (error.URLError, TimeoutError, OSError):
            if attempt == 3:
                raise StageError('Public PBR download failed; completed files remain resumable.') from None
        time.sleep(2**attempt)


def acquire(ctx, cfg):
    plan = read_json(ctx.inputs['asset_demands']['plan'])
    ids = validate_selection(plan, cfg.get('max_materials',6))
    resolution = cfg.get('resolution','1k')
    if resolution not in ('1k','2k'):
        raise StageError('Public surfaces support 1k or 2k maps.')
    bundle = {'schema_version':1, 'mesh_library':{}, 'texture_library':{}, 'asset_descriptors':{}}
    files = []; entries = []
    for name in ids:
        folder = ctx.directory/name
        folder.mkdir(exist_ok=True)
        metadata = folder/'provider.json'
        if not metadata.exists():
            write_json(metadata, json.loads(fetch('https://api.polyhaven.com/files/'+name, 8*1024*1024)))
        data = read_json(metadata); maps = {}; sources = {}
        for remote, channel in [('Diffuse','base'),('nor_dx','normal'),('Rough','roughness'),('Metal','metallic'),('AO','ao'),('Displacement','height')]:
            choices = data.get(remote,{}).get(resolution,{})
            ext = 'png' if 'png' in choices and channel != 'base' else 'jpg' if 'jpg' in choices else None
            if not ext:
                continue
            item = choices[ext]; target = folder/(channel+'.'+ext)
            expected = item.get('md5','').lower()
            if len(expected) != 32:
                raise StageError('Public PBR metadata is missing a provider checksum.')
            if not target.exists() or hashlib.md5(target.read_bytes()).hexdigest() != expected:
                raw = fetch(item['url'])
                if hashlib.md5(raw).hexdigest() != expected:
                    raise StageError('Public PBR download checksum mismatch: '+name+'/'+channel)
                partial = target.with_suffix(target.suffix+'.part'); partial.write_bytes(raw); partial.replace(target)
            with Image.open(target) as image:
                image.verify()
            maps[channel] = str(target.resolve())
            sources[channel] = {'url':item['url'], 'md5':expected, 'sha256':digest(target)}
            files.append(target)
        if not {'base','normal','roughness'} <= maps.keys():
            raise StageError('Public PBR source lacks a matched albedo/normal/roughness set: '+name)
        info = menu()[name]
        bundle['texture_library'][name] = maps
        bundle['asset_descriptors'][name] = {**info, 'kind':'textures', 'source':'https://polyhaven.com/a/'+name,
            'license':'CC0-1.0', 'normal_convention':'DirectX', 'channels':sorted(maps)}
        entries.append({'id':name, 'source':'https://polyhaven.com/a/'+name, 'license':'CC0-1.0', 'channels':sources})
        files.append(metadata)
    receipt = ctx.directory/'provenance.json'
    write_json(receipt, {'policy':'Public sources downloaded into this run; no previous case assets.', 'entries':entries})
    out = ctx.directory/'resources.json'; write_json(out,bundle)
    return {'resources':str(out), '_files':[out,receipt]+files}
