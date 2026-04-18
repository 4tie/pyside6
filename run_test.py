import subprocess, sys
proc = subprocess.Popen(
    [sys.executable, '-c', 'import tests.test_improve_page_bug; print("ok")'],
    cwd='T:/ae/pyside6',
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)
try:
    out, _ = proc.communicate(timeout=15)
    print(out[:3000])
    print('EXIT:', proc.returncode)
except subprocess.TimeoutExpired:
    proc.kill()
    out, _ = proc.communicate()
    print('TIMED OUT, partial output:')
    print(out[:3000] if out else '(none)')
