"""Protect framework-independent layers during later refactoring."""
import ast
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]

class ArchitectureTests(unittest.TestCase):
    def test_core_has_no_ui_imports(self):
        banned={'streamlit','folium','streamlit_folium','ui','app','astana','mobile_ui'}
        for folder in ('algorithms','environments','services','infrastructure','utils','domain'):
            for path in (ROOT/folder).glob('*.py'):
                for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                    modules=[]
                    if isinstance(node,ast.Import):modules=[x.name for x in node.names]
                    if isinstance(node,ast.ImportFrom):modules=[node.module or '']
                    for module in modules:
                        self.assertNotIn(module.split('.')[0],banned,str(path))

    def test_core_import_does_not_initialize_streamlit(self):
        code='import services.simulation, services.dispatch, infrastructure.graph_builder; import sys; assert "streamlit" not in sys.modules'
        result=subprocess.run([sys.executable,'-X','utf8','-c',code],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
        self.assertEqual(result.returncode,0,result.stderr)
