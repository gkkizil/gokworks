'use strict';

// Only these same-repository branches may enter the automatic integration path.
const BRANCHES = ['agent/codex', 'agent/claude'];
const STATUS = 'GOKWORKS agent validation';

const description = base => `main:${base}`;
const runUrl = context => `${context.serverUrl || 'https://github.com'}/${context.repo.owner}/${context.repo.repo}/actions/runs/${context.runId}`;

async function branchSha(github, repo, branch) {
  try {
    return (await github.rest.repos.getBranch({...repo, branch})).data.commit.sha;
  } catch (error) {
    if (error.status === 404 && BRANCHES.includes(branch)) return null;
    throw error;
  }
}

async function latestStatus(github, repo, head) {
  const {data} = await github.rest.repos.listCommitStatusesForRef({...repo, ref: head, per_page: 100});
  return data.find(status => status.context === STATUS);
}

async function prepare({github, context, core, retryFailed = false}) {
  const repo = context.repo;
  const base = await branchSha(github, repo, 'main');
  const candidates = [];
  for (const branch of BRANCHES) {
    const head = await branchSha(github, repo, branch);
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
    candidates.push({branch, head, base, pull: pull.number, cached});
  }
  return {include: candidates};
}

async function finish({github, context, core, candidates}) {
  const repo = context.repo;
  const merged = [];
  for (const candidate of candidates) {
    const {branch, head, base, pull: number} = candidate;
    if (!BRANCHES.includes(branch)) throw new Error('Unsupported integration branch.');
    const status = await latestStatus(github, repo, head);
    if (status?.state !== 'success' || status.description !== description(base)) {
      core.notice(`${branch}: no successful validation for this head/main pair.`);
      continue;
    }
    // Both agents share this serialized workflow. A changed main is retested by
    // the next scheduled run, rather than reusing the other branch's old result.
    if (await branchSha(github, repo, 'main') !== base || await branchSha(github, repo, branch) !== head) {
      core.notice(`${branch}: main or the source branch advanced; a fresh validation is needed.`);
      continue;
    }
    const {data: pull} = await github.rest.pulls.get({...repo, pull_number: number});
    if (pull.state !== 'open' || pull.draft || pull.base.ref !== 'main' || pull.base.sha !== base || pull.head.ref !== branch ||
        pull.head.sha !== head || pull.head.repo?.full_name !== `${repo.owner}/${repo.repo}`) {
      core.notice(`${branch}: PR no longer matches the validated request.`);
      continue;
    }
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
  return merged;
}

module.exports = {BRANCHES, STATUS, description, prepare, finish};
