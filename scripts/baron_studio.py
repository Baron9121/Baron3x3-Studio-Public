#!/usr/bin/env python3
from studio.cli import main
import subprocess
import sys
if __name__ == '__main__':
    try: main()
    except (ValueError, FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f'STOP: {e}', file=sys.stderr)
        if isinstance(e,subprocess.CalledProcessError) and e.stderr: print(e.stderr[-2000:],file=sys.stderr)
        sys.exit(2)
