"""Opt-in PBRES name sidecar; never strip prose or mutate resource packages.

Input resources are already semantically mapped PBRES resources, not raw English.
This is a name preservation adapter, not a PBRES converter or semantic reviewer.
"""
import argparse
import importlib.util
import json
from pathlib import Path
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
SCHEMAS = HERE / 'pbres-name-schemas.json'
_UNSET = object()


def read(path):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON object key: ' + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique_object)


def write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def catalog():
    snapshot = read(SCHEMAS)
    entries = {}
    for entry in snapshot['schemas']:
        parts = unquote(entry['schema']['$id']).split('/')
        entries[(parts[-3], parts[-2])] = entry
    return snapshot, entries


def pointer(parts):
    return '/' + '/'.join(str(x).replace('~', '~0').replace('/', '~1') for x in parts)


def extract(document):
    """Retain every schema-declared original, including absent/empty status.

    Fail on unknown versions and invalid data. Identity includes resource ID and
    exact JSON pointer, so repeated feature names never collapse into a glossary.
    """
    from jsonschema import Draft202012Validator
    snapshot, entries = catalog()
    resources = document.get('resources') if isinstance(document, dict) else None
    if not isinstance(resources, list) or not resources:
        raise ValueError('resources must be a nonempty array')
    rows, ids = [], set()
    for resource in resources:
        if not isinstance(resource, dict):
            raise ValueError('resource must be object')
        rid = resource.get('id')
        if not isinstance(rid, str) or not rid or rid in ids:
            raise ValueError('unique nonempty resource IDs required')
        ids.add(rid)
        template = resource.get('template', {})
        key = (template.get('id'), template.get('version'))
        if key not in entries:
            raise ValueError('unreviewed template/version: ' + repr(key))
        entry = entries[key]
        data = resource.get('data')
        errors = sorted(Draft202012Validator(entry['schema']).iter_errors(data), key=lambda e: str(e.path))
        if errors:
            raise ValueError(rid + ': ' + errors[0].message)

        def walk(value, schema, path):
            if schema.get('type') == 'object':
                properties = schema.get('properties', {})
                for original, translated in [('原文', '名称'), ('特性原文', '特性名称')]:
                    if original in properties and translated in properties:
                        status = 'absent' if original not in value else 'empty' if value[original] == '' else 'present'
                        rows.append({'resource_id': rid, 'template': dict(template),
                                     'name_pointer': pointer(path + [translated]),
                                     'original_pointer': pointer(path + [original]),
                                     'translation': value[translated], 'original': value.get(original),
                                     'status': status, 'schema_url': entry['url']})
                for name, child in properties.items():
                    if name in value:
                        walk(value[name], child, path + [name])
            elif schema.get('type') == 'array':
                for index, child in enumerate(value):
                    walk(child, schema['items'], path + [index])
        walk(data, entry['schema'], ['data'])
    return {'version': 'pbres-name-sidecar-v1', 'schema_commit': snapshot['commit'], 'rows': rows}


def validate(document, sidecar):
    """Exact comparison prevents loss, invention, wrong parent or wrong order."""
    if sidecar != extract(document):
        raise ValueError('name sidecar differs from source resources; preserve exact identities, values and absent/empty status')


def policy(sidecar):
    return ('本次试验将主名称与特性原名保存在独立原名表。中文正文和标题不再附英文原名；'
            '表内原名不是正文英文白名单。不得删去整句、骰式、链接或固定中文机制来过检查。'
            '原文缺失/空值保持原状，不自行猜英文；表只覆盖下列已结构化资源，不证明其他专名已齐全。'
            '不要把这张表拼入译文，也不要把领域等普通字段误造为特性原名字段。\n独立原名表：\n'
            + json.dumps(sidecar, ensure_ascii=False))


def gate_module():
    spec = importlib.util.spec_from_file_location('pbres_delivery_gate', HERE / 'delivery_gate.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def binding_module():
    spec = importlib.util.spec_from_file_location('pbres_name_bindings', HERE / 'pbres_bindings.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_bindings(resources, sidecar, sources, bindings, *, markdown_only=False):
    """Validate reviewed associations and exact selectors; not source semantics."""
    validate(resources, sidecar)
    binding_module().validate_config(resources, sidecar, sources, bindings, markdown_only=markdown_only)


def prepare(cases, resources, out, bindings=_UNSET, *, quantity_scopes=_UNSET):
    """Bind sidecar and policy to both drafting arms and later refinement."""
    sidecar = extract(resources)  # Validate before creating a run.
    if bindings is not _UNSET:
        validate_bindings(resources, sidecar, cases, bindings, markdown_only=True)
    gate = gate_module()
    options = {} if quantity_scopes is _UNSET else {'quantity_scopes': quantity_scopes}
    gate.prepare(cases, out, {'allowed_latin': []}, **options)
    run = Path(out)
    write(run / 'original-name-resources.json', resources)
    write(run / 'original-names.json', sidecar)
    guidance = policy(sidecar)
    if bindings is not _UNSET:
        write(run / 'name-bindings.json', bindings)
        guidance += '\n\n' + binding_module().policy(bindings)
    for name in ['phase1-generate.txt', 'baseline-generate.txt']:
        path = run / name
        path.write_text(guidance + '\n\n' + path.read_text(encoding='utf-8'), encoding='utf-8')
    packet = read(run / 'two-pass-packet.json')
    packet['guidance'] = guidance + '\n\n' + packet['guidance']
    if bindings is not _UNSET:
        packet['name_binding_contract'] = {
            'file': 'name-bindings.json', 'sha256': gate.v.digest((run / 'name-bindings.json').read_bytes())}
    write(run / 'two-pass-packet.json', packet)
    gate.update_manifest(run)
    manifest = read(run / 'manifest.json')
    rules = [Path(__file__), SCHEMAS]
    if bindings is not _UNSET:
        rules.append(HERE / 'pbres_bindings.py')
    for path in rules:
        manifest['rules'][str(path.relative_to(gate.v.ROOT))] = gate.v.digest(path.read_bytes())
    for name in ['original-name-resources.json', 'original-names.json']:
        manifest['prepared_files'][name] = gate.v.digest((run / name).read_bytes())
    manifest['original_name_sidecar'] = 'original-names.json'
    if bindings is not _UNSET:
        manifest['prepared_files']['name-bindings.json'] = gate.v.digest((run / 'name-bindings.json').read_bytes())
        manifest['name_bindings'] = 'name-bindings.json'
    write(run / 'manifest.json', manifest)


def polish(run, development=False):
    gate = gate_module()
    gate.polish(run, development)
    run = Path(run)
    if not development:
        path = run / 'baseline-review.txt'
        guidance = policy(read(run / 'original-names.json'))
        if read(run / 'manifest.json').get('name_bindings'):
            guidance += '\n\n' + binding_module().policy(read(run / 'name-bindings.json'))
        path.write_text(guidance + '\n\n' + path.read_text(encoding='utf-8'), encoding='utf-8')
        hashes = read(run / 'stage-input-hashes.json')
        hashes['baseline-review.txt'] = gate.v.digest(path.read_bytes())
        write(run / 'stage-input-hashes.json', hashes)


def check(resources, sidecar, sources, translations, bindings=_UNSET, *, quantity_scopes=_UNSET):
    validate(resources, sidecar)
    # Sidecar English never grants a prose exemption. Dice/links remain protected.
    gate = gate_module()
    options = {} if quantity_scopes is _UNSET else {'quantity_scopes': quantity_scopes}
    result = gate.scan_records(sources, translations, {'allowed_latin': []}, **options)
    if bindings is not _UNSET:
        module = binding_module()
        try:
            module.validate_config(resources, sidecar, sources, bindings)
        except ValueError as error:
            result['name_binding_check'] = {'release_allowed': False,
                                            'configuration_errors': [str(error)], 'bindings': []}
        else:
            result['name_binding_check'] = module.scan(sidecar, translations, bindings, gate.parse_commonmark_ast)
        result['release_allowed'] = result['release_allowed'] and result['name_binding_check']['release_allowed']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('extract'); p.add_argument('resources'); p.add_argument('out')
    p = sub.add_parser('prepare'); p.add_argument('cases'); p.add_argument('resources'); p.add_argument('out'); p.add_argument('--bindings'); p.add_argument('--quantity-scopes')
    p = sub.add_parser('check'); p.add_argument('resources'); p.add_argument('sidecar'); p.add_argument('sources'); p.add_argument('translations'); p.add_argument('--bindings'); p.add_argument('--quantity-scopes')
    p = sub.add_parser('polish'); p.add_argument('run'); p.add_argument('--development', action='store_true')
    args = parser.parse_args()
    if args.command == 'extract':
        write(args.out, extract(read(args.resources)))
    elif args.command == 'prepare':
        prepare(read(args.cases), read(args.resources), args.out, read(args.bindings) if args.bindings else _UNSET,
                quantity_scopes=read(args.quantity_scopes) if args.quantity_scopes is not None else _UNSET)
    elif args.command == 'polish':
        polish(args.run, args.development)
    else:
        result = check(read(args.resources), read(args.sidecar), read(args.sources), read(args.translations),
                       read(args.bindings) if args.bindings else _UNSET,
                       quantity_scopes=read(args.quantity_scopes) if args.quantity_scopes is not None else _UNSET)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result['release_allowed']:
            raise SystemExit(2)


if __name__ == '__main__':
    main()
