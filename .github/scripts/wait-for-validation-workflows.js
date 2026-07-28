/**
 * Wait for required validation workflows to complete successfully for a PR head SHA.
 *
 * Used by Build Documentation / Publish Dev so they do not fail while Test and
 * CI/CD Pipeline are still queued or in progress.
 *
 * @param {object} params
 * @param {import('@actions/github').GitHub} params.github
 * @param {import('@actions/github').context} params.context
 * @param {import('@actions/core')} params.core
 * @param {string[]} [params.workflows] workflow file names to wait on
 * @param {number} [params.timeoutMs] max wait (default 120 minutes)
 * @param {number} [params.pollMs] poll interval (default 30 seconds)
 */
module.exports = async function waitForValidationWorkflows({
  github,
  context,
  core,
  workflows = ["ci.yml", "test.yml"],
  timeoutMs = 120 * 60 * 1000,
  pollMs = 30 * 1000,
}) {
  if (context.eventName !== "pull_request") {
    core.info(`Skipping validation wait for event: ${context.eventName}`);
    return;
  }

  const headSha = context.payload.pull_request.head.sha;
  const owner = context.repo.owner;
  const repo = context.repo.repo;
  const deadline = Date.now() + timeoutMs;

  const labels = {
    "ci.yml": "CI/CD Pipeline",
    "test.yml": "Test",
  };

  async function latestRun(workflowId) {
    const { data } = await github.rest.actions.listWorkflowRuns({
      owner,
      repo,
      workflow_id: workflowId,
      head_sha: headSha,
      per_page: 5,
    });
    return data.workflow_runs.find((run) => run.head_sha === headSha) || null;
  }

  for (const workflowId of workflows) {
    const label = labels[workflowId] || workflowId;
    while (true) {
      const run = await latestRun(workflowId);
      if (!run) {
        if (Date.now() >= deadline) {
          core.setFailed(`Timed out waiting for ${label} to start for ${headSha}`);
          return;
        }
        core.info(`${label}: no run for ${headSha} yet; waiting...`);
      } else if (run.status !== "completed") {
        if (Date.now() >= deadline) {
          core.setFailed(
            `Timed out waiting for ${label} (status=${run.status}) for ${headSha}`,
          );
          return;
        }
        core.info(`${label}: ${run.status} (run ${run.id}); waiting...`);
      } else if (run.conclusion === "success") {
        core.info(`${label}: success (run ${run.id})`);
        break;
      } else {
        core.setFailed(
          `${label} concluded '${run.conclusion}' (run ${run.id}); required before continuing`,
        );
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, pollMs));
    }
  }

  core.info("All required validation workflows passed");
};
