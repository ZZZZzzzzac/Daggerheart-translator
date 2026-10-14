#!/usr/bin/env python3
"""Read-only snapshot, local freshness diff and audit bookkeeping validation."""
import argparse
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def capture(get, project, file_ids, page_size=500):
    """get(path) is injected for offline tests; production uses paratranz-ops."""
    require(file_ids and len(set(file_ids)) == len(file_ids), 'Select unique file IDs')
    started = now()
    before = get('/files')
    require(isinstance(before, list), 'Unexpected file list format')
    selected = [f for f in before if f['id'] in file_ids]
    require(len(selected) == len(file_ids), 'Selected file missing')
    records, pages, seen = [], [], set()
    for file in selected:
        expected = file['total']
        require(type(expected) is int and expected >= 0, 'Invalid file total')
        page, fetched, advertised_pages = 1, 0, None
        while True:
            body = get('/strings?' + urlencode({'file': file['id'], 'page': page,
                                                'pageSize': page_size}))
            require(isinstance(body, dict), 'Unexpected page format')
            require(body.get('page') == page, 'Page number mismatch')
            require(body.get('rowCount') == expected, 'Row count changed')
            count = body.get('pageCount')
            require(type(count) is int and count >= 0, 'Missing page count')
            require(count > 0 or expected == 0, 'Nonempty file has no pages')
            if advertised_pages is None:
                advertised_pages = count
            require(count == advertised_pages, 'Page count changed')
            rows = body.get('results')
            require(isinstance(rows, list), 'Missing page results')
            require(rows or expected == 0, 'Unexpected empty page')
            for row in rows:
                require(type(row.get('id')) is int and row['id'] not in seen,
                        'Missing or duplicate string ID')
                require(row.get('fileId') == file['id'], 'Wrong file in page')
                require(all(k in row for k in ('key', 'original', 'translation', 'version')),
                        'Incomplete string metadata')
                seen.add(row['id'])
                records.append(row)
            fetched += len(rows)
            pages.append({'file_id': file['id'], 'page': page, 'rows': len(rows),
                          'rowCount': expected, 'pageCount': count, 'sha256': digest(body)})
            if page >= count:
                break
            require(fetched < expected, 'Pagination exceeds advertised total')
            page += 1
        require(fetched == expected, 'Incomplete pagination')
    after = get('/files')
    fields = ('id', 'name', 'total', 'modifiedAt')
    signature = lambda fs: sorted([tuple(f.get(k) for k in fields) for f in fs
                                  if f['id'] in file_ids])
    require(signature(selected) == signature(after), 'Files changed during capture; recapture')
    records.sort(key=lambda r: r['id'])
    return {'schema_version': 1, 'project_id': str(project), 'started_at': started,
            'completed_at': now(), 'files': selected, 'project_files': before, 'pages': pages,
            'record_count': len(records), 'records_sha256': digest(records),
            'atomic': False, 'records': records}


def index(snapshot):
    require(snapshot.get('schema_version') == 1, 'Unsupported snapshot schema')
    rows = snapshot['records']
    by_id = {r['id']: r for r in rows}
    require(len(by_id) == len(rows), 'Duplicate IDs in snapshot')
    require(snapshot['record_count'] == len(rows), 'Snapshot count mismatch')
    require(snapshot['records_sha256'] == digest(rows), 'Snapshot hash mismatch')
    files = snapshot['files']
    file_ids = {f['id'] for f in files}
    require(len(file_ids) == len(files), 'Duplicate file metadata')
    require(all(r['fileId'] in file_ids for r in rows), 'Record outside file scope')
    pages = snapshot['pages']
    require(all(p['file_id'] in file_ids for p in pages), 'Page outside file scope')
    for f in files:
        total = f['total']
        require(type(total) is int and total >= 0, 'Invalid file total')
        require(sum(r['fileId'] == f['id'] for r in rows) == total, 'File total mismatch')
        ps = [p for p in pages if p['file_id'] == f['id']]
        require(bool(ps), 'Missing page evidence')
        count = ps[0]['pageCount']
        require(type(count) is int and count >= 0 and (count > 0 or total == 0),
                'Invalid page count evidence')
        require(sorted(p['page'] for p in ps) == list(range(1, max(count, 1) + 1)),
                'Incomplete page evidence')
        require(all(p['pageCount'] == count and p['rowCount'] == total for p in ps),
                'Inconsistent page evidence')
        require(all(type(p['rows']) is int and p['rows'] >= 0 for p in ps)
                and sum(p['rows'] for p in ps) == total, 'Page row total mismatch')
    return by_id


def delta(old, new):
    require(old['project_id'] == new['project_id'], 'Different projects')
    require({f['id'] for f in old['files']} == {f['id'] for f in new['files']},
            'Different file scopes')
    a, b = index(old), index(new)
    fields = ('fileId', 'key', 'original', 'translation', 'context', 'version', 'updatedAt', 'stage')
    changed = [{'id': i, 'fields': [k for k in fields if a[i].get(k) != b[i].get(k)]}
               for i in sorted(a.keys() & b.keys())]
    return {'baseline_sha256': old['records_sha256'], 'latest_sha256': new['records_sha256'],
            'latest_completed_at': new['completed_at'],
            'added': sorted(b.keys() - a.keys()), 'removed': sorted(a.keys() - b.keys()),
            'changed': [r for r in changed if r['fields']],
            'instruction': 'Re-review changed and related entries; changes do not prove resolution.'}


def validate_highlights(text, ranges, require_reason=True):
    """Half-open Unicode code-point ranges into the unchanged full source text."""
    require(isinstance(ranges, list), 'Highlights must be a list')
    previous_end = 0
    for span in ranges:
        require(isinstance(span, dict), 'Highlight must be an object')
        start, end = span.get('start'), span.get('end')
        require(type(start) is int and type(end) is int, 'Highlight offsets must be integers')
        require(0 <= start <= end <= len(text) and (not require_reason or start < end),
                'Highlight outside full text')
        require(start >= previous_end, 'Highlights must be sorted and non-overlapping')
        if require_reason:
            require(isinstance(span.get('reason'), str) and bool(span['reason'].strip()),
                    'Highlight needs an evidence-specific reason')
        if 'text' in span:
            require(span['text'] == text[start:end], 'Highlight text assertion does not match source')
        previous_end = end


def validate(data):
    require(data.get('schema_version') == 1, 'Unsupported audit schema')
    rows = index(data['snapshot'])
    coverage = data['coverage']
    require(len({r['id'] for r in coverage}) == len(coverage), 'Duplicate coverage IDs')
    require({r['id'] for r in coverage} == set(rows), 'Coverage must account for every snapshot ID')
    scoped = set()
    reviewed = set()
    for c in coverage:
        require(c['scope'] in ('in_scope', 'partial', 'excluded'), 'Invalid scope')
        require(type(c.get('reviewed')) is bool, 'reviewed must be boolean')
        if c['scope'] in ('partial', 'excluded'):
            require(bool(c.get('reason')), 'Scope exclusion needs reason')
        if c['scope'] == 'partial':
            require(bool(c.get('included_context')), 'Partial scope needs included context')
        if c['scope'] != 'excluded':
            scoped.add(c['id'])
            if c['reviewed']:
                require(bool(c.get('reviewer')) and bool(c.get('reviewed_at')), 'Missing review provenance')
                require(c.get('snapshot_version') == rows[c['id']]['version'], 'Stale coverage version')
                require(c.get('record_sha256') == digest(rows[c['id']]), 'Stale coverage record hash')
                reviewed.add(c['id'])
    findings = data['findings']
    require(len({f['finding_id'] for f in findings}) == len(findings), 'Duplicate finding IDs')
    statuses = ('confirmed', 'uncertain', 'dismissed', 'resolved', 'stale')
    for f in findings:
        if f['id'] not in scoped:
            e = f.get('removal_evidence', {})
            require(f['status'] == 'stale' and f['id'] not in rows
                    and e.get('removed_id') == f['id']
                    and e.get('latest_sha256') == data['snapshot']['records_sha256']
                    and isinstance(e.get('baseline_sha256'), str)
                    and len(e['baseline_sha256']) == 64,
                    'Finding outside audited scope; deleted history needs stale removal evidence')
        require(f['status'] in statuses, 'Invalid finding status')
        require(f['severity'] in ('critical', 'high', 'medium', 'low'), 'Invalid severity')
        require(f.get('kind') in ('translation', 'source_import', 'mixed'), 'Invalid root-cause kind')
        for field in ('finding_id', 'title', 'problem', 'suggestion', 'original', 'url'):
            require(isinstance(f.get(field), str) and bool(f[field]), 'Missing finding field: ' + field)
        require(isinstance(f.get('translation'), str), 'Missing translation (empty allowed)')
        for side in ('original', 'translation'):
            validate_highlights(f[side], f.get(side + '_highlights', []))
            if side + '_focus_ranges' in f:
                ranges = f[side + '_focus_ranges']
                validate_highlights(f[side], ranges, require_reason=False)
                pieces = [f[side][r['start']:r['end']] for r in ranges]
                require(pieces == f.get(side + '_segments', [f.get(side + '_focus')]),
                        'Focus ranges do not match selected segments')
                require(f.get(side + '_focus') == '\n\n'.join(pieces),
                        'Focus ranges do not reconstruct exact focus')
        if f['status'] != 'stale':
            require(f.get('snapshot_version') == rows[f['id']]['version'], 'Finding version is stale')
            require(f.get('record_sha256') == digest(rows[f['id']]), 'Finding record hash is stale')
            require(f['original'] == rows[f['id']]['original'] and
                    f['translation'] == rows[f['id']]['translation'], 'Finding text is stale')
        if f['status'] == 'confirmed':
            require(f['id'] in reviewed, 'Confirmed finding lacks semantic coverage')
            review = f.get('second_pass', {})
            require(review.get('decision') == 'support' and bool(review.get('reviewer'))
                    and bool(review.get('reason')), 'Confirmed finding lacks independent support')
            first = next(c['reviewer'] for c in coverage if c['id'] == f['id'])
            require(review['reviewer'] != first, 'Second pass must be independent')
        if f['status'] == 'resolved':
            require(bool(f.get('resolution_evidence')) and bool(f.get('verified_at')),
                    'Resolved finding needs readback evidence')
        if f['kind'] in ('source_import', 'mixed') and f['status'] == 'confirmed':
            evidence = f.get('official_evidence', {})
            require(all(evidence.get(k) for k in ('text', 'url', 'version', 'location')),
                    'Source issue requires official version/location evidence')
    return {'raw_entries': len(rows), 'excluded_entries': len(rows) - len(scoped),
            'partial_entries': sum(c['scope'] == 'partial' for c in coverage),
            'in_scope_entries': len(scoped), 'reviewed_entries': len(reviewed),
            'unreviewed_ids': sorted(scoped - reviewed),
            'findings': {s: sum(f['status'] == s for f in findings) for s in statuses},
            'affected_entries': {s: len({f['id'] for f in findings if f['status'] == s}) for s in statuses}}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    s = sub.add_parser('snapshot')
    s.add_argument('--files', type=int, nargs='+', required=True)
    s.add_argument('--out', required=True)
    d = sub.add_parser('diff')
    d.add_argument('baseline'); d.add_argument('latest'); d.add_argument('--out', required=True)
    v = sub.add_parser('validate'); v.add_argument('audit')
    args = p.parse_args()
    if args.command == 'snapshot':
        import os
        path = Path(__file__).resolve().parents[2] / 'paratranz-ops/scripts/para.py'
        spec = importlib.util.spec_from_file_location('para', path)
        para = importlib.util.module_from_spec(spec); spec.loader.exec_module(para)
        session = para.session()
        # GET only. Never follow redirects with an authorization header.
        def get(route):
            response = para.call(session, 'GET', route, allow_redirects=False)
            require(not 300 <= response.status_code < 400, 'Redirect refused')
            return response.json()
        result = capture(get, os.getenv('PARATRANZ_PROJECT_ID', para.DEFAULT_PROJECT_ID), args.files)
    elif args.command == 'diff':
        result = delta(read(args.baseline), read(args.latest))
    else:
        result = validate(read(args.audit))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result['unreviewed_ids'] else 0
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    # A successful run cannot silently destroy an older evidence baseline.
    with target.open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write('\n')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, TypeError, OSError) as exc:
        raise SystemExit(f'Audit data error: {exc}')
