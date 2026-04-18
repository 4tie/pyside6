import subprocess, sys
proc = subprocess.Popen(
    [sys.executable, '-c', 'import app.ui.pages.improve_page; print("import ok")'],
    cwd='T:/ae/pyside6',
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)
try:
    out, _ = proc.communicate(timeout=15)
    print(repr(out))
    print('EXIT:', proc.returncode)
except subprocess.TimeoutExpired:
    proc.kill()
    out, _ = proc.communicate()
    print('TIMED OUT, partial:', repr(out[:500]))
