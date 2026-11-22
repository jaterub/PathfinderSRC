# PathfinderSRC

Radar de oportunidades profesionales por cliente. Repositorio p�blico para mostrar el c�digo, las pruebas y una demo a recruiters; los datos de clientes reales permanecen privados.

**Estado: PR 1 � estructura y CV de demostraci�n.** Todav�a no hay motor ejecutable ni web publicada.

## Estructura actual

```text
motor/README.md                 Qu� reutilizamos de Profesi�n y qu� falta extraer
clientes/demo-01/cv.md           CV aportado, sin identidad ni datos de contacto
clientes/demo-01/README.md       Alcance del ejemplo y datos pendientes
pruebas/test_privacidad.py      Barrera contra clientes/ID* versionados
docs/contrato.md                Contrato t�cnico v0.1, borrador
.github/workflows/ci.yml        Comprueba la barrera y el CV de la demo
.gitignore                     Excluye clientes/ID*/
```

## Extracci�n del proyecto privado

| Entrega | Reutilizaci�n prevista | Resultado |
|---|---|---|
| PR 1 � Esta entrega | Estructura y CV aportado | Base p�blica sin datos personales del CV |
| PR 2 � Motor | Puntuaci�n y auxiliares de `2_motor/radar/score_radar.py`, extracci�n de experiencia de `experience.py` | Algoritmo en `motor/`, configuraci�n por cliente y pruebas con demo-01 |
| PR 3 � Dashboard | `build_informe`, `dashboard_html` y `dashboard_plantilla.html` | Dashboard de demo-01 generado con su perfil y ofertas de ejemplo |

El motor original combina puntuaci�n de competencias, experiencia, parecido con decisiones anteriores, t�tulo y salario. Sus preferencias actuales de IA, ubicaci�n, sueldo y exclusiones pertenecen al perfil de su usuario; no se convertir�n en reglas universales ni en preferencias del primer cliente.

Profesi�n se mantiene privado. No se copian su CV, ofertas, candidaturas, decisiones, registros, credenciales ni tareas de captaci�n. La regresi�n con datos de Profesi�n se ejecutar� all� antes de aprobar la extracci�n; las pruebas p�blicas usar�n datos de demostraci�n.

## Verificaci�n

Con Python 3.12 o posterior, desde la ra�z de un checkout Git:

```sh
python -m unittest discover -s pruebas -p "test_*.py" -v
```

La CI comprueba el �ndice Git: tambi�n falla si se fuerza la incorporaci�n de `clientes/ID*/`. Es una barrera por rutas; no sustituye revisar el contenido y los cambios antes de publicar. Un repositorio p�blico conserva sus datos en el historial incluso despu�s de borrarlos de la versi�n actual.

## Datos de clientes

- `clientes/demo-01/`: �nico ejemplo p�blico previsto; conserva la experiencia profesional que el documento aportado describe como ficticia.
- `clientes/ID*/`: convenci�n reservada para datos privados, ignorada y prohibida en Git. Esta carpeta local no es almacenamiento seguro para una aplicaci�n desplegada ni a�sla usuarios.
- El alojamiento, autenticaci�n y separaci�n del almacenamiento de los clientes reales quedan pendientes. No hay aplicaci�n de producci�n en esta entrega.

El alta y la instalaci�n de piezas de CCC quedan para una entrega posterior.
