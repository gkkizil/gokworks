'use strict';

// Only these same-repository branches may enter the automatic integration path.
const BRANCHES = ['agent/codex', 'agent/claude'];
const STATUS = 'GOKWORKS agent validation';
const AUTOMATION_FILES = new Set([
  '.github/scripts/agent-integration.cjs', '.github/scripts/tests/agent-integration.test.cjs',
  '.github/scripts/report-agent-validation.py', '.github/workflows/agent-integration.yml',
  '.github/workflows/agent-diagnostics.yml', 'tests/test_agent_validation_report.py',
  'docs/agent-integration.md',
]);

// Written to main by the Windows EXE workflow's status commits. They carry no
// application code, so a main advance made only of these keeps a passed
// head's proof (with the short CI checks); a branch changing them is still
// tested in full.
const BUILD_METADATA_FILES = new Set([
  'README.md', 'packaging/windows-build-status.json', 'packaging/latest-windows.json',
]);

// Documentation never runs in the application: Markdown anywhere, images under docs/
// and .gitignore. Runtime data that lives under docs/ (JSON examples, inventories) is not
// matched, so it still needs the full suite.
const DOCUMENT = /^(?:.+\.md|docs\/.+\.(?:png|jpe?g|gif|svg|webp)|\.gitignore)$/i;
const isDocument = name => DOCUMENT.test(name);

// Full-suite validations are split into parallel Windows jobs, each running a
// deterministic part of the collected tests; their results are combined in finish().
const SHARDS = 3;
// Agents usually push several commits within minutes; start once a branch has been
// quiet this long. The 5-minute schedule picks the branch up afterwards.
const SETTLE_MINUTES = 5;

function onlyFiles(comparison, allowed) {
  const files = comparison?.files;
  const ok = name => typeof allowed === 'function' ? allowed(name) : allowed.has(name);
  // GitHub truncates comparison file lists at 300. Unknown/truncated scope
  // always needs the full suite, as do renames from application paths.
  return Array.isArray(files) && files.length > 0 && files.length < 300 &&
    files.every(file => ok(file.filename) && (!file.previous_filename || ok(file.previous_filename)));
}

function documentationOnly(comparison) {
  return onlyFiles(comparison, isDocument);
}

function automationOnly(comparison) {
  return onlyFiles(comparison, AUTOMATION_FILES);
}

const BASE_ONLY_FILES = new Set([...AUTOMATION_FILES, ...BUILD_METADATA_FILES]);
const baseOnly = name => BASE_ONLY_FILES.has(name) || isDocument(name);
// A main advance that may be merged over without retesting: documents and build status only.
const harmlessBase = name => BUILD_METADATA_FILES.has(name) || isDocument(name);

async function documentsOnlyAdvance(github, repo, from, to) {
  if (from === to) return true;
  try {
    const {data: delta} = await github.rest.repos.compareCommitsWithBasehead({...repo, basehead: `${from}...${to}`});
    return delta.status === 'ahead' && delta.behind_by === 0 && onlyFiles(delta, harmlessBase);
  } catch (error) {
    if (error.status !== 404) throw error;
    return false;
  }
}

async function validationMode(github, repo, comparison, previous, base) {
  if (automationOnly(comparison)) return 'automation';
  if (documentationOnly(comparison)) return 'docs';
  const match = /^main:([0-9a-f]{40})$/.exec(previous?.description || '');
  if (previous?.state !== 'success' || !match || match[1] === base) return 'full';
  try {
    const {data: delta} = await github.rest.repos.compareCommitsWithBasehead({
      ...repo, basehead: `${match[1]}...${base}`,
    });
    // The same source head passed already. An exclusively CI or build-status
    // base change preserves application code and only needs the CI/native
    // smoke checks.
    if (delta.status === 'ahead' && delta.behind_by === 0 && onlyFiles(delta, baseOnly)) return 'automation';
  } catch (error) {
    if (error.status !== 404) throw error;
  }
  return 'full';
}

const description = base => `main:${base}`;
const runUrl = context => `${context.serverUrl || 'https://github.com'}/${context.repo.owner}/${context.repo.repo}/actions/runs/${context.runId}`;

async function branchCommit(github, repo, branch) {
  try {
    return (await github.rest.repos.getBranch({...repo, branch})).data.commit;
  } catch (error) {
    if (error.status === 404 && BRANCHES.includes(branch)) return null;
    throw error;
  }
}

async function branchSha(github, repo, branch) {
  return (await branchCommit(github, repo, branch))?.sha ?? null;
}

function settling(commit, now = Date.now()) {
  const when = Date.parse(commit?.commit?.committer?.date || '');
  return Number.isFinite(when) && now - when < SETTLE_MINUTES * 60000;
}

const shardContext = (shard, shards) => `${STATUS} · ${shard}/${shards}`;

async function latestStatus(github, repo, head) {
  const {data} = await github.rest.repos.listCommitStatusesForRef({...repo, ref: head, per_page: 100});
  return data.find(status => status.context === STATUS);
}

async function prepare({github, context, core, retryFailed = false, now = Date.now(), sleep = null}) {
  const repo = context.repo;
  const base = await branchSha(github, repo, 'main');
  const candidates = [];
  for (const branch of BRANCHES) {
    const commit = await branchCommit(github, repo, branch);
    const head = commit?.sha;
    if (!head || head === base) continue;
    const {data: comparison} = await github.rest.repos.compareCommitsWithBasehead({
      ...repo, basehead: `${base}...${head}`,
    });
    if (comparison.ahead_by === 0) continue;
    const {data: pulls} = await github.rest.pulls.list({
      ...repo, state: 'all', base: 'main', head: `${repo.owner}:${branch}`, per_page: 100,
      sort: 'created', direction: 'desc',
    });
    // Never reopen an explicitly closed PR at the same head, or submit a draft.
    let pull = pulls.find(item => item.state === 'open');
    if (pull?.draft || (!pull && pulls.some(item => item.state === 'closed' && !item.merged_at && item.head.sha === head))) {
      core.notice(`${branch}: draft or explicitly closed PR; leaving it for the author.`);
      continue;
    }
    const previous = await latestStatus(github, repo, head);
    const sameBase = previous?.description === description(base);
    if (sameBase && ['failure', 'error'].includes(previous.state) && !retryFailed) {
      core.notice(`${branch}: validation failed; waiting for a new commit/base or a manual retry.`);
      continue;
    }
    const mode = await validationMode(github, repo, comparison, previous, base);
    const cachedProof = sameBase && previous.state === 'success';
    if (!cachedProof && !retryFailed && context.eventName !== 'workflow_dispatch' && settling(commit, now)) {
      // Scheduled scans are not reliable (GitHub may delay them for hours), so wait here
      // rather than leave the branch for a later scan. A newer push during the wait
      // queues its own run, which validates the newer head instead.
      if (!sleep) {
        core.notice(`${branch}: pushed less than ${SETTLE_MINUTES} min ago; waiting for further pushes before validating.`);
        continue;
      }
      const remaining = SETTLE_MINUTES * 60000 - (now - Date.parse(commit.commit.committer.date));
      core.notice(`${branch}: pushed moments ago; waiting ${Math.ceil(remaining / 1000)} s for further pushes.`);
      const waited = Math.min(Math.max(remaining, 0), SETTLE_MINUTES * 60000);
      await sleep(waited);
      now += waited;   // the next branch is judged at the time after this wait, not before it
      if (await branchSha(github, repo, branch) !== head) {
        core.notice(`${branch}: a newer push arrived while waiting; its own run validates it.`);
        continue;
      }
    }
    if (!pull) {
      ({data: pull} = await github.rest.pulls.create({
        ...repo, base: 'main', head: branch, title: `Integrate ${branch} into main`,
        body: `Changes published on \`${branch}\`.\n\n` +
          'The agent integration workflow tests this exact head together with a fixed main commit on Windows. ' +
          'It merges only after successful validation, provided neither branch has advanced. ' +
          'Conflicts, failed checks and repository protection rules keep the PR open.\n\n' +
          'The source branch is retained. Live SOLIDWORKS acceptance is separate from these automated checks.',
      }));
    }
    const cached = sameBase && previous.state === 'success';
    if (!cached) {
      await github.rest.repos.createCommitStatus({
        ...repo, sha: head, state: 'pending', context: STATUS, description: description(base), target_url: runUrl(context),
      });
    }
    const shards = !cached && mode === 'full' ? SHARDS : 1;
    core.notice(`${branch}: ${cached ? 'cached' : mode} validation for ${head.slice(0, 7)} / main ${base.slice(0, 7)}` +
      (shards > 1 ? ` in ${shards} parallel parts.` : '.'));
    for (let shard = 1; shard <= shards; shard++) {
      candidates.push({branch, head, base, pull: pull.number, cached, mode, shard, shards});
    }
  }
  return {include: candidates};
}

async function combineShards(github, context, repo, candidate) {
  // Every part must have passed for this exact head/main pair; one missing or failed part fails all.
  const {head, base, shards} = candidate;
  const {data} = await github.rest.repos.listCommitStatusesForRef({...repo, ref: head, per_page: 100});
  const parts = [];
  for (let shard = 1; shard <= shards; shard++) {
    parts.push(data.find(status => status.context === shardContext(shard, shards) && status.description === description(base)));
  }
  const passed = parts.every(part => part?.state === 'success');
  await github.rest.repos.createCommitStatus({
    ...repo, sha: head, state: passed ? 'success' : 'failure', context: STATUS, description: description(base),
    target_url: runUrl(context),
  });
  return passed;
}

async function finish({github, context, core, candidates}) {
  const repo = context.repo;
  const merged = [];
  const unique = [];
  for (const candidate of candidates) {
    if (!unique.some(item => item.branch === candidate.branch)) unique.push(candidate);
  }
  for (const candidate of unique) {
    const {branch, head, base, pull: number} = candidate;
    if (!BRANCHES.includes(branch)) throw new Error('Unsupported integration branch.');
    if (!candidate.cached && (candidate.shards || 1) > 1) {
      const passed = await combineShards(github, context, repo, candidate);
      core.notice(`${branch}: ${candidate.shards} parallel parts ${passed ? 'all passed' : 'did not all pass'}.`);
    }
    const status = await latestStatus(github, repo, head);
    if (status?.state !== 'success' || status.description !== description(base)) {
      core.notice(`${branch}: no successful validation for this head/main pair.`);
      continue;
    }
    // Both agents share this serialized workflow. A changed main is retested by
    // the next scheduled run, rather than reusing the other branch's old result —
    // unless main only gained documents or build status, which change no tested code.
    const liveBase = await branchSha(github, repo, 'main');
    if (await branchSha(github, repo, branch) !== head || !(await documentsOnlyAdvance(github, repo, base, liveBase))) {
      core.notice(`${branch}: main or the source branch advanced; a fresh validation is needed.`);
      continue;
    }
    const {data: pull} = await github.rest.pulls.get({...repo, pull_number: number});
    // PR.base.sha may retain the base recorded when the PR was created. The
    // live main ref, rather than that historical metadata, identifies the base.
    if (pull.state !== 'open' || pull.draft || pull.base.ref !== 'main' || pull.head.ref !== branch ||
        pull.head.sha !== head || pull.head.repo?.full_name !== `${repo.owner}/${repo.repo}`) {
      core.notice(`${branch}: PR no longer matches the validated request: state=${pull.state}, draft=${pull.draft}, ` +
        `target=${pull.base.ref}, source=${pull.head.ref}@${pull.head.sha}, repository=${pull.head.repo?.full_name}.`);
      continue;
    }
    const [currentBase, currentHead] = await Promise.all([
      branchSha(github, repo, 'main'), branchSha(github, repo, branch),
    ]);
    if (currentBase !== liveBase || currentHead !== head) {
      core.notice(`${branch}: refs changed while reading the PR; fresh validation is needed.`);
      continue;
    }
    if (liveBase !== base) core.notice(`${branch}: main gained only documents since validation; merging the validated head.`);
    try {
      const {data: result} = await github.rest.pulls.merge({
        ...repo, pull_number: number, sha: head, merge_method: 'merge',
      });
      if (result.merged !== true) {
        core.notice(`${branch}: ${result.message || 'repository rules prevent merging'}`);
        continue;
      }
      merged.push(number);
      core.notice(`${branch}: merged PR #${number}; source branch retained.`);
    } catch (error) {
      if (![405, 409, 422].includes(error.status)) throw error;
      core.notice(`${branch}: merge blocked (${error.message}); PR remains open.`);
    }
  }
  if (merged.length) {
    // A main update invalidates the other branch's proof. Explicit dispatch is
    // supported for GITHUB_TOKEN, unlike the suppressed bot-generated push event.
    try {
      await github.rest.actions.createWorkflowDispatch({
        ...repo, workflow_id: 'agent-integration.yml', ref: 'main', inputs: {retry_failed: 'false'},
      });
    } catch (error) {
      core.notice(`Follow-up dispatch unavailable (${error.message}); the scheduled scan will retry.`);
    }
  }
  return merged;
}

async function cancelSuperseded({github, context, core}) {
  const branch = context.ref?.replace(/^refs\/heads\//, '');
  if (context.eventName !== 'push' || !BRANCHES.includes(branch)) return [];
  if (await branchSha(github, context.repo, branch) !== context.sha) return [];
  const {data} = await github.rest.actions.listWorkflowRuns({
    ...context.repo, workflow_id: 'agent-integration.yml', branch, event: 'push', per_page: 100,
  });
  const cancelled = [];
  for (const run of data.workflow_runs) {
    if (run.status !== 'in_progress' || run.head_sha === context.sha || run.head_branch !== branch ||
        run.event !== 'push' || run.name !== 'Agent integration') continue;
    try {
      await github.rest.actions.cancelWorkflowRun({...context.repo, run_id: run.id});
      cancelled.push(run.id);
      core.notice(`Cancelled superseded run ${run.id}; its old head cannot be merged.`);
    } catch (error) {
      if (![405, 409].includes(error.status)) throw error;
    }
  }
  return cancelled;
}

module.exports = {BRANCHES, STATUS, SHARDS, SETTLE_MINUTES, description, shardContext, prepare, finish, cancelSuperseded,
  automationOnly, documentationOnly, isDocument, validationMode, settling};
