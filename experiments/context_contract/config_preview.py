"""Optional offline configuration preview and UNCONFIRMED drafts, stdout only.

Explicit IDs and choices are proposals, never reviewed attribution or alignment.
This helper does not run a delivery check, compare quantities, or export live
configuration. Its envelopes cannot be supplied as either approved config.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
PREVIEW_VERSION = 'pbres-config-preview-v1'
DRAFT_VERSION = 'pbres-config-draft-v1'
NOTE = ('UNCONFIRMED: explicit choices do not approve parent resource attribution, '
        'source/translation alignment, homonym identity, or meaning. Review the '
        'original context independently. This is not a live bindings or quantity '
        'configuration; there is no approve or export-to-live command.')


def _module(name):
    spec = importlib.util.spec_from_file_location('preview_' + name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


names = _module('pbres_names')
bindings = names.binding_module()
gate = names.gate_module()
quantities = gate.quantity_module()


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode('utf-8')).hexdigest()


def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON object key: ' + key)
            result[key] = value
        return result

    def invalid(value):
        raise ValueError('non-finite JSON number: ' + value)

    return json.loads(Path(path).read_text(encoding='utf-8'),
                      object_pairs_hook=unique, parse_constant=invalid)


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + ' must be a nonempty string')


def _records(records, side, unit_id):
    if not isinstance(records, list) or not records:
        raise ValueError(side + ' records must be a nonempty array')
    found, ids = None, set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(side + ' record must be an object')
        _text(record.get('id'), side + ' unit ID')
        if record['id'] in ids or not isinstance(record.get(side), str):
            raise ValueError('duplicate unit ID or invalid ' + side + ' text')
        ids.add(record['id'])
        if record['id'] == unit_id:
            found = (index, record)
    if found is None:
        raise ValueError('selected unit ID missing from ' + side + ': ' + unit_id)
    return found


def _side_preview(record, index, side):
    raw = record[side]
    ast = gate.parse_commonmark_ast(raw)
    blocks = ast['blocks']
    result = {'record_pointer': ('/' if side == 'source' else '/units/') + str(index),
              'raw_text': raw, 'ast_sha256': _digest(ast),
              'ast_api_version': ast.get('pandoc-api-version'), 'blocks': []}
    for block_index, node in enumerate(blocks):
        block = {'block': block_index, 'ast_path': '/blocks/' + str(block_index),
                 'node_type': node['t'], 'ast': copy.deepcopy(node)}
        # Reuse the existing extractors only. Do not tokenize/compare quantities.
        try:
            block['quantity_candidate'] = {
                'selector': {'kind': 'block', 'block': block_index},
                'text': quantities._block(node)}
        except ValueError as error:
            block['quantity_unavailable'] = str(error)
        if node['t'] == 'Header':
            selector = {'kind': 'heading', 'block': block_index, 'level': node['c'][0]}
        else:
            selector = {'kind': 'feature_label', 'block': block_index}
        try:
            block['name_candidate'] = {
                'selector': selector, 'text': bindings._markdown_name(blocks, selector)}
        except ValueError as error:
            block['name_unavailable'] = str(error)
        result['blocks'].append(block)
    return result


def preview(resources, sources, translations, *, resource_id, unit_id):
    """List actual independent slots for supplied IDs; no cross-side pairing."""
    _text(resource_id, 'resource ID')
    _text(unit_id, 'unit ID')
    sidecar = names.extract(resources)
    resource = next((r for r in resources['resources'] if r['id'] == resource_id), None)
    if resource is None:
        raise ValueError('unknown resource ID: ' + resource_id)
    source_index, source = _records(sources, 'source', unit_id)
    target_index, target = _records(translations.get('units') if isinstance(translations, dict)
                                     else None, 'translation', unit_id)
    return {
        'format': PREVIEW_VERSION, 'approval_status': 'unconfirmed',
        'semantic_verified': False, 'note': NOTE,
        'selection': {'resource_id': resource_id, 'unit_id': unit_id},
        'review_status': {'parent_attribution': 'unconfirmed', 'alignment': 'unconfirmed',
                          'homonym_identity': 'unconfirmed'},
        'resource_template': copy.deepcopy(resource['template']),
        'input_sha256': {key: _digest(value) for key, value in
                         [('resources', resources), ('sources', sources), ('translations', translations)]},
        'hash_basis': 'SHA-256 of UTF-8 JSON, sorted keys, compact separators, ensure_ascii=False; not file bytes or a signature',
        'implementation_sha256': {filename: hashlib.sha256((HERE / filename).read_bytes()).hexdigest()
                                  for filename in ['config_preview.py', 'pbres_names.py', 'pbres_bindings.py',
                                                   'quantity_risks.py', 'delivery_gate.py', 'pbres-name-schemas.json']},
        'parser': gate.parser_identity(),
        'name_choices': [dict(copy.deepcopy(row), choice=index) for index, row in enumerate(
            row for row in sidecar['rows'] if row['resource_id'] == resource_id)],
        'sides': {'source': _side_preview(source, source_index, 'source'),
                  'translation': _side_preview(target, target_index, 'translation')},
    }


def _pick(values, index, label):
    if type(index) is not int or not 0 <= index < len(values):
        raise ValueError(label + ' must be an existing zero-based integer index')
    return values[index]


def draft(resources, sources, translations, saved_preview, *, name_selections=(), quantity_selections=()):
    """Bind explicit choices to a fresh snapshot, always leaving approval pending.

    Name choices are (name choice, translation block[, literal suffix]); quantity
    choices are (source block, translation block). No unit/field selectors, semantic
    checks, live schemas, or automatic name/alignment suggestions are generated.
    """
    if not isinstance(saved_preview, dict) or saved_preview.get('format') != PREVIEW_VERSION:
        raise ValueError('a saved unconfirmed preview is required')
    selection = saved_preview.get('selection')
    if not isinstance(selection, dict) or set(selection) != {'resource_id', 'unit_id'}:
        raise ValueError('invalid preview selection')
    current = preview(resources, sources, translations, **selection)
    # Serialized equality also distinguishes booleans from integers in a modified snapshot.
    if _json(current) != _json(saved_preview):
        raise ValueError('stale or modified preview; regenerate it and review all choices again')
    if not isinstance(name_selections, (tuple, list)) or not isinstance(quantity_selections, (tuple, list)):
        raise ValueError('explicit selections must be arrays')
    if not name_selections and not quantity_selections:
        raise ValueError('draft requires at least one explicit choice')
    result = {'format': DRAFT_VERSION, 'approval_status': 'unconfirmed',
              'semantic_verified': False, 'note': NOTE,
              'preview_sha256': _digest(current), 'preview': current,
              'proposed_parent': dict(selection, approval_status='unconfirmed'),
              'proposed_name_bindings': [], 'proposed_quantity_scopes': []}
    target_blocks = current['sides']['translation']['blocks']
    source_blocks = current['sides']['source']['blocks']
    name_targets, quantity_endpoints = set(), set()
    for choice in name_selections:
        if not isinstance(choice, (tuple, list)) or len(choice) not in {2, 3}:
            raise ValueError('name choice requires name index, translation block, and optional literal suffix')
        name_index, block_index = choice[:2]
        name = _pick(current['name_choices'], name_index, 'name choice')
        block = _pick(target_blocks, block_index, 'translation block')
        if 'name_candidate' not in block:
            raise ValueError('selected translation block has no supported name slot')
        if block_index in name_targets:
            raise ValueError('duplicate or conflicting name target')
        name_targets.add(block_index)
        _text(name['translation'], 'chosen resource name')
        selector = dict(block['name_candidate']['selector'])
        observed = block['name_candidate']['text']
        if len(choice) == 3:
            suffix = choice[2]
            _text(suffix, 'literal feature suffix')
            if selector['kind'] != 'feature_label' or not observed.endswith(suffix):
                raise ValueError('literal suffix requires a feature label ending in that suffix')
            selector['suffix'] = suffix
            observed = observed[:-len(suffix)].strip()
        result['proposed_name_bindings'].append({
            **selection, 'name_pointer': name['name_pointer'], 'selector': selector,
            'expected_name': name['translation'], 'observed_name': observed,
            'approval_status': 'unconfirmed'})
    for index, choice in enumerate(quantity_selections):
        if not isinstance(choice, (tuple, list)) or len(choice) != 2:
            raise ValueError('quantity choice requires independent source and translation block indices')
        source_index, target_index = choice
        source_block = _pick(source_blocks, source_index, 'source block')
        target_block = _pick(target_blocks, target_index, 'translation block')
        for side, block in [('source', source_block), ('translation', target_block)]:
            if 'quantity_candidate' not in block:
                raise ValueError('selected ' + side + ' block is unsupported for quantity scopes')
            endpoint = (side, block['block'])
            if endpoint in quantity_endpoints:
                raise ValueError('duplicate quantity endpoint')
            quantity_endpoints.add(endpoint)
        result['proposed_quantity_scopes'].append({
            'id': 'draft-quantity-' + str(index + 1), 'unit_id': selection['unit_id'],
            'source': copy.deepcopy(source_block['quantity_candidate']),
            'translation': copy.deepcopy(target_block['quantity_candidate']),
            'approval_status': 'unconfirmed'})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('preview', help='print unconfirmed names and actual AST blocks')
    d = commands.add_parser('draft', help='print an unconfirmed draft from explicit choices')
    for command in (p, d):
        command.add_argument('resources')
        command.add_argument('sources')
        command.add_argument('translations')
    p.add_argument('--resource-id', required=True)
    p.add_argument('--unit-id', required=True)
    d.add_argument('preview')
    d.add_argument('--name', nargs=2, type=int, action='append', default=[], metavar=('NAME', 'TARGET_BLOCK'))
    d.add_argument('--name-with-suffix', nargs=3, action='append', default=[],
                   metavar=('NAME', 'TARGET_BLOCK', 'LITERAL_SUFFIX'))
    d.add_argument('--quantity', nargs=2, type=int, action='append', default=[], metavar=('SOURCE_BLOCK', 'TARGET_BLOCK'))
    args = parser.parse_args()
    try:
        inputs = [read(getattr(args, key)) for key in ('resources', 'sources', 'translations')]
        if args.command == 'preview':
            result = preview(*inputs, resource_id=args.resource_id, unit_id=args.unit_id)
        else:
            choices = args.name + [(int(n), int(b), suffix) for n, b, suffix in args.name_with_suffix]
            result = draft(*inputs, read(args.preview), name_selections=choices, quantity_selections=args.quantity)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        parser.exit(2, 'config preview: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
