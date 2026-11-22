# Motor reutilizable

`dashboard.py` contiene la función generadora ya extraída del motor privado. La plantilla está en `interfaz/dashboard_plantilla.html`, sin datos incrustados. La extracción del scorer completo sigue pendiente.

El [análisis de v4 y nota de flexibilidad](../docs/ingenieria-inversa-v4.md) sigue todo el flujo y distingue código compartido, perfil y dependencias de integración.

Origen analizado: Profesión, commit `023830220a8502536a9a3d26b39a168f4b749be6`.

| Origen en Profesión | Destino previsto | Tratamiento |
|---|---|---|
| `2_motor/radar/score_radar.py`: `score_offer` y auxiliares necesarios | `motor/puntuacion.py` | Conservar el algoritmo y sus validaciones; recibir el perfil del cliente |
| `2_motor/radar/experience.py` | `motor/experiencia.py` | Reutilizar el reconocimiento de experiencia exigida y su evidencia |
| Constantes de salario, ubicación, roles, listas rumbo/base/resta/neutro, cortes y exclusiones | `clientes/demo-01/perfil.yaml` | Configuración del cliente, sin heredar preferencias del usuario de Profesión |
| `dashboard_html` y `dashboard_plantilla.html` | `motor/dashboard.py` e `interfaz/dashboard_plantilla.html` | Ya extraídos sin datos; el render conserva el escape del generador original |
| `build_informe` | Motor del informe, pendiente | Reutilizar el cálculo de resultados con el perfil del cliente |

Antes de modificar firmas se revisarán también los consumidores: `entrada/respuestas.py` importa `variante_de_rol`; `entrada/importa_api.py` reutiliza `jd_modalidad`; el script usa `pipeline_csv.py` y tiene pruebas directas y de extremo a extremo. No se trasladará el script completo sin separar estas dependencias.

La comparación con decisiones anteriores debe usar solo el historial del cliente evaluado. El historial de Profesión no forma parte del motor ni de la demo.

El primer perfil es de asesoría fiscal: las listas actuales orientadas a IA no sirven como configuración inicial. Su objetivo, condiciones y preferencias siguen pendientes de definición por el cliente.
