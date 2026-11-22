# Contrato t�cnico v0.1

Borrador inicial basado en el alcance acordado. No sustituye un contrato previo: ese texto no se ha aportado a este repositorio.

## Finalidad

Aplicaci�n de b�squeda y evaluaci�n de oportunidades profesionales por cliente, con c�digo y demo p�blicos como portfolio t�cnico. Los CV y datos operativos reales se mantienen privados.

## Entradas previstas

- CV del cliente.
- Perfil validado: objetivo, condiciones, competencias y sus grupos, roles, exclusiones y umbrales. No deducir preferencias personales que no consten.
- Ofertas con identificador, empresa, t�tulo y, cuando est�n disponibles, descripci�n, salario, ubicaci�n y modalidad. Conservar los datos ausentes como desconocidos.
- Decisiones anteriores del mismo cliente, si existen; nunca utilizar las de otro cliente.

El formato ejecutable y su validaci�n se fijar�n junto a la extracci�n del motor. Esta entrega no promete una API ya implementada.

## Salidas previstas

Puntuaci�n desglosada, clasificaci�n (lead/revisar/descartar), motivos y evidencias. Despu�s, un dashboard generado con el perfil y las ofertas del cliente. Las decisiones humanas se conservan y se distinguen de las autom�ticas.

## Privacidad y publicaci�n

Solo se versionan ejemplos revisados para publicaci�n. `clientes/ID*/` queda ignorado y la CI falla si detecta esas rutas en el �ndice Git, incluso con incorporaci�n forzada. La barrera no elimina datos ya publicados ni detecta todos los datos personales posibles.

No se publican el CV, historial, ofertas, registros o credenciales de Profesi�n. El HTML generado contiene datos: se revisar� igual que las entradas antes de publicar una demo. El almacenamiento y control de acceso de los clientes reales requieren su propia implementaci�n antes de atenderlos en una web.

## Criterios de extracci�n

1. Reutilizar el c�digo existente y conservar su validaci�n y manejo de errores.
2. Separar configuraci�n por cliente del algoritmo compartido; no duplicar reglas de negocio modificadas.
3. Probar el motor p�blico con demo-01 y ejemplos sin datos privados.
4. Ejecutar la regresi�n de Profesi�n en privado y revisar diferencias antes de aprobar PR 2.
5. Reutilizar la plantilla y generaci�n de informe para el dashboard, sin conectar la demo al repositorio privado ni a sus credenciales.

## Fuera de esta primera entrega

Motor ejecutable, perfil a�n no validado, ofertas demo, dashboard, alojamiento, captaci�n de nuevas fuentes, automatismos y alta en CCC. Se mantienen como entregas posteriores, sin declararlas completadas.
