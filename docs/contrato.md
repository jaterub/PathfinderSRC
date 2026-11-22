# Contrato técnico v0.1

Borrador inicial basado en el alcance acordado. No sustituye un contrato previo: ese texto no se ha aportado a este repositorio.

## Finalidad

Aplicación de búsqueda y evaluación de oportunidades profesionales por cliente, con código y demo públicos como portfolio técnico. Los CV y datos operativos reales se mantienen privados.

## Entradas previstas

- CV del cliente.
- Perfil validado: objetivo, condiciones, competencias y sus grupos, roles, exclusiones y umbrales. No deducir preferencias personales que no consten.
- Ofertas con identificador, empresa, título y, cuando estén disponibles, descripción, salario, ubicación y modalidad. Conservar los datos ausentes como desconocidos.
- Decisiones anteriores del mismo cliente, si existen; nunca utilizar las de otro cliente.

El formato ejecutable y su validación se fijarán junto a la extracción del motor. Esta entrega no promete una API ya implementada.

## Salidas previstas

Puntuación desglosada, clasificación (lead/revisar/descartar), motivos y evidencias. Después, un dashboard generado con el perfil y las ofertas del cliente. Las decisiones humanas se conservan y se distinguen de las automáticas.

## Privacidad y publicación

Solo se versionan ejemplos revisados para publicación. `clientes/ID*/` queda ignorado y la CI falla si detecta esas rutas en el índice Git, incluso con incorporación forzada. La barrera no elimina datos ya publicados ni detecta todos los datos personales posibles.

No se publican el CV, historial, ofertas, registros o credenciales de Profesión. El HTML generado contiene datos: se revisará igual que las entradas antes de publicar una demo. El almacenamiento y control de acceso de los clientes reales requieren su propia implementación antes de atenderlos en una web.

## Criterios de extracción

1. Reutilizar el código existente y conservar su validación y manejo de errores.
2. Separar configuración por cliente del algoritmo compartido; no duplicar reglas de negocio modificadas.
3. Probar el motor público con demo-01 y ejemplos sin datos privados.
4. Ejecutar la regresión de Profesión en privado y revisar diferencias antes de aprobar PR 2.
5. Reutilizar la plantilla y generación de informe para el dashboard, sin conectar la demo al repositorio privado ni a sus credenciales.

## Fuera de esta primera entrega

Puntuación ejecutable por cliente, perfil aún no validado, ofertas demo, dashboard con datos del cliente, alojamiento, captación de nuevas fuentes, automatismos y alta en CCC. Se mantienen como entregas posteriores, sin declararlas completadas. La plantilla v4 sin datos y su función de render ya están extraídas; la ingeniería inversa y sus límites se documentan en `ingenieria-inversa-v4.md`.
