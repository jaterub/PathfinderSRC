"""Comprueba lo que se publica, incluyendo archivos ignorados añadidos con -f."""
from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Privacidad(unittest.TestCase):
    def test_no_hay_clientes_privados_en_git(self):
        paths = subprocess.check_output(
            ["git", "ls-files", "-z"], cwd=ROOT
        ).decode("utf-8").split("\0")
        prohibidos = [p for p in paths if re.match(r"clientes/ID[^/]*(?:/|$)", p, re.I)]
        self.assertEqual(prohibidos, [], "Datos privados versionados: " + repr(prohibidos))

    def test_cv_demo_no_incluye_campos_personales(self):
        cv = (ROOT / "clientes/demo-01/cv.md").read_text(encoding="utf-8")
        self.assertTrue(cv.startswith("# Cliente demo 01\n"))
        self.assertNotRegex(cv, r"(?im)^\*\*(?:Dirección|Mail|Móvil|Fecha de nacimiento):")
        self.assertNotRegex(cv, r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")


if __name__ == "__main__":
    unittest.main()
