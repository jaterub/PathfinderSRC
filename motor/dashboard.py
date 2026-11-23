"""Render del dashboard v4 extraído de Profesión, sin datos de ningún cliente."""
import json
from pathlib import Path


PLANTILLA = Path(__file__).resolve().parents[1] / "interfaz/dashboard_plantilla.html"


def dashboard_html(data):
    """Conserva el escape del generador original al incrustar el informe como JSON."""
    plantilla = PLANTILLA.read_text(encoding="utf-8")
    datos = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return plantilla.replace("/*__DATOS__*/null", datos, 1)
