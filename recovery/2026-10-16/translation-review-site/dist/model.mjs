/** Browser-local, read-only adapters. No networking, storage, execution of markup,
 * alignment inference, semantic comparison, or approval is performed here. */
const NOTICE = '未确认 · 完成只记阅读进度，不批准配置或证明语义正确';
const OFFSET_BASIS = 'Unicode code points in extracted_text, not raw Markdown';
const SUGGESTION = '人工回查完整上下文、归属和对应关系；此页不批准配置，也不修改原译文。';
const has = (o, k) => Object.hasOwn(o, k);
const fail = message => { throw new Error(message); };
const object = (v, label) => v !== null && typeof v === 'object' && !Array.isArray(v) ? v : fail(`${label} must be an object`);
const array = (v, label) => Array.isArray(v) ? v : fail(`${label} must be an array`);
const text = (v, label, nonempty = false) => typeof v === 'string' && (!nonempty || v.trim()) ? v : fail(`${label} must be ${nonempty ? 'nonempty ' : ''}text`);
const integer = (v, label, min = 0) => Number.isSafeInteger(v) && v >= min ? v : fail(`${label} must be a safe integer >= ${min}`);
const bool = (v, label) => typeof v === 'boolean' ? v : fail(`${label} must be a boolean`);
const cp = value => Array.from(value);
const pyWhitespace = /^[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+|[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+$/gu;
const pyStrip = value => value.replace(pyWhitespace, '');
const pyLeft = value => value.replace(/^[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/u, '');

function jsonValue(value, path = '$', seen = new Set(), depth = 0) {
  if (depth > 100) fail('JSON is too deeply nested');
  if (typeof value === 'string') {
    for (let i = 0; i < value.length; i++) {
      const n = value.charCodeAt(i);
      if (n >= 0xd800 && n <= 0xdbff) {
        const next = value.charCodeAt(++i);
        if (!(next >= 0xdc00 && next <= 0xdfff)) fail(`${path} contains an unpaired Unicode surrogate`);
      } else if (n >= 0xdc00 && n <= 0xdfff) fail(`${path} contains an unpaired Unicode surrogate`);
    }
    return;
  }
  if (value === null || typeof value === 'boolean') return;
  if (typeof value === 'number') {
    if (!Number.isFinite(value) || (Number.isInteger(value) && !Number.isSafeInteger(value))) fail(`${path} contains an unsupported/non-finite number`);
    return;
  }
  if (!value || typeof value !== 'object') fail(`${path} is not a JSON value`);
  const proto = Object.getPrototypeOf(value);
  if (!Array.isArray(value) && proto !== Object.prototype && proto !== null) fail(`${path} must be a plain JSON object`);
  if (seen.has(value)) fail('Cyclic JSON is unsupported');
  seen.add(value);
  for (const key of Reflect.ownKeys(value)) {
    if (typeof key !== 'string') fail('JSON symbols are unsupported');
    if (Array.isArray(value) && key === 'length') continue;
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if (!descriptor || !has(descriptor, 'value')) fail('JSON accessors are unsupported');
    jsonValue(key, `${path} key`, seen, depth + 1);
    jsonValue(descriptor.value, `${path}.${key}`, seen, depth + 1);
  }
  if (Array.isArray(value) && Object.keys(value).length !== value.length) fail('Sparse or decorated arrays are unsupported');
  seen.delete(value);
}

/** Parse JSON while rejecting duplicate keys rather than silently changing evidence.
 * Use this on uploaded JSON before normalizeReport. A previously parsed object
 * cannot retain evidence of duplicate keys. */
export function parseReportJSON(source) {
  text(source, 'JSON input');
  let position = 0;
  const ws = () => { while (/[\x20\t\r\n]/.test(source[position] || '\0')) position++; };
  function string() {
    const start = position++;
    while (position < source.length) {
      const c = source[position++];
      if (c === '\\') position++;
      else if (c === '"') return JSON.parse(source.slice(start, position));
    }
    fail('Unterminated JSON string');
  }
  function value(depth = 0) {
    if (depth > 100) fail('JSON is too deeply nested');
    ws();
    const c = source[position];
    if (c === '"') { string(); return; }
    if (c === '{' || c === '[') {
      position++;
      ws();
      const end = c === '{' ? '}' : ']';
      const keys = new Set();
      if (source[position] === end) { position++; return; }
      while (position < source.length) {
        ws();
        if (c === '{') {
          if (source[position] !== '"') fail('Expected JSON object key');
          const key = string();
          if (keys.has(key)) fail(`Duplicate JSON object key: ${key}`);
          keys.add(key);
          ws();
          if (source[position++] !== ':') fail('Expected JSON colon');
        }
        value(depth + 1);
        ws();
        if (source[position] === end) { position++; return; }
        if (source[position++] !== ',') fail('Expected JSON separator');
      }
      fail('Unterminated JSON container');
    }
    const match = /^(?:true|false|null|-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)/.exec(source.slice(position));
    if (!match) fail('Invalid JSON value');
    position += match[0].length;
  }
  value(); ws();
  if (position !== source.length) fail('Unexpected content after JSON');
  const data = JSON.parse(source);
  jsonValue(data);
  return data;
}

function keyCompare(a, b) {
  const x = cp(a), y = cp(b);
  for (let i = 0; i < Math.min(x.length, y.length); i++) {
    const d = x[i].codePointAt(0) - y[i].codePointAt(0);
    if (d) return d;
  }
  return x.length - y.length;
}
function canonical(value, draftHash = false) {
  if (Array.isArray(value)) return '[' + value.map(v => canonical(v, draftHash)).join(',') + ']';
  if (value !== null && typeof value === 'object') return '{' + Object.keys(value).sort(keyCompare).map(k => JSON.stringify(k) + ':' + canonical(value[k], draftHash)).join(',') + '}';
  // Python and JavaScript serialize floating point values differently. Refuse an
  // ambiguous draft digest rather than treating another serialization as verified.
  if (draftHash && typeof value === 'number' && (!Number.isSafeInteger(value) || Object.is(value, -0))) fail('Draft SHA-256 canonicalization supports safe integer numbers only');
  return JSON.stringify(value);
}
const equal = (a, b) => canonical(a) === canonical(b);
async function digest(value) {
  if (!globalThis.crypto?.subtle) fail('SHA-256 verification requires a secure browser context');
  const bytes = new TextEncoder().encode(canonical(value, true));
  return Array.from(new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256', bytes)), n => n.toString(16).padStart(2, '0')).join('');
}
function exactKeys(value, keys, label) {
  object(value, label);
  if (Object.keys(value).sort().join('|') !== [...keys].sort().join('|')) fail(`${label} has missing or unsupported fields`);
}
function selector(value, mode = 'quantity') {
  object(value, 'selector');
  if (value.kind === 'block' && mode === 'quantity') {
    exactKeys(value, ['kind', 'block'], 'block selector'); integer(value.block, 'block');
  } else if (value.kind === 'unit' && mode === 'quantity') exactKeys(value, ['kind'], 'unit selector');
  else if (value.kind === 'field') {
    exactKeys(value, ['kind', 'pointer'], 'field selector');
    text(value.pointer, 'field pointer', true);
    if (!value.pointer.startsWith('/') || /~(?![01])/u.test(value.pointer)) fail('Invalid RFC 6901 field pointer');
    if (mode === 'quantity' && !value.pointer.startsWith('/quantity_fields/')) fail('Quantity field must be inside /quantity_fields/');
  } else if (mode === 'name' && ['heading', 'feature_label'].includes(value.kind)) {
    const keys = ['kind', 'block'];
    if (value.kind === 'heading') keys.push('level');
    if (has(value, 'suffix') && value.kind === 'feature_label') keys.push('suffix');
    exactKeys(value, keys, 'name selector'); integer(value.block, 'block');
    if (value.kind === 'heading' && integer(value.level, 'heading level', 1) > 6) fail('Heading level must be between 1 and 6');
    if (has(value, 'suffix')) text(value.suffix, 'literal suffix', true);
  } else fail('Unsupported selector kind');
  return value;
}
function spans(value, full, label, quoteKey = 'text') {
  const points = cp(full);
  let previous = 0;
  return array(value, label).map((range, i) => {
    object(range, label + ' range');
    const start = integer(range.start, label + ' start');
    const end = integer(range.end, label + ' end');
    if (!(start < end && end <= points.length && start >= previous)) fail(`${label} ranges must be in bounds, ordered, and nonoverlapping`);
    previous = end;
    const quote = text(range[quoteKey], label + ' quote');
    if (quote !== points.slice(start, end).join('')) fail(`${label} quote must equal its exact Unicode code-point range`);
    return {start, end, text: quote, reason: text(range.reason, label + ' reason', true)};
  });
}
const context = (original, translation) => [{label: '完整原始 Markdown（仅文本展示，不按数量偏移高亮）', original, translation}];
function finding(id, title, original, translation, problem, location, extra = {}) {
  return {id, title, location, problem, suggestion: SUGGESTION, original, translation,
    original_highlights: [], translation_highlights: [], related_contexts: [], ...extra};
}
const whole = (full, reason) => full ? [{start: 0, end: cp(full).length, text: full, reason}] : [];
const gateText = value => value ? '未见阻断项（不等于语义通过）' : '阻止交付，需处理';
function gate(data, label, required = false) {
  if (!has(data, 'release_allowed')) {
    if (required) fail(`${label} release_allowed is missing`);
    return undefined;
  }
  return bool(data.release_allowed, `${label} release_allowed`);
}

function quantitySide(evidence, side, uid) {
  object(evidence, 'quantity evidence');
  if (evidence.side !== side || evidence.unit_id !== uid) fail('Quantity evidence side or unit disagrees with its scope');
  if (evidence.offset_basis !== OFFSET_BASIS) fail('Quantity offsets must explicitly refer to extracted_text Unicode code points');
  selector(evidence.selector);
  if (!has(evidence, 'extracted_text') && !has(evidence, 'unavailable')) fail('Quantity evidence requires extracted_text or unavailable reason');
  const full = text(has(evidence, 'extracted_text') ? evidence.extracted_text : '', 'extracted_text');
  if (has(evidence, 'unavailable')) text(evidence.unavailable, 'unavailable reason', true);
  if (has(evidence, 'raw_text')) text(evidence.raw_text, 'raw text');
  if (has(evidence, 'field_pointer')) text(evidence.field_pointer, 'field pointer');
  if (has(evidence, 'record_pointer')) text(evidence.record_pointer, 'record pointer');
  if (has(evidence, 'ast_paths')) array(evidence.ast_paths, 'AST paths').forEach(p => text(p, 'AST path'));
  const all = [];
  for (const key of ['tokens', 'uncertain']) {
    for (const item of array(has(evidence, key) ? evidence[key] : [], key)) {
      object(item, key + ' item');
      const reason = key === 'tokens'
        ? '数量表面证据，未核对语义：' + text(item.kind, 'token kind', true) + '=' + text(item.value, 'token value')
        : '不确定数量表达：' + text(item.reason, 'uncertain reason', true);
      all.push({...item, reason});
    }
  }
  all.sort((a, b) => a.start - b.start || a.end - b.end);
  return {full, marks: spans(all, full, 'quantity evidence', 'quote')};
}
function quantityReport(data, prefix = 'quantity') {
  object(data, 'quantity report');
  if (data.version !== 'mechanic-quantity-scopes-v1' || data.semantic_verified !== false) fail('Expected a semantically unverified mechanic-quantity-scopes-v1 report');
  if (!['needs_review', 'quantity_surface_match', 'no_scopes_configured'].includes(data.status)) fail('Invalid quantity report status');
  const release = gate(data, 'quantity report');
  const errors = array(data.configuration_errors, 'quantity configuration errors');
  const scopes = array(data.scopes, 'quantity scopes');
  const findings = [], ids = new Set(), contradictions = [];
  let riskCount = 0, hasUncertain = false;
  for (const [index, scope] of scopes.entries()) {
    object(scope, 'quantity scope');
    const uid = text(scope.unit_id, 'unit ID', true), sid = text(scope.id, 'scope ID', true);
    if (ids.has(sid)) fail('Duplicate quantity scope ID');
    ids.add(sid);
    if (scope.semantic_verified !== false) fail('Quantity scope cannot claim semantic verification');
    if (!['needs_review', 'quantity_surface_match'].includes(scope.status)) fail('Invalid quantity scope status');
    const left = quantitySide(scope.source, 'source', uid), right = quantitySide(scope.translation, 'translation', uid);
    const risks = array(scope.risks, 'risks');
    const details = risks.map(r => {
      object(r, 'risk');
      // Embedded evidence is retained by the producer; it must agree with the
      // displayed scope evidence rather than secretly referring to another span.
      for (const side of ['source', 'translation']) if (has(r, side) && !equal(r[side], scope[side])) fail('Risk evidence disagrees with its scope');
      return text(r.kind, 'risk kind', true) + '：' + text(r.detail, 'risk detail');
    });
    riskCount += risks.length;
    const unsupported = ['source', 'translation'].some(side => has(scope[side], 'unavailable') || (scope[side].uncertain ?? []).length > 0);
    hasUncertain ||= unsupported || scope.status === 'needs_review';
    if (scope.status === 'quantity_surface_match' && (risks.length || unsupported)) contradictions.push(`范围 ${sid} 标为表面相同，但保留了风险或不可比证据`);
    if (scope.status === 'needs_review' && !risks.length) contradictions.push(`范围 ${sid} 待审但未列出风险说明`);
    const locations = [], notes = [];
    for (const side of ['source', 'translation']) {
      const ev = scope[side];
      locations.push(side + ' ' + canonical(ev.selector));
      notes.push(side + ' 定位：' + (ev.field_pointer ?? '不可用') + '；AST：' + canonical(ev.ast_paths ?? []));
      if (has(ev, 'unavailable')) notes.push(side + ' 无法提取：' + ev.unavailable);
    }
    findings.push(finding(`${prefix}-scope-${index}`, (scope.status === 'needs_review' ? '数量风险待审' : '数量表面相同，语义未核对') + ' · ' + sid,
      left.full, right.full,
      '这是风险线索，不是确认译错。数字相同也不能证明主体、单位、条件或语义正确。\n高亮严格对应 extracted_text 的 Unicode 码点偏移，不是原始 Markdown 偏移。\n' + [...details, ...notes].join('\n'),
      'unit ' + uid + ' · ' + locations.join(' / '),
      {original_highlights: left.marks, translation_highlights: right.marks, related_contexts: context(scope.source.raw_text ?? left.full, scope.translation.raw_text ?? right.full)}));
  }
  errors.forEach((error, i) => findings.push(finding(`${prefix}-configuration-${i}`, '配置错误 · 无法完成数量范围核对', '', '', text(error, 'configuration error'), 'quantity configuration')));
  if (has(data, 'risk_count') && integer(data.risk_count, 'risk_count') !== riskCount) contradictions.push(`risk_count=${data.risk_count}，条目实际列出 ${riskCount} 项风险`);
  const blockers = Boolean(errors.length || riskCount || hasUncertain);
  if (release === true && blockers) contradictions.push('数量子门禁允许交付，但存在配置错误、风险或待审范围');
  if (data.status === 'no_scopes_configured' && (scopes.length || errors.length)) contradictions.push('数量报告标为未配置范围，但存在范围或配置错误');
  if (data.status === 'quantity_surface_match' && (!scopes.length || blockers)) contradictions.push('数量报告标为表面相同，但范围为空或存在阻断项');
  if (data.status === 'needs_review' && !blockers) contradictions.push('数量报告标为待审，但未提供待审证据');
  let description = '数量报告仅包含显式范围，未扫描或未配置的内容不算已审。输入状态：' + data.status + '；配置错误：' + errors.length + '；数量子门禁：' + (release === undefined ? '未提供' : gateText(release));
  if (contradictions.length) {
    const detail = '报告状态矛盾，需核对：\n' + contradictions.join('\n');
    description += '\n' + detail;
    findings.unshift(finding(`${prefix}-contradiction`, '数量报告状态矛盾，需核对', '', '', detail, 'saved quantity envelope'));
  }
  return {findings, description, blocked: release === false || blockers, contradictions};
}

class UnsupportedAST extends Error {}
function inline(nodes) {
  return array(nodes, 'AST inlines').map(node => {
    object(node, 'AST inline');
    const kind = text(node.t, 'AST node type', true);
    if (kind === 'Str') return text(node.c, 'AST Str content');
    if (['Space', 'SoftBreak', 'LineBreak'].includes(kind)) return ' ';
    if (['Strong', 'Emph'].includes(kind)) return inline(node.c);
    if (kind === 'Link') {
      const content = array(node.c, 'AST Link content');
      if (content.length !== 3) fail('Malformed AST Link');
      return inline(content[1]);
    }
    throw new UnsupportedAST('unsupported inline: ' + kind);
  }).join('');
}
function blockText(node) {
  object(node, 'AST block');
  const kind = text(node.t, 'AST node type', true);
  if (['Para', 'Plain'].includes(kind)) return inline(node.c);
  if (kind === 'Header') {
    const c = array(node.c, 'AST Header content');
    if (c.length !== 3) fail('Malformed AST Header');
    integer(c[0], 'AST heading level', 1);
    return inline(c[2]);
  }
  throw new UnsupportedAST('unsupported block: ' + kind);
}
function nameText(node, sel) {
  if (sel.kind === 'heading') {
    if (node.t !== 'Header' || node.c?.[0] !== sel.level) fail('Selected block is not the declared heading');
    return pyStrip(blockText(node));
  }
  if (sel.kind !== 'feature_label' || node.t !== 'Para') fail('Feature label requires a top-level paragraph');
  const nodes = array(node.c, 'feature inlines');
  if (!nodes.length || !['Strong', 'Emph'].includes(nodes[0].t)) fail('Feature label must start with parsed emphasis');
  let name = pyStrip(inline(nodes[0].c));
  if (/[:：]$/u.test(name)) name = pyStrip(name.slice(0, -1));
  else {
    let i = 1;
    while (nodes[i]?.t === 'Space') i++;
    if (nodes[i]?.t !== 'Str' || !/^[:：]/u.test(text(nodes[i]?.c, 'delimiter'))) fail('Feature label requires a colon delimiter');
  }
  if (has(sel, 'suffix')) {
    if (!name.endsWith(sel.suffix)) fail('Name does not have its declared literal suffix');
    name = pyStrip(name.slice(0, -sel.suffix.length));
  }
  return name;
}
async function draftReport(data) {
  if (data.approval_status !== 'unconfirmed' || data.semantic_verified !== false) fail('Draft must remain unconfirmed and semantically unverified');
  const preview = object(data.preview, 'draft preview');
  if (preview.format !== 'pbres-config-preview-v1' || preview.approval_status !== 'unconfirmed' || preview.semantic_verified !== false) fail('Invalid draft preview status');
  if (text(data.preview_sha256, 'preview_sha256') !== await digest(preview)) fail('Invalid or modified draft preview SHA-256 snapshot');
  exactKeys(preview.selection, ['unit_id', 'resource_id'], 'preview selection');
  const uid = text(preview.selection.unit_id, 'unit ID', true), rid = text(preview.selection.resource_id, 'resource ID', true);
  if (!equal(data.proposed_parent, {...preview.selection, approval_status: 'unconfirmed'})) fail('Draft parent disagrees with selected snapshot');
  if (has(preview, 'review_status')) {
    object(preview.review_status, 'preview review_status');
    for (const key of ['parent_attribution', 'alignment', 'homonym_identity']) if (preview.review_status[key] !== 'unconfirmed') fail('Preview review status must remain unconfirmed');
  }
  const sides = object(preview.sides, 'preview sides'), raw = {}, blocks = {};
  for (const side of ['source', 'translation']) {
    const saved = object(sides[side], side + ' snapshot');
    raw[side] = text(saved.raw_text, side + ' raw text');
    blocks[side] = array(saved.blocks, side + ' blocks');
    blocks[side].forEach((b, i) => {
      object(b, 'preview block');
      if (b.block !== i || b.ast_path !== '/blocks/' + i) fail('Block index or AST path disagrees with snapshot');
      object(b.ast, 'saved AST');
      if (text(b.node_type, 'node type', true) !== text(b.ast.t, 'AST node type', true)) fail('Block type disagrees with saved AST');
    });
  }
  const selectedBlock = (side, sel) => {
    integer(sel.block, 'selected block');
    const selected = blocks[side][sel.block];
    if (!selected) fail('Selected block is missing');
    return selected;
  };
  const choices = array(preview.name_choices, 'name choices');
  const names = array(data.proposed_name_bindings, 'proposed name bindings');
  const scopes = array(data.proposed_quantity_scopes, 'proposed quantity scopes');
  if (!names.length && !scopes.length) fail('Draft requires at least one explicit choice');
  const findings = [], targets = new Set(), endpoints = new Set(), ids = new Set();
  for (const [index, item] of names.entries()) {
    object(item, 'name binding');
    if (item.approval_status !== 'unconfirmed' || item.unit_id !== uid || item.resource_id !== rid) fail('Name selection disagrees with unconfirmed parent');
    const sel = selector(item.selector, 'name');
    if (!['heading', 'feature_label'].includes(sel.kind)) fail('Draft names require Markdown slot selectors');
    const selected = selectedBlock('translation', sel), candidate = object(selected.name_candidate, 'name candidate');
    const base = {...sel}; delete base.suffix;
    if (!equal(base, candidate.selector)) fail('Name selector disagrees with snapshot');
    if (targets.has(selected.block)) fail('Duplicate name target');
    targets.add(selected.block);
    const pointer = text(item.name_pointer, 'name pointer', true);
    const rows = choices.filter(row => object(row, 'name choice').resource_id === rid && row.name_pointer === pointer);
    if (rows.length !== 1 || rows[0].translation !== text(item.expected_name, 'expected name', true)) fail('Name pointer or expected name disagrees with snapshot');
    const observed = text(item.observed_name, 'observed name');
    let snapshotName = text(candidate.text, 'name candidate text');
    if (has(sel, 'suffix')) {
      if (!snapshotName.endsWith(sel.suffix)) fail('Name candidate does not have its literal suffix');
      snapshotName = pyStrip(snapshotName.slice(0, -sel.suffix.length));
    }
    if (snapshotName !== observed) fail('Observed name disagrees with snapshot candidate');
    let display, marks = [], body = raw.translation;
    try {
      if (nameText(selected.ast, base) !== candidate.text || nameText(selected.ast, sel) !== observed) fail('Observed name disagrees with selected AST slot');
      body = blockText(selected.ast);
      const start = cp(body).length - cp(pyLeft(body)).length;
      if (cp(body).slice(start, start + cp(observed).length).join('') !== observed) fail('Name prefix does not match selected block');
      marks = observed ? [{start, end: start + cp(observed).length, text: observed, reason: '人工选中的名称槽位；身份未确认'}] : [];
      display = '译文显示所选块的可见文字；只高亮名称槽位，后缀及重复正文词不高亮。';
    } catch (error) {
      if (!(error instanceof UnsupportedAST)) throw error;
      body = raw.translation;
      display = '浏览器适配器不支持此 AST 结构；仅显示完整原始 Markdown 和已保存的选择值，无法在正文中验证名称位置，不生成高亮。原因：' + error.message;
    }
    const row = rows[0];
    findings.push(finding('draft-name-' + index, '未确认名称槽位 · ' + item.expected_name, raw.source, body,
      'UNCONFIRMED：资源归属、名称身份及原译文对应关系均待核对。\n未指定原文名称位置：左侧保留完整原文，不按同名词面推断位置。\n' + display + '\n资源原名参考（不是正文位置证据）：' + canonical(row.original ?? null) + '；状态：' + text(row.status, 'original status') + '\n期望名称：' + item.expected_name + '；所选名称：' + observed + '\n资源：' + rid + '；名称路径：' + pointer,
      'unit ' + uid + ' · translation ' + selected.ast_path, {translation_highlights: marks, related_contexts: context(raw.source, raw.translation)}));
  }
  for (const [index, item] of scopes.entries()) {
    object(item, 'draft quantity scope');
    if (item.approval_status !== 'unconfirmed' || item.unit_id !== uid) fail('Quantity selection disagrees with unconfirmed parent');
    const sid = text(item.id, 'draft scope ID', true);
    if (ids.has(sid)) fail('Duplicate draft scope ID');
    ids.add(sid);
    const extracted = {}, highlights = {}, locations = [], unsupported = [];
    for (const side of ['source', 'translation']) {
      const candidate = object(item[side], 'quantity candidate');
      exactKeys(candidate, ['selector', 'text'], 'quantity candidate');
      selector(candidate.selector);
      if (candidate.selector.kind !== 'block') fail('Draft quantity choices require block selectors');
      text(candidate.text, 'quantity candidate text');
      const selected = selectedBlock(side, candidate.selector), endpoint = side + ':' + selected.block;
      if (endpoints.has(endpoint)) fail('Duplicate quantity endpoint');
      endpoints.add(endpoint);
      if (!equal(candidate, selected.quantity_candidate)) fail('Quantity choice disagrees with snapshot');
      try {
        extracted[side] = blockText(selected.ast);
        if (extracted[side] !== candidate.text) fail('Quantity text disagrees with selected AST block');
        highlights[side] = whole(extracted[side], '未确认的所选范围，不是数量风险');
      } catch (error) {
        if (!(error instanceof UnsupportedAST)) throw error;
        extracted[side] = raw[side]; highlights[side] = [];
        unsupported.push(side + '：浏览器适配器不支持此 AST 结构；仅显示完整原始 Markdown，不生成高亮。已保存的所选文本（未重新验证）：' + candidate.text + '。原因：' + error.message);
      }
      locations.push(side + ' ' + selected.ast_path);
    }
    findings.push(finding('draft-quantity-' + index, '未确认数量范围 · ' + sid, extracted.source, extracted.translation,
      'UNCONFIRMED：两侧整块高亮只表示人工选择的范围，不是数字风险证据。\n此草稿未运行数字比较；没有批准范围对应关系，数字相同也不能证明语义正确。' + (unsupported.length ? '\n' + unsupported.join('\n') : ''),
      'unit ' + uid + ' · ' + locations.join(' / '), {original_highlights: highlights.source, translation_highlights: highlights.translation, related_contexts: context(raw.source, raw.translation)}));
  }
  return {findings, description: '配置草稿：仅显示已显式选择的位置；未选择的内容不算已审。preview SHA-256 已核对，仅验证快照内一致性，不是签名，也不证明与当前项目文件或原始 Markdown 的解析一致。'};
}

function nameReport(data) {
  object(data, 'name_binding_check');
  const release = gate(data, 'name check', true);
  const rows = array(data.bindings, 'name bindings'), errors = array(data.configuration_errors, 'name configuration errors');
  const findings = []; let issueCount = 0;
  rows.forEach((row, i) => {
    object(row, 'name binding');
    const uid = text(row.unit_id, 'name unit ID', true), rid = text(row.resource_id, 'name resource ID', true);
    const pointer = text(row.name_pointer, 'name pointer', true), sel = selector(row.selector, 'name');
    const expected = text(row.expected, 'expected name'), actual = has(row, 'actual') ? text(row.actual, 'actual name') : '';
    const issues = array(row.findings, 'name findings'); issueCount += issues.length;
    const details = issues.map(issue => text(object(issue, 'name finding').kind, 'name finding kind') + '：' + text(issue.text, 'name finding text'));
    const title = issues.length ? '名称检查待处理' : !has(row, 'actual') ? '名称证据缺失' : '名称检查未列出问题，语义未核对';
    findings.push(finding('check-name-' + i, title + ' · ' + expected, '', actual,
      '这是已保存的名称检查结果，不重新执行检查，也不证明资源归属或语义正确。\n期望名称（资源表中文值，不是原文）：' + expected + '\n实际提取名称：' + (has(row, 'actual') ? actual || '空字符串（已提取但值为空）' : '未提供，不能补造') + '\n证据缺口：此检查结果没有原文正文、完整译文或正文字符偏移；右侧仅显示已保存的提取值，不推断对应原文，也不生成正文高亮。\n资源：' + rid + '；名称路径：' + pointer + '\n' + (details.length ? details.join('\n') : '此行未列出问题；未列出问题不等于人工确认。'),
      'unit ' + uid + ' · translation ' + canonical(sel)));
  });
  errors.forEach((error, i) => findings.push(finding('check-name-configuration-' + i, '名称配置错误 · 无法完成名称核对', '', '', text(error, 'name configuration error') + '\n检查结果未提供可定位正文证据，不生成高亮。', 'name configuration')));
  const missing = rows.some(row => !has(row, 'actual'));
  const contradictory = release && Boolean(errors.length || issueCount || missing);
  return {findings, blocked: !release || Boolean(errors.length || issueCount || missing), contradictions: contradictory ? ['名称子门禁允许交付，但存在配置错误、问题或缺失的提取证据'] : [], description: '名称检查：' + gateText(release) + '；绑定条目：' + rows.length + '；配置错误：' + errors.length};
}
function checkReport(data) {
  const release = gate(data, 'top-level check');
  let findings = [], coverage = [], blockers = [], contradictions = [];
  if (has(data, 'semantic_verified') && data.semantic_verified !== false) fail('Combined check cannot claim semantic verification');
  if (has(data, 'identity_errors') || has(data, 'units')) {
    const errors = array(data.identity_errors, 'identity errors'), units = array(data.units, 'base delivery units');
    errors.forEach((error, i) => findings.push(finding('check-identity-' + i, '基础交付身份错误', '', '', text(error, 'identity error') + '\n未提供完整正文证据，不推断高亮。', 'identity')));
    let count = 0;
    units.forEach((unit, i) => {
      object(unit, 'delivery unit');
      const uid = text(unit.id, 'delivery unit ID', true), issues = array(unit.findings, 'base delivery findings');
      count += issues.length;
      if (issues.length) {
        issues.forEach(issue => { object(issue, 'delivery finding'); text(issue.kind, 'delivery finding kind'); text(issue.text, 'delivery finding text'); });
        findings.push(finding('check-base-' + i, '基础交付阻断项 · ' + uid, '', '', '保留检查器报告的全部问题字段；没有完整正文或可靠的共同偏移基准，不生成高亮。\n' + issues.map(issue => canonical(issue)).join('\n'), 'unit ' + uid));
      }
    });
    coverage.push('基础交付：身份错误 ' + errors.length + '；正文阻断项 ' + count);
    blockers.push(Boolean(errors.length || count));
  } else coverage.push('基础交付结果：未提供，不能由子检查推断');
  for (const [key, label, adapt] of [['name_binding_check', '名称检查', nameReport], ['quantity_risk_check', '数量检查', quantityReport]]) {
    if (!has(data, key)) { coverage.push(label + '：未提供，不能视为已检查或通过'); continue; }
    object(data[key], key); gate(data[key], key, true);
    const result = adapt(data[key]);
    findings.push(...result.findings); coverage.push(result.description); blockers.push(result.blocked); contradictions.push(...result.contradictions);
  }
  if (release === true && blockers.some(Boolean)) contradictions.unshift('顶层允许交付，但存在阻断项；子项无阻断也不能替代总门禁');
  const gateNotice = contradictions.length ? '报告状态矛盾，需核对' : release === undefined ? '总门禁状态缺失' : release ? '总门禁：未见阻断' : '总门禁：阻止交付';
  const description = '完整检查报告 · ' + gateNotice + '\n顶层 release_allowed：' + (release === undefined ? '未提供' : String(release)) + '；' + (release === undefined ? '未提供总门禁状态' : gateText(release)) + '\n' + coverage.join('\n') + (contradictions.length ? '\n输入状态矛盾：\n' + contradictions.join('\n') : '') + '\n各项仅陈述检查器保存的结果。没有执行的名称/数量检查不算通过；数字相同不能证明语义正确。';
  findings.unshift(finding('check-overview', '完整检查报告 · ' + gateNotice, '', '', description, 'saved check envelope'));
  return {findings, description, notice: gateNotice + ' · ' + NOTICE};
}

function auditReport(data) {
  if (data.schemaVersion !== 1) fail('Unsupported audit schemaVersion');
  if (has(data, 'reportId')) text(data.reportId, 'reportId', true);
  const title = text(data.title, 'report title');
  const ids = new Set();
  const findings = array(data.findings, 'audit findings').map((row, index) => {
    object(row, 'audit finding');
    const identity = row.finding_id ?? row.id;
    if (!(typeof identity === 'string' && identity.trim()) && !Number.isSafeInteger(identity)) fail('Audit finding requires a stable nonempty id');
    const id = String(identity);
    if (ids.has(id)) fail('Duplicate audit finding ID'); ids.add(id);
    for (const key of ['title', 'location', 'problem', 'suggestion', 'original', 'translation']) text(row[key], 'finding ' + key);
    if (has(row, 'status') && !['confirmed', 'uncertain'].includes(row.status)) fail('Invalid audit finding status');
    const related = array(has(row, 'related_contexts') ? row.related_contexts : [], 'related contexts').map(c => {
      object(c, 'related context');
      return {label: text(c.label, 'context label'), original: text(c.original, 'context original'), translation: text(c.translation, 'context translation')};
    });
    const result = finding(id, row.title, row.original, row.translation, row.problem, row.location, {suggestion: row.suggestion, related_contexts: related});
    for (const side of ['original', 'translation']) {
      // This renderer never turns focus text into a highlight. Saved highlight
      // ranges must carry their own exact quoted text and reason.
      result[side + '_highlights'] = spans(has(row, side + '_highlights') ? row[side + '_highlights'] : [], row[side], side + ' highlights');
      const hasFocus = has(row, side + '_focus'), hasSegments = has(row, side + '_segments'), hasRanges = has(row, side + '_focus_ranges');
      const full = row[side], points = cp(full);
      if (hasFocus) text(row[side + '_focus'], side + ' focus');
      const pieces = hasSegments ? array(row[side + '_segments'], side + ' segments') : hasFocus ? [row[side + '_focus']] : [];
      pieces.forEach(piece => { text(piece, side + ' segment'); if (!full.includes(piece)) fail('Focus segment must be an exact source substring'); });
      if (hasSegments && hasFocus && row[side + '_focus'] !== pieces.join('\n\n')) fail('Focus must match segment join');
      if (hasRanges) {
        const ranges = array(row[side + '_focus_ranges'], side + ' focus ranges');
        if ((!hasFocus && !hasSegments) || ranges.length !== pieces.length) fail('Focus range/segment count mismatch');
        let previous = 0;
        ranges.forEach((r, i) => {
          object(r, 'focus range');
          const start = integer(r.start, 'focus start'), end = integer(r.end, 'focus end');
          if (start > end || end > points.length || start < previous || points.slice(start, end).join('') !== pieces[i]) fail('Focus range must anchor its exact source occurrence');
          previous = end;
        });
      }
    }
    if (has(row, 'status')) result.problem = '输入报告标记：' + row.status + '；本页未重新执行语义核查。\n' + result.problem;
    // Keep saved reference text visible without rendering URLs or active markup.
    for (const key of ['reference_evidence', 'official_evidence']) if (has(row, key) && row[key] !== null) {
      object(row[key], key);
      result.related_contexts.push({label: key === 'official_evidence' ? '输入报告保存的官方证据（本页未验证来源）' : '输入报告保存的参考证据（本页未验证来源）', original: text(row[key].text, key + ' text'), translation: ''});
    }
    return result;
  });
  const description = ['已保存的审阅报告；本页验证文本范围，不重新执行语义检查。空队列或阅读完成不等于审核通过。'];
  for (const key of ['sourceDescription', 'notes', 'emptyMessage', 'sourceCutoff']) if (has(data, key)) description.push(text(data[key], key));
  if (has(data, 'progressNotice')) description.push('输入报告提示：' + text(data.progressNotice, 'progressNotice'));
  return {title, findings, description: description.join('\n')};
}

/** Normalize one supported saved report into inert, code-point-anchored evidence. */
export async function normalizeReport(data) {
  jsonValue(data);
  object(data, 'report');
  let result;
  if (has(data, 'format')) {
    if (data.format !== 'pbres-config-draft-v1') fail('Unsupported report format');
    result = await draftReport(data);
  } else if (has(data, 'schemaVersion')) {
    result = auditReport(data);
  } else if (has(data, 'name_binding_check') || has(data, 'quantity_risk_check') || (has(data, 'release_allowed') && has(data, 'identity_errors') && has(data, 'units'))) {
    result = checkReport(data);
  } else if (data.version === 'mechanic-quantity-scopes-v1') {
    result = quantityReport(data);
    if (result.contradictions.length) result.notice = '报告状态矛盾，需核对 · ' + NOTICE;
  } else fail('Unsupported report. Expected config draft, quantity report, complete check, or schemaVersion 1 audit report');
  return {title: result.title ?? '离线配置与数量证据审阅 · 未确认', notice: result.notice ?? NOTICE, description: result.description, findings: result.findings};
}
