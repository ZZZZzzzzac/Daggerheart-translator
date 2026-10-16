import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {normalizeReport, parseReportJSON} from './dist/model.mjs';

const BASIS = 'Unicode code points in extracted_text, not raw Markdown';
const copy = value => structuredClone(value);
const cleanFinding = () => ({finding_id: 'synthetic-1', title: '测试审阅', location: 'synthetic example', problem: '此处待核对', suggestion: '人工回查', original: '😀 Gain 2 points. 2 again.', translation: '😀 获得3点。', original_highlights: [{start: 7, end: 8, text: '2', reason: '显式数量证据'}], translation_highlights: [{start: 4, end: 5, text: '3', reason: '显式数量证据'}], related_contexts: []});
const audit = () => ({schemaVersion: 1, reportId: 'synthetic', title: '公开合成示例', findings: [cleanFinding()]});
const ev = (side, full = '😀 2') => ({unit_id: 'u', side, selector: {kind: 'block', block: 0}, offset_basis: BASIS, extracted_text: full, raw_text: '**' + full + '**', tokens: [{start: 2, end: 3, quote: '2', kind: 'integer', value: '2'}], uncertain: [], ast_paths: ['/blocks/0']});
const quantity = () => ({version: 'mechanic-quantity-scopes-v1', semantic_verified: false, release_allowed: true, status: 'quantity_surface_match', risk_count: 0, configuration_errors: [], scopes: [{id: 'scope', unit_id: 'u', semantic_verified: false, status: 'quantity_surface_match', source: ev('source'), translation: ev('translation'), risks: []}]});
function canonical(value) {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value && typeof value === 'object') return '{' + Object.keys(value).sort((a, b) => {
    const x = Array.from(a, c => c.codePointAt(0)), y = Array.from(b, c => c.codePointAt(0));
    for (let i = 0; i < Math.min(x.length, y.length); i++) if (x[i] !== y[i]) return x[i] - y[i];
    return x.length - y.length;
  }).map(key => JSON.stringify(key) + ':' + canonical(value[key])).join(',') + '}';
  return JSON.stringify(value);
}
const sign = draft => { draft.preview_sha256 = createHash('sha256').update(canonical(draft.preview)).digest('hex'); return draft; };
function draft() {
  const sourceAst = {t: 'Para', c: [{t: 'Str', c: 'Gain'}, {t: 'Space'}, {t: 'Str', c: '2'}]};
  const targetAst = {t: 'Para', c: [{t: 'Strong', c: [{t: 'Str', c: '😀示例（特性）'}]}, {t: 'Str', c: '：'}, {t: 'Space'}, {t: 'Str', c: '获得2点。😀示例'}]};
  const block = (ast, full) => ({block: 0, ast_path: '/blocks/0', node_type: ast.t, ast, quantity_candidate: {selector: {kind: 'block', block: 0}, text: full}});
  const s = block(sourceAst, 'Gain 2'), t = block(targetAst, '😀示例（特性）： 获得2点。😀示例');
  t.name_candidate = {selector: {kind: 'feature_label', block: 0}, text: '😀示例（特性）'};
  const preview = {format: 'pbres-config-preview-v1', approval_status: 'unconfirmed', semantic_verified: false, selection: {unit_id: 'u', resource_id: 'r'}, review_status: {parent_attribution: 'unconfirmed', alignment: 'unconfirmed', homonym_identity: 'unconfirmed'}, name_choices: [{resource_id: 'r', name_pointer: '/name', translation: '示例', original: 'Example', status: 'available'}], sides: {source: {raw_text: 'Gain 2', blocks: [s]}, translation: {raw_text: '**😀示例（特性）**： 获得2点。😀示例', blocks: [t]}}};
  return sign({format: 'pbres-config-draft-v1', approval_status: 'unconfirmed', semantic_verified: false, preview, proposed_parent: {unit_id: 'u', resource_id: 'r', approval_status: 'unconfirmed'}, proposed_name_bindings: [{unit_id: 'u', resource_id: 'r', approval_status: 'unconfirmed', name_pointer: '/name', selector: {kind: 'feature_label', block: 0, suffix: '（特性）'}, expected_name: '示例', observed_name: '😀示例'}], proposed_quantity_scopes: [{id: 'draft-scope-1', unit_id: 'u', approval_status: 'unconfirmed', source: copy(s.quantity_candidate), translation: copy(t.quantity_candidate)}]});
}

test('lean schemaVersion 1 supports exact astral Unicode code-point highlights', async () => {
  const data = audit(), before = JSON.stringify(data), out = await normalizeReport(data);
  assert.equal(out.findings[0].id, 'synthetic-1');
  assert.equal(out.findings[0].original_highlights[0].text, '2');
  assert.equal(out.findings[0].original_highlights[0].start, 7);
  assert.match(out.notice, /不批准/);
  assert.equal(JSON.stringify(data), before);
});

test('rejects UTF-16 offsets, mismatched quote, overlap, unordered and missing quote', async () => {
  for (const marks of [
    [{start: 8, end: 9, text: '2', reason: 'bad UTF-16 offset'}],
    [{start: 7, end: 8, text: '3', reason: 'wrong quote'}],
    [{start: 7, end: 9, text: '2 ', reason: 'a'}, {start: 8, end: 9, text: ' ', reason: 'b'}],
    [{start: 17, end: 18, text: '2', reason: 'later'}, {start: 7, end: 8, text: '2', reason: 'earlier'}],
    [{start: 7, end: 8, reason: 'no quote'}],
    [{start: true, end: 8, text: '2', reason: 'boolean'}],
    [{start: 7, end: 7, text: '', reason: 'empty'}],
    [{start: 7, end: 100, text: '2', reason: 'bounds'}],
  ]) { const data = audit(); data.findings[0].original_highlights = marks; await assert.rejects(normalizeReport(data)); }
});

test('text remains inert and repeated words never create inferred highlights', async () => {
  const data = audit();
  Object.assign(data.findings[0], {original: '<script>danger()</script> same same\r\n', translation: '同 同', original_highlights: [], translation_highlights: [], original_focus: 'same'});
  const out = await normalizeReport(data);
  assert.equal(out.findings[0].original, data.findings[0].original);
  assert.deepEqual(out.findings[0].original_highlights, []);
});

test('normalization preserves exact combining marks, CRLF and range text', async () => {
  const data = audit(); Object.assign(data.findings[0], {original: '😀e\u0301\r\nA', original_highlights: [{start: 1, end: 3, text: 'e\u0301', reason: 'decomposed'}]});
  assert.equal((await normalizeReport(data)).findings[0].original_highlights[0].text, 'e\u0301');
  data.findings[0].original_highlights[0].text = 'é'; await assert.rejects(normalizeReport(data), /exact Unicode/);
});

test('rejects unsupported reports, unsupported versions and malformed JSON data', async () => {
  for (const data of [null, [], {}, {schemaVersion: 2, findings: []}, {format: 'pbres-config-preview-v1'}, {version: 'mechanic-quantity-scopes-v2'}, {x: NaN}, {x: Infinity}, {x: '\ud800'}, {x: undefined}, {x: 9007199254740992}, new Date()]) await assert.rejects(normalizeReport(data));
  const cyc = {}; cyc.x = cyc; await assert.rejects(normalizeReport(cyc), /Cyclic/);
  const value = {}; Object.defineProperty(value, 'x', {get() {throw new Error('getter ran');}}); await assert.rejects(normalizeReport(value), /accessors/);
});

test('strict JSON parser rejects duplicate, escaped duplicate, nonfinite, malformed and nested duplicates', () => {
  for (const source of ['{"x":1,"x":2}', '{"x":1,"\\u0078":2}', '{"nested":{"a":1,"a":2}}', '{"a":1,}', '[1,]', '1e999', 'NaN', '{"a":"\\ud800"}', 'true false', '{"x":01}', '"unfinished']) assert.throws(() => parseReportJSON(source));
  const parsed = parseReportJSON('{"__proto__":{"safe":true},"list":[null,true,1,"中文😀"]}');
  assert.equal(Object.hasOwn(parsed, '__proto__'), true);
  assert.equal({}.safe, undefined);
  assert.deepEqual(parsed.list, [null, true, 1, '中文😀']);
});

test('quantity evidence is validated on extracted text, never raw Markdown', async () => {
  const data = quantity(), out = await normalizeReport(data);
  assert.equal(out.findings[0].original, '😀 2');
  assert.equal(out.findings[0].original_highlights[0].start, 2);
  assert.equal(out.findings[0].related_contexts[0].original, '**😀 2**');
  assert.match(out.description, /仅包含显式范围/);
  data.scopes[0].source.offset_basis = 'UTF-16'; await assert.rejects(normalizeReport(data), /offsets/);
});

test('quantity tokens and uncertain spans reject overlap across both arrays', async () => {
  const data = quantity(); data.scopes[0].source.uncertain = [{start: 2, end: 3, quote: '2', reason: 'ambiguous'}];
  await assert.rejects(normalizeReport(data), /nonoverlapping/);
});

test('quantity report rejects evidence side/unit mismatch and contradictory embedded evidence', async () => {
  for (const property of ['side', 'unit_id']) { const data = quantity(); data.scopes[0].source[property] = 'wrong'; await assert.rejects(normalizeReport(data), /disagrees/); }
  const data = quantity(); data.scopes[0].risks = [{kind: 'sample', detail: 'sample', source: {...data.scopes[0].source, extracted_text: 'wrong'}}]; await assert.rejects(normalizeReport(data), /Risk evidence/);
});

test('quantity configuration errors, missing extraction and input contradictions stay visible', async () => {
  const data = quantity(); data.configuration_errors = ['synthetic config error']; data.risk_count = 42;
  const out = await normalizeReport(data);
  assert.match(out.notice, /矛盾/); assert.match(out.description, /risk_count=42/); assert(out.findings.some(f => f.problem.includes('synthetic config error')));
  const absent = quantity(); absent.release_allowed = false; absent.status = 'needs_review'; absent.risk_count = 1;
  const scope = absent.scopes[0]; scope.status = 'needs_review'; scope.source = {side: 'source', unit_id: 'u', selector: {kind: 'block', block: 0}, offset_basis: BASIS, unavailable: 'unsupported node'}; scope.risks = [{kind: 'quantity_scope_unavailable', detail: 'unavailable'}];
  const row = (await normalizeReport(absent)).findings[0]; assert.equal(row.original, ''); assert.deepEqual(row.original_highlights, []); assert.match(row.problem, /unsupported node/);
});

test('unconfirmed and semantic-verified gates are enforced', async () => {
  const q = quantity(); q.semantic_verified = true; await assert.rejects(normalizeReport(q), /unverified/);
  const scope = quantity(); scope.scopes[0].semantic_verified = true; await assert.rejects(normalizeReport(scope), /semantic verification/);
  const d = draft(); d.approval_status = 'approved'; await assert.rejects(normalizeReport(d), /unconfirmed/);
});

test('draft validates canonical preview digest, anchored name suffix, whole range, and unchanged input', async () => {
  const data = draft(), before = JSON.stringify(data), out = await normalizeReport(data);
  assert.equal(out.findings.length, 2);
  assert.equal(out.findings[0].translation_highlights[0].text, '😀示例');
  assert.equal(out.findings[0].translation_highlights[0].end, 3);
  assert.deepEqual(out.findings[0].original_highlights, []);
  assert.equal(out.findings[1].translation_highlights[0].end, Array.from(out.findings[1].translation).length);
  assert.match(out.description, /不是签名/);
  assert.equal(JSON.stringify(data), before);
});

test('draft rejects hash change, parent mismatch, tampered candidate and wrong observed name', async () => {
  const mutations = [
    d => { d.preview.sides.source.raw_text += '!'; },
    d => { d.proposed_parent.unit_id = 'other'; },
    d => { d.proposed_name_bindings[0].observed_name = 'bad'; },
    d => { d.proposed_quantity_scopes[0].source.text = 'Gain 3'; },
    d => { d.preview.sides.source.blocks[0].quantity_candidate.text = 'Gain 3'; d.proposed_quantity_scopes[0].source.text = 'Gain 3'; sign(d); },
    d => { d.preview.sides.translation.blocks[0].ast.c[0].c[0].c = 'wrong'; sign(d); },
  ];
  for (const mutate of mutations) { const data = draft(); mutate(data); await assert.rejects(normalizeReport(data)); }
});

test('draft rejects duplicate targets, duplicate endpoints and duplicate scope IDs', async () => {
  const n = draft(); n.proposed_name_bindings.push(copy(n.proposed_name_bindings[0])); await assert.rejects(normalizeReport(n), /Duplicate name/);
  const q = draft(); q.proposed_quantity_scopes.push({...copy(q.proposed_quantity_scopes[0]), id: 'scope2'}); await assert.rejects(normalizeReport(q), /Duplicate quantity endpoint/);
  const id = draft(); id.proposed_quantity_scopes.push(copy(id.proposed_quantity_scopes[0])); await assert.rejects(normalizeReport(id), /Duplicate draft scope/);
});

test('unsupported draft body displays raw evidence explicitly without invented highlights', async () => {
  const data = draft();
  data.preview.sides.translation.blocks[0].ast.c.push({t: 'Code', c: [['', [], []], 'example']});
  sign(data);
  const out = await normalizeReport(data);
  for (const f of out.findings) {
    assert.equal(f.translation, data.preview.sides.translation.raw_text);
    assert.deepEqual(f.translation_highlights, []);
    assert.match(f.problem, /不支持此 AST 结构/);
  }
});

test('draft SHA canonical key ordering follows Python Unicode code points', async () => {
  const data = draft(); data.preview.extra = {'😀': 'astral', '\uffff': 'BMP'}; sign(data);
  assert.equal((await normalizeReport(data)).findings.length, 2);
});

test('draft refuses floating-point canonicalization ambiguity', async () => {
  const data = draft(); data.preview.extra = 1.5; sign(data);
  await assert.rejects(normalizeReport(data), /safe integer numbers only/);
});

test('combined report preserves top gate, missing checks, full base issue fields and contradictions', async () => {
  const data = {release_allowed: true, identity_errors: ['duplicate source ID'], units: [{id: 'u', findings: [{kind: 'format', text: 'broken', extra_evidence: {count: 2}}]}], quantity_risk_check: quantity()};
  const out = await normalizeReport(data);
  assert.match(out.notice, /矛盾/);
  assert.match(out.description, /名称检查：未提供/);
  assert.match(out.description, /顶层 release_allowed：true/);
  assert(out.findings.some(f => f.problem.includes('extra_evidence')));
  assert(out.findings.some(f => f.title.includes('身份错误')));
});

test('combined report does not promote subcheck success into total success', async () => {
  const out = await normalizeReport({quantity_risk_check: quantity()});
  assert.match(out.notice, /总门禁状态缺失/);
  assert.match(out.description, /基础交付结果：未提供/);
  const gateFalse = await normalizeReport({release_allowed: false, identity_errors: [], units: [], quantity_risk_check: quantity()});
  assert.match(gateFalse.notice, /阻止交付/);
});

test('name check preserves extraction absence and never highlights inferred original names', async () => {
  const data = {release_allowed: true, name_binding_check: {release_allowed: true, configuration_errors: [], bindings: [{unit_id: 'u', resource_id: 'r', name_pointer: '/name', selector: {kind: 'heading', block: 0, level: 2}, expected: '示例', findings: []}]}};
  const out = await normalizeReport(data), f = out.findings.find(f => f.id === 'check-name-0');
  assert.equal(f.original, ''); assert.equal(f.translation, ''); assert.deepEqual(f.original_highlights, []); assert.match(f.problem, /未提供，不能补造/); assert.match(out.notice, /矛盾/);
});

test('malformed gates and incomplete paired base envelope are rejected', async () => {
  for (const data of [{release_allowed: 'true', identity_errors: [], units: []}, {name_binding_check: {release_allowed: true}}, {release_allowed: true, identity_errors: [], quantity_risk_check: quantity()}, {quantity_risk_check: {...quantity(), release_allowed: undefined}}]) await assert.rejects(normalizeReport(data));
});

test('normalized audit rejects duplicate identities and misanchored focus ranges', async () => {
  const duplicate = audit(); duplicate.findings.push(copy(duplicate.findings[0])); await assert.rejects(normalizeReport(duplicate), /Duplicate audit/);
  const focus = audit(); focus.findings[0].original_focus = '2'; focus.findings[0].original_focus_ranges = [{start: 8, end: 9}]; await assert.rejects(normalizeReport(focus), /exact source occurrence/);
});

test('present-but-null evidence and optional arrays are malformed, not empty', async () => {
  for (const key of ['extracted_text', 'tokens', 'uncertain']) {
    const data = quantity(); data.scopes[0].source[key] = null; await assert.rejects(normalizeReport(data));
  }
  for (const key of ['original_highlights', 'translation_highlights', 'related_contexts']) {
    const data = audit(); data.findings[0][key] = null; await assert.rejects(normalizeReport(data));
  }
});
