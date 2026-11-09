'use strict';

const {test} = require('node:test');
const assert = require('node:assert/strict');
const {BRANCHES, STATUS, SHARDS, description, shardContext, prepare, finish, cancelSuperseded, automationOnly, documentationOnly,
  validationMode, settling} = require('../agent-integration.cjs');

const branchesOf = matrix => [...new Set(matrix.include.map(item => item.branch))];

function fixture() {
  const context = {repo: {owner: 'owner', repo: 'gokworks'}, serverUrl: 'https://github.com', runId: 42};
  const refs = {'main': 'a'.repeat(40), 'agent/codex': 'b'.repeat(40), 'agent/claude': 'c'.repeat(40)};
  const statuses = new Map(), pulls = [], calls = [], notices = [];
  const core = {notice: text => notices.push(text)};
  let nextNumber = 1;
  function pull(branch, extra = {}) {
    const item = {number: nextNumber++, state: 'open', draft: false, merged_at: null,
      base: {ref: 'main', sha: refs.main},
      head: {ref: branch, sha: refs[branch], repo: {full_name: 'owner/gokworks'}}, ...extra};
    pulls.push(item);
    return item;
  }
  function status(branch, state = 'success', base = refs.main) {
    statuses.set(refs[branch], [{context: STATUS, state, description: description(base)}]);
  }
  const github = {rest: {
    actions: {
      createWorkflowDispatch: async args => { calls.push(['dispatch', args]); return {status: 204}; },
    },
    repos: {
      getBranch: async ({branch}) => {
        if (!refs[branch]) throw Object.assign(new Error('Not found'), {status: 404});
        return {data: {commit: {sha: refs[branch]}}};
      },
      compareCommitsWithBasehead: async ({basehead}) => ({data: {ahead_by: basehead.split('...')[1] === refs.main ? 0 : 1}}),
      listCommitStatusesForRef: async ({ref}) => ({data: statuses.get(ref) || []}),
      createCommitStatus: async args => {
        calls.push(['status', args]);
        statuses.set(args.sha, [args, ...(statuses.get(args.sha) || [])]);
        return {data: args};
      },
    },
    pulls: {
      list: async ({head}) => ({data: pulls.filter(item => head === `owner:${item.head.ref}`)}),
      create: async args => {
        calls.push(['create', args]);
        return {data: pull(args.head)};
      },
      get: async ({pull_number}) => ({data: pulls.find(item => item.number === pull_number)}),
      merge: async args => {
        calls.push(['merge', args]);
        const item = pulls.find(item => item.number === args.pull_number);
        assert.equal(args.sha, refs[item.head.ref]);
        refs.main = `merged-${args.pull_number}`;
        item.state = 'closed'; item.merged_at = 'now';
        return {data: {merged: true}};
      },
    },
  }};
  return {github, context, core, refs, statuses, pulls, calls, notices, pull, status};
}

function candidate(f, branch = 'agent/codex') {
  const p = f.pull(branch);
  return {branch, head: f.refs[branch], base: f.refs.main, pull: p.number, cached: false};
}

test('only the two agent branches are eligible', () => {
  assert.deepEqual(BRANCHES, ['agent/codex', 'agent/claude']);
});

test('unchanged or missing branches do not create PRs', async () => {
  const f = fixture();
  f.refs['agent/codex'] = f.refs.main;
  delete f.refs['agent/claude'];
  assert.deepEqual(await prepare(f), {include: []});
  assert.deepEqual(f.calls, []);
});

test('already merged ancestor branches do not create another PR', async () => {
  const f = fixture();
  f.github.rest.repos.compareCommitsWithBasehead = async () => ({data: {ahead_by: 0}});
  assert.deepEqual(await prepare(f), {include: []});
});

test('both changed branches get a PR and pending status for the exact main/head pair', async () => {
  const f = fixture();
  const matrix = await prepare(f);
  assert.equal(branchesOf(matrix).length, 2);
  assert.equal(matrix.include.length, 2 * SHARDS);
  for (const branch of BRANCHES) {
    assert.deepEqual(matrix.include.filter(item => item.branch === branch).map(item => `${item.shard}/${item.shards}`),
      Array.from({length: SHARDS}, (_, index) => `${index + 1}/${SHARDS}`));
  }
  assert.equal(f.calls.filter(([name]) => name === 'create').length, 2);
  for (const item of matrix.include) {
    assert.equal(item.base, f.refs.main);
    assert.equal(item.head, f.refs[item.branch]);
    assert.equal(item.cached, false);
    const proof = f.statuses.get(item.head)[0];
    assert.equal(proof.state, 'pending');
    assert.equal(proof.description, description(item.base));
    assert.equal(proof.target_url, 'https://github.com/owner/gokworks/actions/runs/42');
  }
});

test('existing open PRs are reused on later scans', async () => {
  const f = fixture(); f.pull('agent/codex'); f.pull('agent/claude');
  await prepare(f);
  assert.equal(f.calls.filter(([name]) => name === 'create').length, 0);
});

test('draft and deliberately closed PRs are left alone', async () => {
  const f = fixture();
  f.pull('agent/codex', {draft: true}); f.pull('agent/claude', {state: 'closed'});
  assert.deepEqual(await prepare(f), {include: []});
  assert.deepEqual(f.calls, []);
});

test('a new head may get a PR after an older head was closed', async () => {
  const f = fixture();
  f.pull('agent/codex', {state: 'closed'}); f.refs['agent/codex'] = 'd'.repeat(40);
  assert.equal(branchesOf(await prepare(f)).length, 2);
});

for (const state of ['failure', 'error']) {
  test(`unchanged ${state} is not retested every scheduled scan`, async () => {
    const f = fixture(); f.status('agent/codex', state); f.status('agent/claude', state);
    assert.deepEqual(await prepare(f), {include: []});
    assert.deepEqual(f.calls, []);
  });
}

test('manual retry reruns a failed pair', async () => {
  const f = fixture(); f.status('agent/codex', 'failure'); f.status('agent/claude', 'error');
  const matrix = await prepare({...f, retryFailed: true});
  assert.equal(branchesOf(matrix).length, 2);
  assert.ok(matrix.include.every(item => item.cached === false));
});

test('a successful pair may reuse its result without rerunning Windows tests', async () => {
  const f = fixture(); f.status('agent/codex'); f.status('agent/claude');
  assert.ok((await prepare(f)).include.every(item => item.cached === true));
  assert.equal(f.calls.filter(([name]) => name === 'status').length, 0);
});

for (const state of ['success', 'failure', 'error']) {
  test(`main advancing invalidates a previous ${state} result`, async () => {
    const f = fixture(); f.status('agent/codex', state, 'older-main'); f.status('agent/claude', state, 'older-main');
    assert.ok((await prepare(f)).include.every(item => item.cached === false));
  });
}

test('a pending result from a cancelled run is retried', async () => {
  const f = fixture(); f.status('agent/codex', 'pending'); f.status('agent/claude', 'pending');
  assert.ok((await prepare(f)).include.every(item => item.cached === false));
});

test('unexpected API errors fail instead of certifying success', async () => {
  const f = fixture();
  f.github.rest.repos.getBranch = async () => { throw Object.assign(new Error('Forbidden'), {status: 403}); };
  await assert.rejects(prepare(f), /Forbidden/);
});

for (const state of [null, 'pending', 'failure', 'error']) {
  test(`no merge with ${state} verification`, async () => {
    const f = fixture(), item = candidate(f);
    if (state) f.status(item.branch, state);
    assert.deepEqual(await finish({...f, candidates: [item]}), []);
    assert.equal(f.calls.length, 0);
  });
}

test('a success for a different main commit does not permit merging', async () => {
  const f = fixture(), item = candidate(f); f.status(item.branch, 'success', 'older-main');
  assert.deepEqual(await finish({...f, candidates: [item]}), []);
});

for (const changed of ['main', 'agent/codex']) {
  test(`${changed} advancing after validation prevents merge`, async () => {
    const f = fixture(), item = candidate(f); f.status(item.branch);
    f.refs[changed] = 'advanced';
    assert.deepEqual(await finish({...f, candidates: [item]}), []);
    assert.equal(f.calls.length, 0);
  });
}

for (const problem of ['closed', 'draft', 'wrong-base', 'wrong-head', 'advanced-head', 'fork']) {
  test(`a ${problem} PR cannot enter the merge path`, async () => {
    const f = fixture(), item = candidate(f); f.status(item.branch);
    const p = f.pulls[0];
    if (problem === 'closed') p.state = 'closed';
    if (problem === 'draft') p.draft = true;
    if (problem === 'wrong-base') p.base.ref = 'release';
    if (problem === 'wrong-head') p.head.ref = 'other';
    if (problem === 'advanced-head') p.head.sha = 'advanced';
    if (problem === 'fork') p.head.repo.full_name = 'someone/fork';
    assert.deepEqual(await finish({...f, candidates: [item]}), []);
    assert.equal(f.calls.length, 0);
  });
}

test('successful validation merges with the exact head SHA and preserves the source branch', async () => {
  const f = fixture(), item = candidate(f); f.status(item.branch);
  assert.deepEqual(await finish({...f, candidates: [item]}), [item.pull]);
  const request = f.calls.find(([name]) => name === 'merge')[1];
  assert.equal(request.sha, item.head);
  assert.equal(request.merge_method, 'merge');
  assert.equal(f.refs[item.branch], item.head);
  const followup = f.calls.find(([name]) => name === 'dispatch')[1];
  assert.equal(followup.ref, 'main');
  assert.equal(followup.workflow_id, 'agent-integration.yml');
});

test('merging one agent invalidates the other agents old base proof', async () => {
  const f = fixture();
  const items = BRANCHES.map(branch => candidate(f, branch));
  for (const branch of BRANCHES) f.status(branch);
  assert.deepEqual(await finish({...f, candidates: items}), [items[0].pull]);
  assert.equal(f.calls.filter(([name]) => name === 'merge').length, 1);
});

for (const code of [405, 409, 422]) {
  test(`merge rejection ${code} keeps the PR open`, async () => {
    const f = fixture(), item = candidate(f); f.status(item.branch);
    f.github.rest.pulls.merge = async () => { throw Object.assign(new Error('Blocked'), {status: code}); };
    assert.deepEqual(await finish({...f, candidates: [item]}), []);
    assert.equal(f.pulls[0].state, 'open');
  });
}

test('missing merge permission is reported as an error', async () => {
  const f = fixture(), item = candidate(f); f.status(item.branch);
  f.github.rest.pulls.merge = async () => { throw Object.assign(new Error('Forbidden'), {status: 403}); };
  await assert.rejects(finish({...f, candidates: [item]}), /Forbidden/);
});

test('unsupported branches are rejected even with a supplied candidate', async () => {
  const f = fixture();
  await assert.rejects(finish({...f, candidates: [{branch: 'untrusted'}]}), /Unsupported/);
});

test('no follow-up is dispatched when no PR was merged', async () => {
  const f = fixture(), item = candidate(f);
  await finish({...f, candidates: [item]});
  assert.equal(f.calls.filter(([name]) => name === 'dispatch').length, 0);
});

test('scheduled scan remains a fallback when follow-up dispatch is unavailable', async () => {
  const f = fixture(), item = candidate(f); f.status(item.branch);
  f.github.rest.actions.createWorkflowDispatch = async () => { throw new Error('Workflow is being indexed'); };
  assert.deepEqual(await finish({...f, candidates: [item]}), [item.pull]);
  assert.ok(f.notices.some(message => message.includes('scheduled scan')));
});

test('a new push cancels only in-progress integration runs of its superseded head', async () => {
  const f = fixture();
  f.context.eventName = 'push'; f.context.ref = 'refs/heads/agent/codex'; f.context.sha = f.refs['agent/codex'];
  const old = {id: 1, name: 'Agent integration', status: 'in_progress', event: 'push', head_branch: 'agent/codex', head_sha: 'old'};
  f.github.rest.actions.listWorkflowRuns = async () => ({data: {workflow_runs: [old,
    {...old, id: 2, head_sha: f.context.sha}, {...old, id: 3, head_branch: 'agent/claude'},
    {...old, id: 4, event: 'workflow_dispatch'}, {...old, id: 5, status: 'completed'},
    {...old, id: 6, name: 'Other workflow'}, {...old, id: 7, status: 'queued'}]}});
  f.github.rest.actions.cancelWorkflowRun = async args => f.calls.push(['cancel', args.run_id]);
  assert.deepEqual(await cancelSuperseded(f), [1]);
  assert.deepEqual(f.calls, [['cancel', 1]]);
});

test('a stale push notification cannot cancel the current validation', async () => {
  const f = fixture();
  f.context.eventName = 'push'; f.context.ref = 'refs/heads/agent/codex'; f.context.sha = 'old';
  assert.deepEqual(await cancelSuperseded(f), []);
  assert.deepEqual(f.calls, []);
});

test('scheduled runs never cancel an in-progress validation', async () => {
  const f = fixture(); f.context.eventName = 'schedule';
  assert.deepEqual(await cancelSuperseded(f), []);
});

test('historical PR base metadata does not block a validated live main snapshot', async () => {
  const f = fixture(), item = candidate(f); f.status(item.branch);
  f.pulls[0].base.sha = 'base-recorded-when-pr-opened';
  assert.deepEqual(await finish({...f, candidates: [item]}), [item.pull]);
});

test('main advancing while PR metadata is fetched still prevents merge', async () => {
  const f = fixture(), item = candidate(f); f.status(item.branch);
  f.github.rest.pulls.get = async () => { f.refs.main = 'advanced'; return {data: f.pulls[0]}; };
  assert.deepEqual(await finish({...f, candidates: [item]}), []);
  assert.equal(f.calls.filter(([name]) => name === 'merge').length, 0);
});

test('known CI-only changes select focused checks', () => {
  assert.equal(automationOnly({files: [{filename: '.github/scripts/agent-integration.cjs'},
    {filename: '.github/workflows/agent-integration.yml'}]}), true);
});

for (const files of [undefined, [], [{filename: 'gui_qt/app.py'}],
  [{filename: '.github/scripts/agent-integration.cjs'}, {filename: 'gui_qt/app.py'}],
  [{filename: '.github/scripts/agent-integration.cjs', previous_filename: 'modules/dfm_analyzer/ui.py'}],
  Array.from({length: 300}, () => ({filename: '.github/scripts/agent-integration.cjs'}))]) {
  test('application, missing or truncated scope needs the full suite: ' + JSON.stringify(files)?.slice(0, 80), () => {
    assert.equal(automationOnly({files}), false);
  });
}

test('a passed source head needs only CI checks when main changed exclusively in CI files', async () => {
  const f = fixture(), oldBase = 'd'.repeat(40);
  f.github.rest.repos.compareCommitsWithBasehead = async args => {
    assert.equal(args.basehead, `${oldBase}...${f.refs.main}`);
    return {data: {status: 'ahead', behind_by: 0, files: [{filename: '.github/scripts/agent-integration.cjs'}]}};
  };
  assert.equal(await validationMode(f.github, f.context.repo, {files: [{filename: 'modules/dfm_analyzer/ui.py'}]},
    {state: 'success', description: description(oldBase)}, f.refs.main), 'automation');
});

for (const reason of ['application-change', 'failed-proof', 'diverged', 'missing-files']) {
  test(`cross-base reuse is refused for ${reason}`, async () => {
    const f = fixture(), oldBase = 'd'.repeat(40);
    const delta = {status: reason === 'diverged' ? 'diverged' : 'ahead', behind_by: 0,
      files: reason === 'missing-files' ? undefined : [{filename: reason === 'application-change' ? 'gui_qt/app.py' : '.github/scripts/agent-integration.cjs'}]};
    f.github.rest.repos.compareCommitsWithBasehead = async () => ({data: delta});
    assert.equal(await validationMode(f.github, f.context.repo, {},
      {state: reason === 'failed-proof' ? 'failure' : 'success', description: description(oldBase)}, f.refs.main), 'full');
  });
}

test('a passed source head needs only CI checks when main changed only by EXE build status commits', async () => {
  const f = fixture(), oldBase = 'd'.repeat(40);
  f.github.rest.repos.compareCommitsWithBasehead = async () => ({data: {status: 'ahead', behind_by: 0,
    files: [{filename: 'README.md'}, {filename: 'packaging/windows-build-status.json'}, {filename: 'packaging/latest-windows.json'}]}});
  assert.equal(await validationMode(f.github, f.context.repo, {files: [{filename: 'modules/dfm_analyzer/ui.py'}]},
    {state: 'success', description: description(oldBase)}, f.refs.main), 'automation');
});

test('a branch changing build status files is still tested in full', () => {
  assert.equal(automationOnly({files: [{filename: 'README.md'}]}), false);
  assert.equal(automationOnly({files: [{filename: 'packaging/latest-windows.json'}]}), false);
});

test('build status plus application changes on main still need the full suite', async () => {
  const f = fixture(), oldBase = 'd'.repeat(40);
  f.github.rest.repos.compareCommitsWithBasehead = async () => ({data: {status: 'ahead', behind_by: 0,
    files: [{filename: 'packaging/windows-build-status.json'}, {filename: 'gui_qt/app.py'}]}});
  assert.equal(await validationMode(f.github, f.context.repo, {},
    {state: 'success', description: description(oldBase)}, f.refs.main), 'full');
});

test('documentation-only branches take the light docs path', async () => {
  const docs = {files: [{filename: 'README.md'}, {filename: 'docs/readme/nesting.png'}, {filename: 'modules/x/README.md'},
    {filename: '.gitignore'}]};
  assert.equal(documentationOnly(docs), true);
  for (const name of ['docs/inventory.json', 'gui_qt/app.py', 'docs/readme/script.py']) {
    assert.equal(documentationOnly({files: [...docs.files, {filename: name}]}), false, name);
  }
  const f = fixture();
  assert.equal(await validationMode(f.github, f.context.repo, docs, undefined, f.refs.main), 'docs');
});

test('docs and cached validations run as a single job; only full runs are split', async () => {
  const f = fixture();
  f.github.rest.repos.compareCommitsWithBasehead = async ({basehead}) => ({data: {ahead_by: 1,
    files: [{filename: basehead.endsWith(f.refs['agent/codex']) ? 'README.md' : 'gui_qt/app.py'}]}});
  const matrix = await prepare(f);
  const codex = matrix.include.filter(item => item.branch === 'agent/codex');
  assert.deepEqual(codex.map(item => [item.mode, item.shard, item.shards]), [['docs', 1, 1]]);
  assert.equal(matrix.include.filter(item => item.branch === 'agent/claude').length, SHARDS);
});

test('a branch pushed moments ago waits for the push burst to settle', async () => {
  const f = fixture(), now = Date.parse('2026-11-09T12:00:00Z');
  const getBranch = f.github.rest.repos.getBranch;
  f.github.rest.repos.getBranch = async args => {
    const {data} = await getBranch(args);
    const minutes = args.branch === 'agent/codex' ? 2 : 6;
    return {data: {commit: {...data.commit, commit: {committer: {date: new Date(now - minutes * 60000).toISOString()}}}}};
  };
  assert.deepEqual(branchesOf(await prepare({...f, now})), ['agent/claude']);
  assert.ok(f.notices.some(text => text.startsWith('agent/codex') && text.includes('waiting')));
  assert.deepEqual(branchesOf(await prepare({...f, now, context: {...f.context, eventName: 'workflow_dispatch'}})).sort(),
    [...BRANCHES].sort());
  assert.equal(settling({commit: {committer: {date: 'garbage'}}}, now), false);
});

function shardItems(item) {
  return Array.from({length: SHARDS}, (_, index) => ({...item, mode: 'full', shard: index + 1, shards: SHARDS}));
}

function shardStatus(f, item, states) {
  states.forEach((state, index) => f.statuses.set(item.head, [{context: shardContext(index + 1, SHARDS), state,
    description: description(item.base)}, ...(f.statuses.get(item.head) || [])]));
}

test('parallel parts that all passed are combined into one success and merged', async () => {
  const f = fixture(), item = candidate(f);
  shardStatus(f, item, Array(SHARDS).fill('success'));
  assert.deepEqual(await finish({...f, candidates: shardItems(item)}), [item.pull]);
  const combined = f.calls.filter(([name, args]) => name === 'status' && args.context === STATUS);
  assert.deepEqual(combined.map(([, args]) => args.state), ['success']);
  assert.equal(f.calls.filter(([name]) => name === 'merge').length, 1);
});

for (const states of [['success', 'failure', 'success'], ['success', 'success']]) {
  test(`one failed or missing part fails the whole validation: ${states}`, async () => {
    const f = fixture(), item = candidate(f);
    shardStatus(f, item, states);
    assert.deepEqual(await finish({...f, candidates: shardItems(item)}), []);
    assert.equal(f.statuses.get(item.head)[0].state, 'failure');
    assert.equal(f.calls.filter(([name]) => name === 'merge').length, 0);
  });
}

test('a part that passed for an older main does not count', async () => {
  const f = fixture(), item = candidate(f);
  shardStatus(f, item, Array(SHARDS).fill('success'));
  f.statuses.get(item.head)[0].description = description('e'.repeat(40));
  assert.deepEqual(await finish({...f, candidates: shardItems(item)}), []);
});

test('main gaining only documents after validation still merges the validated head', async () => {
  const f = fixture(), item = candidate(f); f.status(item.branch);
  f.refs.main = 'f'.repeat(40);
  f.github.rest.repos.compareCommitsWithBasehead = async ({basehead}) => {
    assert.equal(basehead, `${item.base}...${f.refs.main}`);
    return {data: {status: 'ahead', behind_by: 0, files: [{filename: 'README.md'}, {filename: 'docs/readme/home.png'}]}};
  };
  assert.deepEqual(await finish({...f, candidates: [item]}), [item.pull]);
  assert.ok(f.notices.some(text => text.includes('only documents')));
});

for (const filename of ['gui_qt/app.py', '.github/workflows/agent-integration.yml', 'docs/inventory.json']) {
  test(`main gaining ${filename} after validation needs a fresh validation`, async () => {
    const f = fixture(), item = candidate(f); f.status(item.branch);
    f.refs.main = 'f'.repeat(40);
    f.github.rest.repos.compareCommitsWithBasehead = async () => ({data: {status: 'ahead', behind_by: 0,
      files: [{filename: 'README.md'}, {filename}]}});
    assert.deepEqual(await finish({...f, candidates: [item]}), []);
  });
}

test('with a sleep function the push run itself waits out the burst instead of relying on schedules', async () => {
  const f = fixture(), now = Date.parse('2026-11-09T12:00:00Z'), waits = [];
  const getBranch = f.github.rest.repos.getBranch;
  f.github.rest.repos.getBranch = async args => {
    const {data} = await getBranch(args);
    return {data: {commit: {...data.commit, commit: {committer: {date: new Date(now - 2 * 60000).toISOString()}}}}};
  };
  const sleep = async ms => { waits.push(ms); if (waits.length === 2) f.refs['agent/claude'] = 'e'.repeat(40); };
  const matrix = await prepare({...f, now, sleep});
  assert.deepEqual(waits, [3 * 60000, 3 * 60000]);
  assert.deepEqual(branchesOf(matrix), ['agent/codex']);
  assert.ok(f.notices.some(text => text.includes('newer push arrived')));
});
