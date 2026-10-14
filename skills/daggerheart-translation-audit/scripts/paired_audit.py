#!/usr/bin/env python3
"""Preserve paired texts, validate authored semantic reviews, and export HTML-report data.

This tool does not perform semantic review. It never marks an entry reviewed merely
because text was normalized, searched, compared, or rendered. Standard library only.
"""
import argparse
import copy
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

CATEGORIES = ('meaning', 'omission', 'addition', 'terminology', 'consistency',
              'grammar', 'style', 'formatting', 'alignment', 'source_issue', 'other')
SEVERITIES = ('critical', 'high', 'medium', 'low')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()



def timestamp(value, label):
    require(nonempty(value), label + ' must be an ISO-8601 timestamp with timezone')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError(label + ' must be an ISO-8601 timestamp with timezone') from None
    require(parsed.tzinfo is not None, label + ' must include a timezone')


def check_url(value):
    require(isinstance(value, str), 'url must be a string')
    if value:
        try:
            parsed = urlsplit(value)
            valid = (parsed.scheme == 'https' and parsed.hostname
                     and not parsed.username and not parsed.password)
        except ValueError:
            valid = False
        require(valid, 'url must be an absolute HTTPS URL without credentials')


def segment_hash(segment):
    return digest({key: value for key, value in segment.items() if key != 'segmentSha256'})


def normalize(data, method='explicit-pair'):
    """Normalize supplied text pairs; whitespace and Unicode are unchanged."""
    require(isinstance(data, dict), 'Paired input must be an object with segments')
    require(data.get('schemaVersion', 1) == 1, 'Unsupported paired input schemaVersion')
    require(nonempty(data.get('title')), 'Paired input requires a title')
    require(method in ('explicit-pair', 'whole-document'), 'Invalid pairing method')
    rows = data.get('segments')
    require(isinstance(rows, list) and bool(rows), 'segments must be a nonempty array')
    segments, seen = [], set()
    for row in rows:
        require(isinstance(row, dict), 'Each segment must be an object')
        ident = row.get('id')
        require(nonempty(ident), 'Each segment needs a stable nonempty string id')
        require(ident not in seen, 'Duplicate segment id: ' + ident)
        seen.add(ident)
        for side in ('original', 'translation'):
            require(isinstance(row.get(side), str), ident + ': explicit ' + side + ' string required (empty allowed)')
        require(row['original'] != '' or row['translation'] != '', ident + ': both sides cannot be empty')
        segment = {'id': ident, 'original': row['original'], 'translation': row['translation'],
                   'location': row.get('location', ident),
                   'alignment': {'method': method, 'note': row.get('alignmentNote', '')}}
        require(nonempty(segment['location']), ident + ': location must be nonempty text')
        require(isinstance(segment['alignment']['note'], str), ident + ': alignmentNote must be text')
        for field in ('context', 'provider', 'url'):
            if field in row:
                require(isinstance(row[field], str), ident + ': ' + field + ' must be text')
                segment[field] = row[field]
        if 'url' in segment:
            check_url(segment['url'])
        # Preserve any locators already supplied; never require or obtain sources.
        if 'provenance' in row:
            require(isinstance(row['provenance'], dict), ident + ': provenance must be an object')
            segment['provenance'] = copy.deepcopy(row['provenance'])
        segment['segmentSha256'] = segment_hash(segment)
        segments.append(segment)
    normalized_input = {'schemaVersion': 1, 'type': 'paired-audit-input',
                'title': data['title'], 'sourceLanguage': data.get('sourceLanguage', ''),
                'targetLanguage': data.get('targetLanguage', ''),
                'inputSha256': digest(segments), 'segments': segments}
    input_index(normalized_input)
    return normalized_input


def input_index(normalized_input):
    require(isinstance(normalized_input, dict) and normalized_input.get('schemaVersion') == 1
            and normalized_input.get('type') == 'paired-audit-input', 'Unsupported normalized paired input')
    require(nonempty(normalized_input.get('title')), 'Input requires title')
    for key in ('sourceLanguage', 'targetLanguage'):
        require(isinstance(normalized_input.get(key), str), key + ' must be text')
    rows = normalized_input.get('segments')
    require(isinstance(rows, list) and bool(rows), 'Input segments must be nonempty')
    by_id = {}
    for row in rows:
        require(isinstance(row, dict) and nonempty(row.get('id')), 'Invalid normalized input segment')
        ident = row['id']
        require(ident not in by_id, 'Duplicate segment id: ' + ident)
        for side in ('original', 'translation'):
            require(isinstance(row.get(side), str), ident + ': ' + side + ' must be text')
        require(row['original'] != '' or row['translation'] != '', ident + ': both sides cannot be empty')
        require(nonempty(row.get('location')), ident + ': missing location')
        alignment = row.get('alignment')
        require(isinstance(alignment, dict) and alignment.get('method') in ('explicit-pair', 'whole-document')
                and isinstance(alignment.get('note'), str), ident + ': invalid alignment metadata')
        for field in ('context', 'provider', 'url'):
            if field in row:
                require(isinstance(row[field], str), ident + ': ' + field + ' must be text')
        if 'url' in row:
            check_url(row['url'])
        if 'provenance' in row:
            require(isinstance(row['provenance'], dict), ident + ': invalid provenance')
        require(row.get('segmentSha256') == segment_hash(row), ident + ': stale segment hash')
        by_id[ident] = row
    require(normalized_input.get('inputSha256') == digest(rows), 'Input collection hash mismatch')
    return by_id


def prepare(normalized_input):
    input_index(normalized_input)
    return {'schemaVersion': 1, 'type': 'paired-audit-review',
            'inputSha256': normalized_input['inputSha256'],
            'coverage': [{'id': row['id'], 'segmentSha256': row['segmentSha256'],
                          'status': 'unreviewed', 'alignment': 'unverified',
                          'reviewer': '', 'reviewedAt': '', 'assessment': '',
                          'conclusion': '', 'findingIds': []} for row in normalized_input['segments']],
            'findings': []}


def validate_ranges(text, spans, label, evidence=True):
    require(isinstance(spans, list), label + ' must be an array')
    previous_end = 0
    for span in spans:
        require(isinstance(span, dict), label + ' span must be an object')
        start, end = span.get('start'), span.get('end')
        require(type(start) is int and type(end) is int, label + ' offsets must be Unicode code-point integers')
        require(0 <= start <= end <= len(text) and (not evidence or start < end), label + ' span outside exact text')
        require(start >= previous_end, label + ' spans must be sorted and non-overlapping')
        if evidence:
            require(nonempty(span.get('reason')), label + ' span needs an evidence-specific reason')
            require(isinstance(span.get('text'), str) and span['text'] == text[start:end],
                    label + ' text must equal the exact source slice')
        elif 'text' in span:
            require(span['text'] == text[start:end], label + ' focus text mismatch')
        previous_end = end


def validate(normalized_input, review):
    """Check evidence against supplied texts, not the truth of semantic judgments."""
    rows = input_index(normalized_input)
    require(isinstance(review, dict) and review.get('schemaVersion') == 1
            and review.get('type') == 'paired-audit-review', 'Unsupported paired review')
    require(review.get('inputSha256') == normalized_input['inputSha256'], 'Review belongs to a different paired input; review the current texts')
    coverage = review.get('coverage')
    require(isinstance(coverage, list), 'coverage must be an array')
    ledger = {}
    for entry in coverage:
        require(isinstance(entry, dict) and nonempty(entry.get('id')), 'Invalid coverage entry')
        ident = entry['id']
        require(ident not in ledger, 'Duplicate coverage id: ' + ident)
        require(ident in rows, 'Coverage id not in input: ' + ident)
        require(entry.get('segmentSha256') == rows[ident]['segmentSha256'], ident + ': review has stale segment hash')
        require(entry.get('status') in ('unreviewed', 'reviewed', 'excluded'), ident + ': invalid coverage status')
        finding_ids = entry.get('findingIds')
        require(isinstance(finding_ids, list) and all(nonempty(x) for x in finding_ids)
                and len(set(finding_ids)) == len(finding_ids), ident + ': invalid findingIds')
        if entry['status'] == 'reviewed':
            require(nonempty(entry.get('reviewer')), ident + ': reviewer identity required')
            timestamp(entry.get('reviewedAt'), ident + ': reviewedAt')
            require(nonempty(entry.get('assessment')), ident + ': semantic assessment required')
            require(entry.get('alignment') in ('verified', 'unresolved'), ident + ': reviewed alignment decision required')
            require(entry.get('conclusion') in ('no_issue', 'findings', 'uncertain'), ident + ': invalid conclusion')
            if entry['alignment'] == 'unresolved':
                require(entry['conclusion'] == 'uncertain', ident + ': unresolved alignment cannot support a definite conclusion')
        else:
            require(not finding_ids, ident + ': unreviewed/excluded entry cannot contain findings')
            require(entry.get('alignment') == 'unverified', ident + ': unreviewed/excluded alignment must remain unverified')
            require(entry.get('conclusion', '') == '', ident + ': unreviewed/excluded entry cannot have a semantic conclusion')
            if entry['status'] == 'excluded':
                require(nonempty(entry.get('reason')), ident + ': exclusion needs an explicit reason')
                require(nonempty(entry.get('excludedBy')) and nonempty(entry.get('scopeEvidence')),
                        ident + ': exclusion needs excludedBy and scopeEvidence documenting the authorized scope')
        ledger[ident] = entry
    require(set(ledger) == set(rows), 'Coverage must account for every segment ID, including unmatched text')
    findings = review.get('findings')
    require(isinstance(findings, list), 'findings must be an array')
    found = {}
    for finding in findings:
        require(isinstance(finding, dict), 'Finding must be an object')
        fid, ident = finding.get('finding_id'), finding.get('id')
        require(nonempty(fid) and fid not in found, 'Invalid or duplicate finding_id')
        require(isinstance(ident, str) and ident in rows, fid + ': finding references unknown segment')
        row, entry = rows[ident], ledger[ident]
        require(entry['status'] == 'reviewed', fid + ': finding lacks an actual semantic review')
        require(finding.get('segmentSha256') == row['segmentSha256'], fid + ': stale finding segment hash')
        require(finding.get('status') in ('confirmed', 'uncertain'), fid + ': invalid status')
        require(finding.get('severity') in SEVERITIES, fid + ': invalid severity')
        require(finding.get('category') in CATEGORIES, fid + ': invalid category')
        if finding['status'] == 'confirmed':
            second = finding.get('second_pass')
            require(isinstance(second, dict) and second.get('decision') == 'support'
                    and nonempty(second.get('reviewer')) and nonempty(second.get('reason')),
                    fid + ': confirmed finding needs an independent supporting second_pass')
            require(second['reviewer'] != entry['reviewer'], fid + ': second-pass reviewer must be different from first reviewer')
        if 'reference_evidence' in finding:
            reference = finding['reference_evidence']
            require(isinstance(reference, dict) and nonempty(reference.get('text')),
                    fid + ': reference_evidence needs text')
            if 'url' in reference:
                check_url(reference['url'])
        for key in ('title', 'problem', 'suggestion'):
            require(nonempty(finding.get(key)), fid + ': missing ' + key)
        if 'label' in finding:
            require(nonempty(finding['label']), fid + ': label must be nonempty text')
        evidence_count = 0
        for side in ('original', 'translation'):
            if side in finding:
                require(finding[side] == row[side], fid + ': stale ' + side + ' assertion')
            spans = finding.get(side + '_highlights')
            validate_ranges(row[side], spans, fid + ': ' + side + '_highlights')
            evidence_count += len(spans)
            if not spans:
                require(nonempty(finding.get(side + '_absence_reason')),
                        fid + ': explain why ' + side + ' has no highlight (missing or unlocalized text)')
            ranges = finding.get(side + '_focus_ranges', [{'start': 0, 'end': len(row[side])}])
            require(bool(ranges), fid + ': focus ranges must not be empty')
            validate_ranges(row[side], ranges, fid + ': ' + side + '_focus_ranges', evidence=False)
            require(all(any(r['start'] <= h['start'] and h['end'] <= r['end'] for r in ranges) for h in spans),
                    fid + ': focus ranges must include every evidence highlight')
        require(evidence_count > 0, fid + ': at least one exact evidence span is required')
        if entry['alignment'] == 'unresolved':
            require(finding['status'] == 'uncertain', fid + ': unresolved alignment cannot support a confirmed finding')
        found[fid] = finding
    for ident, entry in ledger.items():
        actual = {fid for fid, finding in found.items() if finding['id'] == ident}
        require(set(entry['findingIds']) == actual, ident + ': coverage findingIds do not match findings')
        if entry['status'] == 'reviewed':
            statuses = {found[fid]['status'] for fid in actual}
            if entry['conclusion'] == 'no_issue':
                require(not actual and entry['alignment'] == 'verified', ident + ': no_issue requires verified alignment and no findings')
            elif entry['conclusion'] == 'findings':
                require('confirmed' in statuses, ident + ': findings conclusion needs a confirmed finding')
            else:
                require(statuses == {'uncertain'}, ident + ': uncertain conclusion needs only uncertain findings')
    unreviewed = [ident for ident, entry in ledger.items() if entry['status'] == 'unreviewed']
    excluded = [ident for ident, entry in ledger.items() if entry['status'] == 'excluded']
    unresolved = [ident for ident, entry in ledger.items() if entry['status'] == 'reviewed' and entry['alignment'] == 'unresolved']
    reviewed = sum(entry['status'] == 'reviewed' for entry in ledger.values())
    return {'totalSegments': len(rows), 'reviewedSegments': reviewed,
            'noIssueSegments': sum(entry.get('conclusion') == 'no_issue' for entry in ledger.values()),
            'unreviewedIds': unreviewed, 'excludedIds': excluded, 'unresolvedAlignmentIds': unresolved,
            'completeReview': not (unreviewed or unresolved) and reviewed > 0,
            'allInputReviewed': reviewed == len(rows) and not unresolved,
            'findings': {status: sum(f['status'] == status for f in findings) for status in ('confirmed', 'uncertain')},
            'validationScope': 'Structural validation of reviewer assertions; semantic correctness is not machine-certified.'}


def export_report(normalized_input, review, report_id, allow_incomplete=False):
    summary = validate(normalized_input, review)
    require(nonempty(report_id), 'A stable report ID is required')
    require(summary['completeReview'] or allow_incomplete,
            'Review coverage is incomplete; finish review or explicitly use --allow-incomplete')
    rows = input_index(normalized_input)
    findings = []
    for source in review['findings']:
        row = rows[source['id']]
        finding = {key: source[key] for key in ('finding_id', 'id', 'title', 'status', 'severity', 'problem', 'suggestion')}
        finding.update({'label': source.get('label', source['category']), 'category': source['category'],
                        'original': row['original'], 'translation': row['translation'], 'location': row['location']})
        for key in ('url', 'provider', 'context'):
            if key in row:
                finding[key] = row[key]
        for key in ('second_pass', 'reference_evidence'):
            if key in source:
                finding[key] = copy.deepcopy(source[key])
        for side in ('original', 'translation'):
            ranges = copy.deepcopy(source.get(side + '_focus_ranges', [{'start': 0, 'end': len(row[side])}]))
            pieces = [row[side][r['start']:r['end']] for r in ranges]
            finding[side + '_focus_ranges'] = ranges
            finding[side + '_segments'] = pieces
            finding[side + '_focus'] = '\n\n'.join(pieces)
            finding[side + '_highlights'] = copy.deepcopy(source[side + '_highlights'])
            if side + '_absence_reason' in source:
                finding[side + '_absence_reason'] = source[side + '_absence_reason']
        findings.append(finding)
    total, reviewed = summary['totalSegments'], summary['reviewedSegments']
    coverage_text = (f'Reviewed {reviewed}/{total} supplied segments; '
                     f'{len(summary["unreviewedIds"])} unreviewed, {len(summary["excludedIds"])} excluded, '
                     f'{len(summary["unresolvedAlignmentIds"])} unresolved alignments.')
    notes = coverage_text + (' All in-scope supplied segments have recorded semantic review and verified alignment.'
                             if summary['completeReview'] else ' Partial report: no conclusion about unreviewed or unresolved material.')
    notes += (' Excluded segments are not reviewed and have no semantic conclusion. ' if summary['excludedIds'] else ' ')
    notes += ('Coverage applies only to the supplied paired texts. '
              'Automation validates evidence and review records; a human or AI reviewer supplies semantic judgments.')
    for field, label in (('unreviewedIds', 'Unreviewed IDs'),
                         ('unresolvedAlignmentIds', 'Unresolved alignment IDs')):
        if summary[field]:
            notes += '\n' + label + ': ' + ', '.join(summary[field])
    if summary['excludedIds']:
        ledger = {entry['id']: entry for entry in review['coverage']}
        notes += '\nExcluded scope: ' + '; '.join(
            ident + ': ' + ledger[ident]['reason'] + ' (scope evidence: '
            + ledger[ident]['scopeEvidence'] + ')'
            for ident in summary['excludedIds'])
    empty_message = ('No issues were recorded in the completed semantic review of the in-scope supplied segments.'
                     if summary['completeReview'] else 'No findings recorded so far. Review coverage is incomplete; this is not a clean audit.')
    return {'schemaVersion': 1, 'reportId': report_id, 'title': normalized_input['title'],
            'inputSha256': normalized_input['inputSha256'], 'coverageSummary': summary,
            'notes': notes, 'emptyMessage': empty_message, 'findings': findings}



def reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON object key: ' + key)
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_bytes().decode('utf-8'), object_pairs_hook=reject_duplicates,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Invalid JSON constant: ' + value)))


def write_json(path, data):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Do not overwrite supplied inputs, authored reviews, or reports silently.
    with target.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')



def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    normal = commands.add_parser('normalize', help='Preserve explicit JSON pairs or a whole-document pair; does not review')
    normal.add_argument('--pairs')
    for side in ('original', 'translation'):
        group = normal.add_mutually_exclusive_group()
        group.add_argument('--' + side + '-file')
        group.add_argument('--' + side + '-text')
    normal.add_argument('--id', default='document')
    normal.add_argument('--title')
    normal.add_argument('--source-language', default='')
    normal.add_argument('--target-language', default='')
    normal.add_argument('--out', required=True)
    for command in ('prepare', 'validate', 'export'):
        sub = commands.add_parser(command)
        sub.add_argument('input', help='Normalized paired input JSON')
        if command != 'prepare':
            sub.add_argument('review')
        if command != 'validate':
            sub.add_argument('--out', required=True)
        if command == 'export':
            sub.add_argument('--report-id', required=True)
            sub.add_argument('--allow-incomplete', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.command == 'normalize':
            paired_args = [getattr(args, side + '_' + kind) for side in ('original', 'translation') for kind in ('file', 'text')]
            if args.pairs:
                require(not any(value is not None for value in paired_args), '--pairs cannot be combined with file/text inputs')
                data = read_json(args.pairs)
                require(isinstance(data, dict), 'Paired input must be an object with segments')
                if args.title is not None:
                    data['title'] = args.title
                result = normalize(data)
            else:
                pair = {'id': args.id}
                for side in ('original', 'translation'):
                    filename, inline = getattr(args, side + '_file'), getattr(args, side + '_text')
                    require(filename is not None or inline is not None, 'Provide --' + side + '-file or --' + side + '-text; use explicit empty text for an unmatched side')
                    raw = Path(filename).read_bytes() if filename is not None else inline.encode('utf-8')
                    pair[side] = raw.decode('utf-8')
                result = normalize({'title': args.title or 'Translation audit', 'sourceLanguage': args.source_language,
                                    'targetLanguage': args.target_language, 'segments': [pair]}, method='whole-document')
        elif args.command == 'prepare':
            result = prepare(read_json(args.input))
        elif args.command == 'validate':
            result = validate(read_json(args.input), read_json(args.review))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result['completeReview'] else 1
        elif args.command == 'export':
            result = export_report(read_json(args.input), read_json(args.review), args.report_id, args.allow_incomplete)
        write_json(args.out, result)
        print(args.out)
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print('error: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
