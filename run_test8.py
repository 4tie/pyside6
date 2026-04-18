import subprocess, sys
# Try with a completely fresh temp dir
import tempfile, os, shutil
tmpdir = tempfile.mkdtemp()
# Create a minimal test file
test_content = '''
def test_simple():
    assert 1 + 1 == 2
'''
with open(os.path.join(tmpdir, 'test_simple.py'), 'w') as f:
    f.write(test_content)

proc = subprocess.Popen(
    [sys.executable, '-m', 'pytest', 'test_simple.py', '-v'],
    cwd=tmpdir,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)
try:
    out, _ = proc.communicate(timeout=15)
    print(repr(out[:3000]))
    print('EXIT:', proc.returncode)
except subprocess.TimeoutExpired:
    proc.kill()
    out, _ = proc.communicate()
    print('TIMED OUT, partial:', repr(out[:500]))
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)
