"""Publish only the standalone K/R artifact metadata; preserve app releases."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

from publish_status import git

BASE = "k_factor/standalone"
START, END = "<!-- kr-windows-release:start -->", "<!-- kr-windows-release:end -->"


def main():
    request = json.loads(Path(BASE + "/windows-build-request.json").read_text(encoding="utf-8"))
    report = {"commit": os.environ["GITHUB_SHA"], "request_id": request["request_id"], "distribution": "directory",
              "status": os.environ["BUILD_STATUS"],
              "run_url": f'https://github.com/{os.environ["GITHUB_REPOSITORY"]}/actions/runs/{os.environ["GITHUB_RUN_ID"]}',
              "download_url": os.environ.get("ARTIFACT_URL", ""), "files": {}}
    package = Path("dist/kr-probe/GOKWORKS-KR-Deneme")
    for relative in ("GOKWORKS-KR-Deneme.exe", "native/Gokworks.KrProbe.exe"):
        path = package / relative
        if path.exists():
            report["files"][relative] = {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    smoke = package / "windows-smoke.json"
    if smoke.exists():
        report["smoke"] = json.loads(smoke.read_text(encoding="utf-8"))
    security = Path("build/kr-security-report.json")
    if security.exists():
        report["security"] = json.loads(security.read_text(encoding="utf-8-sig"))
    if report["status"] != "success":
        log = Path("kr-windows-build.log")
        if log.exists():
            report["build_log_tail"] = log.read_text(encoding="utf-8", errors="replace")[-16000:]
    else:
        if (not report["download_url"] or report.get("smoke", {}).get("status") != "passed" or len(report["files"]) != 2
                or report.get("security", {}).get("status") != "no_detection"
                or report["security"].get("source_commit") != report["commit"]):
            raise RuntimeError("Success requires both entrypoints, artifact URL, packaged smoke, and a matching completed Defender scan.")
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    with TemporaryDirectory() as temporary:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(temporary) / "index")}
        for attempt in range(3):
            git("fetch", "--quiet", "origin", "refs/heads/main")
            parent = git("rev-parse", "FETCH_HEAD")
            git("read-tree", parent, env=env)
            files = {BASE + "/windows-build-status.json": payload}
            if report["status"] == "success":
                readme = git("show", f"{parent}:{BASE}/README.md")
                block = (f'{START}\n**Windows paketi:** [K/R atama aracını indir]({report["download_url"]}). '
                         'ZIP dosyasını çıkartıp **GOKWORKS-KR-Deneme.exe** dosyasını açın. '
                         'Alt klasörleri koruyun; EXE’yi tek başına taşımayın. Python ve .NET kurulumu gerekmez.\n\n'
                         f'[Derleme kaydı]({report["run_url"]}) · Kaynak: `{report["commit"][:7]}` · '
                         f'[SHA256, Defender taraması ve açılış kontrolü](windows-build-status.json)\n{END}')
                readme, count = re.subn(re.escape(START) + r".*?" + re.escape(END), lambda match: block, readme, flags=re.S)
                if count != 1:
                    raise RuntimeError("K/R README release marker missing or duplicated")
                files[BASE + "/README.md"] = readme + "\n"
            for path, content in files.items():
                blob = git("hash-object", "-w", "--stdin", data=content)
                git("update-index", "--add", "--cacheinfo", "100644", blob, path, env=env)
            tree = git("write-tree", env=env)
            commit = git("-c", "user.name=github-actions[bot]", "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
                         "commit-tree", tree, "-p", parent, "-m", f'K/R Windows build {report["commit"][:8]}: {report["status"]}')
            pushed = subprocess.run(["git", "push", "origin", f"{commit}:refs/heads/main"], capture_output=True, text=True)
            if pushed.returncode == 0:
                print(payload)
                return
            latest = git("ls-remote", "origin", "refs/heads/main").split()[0]
            if latest == parent or attempt == 2:
                raise RuntimeError(pushed.stderr)


if __name__ == "__main__":
    main()
