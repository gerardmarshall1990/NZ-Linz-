"""The 2-8 Parrish Road pack scripts must at least compile, and must not write outputs into git-tracked paths."""
import py_compile, pathlib
PACK = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "parrish_pack"
def test_pack_scripts_compile():
    files = sorted(PACK.glob("*.py")); assert len(files) >= 8
    for f in files: py_compile.compile(str(f), doistfile=None, doraise=True) if False else py_compile.compile(str(f), cfile="/tmp/_pp_" + f.name + "c", doraise=True)
def test_outputs_ignored():
    ig = (PACK.parent.parent / ".gitignore").read_text().splitlines()
    assert "out/" in ig and "data/" in ig
