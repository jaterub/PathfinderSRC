# PathfinderSRC

Radar de oportunidades profesionales por cliente. Repositorio público para mostrar el código, las pruebas y una demo a recruiters; los datos de clientes reales permanecen privados.

**Estado: base pública, CV demo y primera extracción del dashboard v4.** La plantilla y el render ya están extraídos. La puntuación por cliente y la conexión del perfil siguen pendientes; no hay web publicada.

El [análisis de ingeniería inversa y la nota de flexibilidad](docs/ingenieria-inversa-v4.md) documentan el flujo real, sus dependencias y las partes específicas del usuario original. Distinguen lo que ya hace el HTML de las conexiones todavía pendientes.

## Estructura actual

```text
motor/README.md                 Qué reutilizamos de Profesión y qué falta extraer
motor/dashboard.py              Función de generación extraída del motor original
interfaz/dashboard_plantilla.html Código de la interfaz v4, sin datos incrustados
clientes/demo-01/cv.md           CV aportado, sin identidad ni datos de contacto
clientes/demo-01/README.md       Alcance del ejemplo y datos pendientes
pruebas/test_privacidad.py      Barrera contra clientes/ID* versionados
pruebas/test_dashboard.py       Escape seguro del JSON y generaciones independientes
docs/contrato.md                Contrato técnico v0.1, borrador
docs/ingenieria-inversa-v4.md    Dependencias, flujo y nota de flexibilidad
.github/workflows/ci.yml        Comprueba la barrera y el CV de la demo
.gitignore                     Excluye clientes/ID*/
```

## Extracción del proyecto privado

| Entrega | Reutilización prevista | Resultado |
|---|---|---|
| PR 1 · Esta entrega | Estructura y CV aportado | Base pública sin datos personales del CV |
| PR 2 · Motor | Puntuación y auxiliares de `2_motor/radar/score_radar.py`, extracción de experiencia de `experience.py` | Algoritmo en `motor/`, configuración por cliente y pruebas con demo-01 |
| Dashboard · Primera extracción aquí | `dashboard_html` y `dashboard_plantilla.html` ya extraídos; `build_informe` pendiente | Código de interfaz y render públicos; integración con el perfil y ofertas demo aún pendiente |

El motor original combina puntuación de competencias, experiencia, parecido con decisiones anteriores, título y salario. Sus preferencias actuales de IA, ubicación, sueldo y exclusiones pertenecen al perfil de su usuario; no se convertirán en reglas universales ni en preferencias del primer cliente.

Profesión se mantiene privado. No se copian su CV, ofertas, candidaturas, decisiones, registros, credenciales ni tareas de captación. La regresión con datos de Profesión se ejecutará allí antes de aprobar la extracción; las pruebas públicas usarán datos de demostración.

## Verificación

Con Python 3.12 o posterior, desde la raíz de un checkout Git:

```sh
python -m unittest discover -s pruebas -p "test_*.py" -v
```

La CI comprueba el índice Git: también falla si se fuerza la incorporación de `clientes/ID*/`. Es una barrera por rutas; no sustituye revisar el contenido y los cambios antes de publicar. Un repositorio público conserva sus datos en el historial incluso después de borrarlos de la versión actual.

## Datos de clientes

- `clientes/demo-01/`: único ejemplo público previsto; conserva la experiencia profesional que el documento aportado describe como ficticia.
- `clientes/ID*/`: convención reservada para datos privados, ignorada y prohibida en Git. Esta carpeta local no es almacenamiento seguro para una aplicación desplegada ni aísla usuarios.
- El alojamiento, autenticación y separación del almacenamiento de los clientes reales quedan pendientes. No hay aplicación de producción en esta entrega.

El alta y la instalación de piezas de CCC quedan para una entrega posterior.
