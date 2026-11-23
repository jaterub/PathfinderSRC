"""Regresión pública de la parte de generación extraída, con datos sintéticos."""
import json
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from motor.dashboard import dashboard_html, PLANTILLA


class Scripts(HTMLParser):
    count = 0

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.count += 1


class Dashboard(unittest.TestCase):
    def test_no_permite_cerrar_el_script_desde_los_datos(self):
        data = {"perfil": {"objetivo": "Fiscalidad </script><script>alert(1)</script> · á"}}
        html = dashboard_html(data)
        payload = re.search(r"^const D = (.+);$", html, re.M).group(1)
        self.assertEqual(json.loads(payload), data)
        self.assertNotIn("</script>", payload)
        parser = Scripts()
        parser.feed(html)
        self.assertEqual(parser.count, 1)

    def test_generaciones_independientes_sin_datos_heredados(self):
        primero = dashboard_html({"perfil": {"objetivo": "OBJETIVO_CLIENTE_UNO"}})
        segundo = dashboard_html({"perfil": {"objetivo": "OBJETIVO_CLIENTE_DOS"}})
        self.assertIn("OBJETIVO_CLIENTE_UNO", primero)
        self.assertNotIn("OBJETIVO_CLIENTE_UNO", segundo)
        self.assertNotIn("OBJETIVO_CLIENTE_DOS", primero)
        self.assertEqual(PLANTILLA.read_text(encoding="utf-8").count("/*__DATOS__*/null"), 1)


if __name__ == "__main__":
    unittest.main()
