"""Explicit PBRES name locations, not entity recognition or prose coverage.

The caller reviews the unit parents and the target locations. These checks prove
that their configuration is consistent and the named slots match the sidecar;
they cannot prove that the caller attributed a homonym to the correct entity.
"""
import json
import re
import subprocess

VERSION = 'pbres-name-bindings-v1'


def _object(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(label + ' requires exactly: ' + ', '.join(keys))


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + ' must be a nonempty string')


def _pointer_parts(value):
    _text(value, 'field pointer')
    if not value.startswith('/') or re.search(r'~(?![01])', value):
        raise ValueError('invalid RFC 6901 field pointer')
    parts = [x.replace('~1', '/').replace('~0', '~') for x in value[1:].split('/')]
    if len(parts) < 2 or parts[0] != 'name_fields':
        raise ValueError('field pointer must name a value inside /name_fields/')
    return parts


def validate_config(resources, sidecar, sources, config, *, markdown_only=False):
    """Validate declarations/references, never infer source semantics.

    The caller must first validate the sidecar against the source resources.
    No data in these inputs is changed. Invalid declarations raise ValueError.
    """
    _object(config, ('version', 'unit_parents', 'bindings'), 'bindings document')
    if config['version'] != VERSION:
        raise ValueError('unsupported name bindings version')
    if not isinstance(config['unit_parents'], list) or not isinstance(config['bindings'], list):
        raise ValueError('unit_parents and bindings must be arrays')
    if not isinstance(sources, list) or not sources:
        raise ValueError('bindings require nonempty source units')
    unit_ids = set()
    for unit in sources:
        if not isinstance(unit, dict):
            raise ValueError('source unit must be an object')
        _text(unit.get('id'), 'source unit id')
        if not isinstance(unit.get('source'), str) or unit['id'] in unit_ids:
            raise ValueError('invalid source or duplicate source unit id')
        unit_ids.add(unit['id'])
    resource_ids = {resource['id'] for resource in resources['resources']}
    names = {(row['resource_id'], row['name_pointer']): row for row in sidecar['rows']}
    parents = {}
    for parent in config['unit_parents']:
        _object(parent, ('unit_id', 'resource_id'), 'unit parent')
        for key in ('unit_id', 'resource_id'):
            _text(parent[key], key)
        uid, rid = parent['unit_id'], parent['resource_id']
        if uid in parents:
            raise ValueError('duplicate unit parent: ' + uid)
        if uid not in unit_ids or rid not in resource_ids:
            raise ValueError('unit parent references unknown unit/resource')
        parents[uid] = rid
    targets = set()
    for binding in config['bindings']:
        _object(binding, ('unit_id', 'resource_id', 'name_pointer', 'selector'), 'name binding')
        for key in ('unit_id', 'resource_id', 'name_pointer'):
            _text(binding[key], key)
        uid, rid = binding['unit_id'], binding['resource_id']
        if uid not in parents:
            raise ValueError('binding requires a reviewed unit parent: ' + uid)
        if parents[uid] != rid:
            raise ValueError('binding resource differs from unit parent: ' + uid)
        identity = (rid, binding['name_pointer'])
        if identity not in names:
            raise ValueError('binding references unknown resource/name pointer: ' + repr(identity))
        _text(names[identity]['translation'], 'bound sidecar translation')
        selector = binding['selector']
        if not isinstance(selector, dict):
            raise ValueError('selector must be an object')
        kind = selector.get('kind')
        if kind == 'field':
            _object(selector, ('kind', 'pointer'), 'field selector')
            _pointer_parts(selector['pointer'])
            if markdown_only:
                raise ValueError('field selectors are standalone-check only; prepared runs deliver Markdown')
            target = (uid, 'field', selector['pointer'])
        elif isinstance(kind, str) and kind in {'heading', 'feature_label'}:
            keys = ('kind', 'block', 'level') if kind == 'heading' else ('kind', 'block')
            if kind == 'feature_label' and 'suffix' in selector:
                keys += ('suffix',)
                _text(selector['suffix'], 'feature label suffix')
            _object(selector, keys, 'Markdown selector')
            if type(selector['block']) is not int or selector['block'] < 0:
                raise ValueError('selector block must be a zero-based nonnegative integer')
            if kind == 'heading' and (type(selector['level']) is not int or not 1 <= selector['level'] <= 6):
                raise ValueError('heading level must be an integer from 1 to 6')
            # A different asserted kind/level cannot make the same slot distinct.
            target = (uid, 'block', selector['block'])
        else:
            raise ValueError('unsupported selector kind')
        if target in targets:
            raise ValueError('duplicate or conflicting binding target: ' + repr(target))
        targets.add(target)


def _inline_text(inlines):
    """Visible name text only. Code/raw HTML/images are not name evidence."""
    values = []
    for node in inlines:
        kind, content = node['t'], node.get('c')
        if kind == 'Str':
            values.append(content)
        elif kind in {'Space', 'SoftBreak', 'LineBreak'}:
            values.append(' ')
        elif kind in {'Emph', 'Strong'}:
            values.append(_inline_text(content))
        elif kind == 'Link':
            values.append(_inline_text(content[-2]))  # Never destination/title.
        else:
            raise ValueError('unsupported inline node in bound name: ' + kind)
    return ''.join(values)


def _markdown_name(blocks, selector):
    index = selector['block']
    if index >= len(blocks):
        raise ValueError('bound Markdown block is missing')
    block = blocks[index]
    if selector['kind'] == 'heading':
        if block['t'] != 'Header' or block['c'][0] != selector['level']:
            raise ValueError('bound block is not a heading of the declared level')
        return _inline_text(block['c'][-1]).strip()
    if block['t'] != 'Para':
        raise ValueError('feature label requires a top-level paragraph')
    inlines = block['c']
    if not inlines or inlines[0]['t'] not in {'Strong', 'Emph'}:
        raise ValueError('feature label must start with parsed emphasis')
    name = _inline_text(inlines[0]['c']).strip()
    if name.endswith((':', '：')):
        name = name[:-1].strip()
    else:
        # A colon must immediately follow the emphasized name (spaces allowed).
        rest = inlines[1:]
        while rest and rest[0]['t'] == 'Space':
            rest = rest[1:]
        if not rest or rest[0]['t'] != 'Str' or not rest[0]['c'].startswith((':', '：')):
            raise ValueError('feature label requires a colon delimiter')
    if 'suffix' in selector:
        suffix = selector['suffix']
        if not name.endswith(suffix):
            raise ValueError('feature label does not have its declared literal suffix')
        name = name[:-len(suffix)].strip()
    return name


def _field_name(unit, selector):
    value = unit
    for part in _pointer_parts(selector['pointer']):
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and re.fullmatch(r'0|[1-9][0-9]*', part) and int(part) < len(value):
            value = value[int(part)]
        else:
            raise ValueError('bound name field is missing or has an invalid array index')
    if not isinstance(value, str):
        raise ValueError('bound name field must be a plain string')
    return value


def scan(sidecar, translations, config, parse_ast):
    """Check validated declarations. Caller checks record identity separately."""
    names = {(row['resource_id'], row['name_pointer']): row['translation'] for row in sidecar['rows']}
    units = {}
    records = translations.get('units') if isinstance(translations, dict) else None
    for unit in records if isinstance(records, list) else []:
        if isinstance(unit, dict) and isinstance(unit.get('id'), str):
            units.setdefault(unit['id'], []).append(unit)
    parsed, results = {}, []
    for binding in config['bindings']:
        uid = binding['unit_id']
        row = {key: binding[key] for key in ('unit_id', 'resource_id', 'name_pointer', 'selector')}
        row['expected'] = names[(binding['resource_id'], binding['name_pointer'])]
        row['findings'] = []
        matches = units.get(uid, [])
        if len(matches) != 1:
            row['findings'].append({'kind': 'name_binding_identity_error', 'text': 'bound translation unit missing or duplicated'})
        else:
            unit, selector = matches[0], binding['selector']
            try:
                if selector['kind'] == 'field':
                    actual = _field_name(unit, selector)
                else:
                    if not isinstance(unit.get('translation'), str):
                        raise ValueError('bound translation must be Markdown text')
                    if uid not in parsed:
                        parsed[uid] = parse_ast(unit['translation'])['blocks']
                    actual = _markdown_name(parsed[uid], selector)
                row['actual'] = actual
                if actual != row['expected']:
                    row['findings'].append({'kind': 'bound_name_mismatch', 'text': actual})
            except (ValueError, RuntimeError, subprocess.SubprocessError, OSError,
                    KeyError, TypeError, IndexError, AttributeError) as error:
                row['findings'].append({'kind': 'bound_name_selector_failed', 'text': str(error)})
        results.append(row)
    return {'release_allowed': all(not row['findings'] for row in results),
            'configuration_errors': [], 'bindings': results,
            'scope': 'Explicit slots only. Reviewed parent attribution and unbound prose semantics are not verified.'}


def policy(config):
    return ('已人工确认的名称位置绑定如下；只核对这些位置，不要求未绑定正文复述名称。'
            'selector.block 是译文 CommonMark 顶层块的从 0 开始的索引；heading 核对整个标题，'
            'feature_label 核对段首加粗/斜体且带冒号的名称；如声明 suffix，只移除逐字匹配的指定后缀。'
            '不得把名称藏入注释、代码或链接目标。'
            '\n名称绑定：\n' + json.dumps(config, ensure_ascii=False))
