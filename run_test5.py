import subprocess, sys
proc = subprocess.Popen(
    [sys.executable, '-m', 'pytest', 'tests/ui/test_ui_rendering_bugs.py', '--co', '-q', '--no-header'],
    cwd='T:/ae/pyside6',
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)
try:
    out, _ = proc.communicate(timeout=30)
    print(repr(out[:3000]))
    print('EXIT:', proc.returncode)
except subprocess.TimeoutExpired:
    proc.kill()
    out, _ = proc.communicate()
    print('TIMED OUT, partial:', repr(out[:500]))
