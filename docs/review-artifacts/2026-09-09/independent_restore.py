"""Run Claude's restore specimen with unique disposable database names.

The original specimen is kept intact. Remove its preliminary DROP statements so
the independent run never replaces a database that already exists. All database
operations target the documented trendsell-test-db container, not production.
"""
from pathlib import Path
import subprocess
import uuid

original = Path(__file__).with_name('restore_drill.py')
suffix = uuid.uuid4().hex[:16]
source_name, destination_name = f'review_src_{suffix}', f'review_dst_{suffix}'
code = original.read_text().replace('drill_src', source_name).replace('drill_dst', destination_name)
code = code.replace("    psql(f'DROP DATABASE IF EXISTS {name}')\n", '')
try:
    exec(compile(code, str(original), 'exec'), {'__name__': '__main__', '__file__': str(original)})
finally:
    # Also clean our uniquely named fixtures if seeding or replay raises.
    for name in (source_name, destination_name):
        subprocess.run(['docker', 'exec', 'trendsell-test-db', 'psql', '-U', 'trendsell_test',
                        '-d', 'postgres', '-v', 'ON_ERROR_STOP=1', '-tAc',
                        f'DROP DATABASE IF EXISTS {name}'], check=True, capture_output=True)
