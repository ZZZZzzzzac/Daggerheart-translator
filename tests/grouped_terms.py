import json
from pathlib import Path

RESOURCES = Path(__file__).resolve().parents[1] / 'skills/daggerheart-translation-pipeline/resources'

def default_paths():
    manifest = json.loads((RESOURCES / 'term-groups.json').read_text(encoding='utf-8'))
    return [RESOURCES / g['file'] for g in manifest['groups'] if g['default']]

def default_entries():
    return [e for p in default_paths() for e in json.loads(p.read_text(encoding='utf-8'))]

def write_default_table(path):
    path.write_text(json.dumps(default_entries(), ensure_ascii=False), encoding='utf-8')
    return path
