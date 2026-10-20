"""SRS-039/058/059: validate authored files, not vendor negative fixtures."""
from pathlib import Path
import shutil
import subprocess
import sys
import pytest


@pytest.mark.parametrize('location,valid',[('node_modules/vendor/invalid.yaml',True),('.worktrees/old/docs/invalid.yaml',True),('docs/invalid.yaml',False)])
def test_baseline_validation_scope(tmp_path,location,valid):
    root=Path(__file__).resolve().parents[1]
    for folder in ['docs','plans','.codex','tools']:
        shutil.copytree(root/folder,tmp_path/folder)
    fixture=tmp_path/location
    fixture.parent.mkdir(parents=True,exist_ok=True)
    fixture.write_text("test: '")
    result=subprocess.run([sys.executable,str(tmp_path/'tools/validate_baseline.py')],capture_output=True,text=True)
    assert (result.returncode==0)==valid,result.stdout+result.stderr
