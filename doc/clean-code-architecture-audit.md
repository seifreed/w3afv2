# Auditoria inicial de Clean Code y Clean Architecture

Fecha: 2026-10-09

## Resultado

| Dimensión | Nota | Confianza |
| --- | ---: | --- |
| Clean Code | 3/10 | Media |
| Clean Architecture | 2/10 | Media |
| Global | 2.5/10 | Media |

La nota global es la media de ambas dimensiones. La puntuación es una línea base
de ingeniería, no una métrica automatizada. Para llegar a 10, las reglas del
proyecto deben estar aplicadas de forma coherente, las dependencias deben tener
dirección explícita y verificable, y las rutas críticas deben contar con pruebas
de comportamiento completas. El inventario dinámico de plugins y el código
vendorizado requieren una revisión separada antes de cerrar la puntuación.

## Hallazgos

### Dependencias entre capas

- El árbol contiene carpetas que sugieren capas, pero `w3af.core.data` todavía
  importa controladores desde 79 archivos (130 coincidencias de import); esto
  acopla datos/dominio con detalles de aplicación e infraestructura.
- Los módulos `w3af/core/data/kb/shell.py`, `read_shell.py` y `exec_shell.py`
  conocen payload handlers, output manager, controladores y plugins. La
  Knowledge Base no está aislada como modelo de dominio.
- `w3af/core/data/kb/knowledge_base.py` publica una instancia global `kb`, que
  introduce estado compartido y dificulta expresar dependencias explícitas.

### Responsabilidades concentradas

- `w3af/core/controllers/w3afCore.py` (692 líneas) construye varios servicios,
  configura estado global y coordina inicialización, estrategia, perfiles,
  estado, objetivos y ejecución.
- `w3af/core/controllers/core_helpers/plugins.py` (463 líneas) mezcla
  descubrimiento del filesystem, importación dinámica, configuración, orden de
  dependencias, creación de instancias y coordinación con output.
- `w3af/core/data/url/extended_urllib.py` (1640 líneas) concentra transporte,
  reintentos, pausas, métricas, evasiones y estado de requests.
- La inicialización de plugins contiene mapas de tipos repetidos; su conjunto
  se mantenía manualmente y podía desincronizarse del filesystem.

### Calidad y verificabilidad

- El gate global de Black pasa: 1967 archivos sin cambios requeridos.
- Ruff global falla con 1260 hallazgos, dominados por nombres indefinidos
  (645), `except` desnudos (222) y usos de imports estrella (89).
- Mypy global falla con errores de imports, nombres y tipos en código propio y
  en el vendor de sqlmap.
- Bandit global falla y recorrió 2,256,458 líneas, incluyendo `venv` y código
  vendorizado: 15,358 hallazgos Low, 966 Medium y 787 High. El output incluye
  warnings del parser, y encontró 16 `# nosec` y 23 hallazgos deshabilitados,
  incompatibles con la política del proyecto.
- `pip-audit` no encontró vulnerabilidades conocidas; mostró warnings al leer
  su caché local.
- El conjunto de pruebas del gestor de plugins depende del ejecutable externo
  `retire`; en este entorno, dos pruebas fallan cuando no está instalado.
- La cobertura observada en el módulo de plugins era 85% antes de este avance.
  No existe aún evidencia de cobertura global del 100%.
- El grafo AST ayuda con referencias estáticas, pero la carga dinámica de plugins
  impide tratarlo como prueba completa de todos los flujos.

## Avance aplicado

- Las estructuras iniciales del registro de plugins se derivan ahora de los
  tipos de paquete descubiertos, conservando la categoría especial `attack` en
  las opciones.
- El descubrimiento ignora carpetas que no sean paquetes Python y excluye
  explícitamente categorías no habilitables (`attack`, `tests`).
- `set_plugins` conserva el orden recibido al eliminar duplicados.
- El orden de evasiones usa la clave de prioridad compatible con Python 3.14.
- Se acotaron tres `except` desnudos encontrados en los módulos revisados y se
  añadieron pruebas reales para estructura del registro y orden de evasiones.
- Las excepciones DB se movieron fuera de `controllers.exceptions` a
  `core.data.db.exceptions`; su base compartida vive ahora en `core.exceptions`.
  Los consumidores Python se actualizaron sin mantener los nombres DB antiguos
  en el módulo de controladores.
- Se corrigieron contratos incompatibles con Python 3 en `Headers.__str__` y
  `DataToken.__str__`, se sustituyó `collections.Iterable` por
  `collections.abc.Iterable`, se dio ID estable a shells de KB y se eliminó un
  sombreado que impedía deserializar valores de la KB.
- La caché del límite de `InfoSet` conserva ahora una copia del grupo y cumple
  el tipo de retorno documentado en `append_uniq_group`.
- El parseo de query strings ya no mezcla `bytes` con separadores `str`, y la
  decodificación porcentual respeta el encoding solicitado. Esto recupera
  parámetros que Python 3.14 descartaba tras un `TypeError` ocultado.
- La normalización conserva la barra raíz para URL `file:///...`; los tests
  usan archivos temporales y la API actual de `multiprocessing`.
- `cleanup()` y `clear()` invalidan las entradas de la caché de `InfoSet` bajo
  el lock del KB, evitando que datos cacheados sobrevivan al borrado.
- Las opciones, parsers, requests y buscadores de `core.data` importan
  `BaseFrameworkException` desde `core.exceptions`, su módulo común, y ya no
  dependen de `controllers.exceptions` para esa clase.
- `is_ip_address` y su test viven ahora en `core.data.misc`; opciones, URL y
  plugins importan desde esa capa de datos, sin dejar un alias en `controllers`.
- `NamedStringIO` e `is_file_like` y sus tests viven ahora en `core.data.misc`; sus
  consumidores de datos y plugins no importan ya `controllers.misc.io`.
- `smart_unicode` decodifica ahora `bytes` conforme a su contrato, y los handlers
  de error para escapes/HTML manejan bytes de Python 3 sin tratar enteros como
  caracteres. El encoder multipart conserva texto al serializar nombres y
  valores, en lugar de interpolar la representación `b'...'`.

## Revisión actualizada

La puntuación global permanece en **2.5/10** (Clean Code 3/10, Clean Architecture
2/10). Se trasladaron errores DB a la capa de datos, el parser URL y la KB
perdieron dependencias concretas de `controllers`, y los contratos Python 3 se
corrigieron. La excepción base común dejó de ser importada desde controladores,
reduciendo las referencias de `core.data` de 179 en 113 archivos a 141 en 88
archivos. Los traslados de `is_ip_address` y `io` redujeron el recuento actual a
130 referencias en 79 archivos. Aun así, `core.data` importa ampliamente desde
`controllers` y las gates globales Ruff/mypy/Bandit fallan.

En las suites integradas de URL, DB, histórico y KB: **203 pasaron, 3 fueron
omitidas y no hubo fallos**. El archivo URL pasa con 113 pruebas y 2 omitidas;
las pruebas de caché, query strings, shell IDs y RFI también pasan en conjunto.
Persisten dos warnings de dependencias `ldap3/pyasn1`; no se suprimieron.

Esta verificación no cubre la suite completa ni acredita cobertura global del
100%. Quedan los defectos de lint/tipos/seguridad, y pruebas de plugins que
requieren el ejecutable externo `retire`.

La verificación más reciente de opciones, parsers, requests y buscadores obtuvo
240 pruebas correctas, 4 omitidas y 146 fallidas; una selección más acotada de
los módulos consumidores obtuvo 12 correctas y 13 fallidas. Los fallos incluyen
uso de `re._pattern_type` y contratos antiguos de HTTP/base64. No se atribuyen
al cambio de ruta de importación, pero tampoco se ha comparado la suite contra
un checkout previo para demostrarlo.

La prueba del helper `is_ip_address` cubre el 100% de sus líneas (5 tests).
Black global pasa y Ruff pasa en orden de imports para los archivos modificados.
La suite que incluyó URL, opciones y `find_vhosts` obtuvo 125 éxitos, 2
omitidos y 2 fallos de integración; uno está en el fixture de `find_vhosts`, que
compara `str` con datos `bytes`, y el otro realiza una conexión HTTP real que no
produce respuesta. Se mantienen registrados sin ocultarlos.

`core.data.misc.io` también tiene 100% de cobertura (4 tests). La suite de
multipart, mutants y plugins de subida obtuvo 23 éxitos y 20 fallos antes del
arreglo de serialización; varios fallos restantes son independientes de ese
encoding y siguen pendientes.

La causa de los nombres `b'file'` quedó reproducida: `smart_str` genera bytes,
pero el encoder multipart construye un cuerpo `str`. El encoder ahora normaliza
bytes a texto en su frontera y las pruebas nuevas cubren valores y nombres byte;
la suite focalizada de encoding/multipart pasa (20 tests, una fixture binaria
omitida porque se lee como UTF-8). Al repetir la batería amplia tras el arreglo,
29 pasaron y 16 fallaron. Los fallos restantes incluyen fixtures binarias
abiertas como texto, APIs privadas de urllib y llamadas HTTP que requieren
servicios externos; no se ha comparado toda esa suite con un checkout anterior.

Una batería adicional de encoding, headers, `HTTPResponse`, URL y multipart
obtuvo 163 éxitos, 3 omitidos y 10 fallos (una prueba se excluyó). Los fallos
observados en `HTTPResponse` terminan en la aserción que exige charset para un
body `str`; no hay evidencia de que los cause el nuevo decode de bytes y tampoco
se compararon con el commit anterior.

La continuación corrigió el contrato de `HTTPResponse` para aceptar cuerpos
`bytes` de `http.client`, decodificar texto según charset de cabecera o meta y
preservar cuerpos binarios, incluidos los bytes crudos al deserializar. También
se corrigió la búsqueda de charset: `re.IGNORECASE` se pasaba como posición de
búsqueda en vez de como bandera. Los hashes de cuerpo/respuesta ahora se
calculan de forma estable sobre bytes SHA-256; la búsqueda de callers estáticos
no encontró consumidores de `HTTPResponse.get_hash()` ni `get_body_hash()` en
el repositorio.

La suite focalizada de respuesta, encoding e histórico obtuvo **40 éxitos y 1
omitido**. La batería ampliada de encoding, headers, `HTTPResponse`, parser URL
y multipart obtuvo **177 éxitos, 2 omitidos y 1 test excluido** (fixture binaria
que el test intenta abrir como UTF-8). Se eliminó el test permanentemente
omitido de `HTTPResponse` cuyo cuerpo no llegaba a ejecutarse. Black global
vuelve a pasar (1967 archivos). Bandit en los dos módulos de producción
modificados no reporta hallazgos; Ruff focal detecta solo los dos nombres de
módulo CamelCase (`HTTPResponse.py`, `test_HTTPResponse.py`), convención que se
mantiene para no romper imports establecidos. La última ejecución global de
`ruff check --statistics .` informa **5776 hallazgos**. Mypy, Bandit global y
pip-audit no se ejecutaron en esta continuación.

Una batería exploratoria de consumidores (`FuzzableRequest`, medición RTT,
plantillas, XML y proxy) obtuvo **12 éxitos y 38 fallos, con 2 warnings**. Los
fallos visibles incluyen APIs incompatibles con Python 3.14 (`collections.Iterable`,
`string.translate`, retorno de `__str__` como bytes y base64 de texto),
concatenación de bytes/texto, apertura UTF-8 de una plantilla binaria y errores
de integración del proxy con mitmproxy/servicios externos. No se comparó esta
batería contra un checkout limpio, así que no se atribuyen los fallos al cambio
de `smart_str`; deben tratarse como defectos o riesgos sin resolver.

La nota global se mantiene en **2.5/10**: esta reparación cierra defectos
concretos de Python 3 en `HTTPResponse`, pero no reduce los acoplamientos de
capas, los módulos concentrados ni los fallos globales de calidad descritos
arriba.

## Prioridades de refactor

1. Establecer límites de capas y una regla automatizada que impida imports desde
   `core.data` hacia `controllers`, `ui` y `plugins`.
2. Separar el modelo y las operaciones de Knowledge Base de shells, output y
   coordinación; retirar el singleton mediante composición explícita.
3. Descomponer `w3afCore`, `CorePlugins` y `ExtendedUrllib` por responsabilidad,
   preservando contratos públicos y flujos de escaneo.
4. Añadir cobertura de comportamiento antes de cada extracción, reemplazando
   dependencias externas por instalaciones reproducibles, no por mocks.
5. Ejecutar y corregir las quality/security gates de todo el repositorio; no
   silenciar reglas. Revisar por separado dependencias, código vendorizado y
   compatibilidad multiplataforma.

La auditoría es deliberadamente iterativa: se actualizarán notas y hallazgos
con cada avance verificado. No se afirmará una nota 10 mientras queden
dependencias de capa, gates fallidas o flujos críticos sin pruebas.
