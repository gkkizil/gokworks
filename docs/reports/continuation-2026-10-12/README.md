# K/R continuation and measured GUI work

> Eski Tk arayüzü için verilen görsel/rapor komutları tarihîdir. Bu betikler ve
> üretilmiş görseller güncel daldan kaldırılmıştır; yeniden incelemek için
> [temizlik öncesi sürümü](https://github.com/gkkizil/gokworks/tree/6c15dba372c5cee9e1454f28ab47d1d1852f3fc9) kullanın.

Baseline source: immutable `70bf2c9484e4e3eb5bfb6796ae98c0c4d0a5f8d6`, extracted with `git archive` outside the checkout. Candidate uses the accompanying changes. Both were measured sequentially using the same enhanced `docs/report-tools/benchmark_gui_events.py`, Python runtime, display `:99` (1920×1080), default theme/scaling and synthetic workload. GUI tests were not run concurrently with benchmarks.

| Operation, 10,000 rows | Baseline median | Candidate median | Reduction |
| --- | --- | --- | --- |
| Clear filters | 7.14 ms | 5.47 ms | 23.4% |
| Reset list | 18.22 ms | 13.80 ms | 24.3% |

Runtime: Python 3.12.14, Tk 9.0, Linux. Three timed repetitions per operation; paired values in the JSON record operation duration and next Tk callback delay. Timing varies with host scheduling; this is a small synthetic sample, not a native SolidWorks speedup. Startup, first/warm page switches, 500-result bursts and alternating filters are recorded as context, without attributing changes in unrelated timings to these fixes.

Clear now applies the final filter pair once (2 → 1 bulk table calls). Reset discards existing rows before clearing the filters (3 → 1 bulk table calls, 95 → 0 old-row styling calls for this workload). Scan order, selection, status and stripe tags remain checked. Mock counters are collected separately from timed runs.

Reproduce from `/workspace/gokworks`:

```bash
DISPLAY=:99 APPDATA=/workspace/.cloud-setup/user \
XDG_CACHE_HOME=/workspace/.cloud-setup/cache \
.venv/bin/python docs/report-tools/benchmark_gui_events.py <source-root> <output.json>
```

The API correction targets the modern `TemplateSheetMetal` parent, freshly verifies parent and inherited child/conversion K/R, captures all configurations including a separately retrieved parent, and verifies rollback after failure. Type 5 snapshots/restores `BendCalculationTableFile` and finalizes allowance `Type` after the active setter. The immutable public GitHub reference and verified documentation mirror are recorded in `../k-radius/api-contract.json`. Native acceptance uses `docs/local-solidworks-check.md`; COM doubles do not establish changes in a live SolidWorks 2025 model.

## Final validation

- Full integrated suite: **356 tests passed**, 0 failed, 0 errors, 0 skipped, 164.167 seconds. Real Tk GUI tests ran on the virtual display.
- Targeted K/R suite: 55 passed; file-list/menu GUI regressions: 14 passed.
- Dependency check, source compilation and `git diff --check` passed.
- Raw final log is retained at `/workspace/.cloud-setup/final-tests.log`; digest and commands are in `validation.json`.
- No live SolidWorks 2025 model was tested. Follow the updated native acceptance guide for the 1.5 mm and 2 mm examples, parent/child parameters, flat patterns and untouched configurations.
- No recurring Astra task was installed: this session exposes no scheduling capability. Scheduled tests were not substituted for recurring development.
