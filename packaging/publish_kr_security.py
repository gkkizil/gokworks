"""Save the original-package scan result without publishing a replacement EXE."""

import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from publish_status import git


def main():
    path = Path("k_factor/standalone/windows-security-request.json")
    request = json.loads(path.read_text(encoding="utf-8"))
    result = Path("kr-security.json")
    report = json.loads(result.read_text(encoding="utf-8-sig")) if result.exists() else {
        "status": "unavailable", "error": "The original artifact could not be downloaded or the Windows scan could not start."}
    if report["status"] != "no_detection":
        log = Path("kr-security-job.log")
        if log.exists():
            report["job_log_tail"] = log.read_text(encoding="utf-8-sig", errors="replace")[-12000:]
    report.update(request_id=request["request_id"], artifact_id=request["artifact_id"], source_commit=request["source_commit"],
                  audit_commit=os.environ["GITHUB_SHA"], job_status=os.environ["JOB_STATUS"],
                  run_url=f'https://github.com/{os.environ["GITHUB_REPOSITORY"]}/actions/runs/{os.environ["GITHUB_RUN_ID"]}')
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    with TemporaryDirectory() as temporary:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(temporary) / "index")}
        for attempt in range(3):
            git("fetch", "--quiet", "origin", "refs/heads/main")
            parent = git("rev-parse", "FETCH_HEAD")
            git("read-tree", parent, env=env)
            blob = git("hash-object", "-w", "--stdin", data=payload)
            git("update-index", "--add", "--cacheinfo", "100644", blob, "k_factor/standalone/windows-security-status.json", env=env)
            tree = git("write-tree", env=env)
            commit = git("-c", "user.name=github-actions[bot]", "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
                         "commit-tree", tree, "-p", parent, "-m", f'Check original K/R package: {report["status"]}')
            pushed = subprocess.run(["git", "push", "origin", f"{commit}:refs/heads/main"], capture_output=True, text=True)
            if pushed.returncode == 0:
                print(payload)
                return
            latest = git("ls-remote", "origin", "refs/heads/main").split()[0]
            if latest == parent or attempt == 2:
                raise RuntimeError(pushed.stderr)


if __name__ == "__main__":
    main()
