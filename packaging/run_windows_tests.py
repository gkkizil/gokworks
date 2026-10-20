"""Keep native pytest output and its exit code intact across PowerShell runs."""

import os
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    command = [sys.executable, '-X', 'faulthandler', '-m', 'pytest', '-vv',
               '--timeout=60', '--timeout-method=thread',
               '-o', 'faulthandler_timeout=60', '-o', 'faulthandler_exit_on_timeout=true',
               '--junitxml=windows-tests.xml', *sys.argv[1:]]
    with (root/'windows-tests.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT,
                                env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONFAULTHANDLER': '1'})
        code = result.returncode
        log.write(f'\nPYTEST_PROCESS_EXIT_CODE={code} (0x{code & 0xffffffff:08X})\n')
    print(f'Windows pytest exit code: {code} (0x{code & 0xffffffff:08X})')
    return 0 if code == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
