from pathlib import Path
import os,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.openrouter_keychain import load_openrouter_key
key=load_openrouter_key()
if not key: raise SystemExit('Brak poprawnego klucza OpenRouter w Keychain. Nie wklejaj sekretu do czatu.')
env=os.environ.copy(); env['OPENROUTER_API_KEY']=key
workspace = ROOT / 'opencode-resolve'
os.chdir(workspace)
exe=str(ROOT/'tools/opencode/node_modules/.bin/opencode')
args = list(sys.argv[1:])
# OpenCode otherwise promotes the surrounding Git root to the project and
# silently ignores this scoped config. Pin the working directory explicitly.
if args and args[0] in {'run', 'tui', 'serve'} and '--dir' not in args:
    args[1:1] = ['--dir', str(workspace)]
os.execve(exe,[exe,*args],env)
