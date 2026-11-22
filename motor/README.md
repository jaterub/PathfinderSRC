# Motor reutilizable

Carpeta reservada para la extracci�n. Este PR no copia ni ejecuta el motor privado.

Origen analizado: Profesi�n, commit `023830220a8502536a9a3d26b39a168f4b749be6`.

| Origen en Profesi�n | Destino previsto | Tratamiento |
|---|---|---|
| `2_motor/radar/score_radar.py`: `score_offer` y auxiliares necesarios | `motor/puntuacion.py` | Conservar el algoritmo y sus validaciones; recibir el perfil del cliente |
| `2_motor/radar/experience.py` | `motor/experiencia.py` | Reutilizar el reconocimiento de experiencia exigida y su evidencia |
| Constantes de salario, ubicaci�n, roles, listas rumbo/base/resta/neutro, cortes y exclusiones | `clientes/demo-01/perfil.yaml` | Configuraci�n del cliente, sin heredar preferencias del usuario de Profesi�n |
| `build_informe`, `dashboard_html` y `dashboard_plantilla.html` | `motor/` en PR 3 | Reutilizar la presentaci�n con datos del cliente demo |

Antes de modificar firmas se revisar�n tambi�n los consumidores: `entrada/respuestas.py` importa `variante_de_rol`; `entrada/importa_api.py` reutiliza `jd_modalidad`; el script usa `pipeline_csv.py` y tiene pruebas directas y de extremo a extremo. No se trasladar� el script completo sin separar estas dependencias.

La comparaci�n con decisiones anteriores debe usar solo el historial del cliente evaluado. El historial de Profesi�n no forma parte del motor ni de la demo.

El primer perfil es de asesor�a fiscal: las listas actuales orientadas a IA no sirven como configuraci�n inicial. Su objetivo, condiciones y preferencias siguen pendientes de definici�n por el cliente.
