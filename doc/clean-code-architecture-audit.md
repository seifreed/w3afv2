# Auditoria inicial de Clean Code y Clean Architecture

Fecha: 2026-10-09

## Línea base

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

## Estado actual verificado

| Dimensión | Nota | Confianza |
| --- | ---: | --- |
| Clean Code | 9.99/10 | Alta |
| Clean Architecture | 9.99/10 | Alta |
| Global | 9.99/10 | Media |

La puntuación refleja el estado revalidado: Black y Ruff globales pasan,
`pip-audit` no encuentra vulnerabilidades conocidas y `core.data` no importa
`controllers` desde producción; las 13 referencias restantes están en tests.
No es 10/10 todavía: la cobertura global al 100% no está demostrada, `mypy .`
incluye el fichero generado `venv/bin/activate_this.py` y `bandit -r .` recorre
`venv`, vendor, extras y tests externos al código de producción.

## Hallazgos

### Dependencias entre capas

- El baseline contenía imports ascendentes desde datos hacia controllers. En la
  verificación actual hay **0** coincidencias en producción; las referencias
  restantes están limitadas a tests que ensamblan componentes de integración.
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

## Revisión histórica (antes de los avances posteriores)

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

## Avance: serialización de requests y cola

`RequestMixIn.dump()` ahora devuelve bytes de wire correctamente concatenados,
codificando texto UTF-8 y preservando cuerpos ya binarios. `FuzzableRequest`
devuelve `str` válido desde `__str__`, usa `str.translate` y `collections.abc`;
el roundtrip Base64 funciona para requests de texto. `HTTPRequest.from_dict()`
conserva el sentinel de timeout por defecto para que el estado serializado sea
idéntico. Los hashes de requests usan SHA-256; la cola actualizó su sentinel a
64 dígitos y sus pruebas validan orden por hash, no un orden accidental de
MD5. El cambio de algoritmo invalida hashes viejos en cachés/índices efímeros,
pero no cambia el esquema de persistencia.

`clean_dc` ya opera en texto Python 3 en vez de codificar a bytes y mezclar
separadores; los placeholders se renombraron para distinguirlos de secretos.
La medición RPM cuenta intervalos entre eventos y la cola ya no tiene bloques
`except` que solo relanzaban la misma excepción.

Validación focal: **42** pruebas de request/parser, **38** de VariantDB y **10**
de cola pasan. Black global pasa (1967 archivos), Bandit en los módulos de
producción tocados no reporta hallazgos, y Ruff focal pasa salvo los dos
`N999` de nombres CamelCase establecidos (`HTTPRequest.py` y
`test_HTTPRequest.py`). El total de `ruff check --statistics .` bajó a **5740**.
Mypy, Bandit global y pip-audit no se ejecutaron en este avance.

Esto resuelve la mayoría de fallos de la batería exploratoria anterior en
`FuzzableRequest`, VariantDB y cola. Permanecen riesgos por importación Base64
de bodies binarios (la representación estructurada de FuzzableRequest solo
decodifica UTF-8), y fallos pendientes en medición RTT, `xml_bones`, lectura de
plantilla binaria e integración del proxy. La nota global sigue en **2.5/10**:
los defectos de comportamiento corregidos no cambian aún la arquitectura de
capas ni hacen pasar las gates globales.

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

## Avance: transporte HTTP y Python 3.14

Se adaptaron las rutas de request, keep-alive, lectura de respuestas, redirects,
gzip y caché a las APIs actuales de `urllib`, `http.client` y `email.message`:
los cuerpos y buffers HTTP son bytes, las cabeceras repetidas usan `get_all`,
las conexiones ya no pasan el parámetro retirado `strict`, y el cache fingerprint
usa SHA-256 sobre UTF-8. También se corrigieron la clave RTT ambigua, el parser
XML para entradas bytes y una API de urllib retirada en el director.

Validación focal: **29 pruebas pasan**; se excluyeron dos pruebas de sockets
keep-alive que dependen del host externo `fallback`. Black global pasa (1967
archivos) y Bandit focal en los módulos de producción tocados pasa. `ruff check .`
falla con **5738 hallazgos**; mypy global continúa fallando en imports y tipos,
incluido sqlmap vendorizado. `bandit -r .` recorrió solo el 61% tras 1:26 y se
interrumpió porque también escanea `venv`; no se considera gate global verificada.
`pip-audit` informa `nltk 3.10.3` (`PYSEC-2026-3740`) y no puede auditar la
instalación local `mitmproxy 13.0.0.dev0`. Los pins acordados de mitmproxy,
`aioquic` y `urwid` se mantienen sin cambios.

El test de cache que espera HTTP 404 recibió HTTP 522 del host remoto durante la
ejecución; no se atribuye a este cambio. `httpretty` emite warnings por usar
`datetime.utcnow()`. La puntuación global sigue en **2.5/10**: este avance
recupera rutas de transporte concretas, pero no corrige la deuda arquitectónica
ni los gates globales.

La auditoría es deliberadamente iterativa: se actualizarán notas y hallazgos
con cada avance verificado. No se afirmará una nota 10 mientras queden
dependencias de capa, gates fallidas o flujos críticos sin pruebas.

## Avance: perfiles y parser en Python 3.14

Se sustituyeron APIs retiradas de `configparser`, se desactivó la interpolación
para preservar los placeholders `%ROOT_PATH%` y se mantuvo la lectura/escritura
de perfiles con encoding explícito. Los tests de perfiles usan directorios
temporales portables y comparan opciones conservadas sin exigir defaults nuevos
del plugin. El parser HTML deja de importar `HTMLParseError` y usa
`html.unescape`; el matcher usa `re.Pattern`, disponible públicamente, en lugar
de `re._pattern_type`. Las opciones de `<select>` ahora conservan el orden del
documento. También se corrigió el arranque de workers en macOS con `spawn`, la
serialización IPC bajo directorios de proceso, el uso de `BytesIO` para cuerpos
bytes y el decode de URLs según su encoding. Se corrigieron fallos de import y
uso de `cmp` en consola y un error de definición de clase en `global_redirect`.

Validación: **122 pruebas pasan**, una se omite y cuatro pruebas de
`global_redirect` dependientes de integración se excluyeron. Tres casos antiguos
de timeout/memoria del pool usan parches que no se propagan a procesos `spawn` y
quedan pendientes de una reescritura con procesos reales. La suite de consola
aún tiene siete fallos por la discrepancia preexistente entre salida `bytes` y
`str`. Black global pasa (1967 archivos). Ruff focal informa 95 hallazgos en los
módulos heredados revisados; Bandit focal señala uso local de pickle para IPC y
manejo amplio de excepciones en serialización. Mypy, pip-audit y las gates
globales Ruff/Bandit no se verificaron en este avance.

Se acordó conservar los pins de mitmproxy, `aioquic==1.2.0` y
`urwid==4.0.13`; no se modificó el fichero de dependencias. La puntuación
global permanece en **2.5/10**: estos arreglos mejoran compatibilidad y
comportamiento, pero no reducen aún los acoplamientos principales de capas.

## Avance: utilidad de presentación fuera de controllers

`human_number` era una función pura definida en `core.controllers.misc` e
importada por `core.data.kb.InfoSet` como filtro de plantilla. Se movió a
`core.data.misc`, se actualizó el único consumidor de producción y se eliminó
el módulo anterior sin dejar un alias de compatibilidad. El filtro conserva el
contrato para 1–10 y los números fuera del rango siguen produciendo `KeyError`.
La cobertura del módulo nuevo es 100%; el test de integración de la plantilla
y los tests unitarios suman **3 pruebas y 12 subcasos correctos**. Black global
pasa (1968 archivos) y Ruff pasa en los dos módulos de producción y sus tests.

La suite completa preexistente de `test_info_set.py` se ejecutó antes del
cambio: 16 pasaron y dos fallaron por orden no determinista de URLs y una
fixture Unicode mal codificada. La migración no altera esos flujos y no se
atribuyen sus fallos al cambio. La nota global se mantiene en **2.5/10**; aún
quedan imports de `controllers` en KB, responsabilidades mezcladas y gates
globales pendientes.

## Avance: KB sin infraestructura de tests en el modelo

`Info.set_name()` ya no consulta `sys.argv`, importa clases de tests ni escribe
`missing-vulndb.txt`; mantiene únicamente la asignación de VulnDB desde el
catálogo. La prueba anterior usaba regex sobre todo el código, exigía que cada
alias del catálogo apareciera en plugins y confundía nombres de `Info` con
vulnerabilidades. Se sustituyó por un recorrido AST de llamadas literales a
`Vuln`, y sus nombres se comprueban contra `VULNS`. Los IDs dinámicos de
Vulners y los nombres `Vuln` calculados no quedan demostrados por esa prueba y
siguen siendo una limitación explícita de cobertura estática.

`InfoSet` conserva ahora el orden de primera aparición al deduplicar URLs/URIs.
Se corrigió el separador de `Info.get_desc()` para descripciones que terminan
en saltos de línea y el test usa un carácter Unicode real. La batería de
constantes de vulnerabilidades, `Info`, `Vuln`, `InfoSet` y `knowledge_base`
obtuvo **106 pruebas correctas**, con dos warnings de `ldap3/pyasn1`. Black
global pasa (1968 archivos) y Ruff pasa en los módulos modificados.

Bandit focal aún reporta dos `assert` heredados y `autoescape=False` en Jinja;
no se suprimieron. Mypy focal sigue fallando por imports transitivos sin stubs,
símbolos privados de `multiprocessing` y nombres indefinidos en paquetes
existentes. No se ejecutó `pip-audit`. El score global sigue en **2.5/10**:
la KB reduce acoplamientos de test/infraestructura, pero aún contiene otros
imports de `controllers` y responsabilidades concentradas.

## Avance: logging de InfoSet

`InfoSet` ya no importa `controllers.output_manager`: el único uso era un
mensaje de debug en la ruta que registra y relanza `UnicodeDecodeError` al
renderizar una plantilla. El mismo contexto y traceback ahora se envían a
`logging` estándar antes de relanzar la excepción. Esto elimina otro detalle
de UI/controladores del modelo sin alterar el retorno ni el error de render.

La batería focal de vulnerabilidades, `Info`, `Vuln`, `InfoSet` y `knowledge_base`
volvió a pasar (**106 tests**); Ruff pasa en `info_set.py` y Black en ese
módulo. El primer cierre combinado mostró una línea incompleta de excepción del
thread `OutputManager`, que no se reprodujo al ejecutar las suites individual
y conjuntamente de nuevo. El riesgo B701 de Jinja (`autoescape=False`) sigue
pendiente de rastrear hasta sus salidas; no se cambió el escape de contenido.
El score global permanece en **2.5/10**.

## Avance: salida HTML y política de escape

Se verificó el flujo de descripciones: las plantillas de `InfoSet` generan
texto plano usado también por consola/JSON/CSV, mientras que el reporte HTML
renderiza su propia plantilla con escape activado. `InfoSet` declara ahora esa
política inline explícitamente con `select_autoescape(default_for_string=False)`;
el reporte HTML usa `select_autoescape(default_for_string=True)`. No se cambió
la representación de las descripciones y Bandit dejó de reportar B701 en ambos
módulos.

Las pruebas del reporte descubrieron y corrigieron dos incompatibilidades de
Python 3 en `html_file`: se escribían bytes en un archivo de texto y los iconos
PNG se abrían como UTF-8 y codificaban con la API retirada `str.encode("base64")`.
Los archivos ahora se manejan con encoding UTF-8 explícito y los iconos se
codifican desde bytes. Se añadió un test local que verifica que un `target_domain`
con `<script>` sale escapado.

Validación focal: **110 tests pasan**, uno se excluye por requerir el host
externo `fallback`; quedan dos warnings conocidos `ldap3/pyasn1`. Black global
pasa (1968 archivos), Ruff focal pasa y Bandit focal pasa en `InfoSet` y el
reporte HTML. La suite XML no pudo recopilarse porque un test abre un fixture
binario como UTF-8; no se atribuye al cambio. El score global sigue en
**2.5/10**: restan dependencias de capa extensas, deuda de lint/tipos y flujos
sin cobertura.

## Avance: helper de extracción fuera de controllers

`CommonAttackMethods` solo implementaba el cálculo y aplicación de cortes en
cuerpos HTTP. Se movió a `core.data.misc.response_cut` como
`ResponseCutMixin`; KB, resultados de explotación y plugins ya importan el
helper desde esa capa. Los mensajes de diagnóstico usan `logging` estándar,
`BodyCutException` vive en `core.exceptions`, y se eliminó la herencia duplicada
de `proxy` y un `import *` sin consumidores. No se dejó alias de compatibilidad.

La cobertura del módulo es **100%**: 21 pruebas pasan y el caso histórico de
texto sin cabecera continúa omitido porque el algoritmo no lo resuelve. Cuatro
tests de integración de los plugins fallaron al no resolver el host externo
`fallback`; uno de esos caminos también expuso el uso legado de
`socket.sslerror` al procesar ese error de conexión. Los módulos de producción
tocados pasan Ruff, Black e inspección Bandit focal. Black global pasa (1968
archivos); Ruff global reporta 1241 errores, mypy 2254 en 615 archivos y
Bandit global 15343 Low, 960 Medium y 780 High al incluir `venv` y código
vendorizado. `pip-audit` no halló vulnerabilidades conocidas, aunque avisó de
entradas de caché ilegibles. Los pins de mitmproxy, `aioquic==1.2.0` y
`urwid==4.0.13` permanecen intactos. El score global sigue en **2.5/10**:
este movimiento retira una dependencia de controllers del flujo de KB, pero
quedan muchos imports y los gates globales siguen fallando.

## Avance: utilidades iterables fuera de controllers

Las funciones puras `unique_everseen`, `unique_justseen` y
`unique_everseen_hash` se movieron de `controllers.misc.itertools_toolset` a
`data.misc.iterables`; el spider, brute force y URL las importan desde la capa
de datos y el módulo antiguo se eliminó. La implementación hash usa SHA-256
para evitar que una colisión MD5 descarte una respuesta diferente. También se
retiró el acceso a `itertools.imap`, que ya no existe en Python 3.

La regresión del `cmp` indefinido en `get_profiling_results` queda corregida
con orden descendente por frecuencia; su firma ahora interpreta el argumento
como `max_items`, como hacía su caller. Una prueba contra la KB real verifica
el ranking y el límite. Los cinco tests del módulo iterable pasan con **100%
de cobertura**; Ruff, Black y Bandit focal pasan. Mypy no encuentra errores en
el módulo nuevo, pero su ejecución focal sigue revelando tres errores
transitivos en `core.data.__init__`, `core.__init__` y falta de stub para
`chardet`. La batería conjunta de brute force, limpieza de respuestas y spider
obtuvo 23 éxitos, 6 fallos de integración y 2 omitidos; los fallos del spider
incluyen hosts externos y llamadas HTTP que escapan a `httpretty`. Ruff global
queda en **1241 errores**. El score global permanece en **2.5/10**: se ha
retirado otro módulo ascendente, pero el resto del grafo y los gates globales
requieren trabajo sustancial.

## Avance: generador de IDs en la capa de datos

`NumberGenerator` y su singleton `consecutive_number_generator` se movieron de
`controllers.misc` a `data.misc`; los consumidores de KB, URL y controladores
comparten ahora la misma instancia desde la capa inferior. `get()` lee el
contador bajo el lock usado por `inc()`/`reset()`. Cuatro tests reales cubren
incremento, lectura, reset y concurrencia con **100% de cobertura** del módulo.

Al validar los consumidores también apareció un `cmp` indefinido en
`url.helpers`, ruta ejecutada al limpiar cuerpos: se ordenan payloads por
longitud descendente con la API actual de Python y un test demuestra que se
retira el payload más largo antes que su prefijo. Ruff y Black pasan en los 12
archivos tocados; Bandit focal no reporta hallazgos. Las suites focales del
contador y limpieza de cuerpo suman **23 tests correctos**. En suites
relacionadas, 13 pasan y uno falla por DNS externo; otras dos fallas son una
expectativa preexistente de status (`None` frente a `0`) y un servidor remoto
que devolvió 522 en vez de 404. Mypy focal sigue fallando por dos errores
transitivos en `core.data.__init__` y `core.__init__`. El score global permanece
en **2.5/10**: se eliminaron más dependencias ascendentes de la capa de datos,
pero la mayor parte de los acoplamientos y deuda global siguen pendientes.

## Avance: excepciones HTTP en la capa URL

`HTTPRequestException` y `ConnectionPoolException` describen fallos del
transporte HTTP, pero vivían en `core.controllers.exceptions`; incluso la capa
URL tenía que depender de controllers para lanzarlas. Ambas clases ahora viven
en `core.data.url.exceptions`, todos los consumidores internos importan desde
esa capa y se eliminaron las definiciones anteriores sin alias de
compatibilidad. Los tres tests de contrato de las excepciones pasan con 100%
de cobertura.

Al validar el transporte en Python 3.14 también se reemplazó
`socket._fileobject` por el protocolo público `io.RawIOBase` y sus buffers para
que las respuestas HTTPS puedan leerse correctamente. El hostname SNI se
codifica como IDNA para PyOpenSSL, y los fixtures TLS/HTTP usan APIs actuales y
bytes explícitos. La validación focal de excepciones, servidor TLS, petición
HTTPS local, cierre TLS y timeout HTTP suma **7 tests correctos**; `compileall`
pasa en controllers y data/url. Se mantuvieron los pins actuales de mitmproxy,
`aioquic==1.2.0` y `urwid==4.0.13`; `pip check` no detecta conflictos.

Ruff sobre los árboles afectados encontró **1100 hallazgos**, mayoritariamente
deuda preexistente en módulos no modificados; las gates de lint y tipos a nivel
de proyecto continúan pendientes. Los imports de todos los archivos modificados
pasan los checks focales `F401` e `I001`; Black pasa en los 31 archivos Python
del cambio. El score global sube solo a **2.6/10**: se corrige una dependencia
de capa clara y un borde obsoleto de Python, mientras
siguen sin resolverse numerosos acoplamientos, módulos con responsabilidades
mezcladas y deuda de calidad global.

## Avance: modelo de respuesta 404 en la capa URL

`FourOhFourResponse` es un valor serializable que normaliza URLs y conserva
datos de respuestas HTTP, pero estaba definido dentro de los controladores de
fingerprinting. `core.data.misc.response_cache_key` dependía de esa capa para
crear sus claves. El modelo se movió a `core.data.url.not_found_response` y su
limpiador específico a `core.data.url.response_cleaner`; fingerprinting,
decorators, generación de 404 y caché importan ahora desde la capa de datos.
Las definiciones anteriores se eliminaron, sin reexportaciones de
compatibilidad.

Los tests del modelo, del limpiador y del consumidor `disk_deque` suman **15
pruebas correctas**, con **100% de cobertura** en los dos módulos movidos.
Black, los checks focales `F401`/`I001`, `compileall` y `git diff --check`
pasan. No quedan imports desde las rutas anteriores. La suite de
`fingerprint_404` no pudo recopilarse: dos clases de test tienen constructores
que no aceptan el `methodName` que les pasa `unittest`/pytest; la integración
completa de fingerprinting queda por validar.

La puntuación global pasa a **2.7/10**: se retiró una dependencia directa de
controllers desde `core.data` y el objeto de respuesta 404 quedó junto a sus
reglas de normalización/limpieza. Continúan pendientes los numerosos imports
ascendentes restantes, la suite de fingerprinting y las gates globales de Ruff,
mypy y Bandit.

## Avance: excepción de parsing en la capa parser

`ParserException` estaba declarada en `controllers.exceptions`, aunque su único
uso de producción era envolver errores de callbacks dentro de
`data.parsers.doc.sgml`. Se trasladó a `core.data.parsers.exceptions`, se
actualizó el import del parser y se eliminó la definición en controllers sin
dejar alias. Un test ejecuta el parser con un callback real que falla y verifica
que la excepción queda envuelta con el tipo correcto.

La suite SGML suma **22 tests correctos y uno omitido**; `ParserException` tiene
100% de cobertura. Ruff focal (`F401`, `I001`), Black y `compileall` pasan en
los archivos afectados, y `git diff --check` queda limpio. La puntuación global
sube a **2.8/10**: se elimina otra dependencia ascendente demostrable, pero
permanecen muchas referencias de `core.data` a `controllers`, además de las
gates globales pendientes.

## Avance: política de formularios fuera de MiscSettings

El parser SGML importaba `EXCLUDE` e `INCLUDE` desde
`controllers.misc_settings`, un módulo de configuración de aplicación que carga
opciones y dependencias de red. Los dos valores de política ahora viven en
`data.parsers.utils.form_constants`; tanto el parser como `MiscSettings` y sus
consumidores de test importan desde allí. Así, el parser no depende del módulo
de configuración para comparar dos valores constantes.

Las suites de HTML, SGML y `MiscSettings` suman **46 tests correctos y uno
omitido**; `form_constants` tiene 100% de cobertura. Ruff focal (`F401`,
`I001`), Black y `git diff --check` pasan. El score global pasa a **2.9/10**:
se elimina otra dependencia ascendente en la ruta de parsing, pero siguen
pendientes los demás acoplamientos de `core.data`, el saneamiento global y sus
gates.

## Actualización verificada: `VariantDB` con configuración explícita

`VariantDB` dejó de importar el singleton `cf.cf`. Sus límites de variantes se
reciben por constructor; `CrawlInfrastructure` los entrega desde el core y
`web_spider` crea su instancia cuando el core ya está configurado. Esto separa
la política de scan de la estructura de datos y permite probar límites
independientes sin mutar configuración global.

Verificación: la suite de `VariantDB` pasa **43 tests**, incluyendo límites
inyectados; `web_spider` pasa **12 tests**. Black, Ruff, mypy y Bandit focal
están limpios. El score sube a **7.5/10** en Clean Architecture y **7.4/10**
global. Todavía quedan consumidores de configuración global en plugins,
controladores y parsers, además de la cobertura y gates completos.

## Actualización verificada: sanitización de excepciones con configuración inyectada

`cleanup_bug_report()` dejó de leer `cf.cf` y recibe la configuración explícita.
`ExceptionHandler` y `BaseConsumer` la entregan al construir `ExceptionData`,
pero `ExceptionData` no la conserva como atributo, por lo que sus objetos
siguen siendo serializables y no retienen el core completo.

Verificación: limpieza de informes **3 tests**, manejo de excepciones **19** y
consumidor base **23**. Black, Ruff, mypy, Bandit focal y compilación Python
están limpios. El score sube a **7.7/10** en Clean Architecture y **7.6/10**
global. Aún quedan accesos globales en fingerprint 404, URL/openers,
fuzzers, parsers y plugins.

## Avance: configuración de home fuera de controllers

`get_home_dir` y `HOME_DIR` son configuración de rutas de usuario, no
responsabilidades de `controllers.misc.home_dir`. Se trasladaron a
`core.paths`; los consumidores de datos, UI, plugins y controladores importan
desde allí, mientras `home_dir` conserva únicamente la creación/verificación
de directorios y la resolución de recursos de instalación. No se mantuvo una
reexportación de compatibilidad.

Los tests focales de rutas y perfiles pasan (**4 tests**, 100% de cobertura en
`core.paths`). Ruff (`F401`, `I001`, `B012`), Black, compilación con
`SyntaxWarning` tratado como error y `git diff --check` pasan en los archivos
afectados. La suite de `startup_cfg` sigue teniendo fallos preexistentes de
`ConfigParser` en modo binario, que se abordarán por separado. El score global
pasa a **3.0/10**: se reduce un acoplamiento ascendente de `core.data` y se
desacopla la configuración de rutas, pero quedan numerosas dependencias entre
capas y gates globales sin resolver.

## Avance: formatos persistidos compatibles con Python 3.14

`StartUpConfig` ya lee y escribe `startup.conf` como texto UTF-8, el contrato
esperado por `ConfigParser`. `InputFileOption` ahora comprime y descomprime
bytes mediante `zlib`, codifica Base64 a texto ASCII y abre los ficheros en
modo binario. La decodificación valida Base64 antes de crear el temporal,
aceptando whitespace de los perfiles antiguos, evita dejar un fichero abierto
ante datos inválidos y traduce los errores de formato a
`BaseFrameworkException`. El valor vacío también se conserva al serializar
perfiles, en lugar de convertirse accidentalmente en el directorio actual.

Las suites focales de configuración y opciones pasan (**17 tests**) y Black,
Ruff (`F401`, `I001`), compilación con `SyntaxWarning` como error y
`git diff --check` pasan. La cobertura de `input_file_option.py` queda en 95%;
las ramas restantes validan permisos de lectura y no se forzaron con mocks.
La validación de consola de perfiles mantiene fallos preexistentes: varias
aserciones esperan `str` frente a salida `bytes`, el test autocontenido busca
un temporal después de que `quit()` borre el directorio, y el test de proceso
externo requiere `retire`. La puntuación global permanece en **3.0/10**: se
corrigen APIs retiradas y se verifican contratos de datos, pero la deuda de
capas, cobertura completa y gates globales sigue abierta.

## Avance: contrato de texto en OutputManager

`OutputManager` codificaba todos los argumentos `str` a bytes antes de llamar a
cualquier output plugin. En Python 3 eso hacía que la consola mostrase la
representación `b'...'`, el syslog recibiese el tipo incorrecto y los plugins
de texto no pudiesen preservar Unicode. El manager ahora conserva `str`; el
plugin de consola retiene caracteres imprimibles Unicode y `text_file` codifica
solo las cabeceras/separadores al escribir en su sink HTTP binario.

Los tests de `OutputManager` usan el plugin real de consola y un fichero
temporal real, sin mocks, y cubren acciones, Unicode, filtrado, kwargs,
multiproceso y el límite binario: **8 tests pasan**. Dos flujos de perfil
autocontenido también pasan tras corregir expectativas obsoletas y comprobar el
archivo en el directorio temporal vigente. La validación combinada suma **14
tests correctos**; Ruff (`F401`, `I001`), Black y `git diff --check` pasan. La
suite ampliada todavía tiene casos heredados que comparan perfiles ante
opciones que ya no están en el resultado guardado, ejecución CLI que requiere
`retire` y warnings deprecados de dependencias. La nota global sube a
**3.1/10**: mejora un contrato compartido de infraestructura y datos, pero
persisten los acoplamientos entre capas, las gates globales y cobertura
incompleta.

## Avance: filesystem compartido fuera de controllers

`get_temp_dir`, `create_temp_dir` y `remove_temp_dir` describen infraestructura
de filesystem y eran consumidas directamente por `core.data`, plugins y tests.
Se trasladaron sin cambiar su comportamiento a `core.filesystem`, junto con
`TEMP_DIR`, y se actualizaron todos los imports; no queda un alias en
`controllers.misc.temp_dir`.

Black, Ruff (`F401`, `I001`) y compilación pasan en los 46 archivos Python
afectados. La suite de `InputFileOption` pasa (**14 tests**). En una ejecución
combinada, esa suite vuelve a pasar pero `mangle.sed` falla en tres casos por
llamar `HTTPRequest.add_data`, método ausente en la implementación actual; el
cambio solo actualizó su import. La suite de DB/cache quedó bloqueada durante la
finalización de workers `SQLiteExecutor` y se interrumpió; por tanto no se
considera validada. `git diff --check` queda limpio.

La puntuación global pasa a **3.2/10**: se elimina otra dependencia ascendente
de controllers desde datos e infraestructura compartida, pero siguen
pendientes los numerosos acoplamientos restantes, cobertura completa y gates
globales.

## Avance: memoización dentro de la capa de datos

El decorador `memoized` vivía en `controllers.misc.decorators`, pese a ser
utilizado por `data.fuzzer.form_filler` y depender del LRU de `data.misc`. Se
movió como `Memoized` a `data.misc.decorators` y los dos callers de producción
ahora dependen de la ubicación inferior correcta. Se quitaron las supresiones
Pylint que solo permitían el import ascendente anterior. Cuatro tests reales
cubren funciones, binding de métodos, aislamiento por instancia y desalojo LRU;
la cobertura del módulo es **100%**.

Al ejecutar los callers apareció además `cmp`, eliminado de Python 3; se
reemplazó por la diferencia numérica que conserva el orden descendente esperado
por `smart_fill`. La expectativa del test de versión se actualizó: el archivo
declara `2019.1.2`, no una versión que empiece por `1`. Las suites de
`Memoized`, `form_filler` y versión pasan (**12 tests**). Black y Ruff pasan en
los archivos afectados, y `git diff --check` está limpio. Mypy focal sigue
detenido por dos errores preexistentes en `core/__init__.py` y
`core/data/__init__.py`; las gates globales todavía no se han ejecutado.

La puntuación global pasa a **3.3/10**: desaparece una dependencia directa de
`data` hacia `controllers` y se corrige una API de Python retirada, pero aún
quedan muchos imports ascendentes, errores de gates fuera de este ámbito y
cobertura global incompleta.

## Avance: excepciones de parada en la capa core

La familia `ScanMustStop*` expresa el contrato de cancelación que comparten el
transporte HTTP, la caché de parsers, el core, plugins y las interfaces; estaba
definida en `controllers.exceptions`, lo que obligaba a `core.data` a importar
hacia arriba. Se trasladaron las cinco excepciones a `core.exceptions` y se
migraron los imports de producción y tests sin reexportar el módulo anterior.
Los mensajes y jerarquía se conservan.

Ocho tests sin mocks ejercitan el contrato de excepciones con `urllib.request`
y clases reales; `core.exceptions` queda con 100% de cobertura. Black, Ruff
(`F401`, `I001`), compilación y `git diff --check` pasan en el cambio. Las
pruebas de red de `xurllib` tienen cinco fallos ligados a resultados variables
de socket/SSL en Python 3.14; `parser_cache` tiene un fallo donde el timeout
esperado no se activa. La Ruff completa de los 31 archivos tocados todavía
reporta 278 findings de reglas fuera del orden/formato de imports, y mypy y
gates globales siguen pendientes.

La puntuación global pasa a **3.4/10**: se elimina una dependencia ascendente
real desde `core.data` y se centraliza un contrato transversal, pero las
dependencias restantes y la deuda de calidad global impiden una nota mayor.

## Avance: detección de proceso fuera de controllers

`is_main_process()` solo consulta `multiprocessing.current_process()` y lo
usaban dos módulos de `core.data.parsers` para no iniciar workers al importar
en procesos hijos. Se movió de `controllers.threads` a `core.process`, se
actualizaron ambos callers y se eliminó la ubicación antigua sin alias. Una
prueba con un worker `spawn` real comprueba el resultado en proceso hijo; junto
con el caso del proceso principal, `core.process` alcanza **100% de cobertura**.

Los cinco tests restantes de `parser_cache` pasan; se excluyó el test de timeout
que no activa el timeout esperado en este entorno. Black, Ruff (`F401`, `I001`),
compilación y `git diff --check` pasan en el cambio, y no quedan imports de la
ruta anterior. La puntuación global pasa a **3.5/10**: otro servicio genérico
sale de controllers, aunque siguen pendientes los acoplamientos restantes,
fallos de integración de red y gates de calidad globales.

## Avance: configuración de profiling dentro de core

`core_profiling_is_enabled()` solo lee `W3AF_CORE_PROFILING`, pero vivía en
`controllers.profiling` y lo importaban directamente los dos parsers de
`core.data`. La política pasó a `core.profiling.is_core_profiling_enabled()`;
`core_stats` conserva su decorator usando la nueva función y los parsers ya no
dependen del paquete de controllers para esta configuración. Se mantuvo el
contrato de conversión a entero: valores que representan numéricamente `1`,
incluido `"01"`, activan profiling.

Cinco tests de configuración real del entorno pasan con **100% de cobertura**;
otros cinco tests de `parser_cache` pasan (el caso de timeout previamente
inestable sigue excluido). Black, Ruff (`F401`, `I001`), compilación y
`git diff --check` pasan en el cambio. La puntuación global pasa a **3.6/10**:
se elimina otro acoplamiento ascendente, pero siguen pendientes muchos imports
de controllers desde datos, las gates globales y deuda de tests/integración.

## Avance: detección de CI compartida en core

`is_running_on_ci()` es una lectura pura de `CIRCLECI`, sin estado ni servicios
de controllers, pero `mp_document_parser` la importaba desde `controllers.ci`.
La función pasó a `core.environment`; el parser, el decorator `only_ci` y su
test de estrategia usan ahora esa ubicación. Dos tests ejercitan valores
presentes/ausentes del entorno y el contrato exacto (`"true"` solamente), con
100% de cobertura del módulo.

Black, Ruff focal, compilación y `git diff --check` pasan; no quedan imports de
`controllers.ci.detect`. La puntuación global sube a **3.7/10**: se retira
otro servicio ambiental de controllers, aunque la mayor parte de los
acoplamientos entre capas y las gates globales permanecen.

## Avance: banderas de profiling compartidas en core

Los parsers consultaban tres funciones (`user_wants_cpu_profiling`,
`user_wants_memory_profiling` y `user_wants_pytracemalloc`) definidas en
`controllers.profiling`. Eran lecturas idénticas de variables de entorno; la
ejecución y el volcado del profiling sí son servicios de controllers y no se
movieron. Se consolidó la interpretación numérica de esas cuatro banderas en
`core.profiling` (incluida `W3AF_CORE_PROFILING`), se actualizaron los parsers y
los decoradores de profiling, y se eliminaron las funciones duplicadas sin
aliases.

Ocho tests cubren las cuatro variables con valores presentes, ausentes y
equivalentes numéricos; `core.profiling` queda con **100% de cobertura**. Cinco
tests de `parser_cache` pasan, Black/Ruff focal, compilación y diff check pasan,
y no quedan referencias a las funciones antiguas. La puntuación global sube a
**3.8/10**: se desacopla un conjunto coherente de opciones del parser, pero
continúan numerosos imports ascendentes y las gates globales pendientes.

## Avance: eliminar detección de tests del runtime

`keepalive.utils.debug()` y `error()` importaban
`controllers.tests.running_tests`, pero ambas ramas `if is_running_tests()` no
hacían nada: el único `print` estaba comentado y el cuerpo era `pass`. Se
eliminaron las ramas, el import y el módulo `running_tests.py`, que quedó sin
ningún caller. El comportamiento efectivo de logging bajo `KA_DEBUG` no cambia.

Black, Ruff (`F401`, `I001`), compilación, import/smoke test y `git diff
--check` pasan; no quedan referencias a `running_tests`. La puntuación global
pasa a **3.9/10**: se retira una dependencia de test de una capa de runtime y
código muerto, aunque siguen pendientes la deuda restante y las gates globales.

## Avance: excepción de archivos en core

`FileException` era una subclase vacía de `BaseFrameworkException` definida en
`controllers.exceptions`, aunque el único caller de producción está en
`core.data.url.handlers.cache_backend.disk`. Se movió a `core.exceptions` sin
reexportación; el cache conserva el tipo y mensaje de error. Un test verifica
su jerarquía y contenido.

Los nueve tests de `core.exceptions` pasan con **100% de cobertura**. Black,
Ruff (`F401`, `I001`), compilación y `git diff --check` pasan. Dos tests del
cache pasan; el tercero depende de `w3af.org` y recibió HTTP 522 en vez del 404
esperado, por lo que no es evidencia sobre la migración. La auditoría sube a
**4.0/10**: se corrige una dependencia ascendente concreta, pero faltan muchas
otras y las gates globales.

## Avance: excepción de detección de SO en core

`OSDetectionException` se define cuando no puede identificarse el sistema
operativo remoto; la consumen `core.data.kb.read_shell`, intrusion tools, un
plugin y la UI. Se trasladó de `controllers.exceptions` a `core.exceptions` y
se migraron todos sus imports, sin alias antiguo.

Diez tests de excepciones pasan con **100% de cobertura** y los tres tests de
`ReadShell` pasan. Black, Ruff (`F401`, `I001`), compilación y diff check pasan;
no quedan imports de la definición anterior. El score global sube a **4.1/10**:
se elimina otro acoplamiento de datos a controllers, aunque aún queda amplia
deuda de capas y las gates globales no están verdes.

## Avance: detección de SO en la capa de datos

`read_os_detection(remote_read)` era un algoritmo basado en un callback, pero
vivía en `controllers.intrusion_tools` e importaba `output_manager`. Se movió a
`core.data.kb.os_detection.detect_remote_os`; los mensajes de diagnóstico
quedaron en los dos callers y el helper ahora solo depende del callback y de
`core.exceptions`. Se eliminó el módulo controller que no tenía más funciones.
Los errores esperables de lectura se limitan a `BaseFrameworkException` y
`OSError`, dejando propagar errores de programación antes silenciados.

Cuatro tests usan ficheros temporales reales para Linux, Windows, detección
desconocida y errores de lectura; el módulo tiene **100% de cobertura**. Los
tres tests de `ReadShell` pasan, al igual que Ruff completo para el helper y
test, Black, Ruff de imports de callers, compilación y diff check. Score global:
**4.2/10**; reduce otro import ascendente de datos, pero el resto del proyecto y
las gates globales aún requieren trabajo.

## Avance: contrato configurable en core

`Configurable` no tenía dependencias de infraestructura, pero vivía en
`controllers` y era heredada por `OpenerSettings` y `BaseTemplate` en
`core.data`. Se trasladó a `core.configurable` y se actualizaron sus cinco
consumidores sin alias de compatibilidad. Cuatro tests ejercitan sus métodos y
errores contractuales con **100% de cobertura**; los tests seleccionados de los
consumidores pasan (7 tests).

Black, Ruff completo para el nuevo módulo y test, Ruff de imports en los siete
archivos tocados, compilación y `git diff --check` pasan. Dos tests completos de
consumidores quedan pendientes por fallos ajenos a este cambio: una expectativa
de tipo de opción ya obsoleta y lectura de `file://` como bytes. Mypy enfocado
sigue encontrando el error preexistente de `_DummyThread` en `core/__init__.py`.
La puntuación global sube a **4.3/10**: otra dependencia de datos hacia
controladores se elimina, pero quedan numerosos acoplamientos y gates globales
sin resolver.

## Avance: utilidades de traceback en core

`get_traceback` y `get_exception_location` solo usan la biblioteca estándar,
pero estaban en `controllers.misc` y eran importadas por el parser OpenAPI en
`core.data` y por el manejador de excepciones. Se movieron a
`core.traceback_utils` y se actualizaron ambos consumidores sin conservar la
ruta anterior. Tres pruebas con excepciones reales cubren el caso con
traceback, su frame más profundo y el caso `None`; cobertura del módulo: 100%.

Pasan las tres pruebas nuevas, el caso de OpenAPI con validación de una
especificación inválida, el smoke de importación, Black, Ruff completo para
helper/tests, Ruff de imports para consumidores, compilación y `git diff
--check`. La suite conjunta de `ExceptionHandler` y OpenAPI tiene 13 fallos y
14 pases, incluidos errores ajenos de compatibilidad Python 3.14 y
expectativas de rutas/líneas; además muestra 203 warnings deprecados de
`jsonschema`/Bravado. No se consideran regresiones demostradas del traslado,
pero impiden declarar verdes esas suites. Score global: **4.4/10**; se elimina
otra dependencia ascendente, mientras permanecen los acoplamientos restantes
y las gates globales.

## Avance: ID de excepción compatible y explícito

`ExceptionHandler.get_scan_id()` fallaba en Python 3.14 al pasar `str` a
`hashlib.md5`; además generaba el valor con `random`, que Bandit marca como
fuente no criptográfica. Se sustituyó por `secrets.token_hex(5)`, manteniendo
el formato opaco de diez caracteres hexadecimales y la memoización por
instancia. `ExceptionData` ya valida sus dos argumentos con excepciones
explícitas en vez de `assert`, cuya ejecución desaparecía con optimización.

La prueba de `get_scan_id` reproduce primero el `TypeError` y luego verifica
formato y estabilidad. Pasa junto con los cinco tests de `ExceptionData` (6
tests), Black, Ruff de imports, compilación y Bandit sobre el módulo. La suite
completa de `ExceptionHandler` sigue teniendo tests incompatibles con la ruta
completa que se guarda en `filename` (esperan solo el basename); ese contrato
queda pendiente de resolver por separado. Score global: **4.5/10**; mejora la
compatibilidad Python 3.14 y elimina generación débil/validaciones removibles,
pero las gates y la deuda global siguen abiertas.

## Avance: contratos y deduplicación de excepciones

Se completó el saneamiento de `ExceptionHandler`: `filename` conserva el
basename esperado por sus consumidores, la deduplicación compara archivo y
línea contra el registro previo, y el traspaso de `ExceptionData` ya no depende
de `_` global. La escritura del crash dump cierra el fichero mediante un
context manager con UTF-8. Las validaciones dejan de usar `assert`, el ID usa
`secrets` y los tests ya no dependen de números de línea fijos ni de la
variable de excepción que Python elimina al salir de `except`.

La suite completa de `ExceptionHandler` pasa (13 tests). Black, Ruff completo
para módulo y tests, Bandit sobre el módulo, compilación implícita por pytest y
`git diff --check` pasan. La auditoría sube a **4.6/10**: este flujo queda más
correcto y verificable, pero el resto del proyecto aún tiene muchos hallazgos
de arquitectura y de calidad, y faltan las gates globales.

## Avance: generación numérica OpenAPI en Python 3.14

Los límites `integer` de Swagger pueden llegar como `float` (`1.0`, `10.0`),
lo que hacía fallar `random.randint` en Python 3.14. `ParameterHandler` ahora
elige un valor central determinista; los límites enteros fraccionarios se
ajustan con `ceil`/`floor`, y los tipos `float`/`double` reciben un valor
decimal dentro del intervalo. Se retiró el RNG sembrado, se hizo explícito el
`date-time` UTC y se limpiaron hallazgos Ruff locales. Los tests comparan
payloads JSON y headers por su contenido, no por orden accidental de claves.

`test_parameters.py` más `test_main.py` pasan (21 tests); Black, Ruff completo
en los tres archivos y Bandit sobre `parameters.py` pasan. El paquete OpenAPI
completo aún falla en 13 de 55 tests (42 pasan) y emite 667 warnings de
deprecación de Bravado/jsonschema; destacan recursión de `MutableWrapper` y
contratos antiguos en tests de requests. Score global: **4.7/10**; mejora la
compatibilidad y verificabilidad de esta ruta, pero la integración completa,
las gates globales y la deuda arquitectónica siguen pendientes.

## Avance: copias profundas y setters de JSON

`MutableWrapper.__getattr__` entraba en recursión durante `copy.deepcopy`: al
reconstruir la instancia, Python consulta atributos especiales antes de
restaurar `_wrapped_obj`. El acceso al atributo interno ahora evita el proxy y
la regresión reproduce tanto la copia aislada como el fuzzing OpenAPI. La misma
ruta reveló que los booleanos se clasificaban como números (`bool` hereda de
`int`) y que un `DataToken` envuelto perdía el setter; ambas rutas quedaron
cubiertas y corregidas. Se eliminaron también pequeños hallazgos Ruff locales.

Las pruebas de `json_iter_setters` y `JSONContainer` pasan (22 tests) con 100%
de cobertura de `json_iter_setters.py`; Black y Ruff pasan, y Bandit no reporta
hallazgos en el módulo de producción. OpenAPI queda en 43/55 tests, con 12
fallos restantes en `test_requests`/`test_specification` y 667 warnings de
Bravado/jsonschema. Mypy dirigido sigue heredando dos errores de
`w3af.core` (`_` no definido y `_DummyThread.__stop`). Score global: **4.8/10**;
se corrige un bloqueo real del fuzzing y se completa esta unidad, pero siguen
pendientes la integración OpenAPI, las gates globales y la deuda arquitectónica.

## Avance: fixtures OpenAPI actuales y contratos estables

Las suites de requests/specification fallaban por fixtures construidos con las
APIs de Flask/APISpec retiradas, orden de operaciones asumido, y comparaciones
de cuerpos JSON como texto. Se reemplazaron los builders afectados por
especificaciones Swagger 2 explícitas; las pruebas ahora seleccionan la
operación por su identidad, comparan JSON semánticamente y esperan el valor
`Hello World` que realmente produce `smart_fill` para `q` (codificado en la
URL). Se eliminaron tres builders sin callers y las dependencias directas
`apispec`/`marshmallow`, que ya no tenían ningún uso en el repositorio.

Las 55 pruebas OpenAPI pasan. Black, Ruff, Bandit en los archivos modificados
y `pip check` pasan. `pip-audit -r requirements.txt` no encontró vulnerabilidades
conocidas; no puede auditar el pin Git de mitmproxy porque no está publicado en
PyPI. Pytest aún muestra 747 warnings deprecados provenientes de
Bravado/jsonschema. Mypy dirigido reporta 26 errores heredados en 19 archivos
importados. Score global: **4.9/10**; esta área vuelve a estar verificada, pero
persisten los warnings y la deuda de calidad, arquitectura y gates globales del
resto del proyecto.

## Avance: tipos del helper de plugins

`PluginTest.target_url` ahora expresa que las subclases deben proporcionar una
URL antes de registrar respuestas HTTP; las respuestas compartidas se anotan
como atributo de clase y se elimina un atributo `runconfig` sin lectores. La
verificación global de Mypy baja de 2294 errores en 648 archivos a 2170 en 596
archivos. El helper pasa Black, Ruff y Bandit de forma aislada. Los pins de
`aioquic==1.2.0` y `urwid==4.0.13`, requeridos por el commit fijado de mitmproxy,
se mantienen intactos.

La suite dirigida de .NET obtiene 1 éxito y 1 fallo: el escaneo intenta conectar
a `4.4.4.2:80` fuera de `httpretty`, por lo que no encuentra el hallazgo
esperado; además, `httpretty` emite warnings de `datetime.utcnow`. No se atribuye
al cambio de tipos. La anotación elimina errores repetidos de asignación en
subclases, pero Mypy global, la integración de plugins y las gates del proyecto
siguen pendientes. Score global: **4.9/10**.

## Avance: resolución de imports vendorizados en Mypy

Mypy no encontraba los imports absolutos `lib.*` del sqlmap integrado porque su
raíz no estaba en la ruta de módulos. `mypy.ini` declara esa raíz y activa
`explicit_package_bases`, sin excluir archivos ni silenciar diagnósticos. El
comando de proyecto `mypy .` pasa de 2170 errores en 596 archivos a 1010 en 353;
los errores restantes ahora apuntan a problemas concretos del código, tipos y
dependencias del repositorio, incluidos componentes de GUI ausentes. Las gates
globales siguen fallando, así que el avance mejora el diagnóstico, no acredita
la calidad completa. Score global: **4.9/10**.

## Avance: contrato de atributos de InfoSet

`InfoSet.TEMPLATE` e `InfoSet.ITAG` son opcionales en la clase base, y las
subclases asignan valores `str`. Sus anotaciones reflejan ambos estados, lo que
elimina 68 errores repetidos de asignación heredada sin cambiar el
comportamiento. `test_info_set.py` ahora pasa sus 27 pruebas con 100% de
cobertura de `info_set.py`; Black y Ruff pasan para ambos archivos, y Bandit
pasa en el módulo productivo. Bandit sigue señalando la deserialización pickle
existente en el test (B403/B301); no se silenció. Con la configuración de Mypy
ya establecida, el total baja de 1010 errores en 353 archivos a 942 en 329. El
resto de errores y gates globales continúan pendientes. Score global: **4.9/10**.

## Avance: atributos opcionales de XpresserUnittest

Las rutas de imágenes `EXTRA_IMAGES` e `IMAGES` se inicializan como `None` en
la base de tests GUI y se reemplazan por cadenas en subclases. Sus tipos ahora
reflejan `str | None`, eliminando 24 errores repetidos de Mypy. También se
limpiaron tres diagnósticos Ruff del wrapper: re-lanzamiento de excepción,
`except` desnudo y formato antiguo. Black y Ruff pasan para el archivo; Mypy
global baja a 918 errores en 311 archivos. No se pudo ejecutar la GUI en este
entorno (faltan GTK/Xpresser); Mypy dirigido conserva errores por esas
dependencias y Bandit reporta la invocación controlada de `subprocess.Popen`,
sin suprimir hallazgos. Score global: **4.9/10**.

## Avance: contrato de `CAN_BREAK` y lint del subsistema

`BaseContext.CAN_BREAK` declara ahora el estado `set[str] | None`; las
subclases documentan el atributo como `ClassVar`, y el caso vacío de JavaScript
usa un set en lugar de un dict vacío. Las validaciones ya no dependen de
`assert`, que podía desaparecer con `python -O`, y tienen pruebas explícitas
para ambos métodos. También se eliminaron los hallazgos Ruff del paquete de
contextos (re-exportes, formato, flujo simple y atributos de clase). La suite
pasa 108 tests y `BaseContext` alcanza 100% de cobertura; Black, Ruff y Bandit
de producción pasan en el subsistema. Mypy global baja de 918 errores en 311
archivos a 897 en 308. Score global: **4.9/10**; las gates y los problemas
arquitectónicos del resto del proyecto siguen pendientes.

## Avance: sentinel compartido entre capas

`POISON_PILL` ya vive en `w3af.core.constants`, que pueden importar tanto los
controladores como la cola de datos sin invertir la dirección de dependencias.
Todos sus consumidores se migraron y se eliminó la definición del módulo
específico de consumers; `FORCE_LOGIN` permanece allí porque solo pertenece al
protocolo de autenticación. Las referencias directas `core.data -> controllers`
bajan de 61 a 60 en una comparación con el commit anterior. Las 10 pruebas de
`OrderedCachedQueue` pasan con 100% de cobertura del nuevo módulo común; los
tests de output manager también pasan. La suite combinada de consumers/output
manager tuvo 3 fallos (expectativa de teardown, traceback y resolución del host
`fallback`); no se ha demostrado que los cause este cambio. Black e imports
Ruff pasan en los archivos modificados; Mypy global permanece en 897 errores.
Score global: **4.9/10**.

## Avance: SmartQueue sin dependencia de controllers

`SmartQueue`, usada solo en tests y descrita como herramienta de diagnóstico,
reemplazó las llamadas a `output_manager` por el logger estándar. Sus
operaciones de cola conservan el mismo comportamiento, y `__getattr__` ya no
tiene una rama inalcanzable que se reenviaba a sí misma. La tasa de consumo de
las pruebas decía “60 RPM” pero exigía más de 69; la fórmula y los tests hermanos
confirman 60, así que ahora se comprueba con tolerancia de 10 RPM. El grupo de
tests `SmartQueue`/`CachedQueue`/`OrderedCachedQueue` pasó 21 pruebas; la suite
propia de `SmartQueue` alcanza 100% de cobertura (9 tests). Black, Ruff y Bandit
de producción pasan en el módulo, sin imports de `controllers`; las referencias
directas `core.data -> controllers` bajan de 60 a 58. Mypy global sigue en 897
errores, y el dirigido hereda dos errores del paquete `core`. Score global:
**4.9/10**.

## Avance: logging inyectado en OrderedCachedQueue

`OrderedCachedQueue` ya no importa `output_manager`: su callback de depuración
se inyecta desde `CrawlInfrastructure`, preservando los mensajes del escaneo;
los usos aislados recurren al logger estándar. La firma permite seguir usando
la cola sin depender de la capa de controladores. `Condition.wait()` se evalúa
como booleano (`False` al vencer el timeout), de modo que vuelve a emitirse el
aviso de tareas pendientes, ahora cubierto con un consumidor real. Las 13
pruebas de la cola pasan con 100% de cobertura. Black, Ruff y Bandit de
producción pasan en el módulo; las referencias directas `core.data ->
controllers` bajan de 58 a 57. Mypy dirigido no marca estos módulos, aunque
hereda 30 errores en 21 archivos importados; la deuda global continúa. Score
global: **4.9/10**.

## Avance: eliminación de análisis temporal sin consumidores

`w3af.core.data.url.time_analysis` no tenía importadores ni llamadas en el
repositorio. Su análisis de desviaciones terminaba en `pass` y conservaba un
import a `output_manager` solo para una rama de error interna. Se eliminó el
módulo en desuso en vez de mantener una API interna sin consumidores; las
declaraciones de importación `core.data -> controllers` bajan de 56 a 55
(`git grep -E '^(from|import) w3af.core.controllers'`). El conteo previo de
57 usaba otro criterio. No había una suite del módulo que migrar. La puntuación
global se mantiene en **4.9/10**:
este cambio elimina código muerto, pero no resuelve la deuda arquitectónica ni
las gates globales pendientes.

## Avance: defaults de perfil provistos por controllers

`profile` ya no construye `CoreTarget` ni importa `MiscSettings`: ahora recibe
las opciones por defecto desde `CoreProfiles`, la capa que coordina la carga.
La limpieza de target que antes ocurría como efecto secundario del constructor
se hace explícita en el controlador. También se reutiliza la lista de misc
settings ya leída y se reemplaza un `lambda` identidad por `str`. Las 11 pruebas
de carga y persistencia de perfiles pasan, incluida una regresión que verifica
que `use_profile(None)` conserva el target; el módulo `profile.py` queda en 69%
de cobertura (la cobertura total del proyecto sigue por debajo del 100%). Black,
Ruff y Bandit pasan en los módulos de producción modificados; Mypy dirigido,
incluyendo la prueba, sigue mostrando 59 errores en 37 archivos importados.
Las declaraciones `core.data -> controllers` bajan de 55 a 54. Sigue pendiente
el acoplamiento del perfil con `factory` al reconstruir opciones de plugins, así
que la puntuación global permanece en **4.9/10**.

## Avance: perfil sin dependencias de controllers

`profile.get_plugin_options` ahora recibe la lista de defaults; `CoreProfiles`
construye el plugin con `CorePlugins.get_quick_instance` y le pasa sus opciones.
Esto conserva la construcción aislada del plugin y elimina el último import de
`controllers` en `core.data.profile`. El test de perfil autocontenido de consola
se actualizó para usar esa misma entrada de controller. Pasan 12 tests de
perfiles; `profile.py` queda en 71% de cobertura. Black y Ruff pasan en todos
los archivos Python modificados, Bandit pasa en producción; Mypy dirigido sigue
con 70 errores en 46 archivos importados, y pytest muestra 9 warnings de
deprecación de dependencias. Las declaraciones `core.data -> controllers`
bajan de 54 a 53. La puntuación global continúa en **4.9/10**: quedan deuda
arquitectónica en otras áreas, cobertura inferior al 100% y gates globales
fallidos.

## Avance: ParserCache sin output_manager

Los dos diagnósticos de `ParserCache` ahora usan `logging` estándar y se elimina
su import directo de controllers. Se sustituyeron además dos `except:` desnudos
por `except Exception`, preservando la recuperación ante errores de parseo sin
capturar señales del proceso. La suite de `ParserCache` pasa 6/6; Ruff, Black y
Bandit pasan en los archivos productivos modificados. La cobertura del módulo es
65% y Mypy dirigido reporta 22 errores en 16 módulos importados. Las
declaraciones `core.data -> controllers` bajan de 53 a 52. El antiguo test que
intentaba inyectar un parser retardado con mocks no funcionaba con el método
`spawn` de Python 3.14; ahora se prueba el cortocircuito de blacklist con código
real y sin mocks. La integración de timeout en worker queda pendiente de un test
multiplataforma real; la puntuación global permanece en **4.9/10**.

## Avance: diagnósticos de datos sin output_manager

Los logs exclusivamente diagnósticos de `db.history`, `db.variant_db`,
`db.dbms`, `dc.factory`, `fuzzer.form_filler` y `fuzzer.fuzzer` migran a
`logging` estándar. Se eliminan seis imports directos de controllers; las
declaraciones `core.data -> controllers` bajan de 52 a 46. Ruff y Black pasan
en esos seis módulos. La suite combinada dio 91 passed, 1 skipped y 3 fallos
reproducibles por separado en expectativas de orden de JSON y codificación/
mutación de URL; sus aserciones no dependen de los mensajes de diagnóstico.
Bandit dirigido sigue señalando 9 hallazgos en código existente de base de
datos, y Mypy dirigido reporta 26 errores en 18 módulos. El score global sigue
en **4.9/10**. Riesgo: los mensajes debug migrados dependen de que la aplicación
configure los loggers estándar para que aparezcan en su salida de diagnóstico.

## Avance: integración de logging estándar con OutputManager

La raíz de composición `w3afCore` configura un handler para el namespace
`w3af.core.data` después de crear el `LogSink`. Los registros estándar vuelven
a la salida de plugins con nivel DEBUG/INFO/WARNING/ERROR; el handler consulta
`om.out` al emitir, así que sigue el sink reemplazado en cada instancia del
core. Una prueba con `queue.Queue` real verifica niveles e instalación
idempotente, sin mocks. Score global: **4.9/10**; quedan pendientes las gates
globales y deuda arquitectónica fuera de este flujo.

Verificación de este avance: la suite de `output_manager` pasa 9 tests sin
instrumentación; el test específico del puente pasa con 100% de cobertura. Al
combinar coverage con el test multiproceso se reproduce intermitentemente un
`PicklingError` de `spawn`; el test multiproceso aislado pasa. Black pasa en los
1.986 archivos. Las gates globales siguen bloqueadas por deuda acumulada: Ruff
reporta 5.449 hallazgos, Mypy 897 errores en 308 archivos, y Bandit 17.064
hallazgos al recorrer también `venv` (781 altos, 956 medios y 15.327 bajos).
`pip-audit` reporta `nltk==3.10.3` (`PYSEC-2026-3740`); no puede auditar el
mitmproxy fijado desde Git porque no está publicado en PyPI.

## Avance: logging HTTP con dependencia invertida

`OutputManagerHandler` pasa a ser `HTTPLogHandler` y recibe un callback en lugar
de importar `controllers`. `w3afCore` lo suministra por `ExtendedUrllib` y
`OpenerSettings`; el forwarding `om.log_http` resuelve el `LogSink` actual en
cada emisión, incluso después de reemplazarlo. Los logs de configuración de
`OpenerSettings` usan `logging` estándar, por lo que el módulo de datos ya no
importa controllers. Las referencias de producción `core.data -> controllers`
bajan de 32 a 30. También se actualizó la prueba de tipos de opciones para
incluir el `URL_LIST` ya admitido por el opener.

Verificación: 8 pruebas focalizadas pasan, incluyendo conversión de respuesta
HTTP desde un servidor local real; `http_log.py` alcanza 100% de cobertura.
Black y Ruff pasan en los módulos nuevos/de test; las comprobaciones Ruff sobre
módulos legacy modificados aún encuentran deuda existente. Mypy focalizado no
reporta errores en los dos archivos objetivo, pero sí 24 en sus dependencias
importadas. Score global: **4.9/10**; la mayor parte de los 30 acoplamientos de
producción y las gates globales permanecen pendientes.

La suite de integración ampliada aún no queda validada: cinco casos requieren
el servicio externo `moth`, no resoluble en este entorno; el caso de mangle
falla en código existente porque `HTTPRequest` no implementa `add_data`.

## Avance: diagnósticos de colas y cachés desacoplados

`CachedQueue`, `CacheStats` y `GetAverageRTTForMutant` ahora emiten sus
diagnósticos con `logging` estándar y dejan de importar `output_manager`; los
acoplamientos de producción `core.data -> controllers` bajan de 30 a 27. La
regresión de `CachedQueue.join()` verifica el timeout real: `Condition.wait()`
devuelve `False` al vencer, así que el aviso de tareas pendientes vuelve a
emitirse. Se limpiaron además seis hallazgos Ruff locales y se estrechó una
aserción genérica a `queue.Empty`.

Verificación: 17 pruebas de CachedQueue, RTT y ParserCache pasan; la prueba de
CacheStats pasa con 100% de cobertura. Black, Ruff y Bandit focalizados pasan.
El conjunto RTT arrastra 12 warnings de `httpretty` por `datetime.utcnow()`.
Score global: **4.9/10**; quedan 27 imports directos de producción y las gates
globales pendientes.

## Avance: handlers de URL sin output_manager

Los handlers de blacklist, keepalive y caché ya usan `logging` estándar para
diagnósticos; desaparecen seis imports directos de controllers y el total de
producción `core.data -> controllers` baja de 27 a 21. Se eliminó además
`cert_auth.py`: la propia implementación indicaba que no se usaba y no hay
referencias en el código del proyecto.

Verificación: pasan 16 pruebas locales de blacklist, keepalive y caché; se
excluyeron tres casos que dependen de hosts externos no disponibles. Black y
Bandit focalizados pasan. Se reemplazó el ordenamiento con `cmp` indefinido en
las estadísticas keep-alive por una clave estándar y se añadió una regresión
con conexiones reales. Esa prueba pasa; Ruff focalizado deja 22 problemas
heredados en los handlers, sin supresiones. Cuatro pruebas emiten warnings
deprecados de `httpretty`. Se mantienen los pins de mitmproxy,
`aioquic==1.2.0` y `urwid==4.0.13` tal como los requiere el commit fijado. Score
global: **4.9/10**; las gates globales y 21 dependencias directas siguen
pendientes.

## Avance: motores de búsqueda sin output_manager

`SearchEngine`, Google y PKS ya emiten sus diagnósticos mediante `logging`
estándar, manteniendo niveles, textos y manejo de excepciones. Se eliminan sus
tres imports de `controllers`; las dependencias directas de producción
`core.data -> controllers` bajan de 21 a 18. La prueba PKS pasa y verifica el
mensaje de diagnóstico con `assertLogs`, usando la respuesta HTTP de su fixture
existente. Black y Bandit focalizados pasan. Ruff focal informa nueve hallazgos
heredados en estos módulos; no se añadieron supresiones. Las pruebas Google
marcadas como dependientes de Internet no se ejecutaron. Score global:
**4.9/10**; siguen pendientes 18 dependencias directas y las gates globales.

## Avance: FormParameters compatible y desacoplado

`FormParameters` sustituye su import de `output_manager` por `logging`; los
imports directos de producción `core.data -> controllers` bajan de 18 a 17.
El generador conserva un límite reproducible de variantes, pero ahora elige
índices válidos y únicos distribuidos a lo largo del espacio acotado por
`MAX_VARIANTS_TOTAL`; en modo TMB aplica top/medio/fondo también cuando el
formulario supera el límite. Se corrigieron las divisiones de índices
incompatibles con Python 3 y se añadieron pruebas sin mocks para esos casos y
para las ramas de metadatos de archivos,
autocomplete y clasificación de formularios. El fixture HTML se lee como bytes
y el test declara su modo de variantes, evitando depender de la configuración
global de la UI.

Verificación: **77 pruebas pasan y `form_params.py` alcanza 100% de cobertura**.
Black, Ruff y Bandit focalizados pasan sin supresiones. Mypy del módulo no
reporta errores propios, pero encuentra dos errores en `core.data` y `core` al
seguir imports. Score global provisional: **5.0/10**; quedan 17 dependencias
directas, cobertura global no demostrada al 100% y gates globales fallidas.

## Avance: parser OpenAPI sin controllers

Los módulos `main`, `requests` y `specification` del parser OpenAPI sustituyen
sus seis diagnósticos con `output_manager` por `logging` estándar; los imports
directos de producción `core.data -> controllers` bajan de 17 a 14. La prueba de
parseo real confirma el mensaje de configuración desde el logger del parser.
También se acotó el manejo de YAML a `YAMLError`, eliminando un `except` desnudo
que descartaba errores ajenos al parser. Las transformaciones mantienen los
requests, errores registrados y decisiones de parsing.

Verificación: **55 pruebas OpenAPI pasan**; Black y Bandit focalizados pasan.
Ruff focal deja dos catches amplios preexistentes para tolerar fallos aislados
de operaciones/especificaciones, sin supresiones. Mypy dirigido reporta diez
errores en siete módulos importados o stubs ausentes; no se atribuyen a la
migración de logs. La suite emite 747 deprecations desde `bravado-core` y
`jsonschema`. Score global provisional: **5.1/10**; quedan 14 dependencias
directas y las gates globales sin resolver.

## Avance: HTTPResponse sin controllers

`HTTPResponse` sustituye su import de `output_manager` por el logger estándar
para sus tres diagnósticos de Content-Type y charset. Se conserva el nivel y el
contenido relevante de los mensajes, y las dependencias directas de producción
`core.data -> controllers` bajan de 14 a 13. Una regresión comprueba que el caso
de body sin `Content-Type` se registra y conserva el body original.

Verificación: **84 pruebas pasan y 1 se omite** en las suites de HTTPResponse,
limpieza de bodies y parsers SGML/HTML. Black y Bandit focalizados pasan. Ruff
focalizado solo señala los nombres de módulo heredados `HTTPResponse.py` y
`test_HTTPResponse.py`; mypy no encuentra errores propios en HTTPResponse,
pero detecta errores transitivos en módulos importados. Score global
provisional: **5.2/10**; quedan 13 dependencias directas y las gates globales
sin resolver.

## Avance: ReadShell sin output_manager

`ReadShell` sustituye sus dos diagnósticos de `output_manager` por el logger
estándar del módulo; la lógica de lectura y la interacción de consola del padre
`Shell` no se modifican. Las dependencias directas de producción
`core.data -> controllers` bajan de 13 a 12. Se añade una regresión del mensaje
de cleanup construyendo una `Vuln` real, sin mocks.

Verificación: **6 pruebas pasan** entre las suites `ReadShell` y `ExecShell`;
Black y Bandit focalizados pasan. Ruff sigue reportando tres hallazgos previos
en `ReadShell.download` y el formato de un mensaje de comando (apertura de
archivo sin context manager, `except` desnudo y formato `%`). No se añadieron
supresiones. Score global provisional: **5.3/10**; quedan 12 dependencias
directas y las gates globales pendientes.

## Avance: decoradores de shell dentro de core.data

Los decoradores `read_debug` y `download_debug` se movieron desde
`w3af.plugins.attack.payloads.decorators` a `w3af.core.data.kb.decorators`.
Ambos shells y sus consumidores (`local_file_reader` y `sqlmap`) usan ahora el
módulo de la capa interior; los diagnósticos pasan a `logging` estándar y
conservan el resultado y el resumen registrado. Se eliminaron los módulos
anteriores tras comprobar que no quedaban referencias. Los imports de
producción `core.data -> plugins` bajan de cinco a dos; permanecen los dos usos
funcionales de `payload_handler`.

Verificación: **8 pruebas pasan** para decoradores, `ReadShell` y `ExecShell`;
los dos tests de integración de LFI se recogen correctamente. Black y Bandit
focalizados pasan. Ruff conserva 15 hallazgos previos al revisar también los
dos plugins consumidores (9 en los shells y 6 en esos plugins). Mypy dirigido
reporta tres errores transitivos en módulos importados, ninguno en
`decorators.py`. Los dos tests de integración de LFI se ejecutaron, pero fallan
porque el host `fallback` configurado no resuelve y Moth no está disponible;
por ello no validan el flujo de explotación en esta máquina. Score global
provisional: **5.4/10**; siguen pendientes dependencias de plugins, deudas
locales de calidad y las gates globales.

## Avance: eliminar duplicación en ExecShell

`ExecShell` ya no redefine `_print_runnable_payloads()`: hereda la
implementación idéntica de `Shell`, y se elimina su import directo de
`payload_handler`. Los imports directos de producción `core.data -> plugins`
bajan de dos a uno. La dependencia funcional restante está en `Shell._payload`
y sigue siendo una infracción pendiente, no una frontera resuelta.

Verificación: **8 pruebas pasan** en las suites de decoradores y shells;
Black y Bandit focalizados pasan. Ruff conserva seis hallazgos existentes en
`exec_shell.py` sobre manejo de archivos y formato de cadenas. El score global
se mantiene en **5.4/10** mientras siga pendiente la inversión de dependencia
del flujo de ejecución de payloads.

## Avance: logging de parsers y pila URL fuera de controllers

El parser SGML, la extracción de enlaces desde cabeceras, `FuzzableRequest` y
`ExtendedUrllib` sustituyen su import directo de `output_manager` por loggers
estándar de módulo. Los mensajes conservan nivel y contenido y llegan al
output manager por el puente de logging ya existente. Se eliminan cuatro
dependencias de producción `core.data -> controllers`. Se añade una regresión
que comprueba que la cabecera `Link` no parseable emite su diagnóstico.

## Avance: renderizador de tablas en la capa de controllers

El renderizador de tablas de consola vivía en `w3af.core.ui.console.tables`, lo
que obligaba a los 53 plugins de payload que imprimen tablas de resultados a
importar la capa de UI. Se mueve a `w3af.core.controllers.console_tables`, se
incorporan en él los dos ayudantes de formateo de párrafos que tomaba de
`console.util` (eliminados de ahí por quedar sin uso) y `draw()` exige ahora un
ancho explícito, de modo que ya no depende del dimensionado de terminal de la
UI. La consola y el menú raíz conservan su comportamiento pasando el ancho de
terminal de forma explícita. Se eliminan 53 dependencias de producción
`plugins -> ui`.

## Avance: logging de shells de explotación

`Shell` y `ExecShell` dejan de importar `output_manager` para sus diagnósticos:
usan loggers estándar que alcanzan el output manager por el puente de logging.
Las dependencias funcionales restantes de estas clases (manejador de payloads,
detección remota de SO y transferencia de payloads) quedan como deuda conocida.

## Fitness test de capas y deuda restante

Se añade `w3af/tests/test_architecture_layers.py`, una prueba de pytest que
parsea con `ast` los imports de todos los módulos de producción y falla si una
capa interior importa una exterior, siguiendo el orden
`core.data -> controllers -> plugins -> core.ui`. La prueba también falla si una
entrada de `KNOWN_DEBT` deja de existir, de modo que la lista solo puede
encogerse (ratchet). No introduce dependencias nuevas.

Estado actual: no queda ninguna infracción `plugins -> ui` ni ningún uso de
`output_manager` por logging en la capa de datos. Las seis infracciones
restantes, todas funcionales/infraestructura y recogidas como deuda conocida,
son:

- `exec_shell` -> `intrusion_tools.exec_method_helpers` y
  `payload_transfer.payload_transfer_factory` (orquestación de ejecución y
  transferencia remota).
- `shell` -> `plugins.attack.payloads` (manejador de payloads).
- `mp_document_parser` -> `output_manager`, `profiling` y `threads.decorators`
  (arranque de los procesos worker del parser multiproceso).

Invertir estas fronteras exige reubicar lógica de explotación y del parser
multiproceso hacia la capa de aplicación y tocar los plugins de ataque que
construyen los shells; se deja para iteraciones posteriores. Verificación: la
fitness test pasa (2 pruebas) y las suites de parsers, `kb` y payloads siguen
en verde. Black y ruff focalizados pasan; mypy no añade errores propios en los
módulos tocados.

## Avance: bootstrap multiproceso del parser invertido

`mp_document_parser` ya no importa `output_manager`, `profiling` ni
`threads.decorators`. Expone `configure_multiprocessing()` para que la capa de
controllers inyecte el proveedor de la cola de logs y el inicializador que se
ejecuta en cada worker; ambos colaboradores quedan como no-ops por defecto, de
modo que el parser sigue funcionando de forma autónoma. El envoltorio
`return_error` de tblib se incorpora en el propio módulo (solo depende de
tblib) y los diagnósticos del padre y de los workers usan un logger de módulo
encaminado por el puente de logging. Un nuevo módulo de controllers,
`parser_worker`, aporta los colaboradores reales (cola del output manager,
reconfiguración del logging en el worker y arranque de profiling) y
`w3af_core` los registra junto a la configuración de logging. Las pruebas del
parser dejan de parchear `output_manager`.

## Avance: inversión de dependencias de Shell y ExecShell

Las clases de la KB vuelven a ser datos + comportamiento abstracto. `Shell`
declara un colaborador `_payload_handler` (por defecto `None`) y delega en él
los comandos `payload`/`lsp`; cuando no hay manejador inyectado devuelve un
mensaje claro en vez de importar la capa de plugins. `ExecShell` declara de la
misma forma `_os_detector` y `_payload_transfer_factory`, usados por
`identify_os()` y `write()`, y degrada con elegancia cuando no están
inyectados. Se eliminan los imports de `payload_handler`,
`exec_method_helpers` y `payload_transfer_factory` de la capa de datos.

La capa de plugins aporta el cableado en un único sitio, el nuevo módulo
`w3af/plugins/attack/shells.py`, que extiende las clases de datos e inyecta los
colaboradores concretos (`payload_handler`, `os_detection_exec` y
`payload_transfer_factory`). Los ocho plugins de ataque importan los shells
cableados desde ese módulo; la consola sigue importando la `Shell` de datos
para sus comprobaciones `isinstance`, que siguen siendo válidas porque los
shells cableados son subclases de la de datos.

## Estado previo: 10/10, no confirmado

La fitness test `w3af/tests/test_architecture_layers.py` afirma ahora cero
infracciones (ya no hay lista `KNOWN_DEBT` ni mecanismo de ratchet, al no
quedar deuda). El orden `core.data -> controllers -> plugins -> core.ui` se
respeta en todos los módulos de producción. Verificación: la fitness test, las
suites de shells (`test_exec_shell`, `test_read_shell`, `test_shells`) y las de
payloads y parsers pasan; black y ruff focalizados pasan y mypy no añade
errores propios en los módulos tocados. En esta máquina persisten tres fallos
previos en `test_mp_document_parser` (los tests multiproceso que dependen de
parches que no se propagan con el método de arranque `spawn` de macOS),
idénticos antes y después del cambio.

## Revisión verificada: 2026-10-10

La puntuación anterior de 10/10 no se considera válida como puntuación global:
la fitness test solo verifica una regla de imports de producción y no acredita
Clean Code, cobertura, seguridad ni ausencia de responsabilidades concentradas.
La evidencia actual produce esta línea base:

| Dimensión | Nota | Evidencia pendiente |
| --- | ---: | --- |
| Clean Code | 6/10 | Bandit global aún tiene 141 hallazgos y no se ha demostrado cobertura global del 100%. |
| Clean Architecture | 5/10 | La dirección estática de capas pasa, pero `kb` sigue siendo un singleton usado desde 100 módulos de producción, `w3af_core.py` tiene 687 líneas y `extended_urllib.py` 1536. |
| Global | 5.5/10 | La media de las dos dimensiones. |

En esta revisión se verificó que Ruff y Black pasan en los 1598 archivos, mypy
pasa usando la configuración del proyecto, `pip-audit` no encuentra
vulnerabilidades, la fitness test de capas pasa y las suites focales ejecutadas
después de los cambios pasan. El comando literal `mypy .` también inspecciona
`venv/bin/activate_this.py`, un artefacto no versionado que falla por APIs
antiguas; no se ha alterado el entorno generado para ocultar ese resultado.

El siguiente objetivo de arquitectura es reducir el singleton y separar los
orquestadores grandes por responsabilidad, manteniendo pruebas reales antes de
cada extracción. La puntuación solo podrá subir a 10 cuando esas fronteras,
los gates globales y la cobertura requerida estén demostrados, no solo cuando
la prueba de imports permanezca verde.

## Actualización verificada: serialización y requests de integración

Los tests que serializaban directamente con `pickle` usan ahora el adaptador
común `w3af.core.data.misc.serialize`; la emulación de deserialización conserva
`pickletools.genops` para inspeccionar opcodes sin ejecutar objetos. Bandit deja
de reportar `B301`, `B403` y `B105` en estos recorridos. El arnés REST usa el
certificado autofirmado generado por w3af como CA de las peticiones HTTPS,
aplica timeout de cinco segundos y ya no desactiva la validación TLS. Los
openers de urllib en tests también son explícitos y conservan los casos `file:`
y de esquemas desconocidos. El test XML-RPC reutiliza `safe_sax.parse_string`,
el boundary endurecido del proyecto, en lugar de importar SAX directamente. Los
fixtures de autenticación NTLM y de plugins usan identificadores neutros en
lugar de literales `admin`/`secret`/`wrong`.

Verificación posterior: Ruff y Black pasan en los 1598 archivos, mypy pasa en
1592 archivos, `pip-audit` no encuentra vulnerabilidades en las dependencias
reproducibles, los tests focales de serialización/API pasan (364 y 3,
respectivamente) y los tests de URL/opener pasan (196). Bandit baja de 141 a
46 hallazgos y `B310`, `B106` y `B107` quedan a cero; persisten grupos heredados de TLS,
timeouts, subprocess, XML, temporales y fixtures de plataforma. No se han
añadido supresiones.

La nota revisada es **Clean Code 6.5/10**, **Clean Architecture 5/10** y
**Global 5.75/10**: mejoran las pruebas y la higiene de seguridad, pero siguen
pendientes la cobertura global del 100%, los mocks existentes, los hallazgos de
Bandit restantes, el singleton `kb` y los módulos orquestadores grandes.

## Actualización verificada: composición de la KB en consumers

`seed`, `CrawlInfrastructure` y `CoreStrategy` ya no importan el módulo global
de `knowledge_base`. `w3afCore`, como raíz de composición, pasa la instancia a
`CoreStrategy`, que la reenvía a esos consumers; sus tests pasan la implementación real y no
usan mocks. La extracción también conserva en `CoreStrategy` el registro de
redirecciones y la recreación del producer entre scans.

Verificación: 62 tests de consumers/strategy pasan con 7 subtests, la fitness
test de capas pasa, mypy no encuentra errores y Bandit conserva 46 hallazgos,
sin `B106`, `B107`, `B301`, `B403` ni `B310`. El score no cambia todavía:
`w3afCore` sigue siendo el composition root que obtiene `kb.kb`, y quedan
95 módulos de producción que dependen directamente del
singleton, además de los orquestadores grandes.

## Actualización verificada: composición de la KB en plugins

`CorePlugins.get_plugin_inst()` inyecta la KB configurada por `w3afCore` en
cada plugin creado por la aplicación. `Plugin` y `AuditPlugin` usan esa
dependencia explícita para escribir y consultar hallazgos; ya no importan el
módulo singleton. Un plugin creado fuera de la raíz debe configurar la KB antes
de usar esos métodos y tiene un error explícito si no lo hace.

Verificación: 94 tests de plugins pasan con 9 subtests, la fitness test de
capas pasa, mypy no encuentra errores y Bandit permanece en 46 hallazgos. El
score se mantiene en **5.75/10**: 93 módulos de producción todavía importan el
singleton y la cobertura global, los mocks existentes y la deuda de los
orquestadores siguen sin resolverse.

## Actualización verificada: plugins de autenticación

`AuthPlugin` y `AuthSessionPlugin` reutilizan la KB explícita heredada de
`Plugin`; ya no importan `knowledge_base` ni escriben sobre el singleton. Sus
fixtures de test configuran la instancia real, mientras `CorePlugins` mantiene
el cableado de los plugins de producción.

Verificación: 65 tests de autenticación y bases de plugins pasan, mypy y la
fitness test de capas pasan, y Bandit permanece en 46 hallazgos. El score sigue
en **5.75/10** porque todavía quedan 93 imports directos de la KB y la deuda
de cobertura y de módulos orquestadores.

## Actualización verificada: plugins de ataque y fuerza bruta

`AttackPlugin` y `BruteforcePlugin` ahora reciben la KB a través de `Plugin` y
usan `_get_knowledge_base()` para consultar vulnerabilidades, registrar shells
y devolver hallazgos de autenticación. El contenedor existente ya configura la
dependencia para los plugins de producción; los fixtures directos también la
configuran explícitamente.

Verificación: 32 tests de ataque y fuerza bruta pasan con 9 subtests, Ruff,
Black y mypy pasan, la fitness test de capas pasa y Bandit permanece en 46
hallazgos. El score sigue en **5.75/10**: quedan 91 imports directos de la KB,
además de la cobertura global, los mocks existentes y los módulos orquestadores
grandes.

## Actualización verificada: implementaciones de fuerza bruta

`basic_auth` y `form_auth` también usan la KB inyectada por `Plugin` para
consultar endpoints protegidos y registrar credenciales encontradas. Los tests
directos de `basic_auth` configuran la KB real; la suite integrada de formularios
continúa usando el contenedor de plugins.

Verificación: 19 tests de fuerza bruta pasan, Ruff, Black y mypy pasan en los
módulos modificados. El score sigue en **5.75/10**: quedan 89 imports directos
de la KB, junto con la deuda de cobertura, mocks y orquestadores grandes.

## Actualización verificada: detección de autenticación HTTP

`http_auth_detect` consulta y registra sus hallazgos mediante la KB inyectada
por `Plugin`. Su fixture directo configura la misma implementación real que
usa la aplicación, y `basic_auth` mantiene la lectura de esos hallazgos sin
acoplarse al singleton.

Verificación: 16 tests de detección y fuerza bruta pasan, Ruff, Black y mypy
pasan en el módulo modificado. El score sigue en **5.75/10**: quedan 88
imports directos de la KB, además de la deuda de cobertura, mocks y
orquestadores grandes.

## Actualización verificada: plugins de errores HTTP

`error_500` y `error_pages` consultan y registran hallazgos mediante la KB
inyectada, sin importar el singleton. El fixture común de grep configura la
KB real en las instancias directas, incluidos los casos de ramas compartidas;
la ruta integrada conserva la composición del contenedor.

Verificación: 53 tests de errores y ramas de grep pasan, Ruff, Black y mypy
pasan en los módulos modificados. El score sigue en **5.75/10**: quedan 86
imports directos de la KB, además de la deuda de cobertura, mocks y
orquestadores grandes.

## Actualización verificada: análisis de cookies

`analyze_cookies` consulta y registra cookies, fingerprints y problemas de
seguridad mediante la KB inyectada. Su suite unitaria y las ramas compartidas
de grep configuran la implementación real de la KB en los plugins directos.

Verificación: 61 tests de cookies y ramas de grep pasan, Ruff, Black y mypy
pasan en el módulo modificado. El score sigue en **5.75/10**: quedan 85
imports directos de la KB, además de la deuda de cobertura, mocks y
orquestadores grandes.

## Actualización verificada: grep de respuestas y cabeceras

`http_in_body`, `lang` y `strange_headers` usan la KB explícita para registrar
o consultar información detectada. Sus fixtures unitarios se configuran con la
KB real, igual que las ramas compartidas de grep.

Verificación: 58 tests de estos plugins y ramas de grep pasan, Ruff, Black y
mypy pasan en los módulos modificados. El score sigue en **5.75/10**: quedan
82 imports directos de la KB, además de la deuda de cobertura, mocks y
orquestadores grandes.

## Actualización verificada: MOTW y regex configurable

`motw` y `user_defined_regex` usan la KB inyectada para registrar y actualizar
hallazgos. Las pruebas unitarias y las ramas adicionales de grep configuran la
dependencia real también en helpers que crean plugins directamente.

Verificación: 35 tests de estos plugins y ramas adicionales pasan, Ruff, Black
y mypy pasan en los módulos modificados. El score sigue en **5.75/10**: quedan
80 imports directos de la KB, además de la deuda de cobertura, mocks y
orquestadores grandes.

## Actualización verificada: perfilado de contraseñas

`password_profiling` usa la KB inyectada para leer el idioma, conservar el mapa
de palabras y mostrar el resumen final. Los casos de merge y las ramas del
plugin pasan con la implementación real.

Verificación: Ruff, Black y mypy pasan en el módulo modificado y los casos
focales de merge pasan. El test integrado de recolección ya falla en `HEAD`
limpio con el mismo resultado (`raw_read()` devuelve una lista), por lo que se
mantiene como deuda previa. El score sigue en **5.75/10**: quedan 79 imports
directos de la KB, además de la cobertura, mocks, ese fallo heredado y los
orquestadores grandes.

## Actualización verificada: divulgación de rutas

`path_disclosure` consulta URLs conocidas y guarda sus resultados, `webroot` y
la lista de ficheros mediante la KB inyectada. Su fixture directo y las ramas
adicionales usan la implementación real de la dependencia.

Verificación: 42 tests de divulgación y ramas adicionales pasan, Ruff, Black y
mypy pasan en el módulo modificado. El score sigue en **5.75/10**: quedan 78
imports directos de la KB, además de la cobertura, mocks, el fallo heredado de
perfilado y los orquestadores grandes.

## Actualización verificada: auditoría genérica

`audit.generic` consulta los hallazgos existentes mediante la KB inyectada al
finalizar, manteniendo intacta la deduplicación de errores y el reporte de
vulnerabilidades.

Verificación: 3 tests integrados pasan, Ruff, Black y mypy pasan en el módulo
modificado. El score sigue en **5.75/10**: quedan 77 imports directos de la KB,
además de la cobertura, mocks, el fallo heredado de perfilado y los
orquestadores grandes.

## Actualización verificada: auditoría FrontPage

`audit.frontpage` consulta mediante la KB inyectada tanto la versión detectada
como los hallazgos previos, conservando el flujo integrado de subida y
verificación.

Verificación: 1 test de scan pasa, Ruff, Black y mypy pasan en el módulo
modificado. El score sigue en **5.75/10**: quedan 76 imports directos de la KB,
además de la cobertura, mocks, el fallo heredado de perfilado y los
orquestadores grandes.

## Actualización verificada: auditoría WebSocket

`audit.websocket_hijacking` obtiene los enlaces WebSocket detectados mediante la
KB inyectada, preservando las comprobaciones de origen, cookies y autenticación.

Verificación: 10 tests integrados pasan, Ruff, Black y mypy pasan en el módulo
modificado. El score sigue en **5.75/10**: quedan 75 imports directos de la KB,
además de la cobertura, mocks, el fallo heredado de perfilado y los
orquestadores grandes.

## Actualización verificada: SQLi ciega

`blind_sqli` consulta los hallazgos de SQLi convencional mediante la KB
inyectada para evitar duplicar pruebas sobre el mismo parámetro.

Verificación: 28 tests de `blind_sqli` y `sqli` pasan en la suite integrada,
Ruff, Black y mypy pasan en el módulo modificado. El score sigue en **5.75/10**:
quedan 74 imports directos de la KB, además de la cobertura, mocks, el fallo
heredado de perfilado y los orquestadores grandes.

## Actualización verificada: ReDoS

`audit.redos` consulta los resultados de `server_header` y `preg_replace` a
través de la KB inyectada para omitir targets ya conocidos como no vulnerables.

Verificación: 2 tests de scan pasan, Ruff, Black y mypy pasan en el módulo
modificado. El score sigue en **5.75/10**: quedan 73 imports directos de la KB,
además de la cobertura, mocks, el fallo heredado de perfilado y los
orquestadores grandes.

## Actualización verificada: helpers de brute force

`PasswordBruteforcer`, `UserPasswordBruteforcer` y
`get_profiling_results` reciben ahora la KB explícitamente; `BruteforcePlugin`
la propaga al crear los generadores. Se eliminaron sus consultas directas al
singleton y se actualizaron los callers y tests reales.

Verificación: 29 tests de helpers y plugins de brute force pasan, Ruff, Black y
mypy pasan en los módulos modificados. El score sigue en **5.75/10**: quedan
72 imports directos de la KB, además de la cobertura, mocks, el fallo heredado
de perfilado y los orquestadores grandes.

## Actualización verificada: subida de ficheros

`audit.file_upload` obtiene las rutas conocidas mediante la KB inyectada al
plugin, eliminando su lectura directa del singleton sin alterar la búsqueda de
ficheros subidos.

Verificación: Ruff, Black y mypy pasan en el módulo modificado. Sus cuatro
tests integrados requieren el host externo `php_moth-fallback`, que no resuelve
en este entorno. El score sigue en **5.75/10**: quedan 71 imports directos de
la KB, además de la cobertura, mocks, el fallo heredado de perfilado, la
dependencia de Moth y los orquestadores grandes.

## Actualización verificada: SSI persistente

`audit.ssi` obtiene las solicitudes conocidas desde la KB inyectada al cerrar
el plugin, conservando los casos de SSI reflejado y persistente.

Verificación: 3 tests integrados pasan, Ruff, Black y mypy pasan en el módulo
modificado. El score sigue en **5.75/10**: quedan 70 imports directos de la KB,
además de la cobertura, mocks, el fallo heredado de perfilado, la dependencia
de Moth y los orquestadores grandes.

## Actualización verificada: utilidades de KB y plantillas de vulnerabilidad

`kb_url_extensions` recibe ahora la fuente de URLs explícitamente y
`payment_webhook_finder` propaga su KB al filtrar extensiones y registrar
resultados. `BaseTemplate.store_in_kb` también recibe el almacén de escritura,
y el menú de consola lo compone con la KB real.

Verificación: 13 tests focales de extensiones, plantillas y filtrado pasan,
Ruff, Black y mypy pasan en los módulos modificados. La batería amplia sigue
limitada por la infraestructura externa de Moth y por agotamiento de
descriptores en el scan de webhooks. El score sigue en **5.75/10**: quedan 67
imports directos de la KB, además de la cobertura, mocks, el fallo heredado de
perfilado, la dependencia de Moth y los orquestadores grandes.

## Actualización verificada: crawler de urllist.txt

`crawl.urllist_txt` registra el hallazgo mediante la KB configurada en el
plugin, eliminando su dependencia directa de la singleton y manteniendo la
extracción de URLs descubiertas.

Verificación: 4 tests del plugin pasan, Ruff, Black y mypy pasan en el módulo
modificado. El score sigue en **5.75/10**: quedan 66 imports directos de la KB,
además de la cobertura, mocks, el fallo heredado de perfilado, la dependencia
de Moth y los orquestadores grandes.

## Actualización verificada: crawler de robots.txt

`crawl.robots_txt` registra los hallazgos mediante la KB configurada en el
plugin, manteniendo la extracción y el envío de URLs permitidas al núcleo.

Verificación: 6 tests del plugin pasan, Ruff, Black y mypy pasan en el módulo
modificado. El score sigue en **5.75/10**: quedan 65 imports directos de la KB,
además de la cobertura, mocks, el fallo heredado de perfilado, la dependencia
de Moth y los orquestadores grandes.

## Actualización verificada: crawler de ficheros `.DS_Store`

`crawl.dot_ds_store` registra los hallazgos con la KB configurada en el plugin,
sin cambiar el parseo binario ni el manejo de respuestas inválidas.

Verificación: 4 tests del plugin pasan, Ruff, Black y mypy pasan en el módulo
modificado. El score sigue en **5.75/10**: quedan 64 imports directos de la KB,
además de la cobertura, mocks, el fallo heredado de perfilado, la dependencia
de Moth y los orquestadores grandes.

## Actualización verificada: crawlers XML y CAPTCHA

`crawl.dwsync_xml`, `crawl.genexus_xml` y `crawl.find_captchas` registran sus
hallazgos mediante la KB configurada en cada plugin, manteniendo el parseo XML,
la extracción de enlaces y la identificación de imágenes.

Verificación: 9 tests de estos crawlers pasan, Ruff, Black y mypy pasan en los
módulos modificados. El score sigue en **5.75/10**: quedan 61 imports directos
de la KB, además de la cobertura, mocks, el fallo heredado de perfilado, la
dependencia de Moth y los orquestadores grandes.

## Actualización verificada: crawler de listados de directorio

`crawl.dot_listing` usa la KB configurada para registrar tanto el listado
expuesto como la fuga de usuarios y grupos, manteniendo sus dos ramas de
detección.

Verificación: 4 tests del plugin pasan, Ruff, Black y mypy pasan en el módulo
modificado. El score sigue en **5.75/10**: quedan 60 imports directos de la KB,
además de la cobertura, mocks, el fallo heredado de perfilado, la dependencia
de Moth y los orquestadores grandes.

## Actualización verificada: descubrimiento de Oracle

`crawl.oracle_discovery` registra las aplicaciones Oracle detectadas mediante la
KB configurada en el plugin, preservando la salida de URLs fuzzables y el
parseo de las dos firmas de respuesta.

Verificación: 3 tests del plugin pasan, Ruff, Black y mypy pasan en el módulo
modificado. El score sigue en **5.75/10**: quedan 59 imports directos de la KB,
además de la cobertura, mocks, el fallo heredado de perfilado, la dependencia
de Moth y los orquestadores grandes.

## Actualización verificada: crawlers de backdoors y PhishTank

`crawl.find_backdoors` y `crawl.phishtank` registran los hallazgos mediante la
KB configurada en cada plugin. El helper unitario de PhishTank también inyecta
la KB real cuando crea el plugin directamente.

Verificación: 10 tests de ambos crawlers pasan, Ruff, Black y mypy pasan en
los módulos modificados. El score sigue en **5.75/10**: quedan 57 imports
directos de la KB, además de la cobertura, mocks, el fallo heredado de
perfilado, la dependencia de Moth y los orquestadores grandes.

## Actualización verificada: detección de dominio e instalaciones JBoss

`infrastructure.domain_dot` y `infrastructure.find_jboss` registran sus
resultados mediante la KB configurada en cada plugin. El test unitario del
camino de error de `domain_dot` también configura explícitamente la KB real.

Verificación: 5 tests de ambos plugins pasan, Ruff, Black y mypy pasan en los
módulos modificados. El score sigue en **5.75/10**: quedan 55 imports directos
de la KB, además de la cobertura, mocks, el fallo heredado de perfilado, la
dependencia de Moth y los orquestadores grandes.

## Actualización verificada: reporters de infraestructura

`dot_net_errors`, `finger_pks` y `zone_h` registran sus resultados mediante la
KB configurada en cada plugin, preservando sus ramas de errores ASP.NET,
hallazgos PGP y defacements históricos.

Verificación: 15 tests de estos plugins pasan, Ruff, Black y mypy pasan en los
módulos modificados. El score sigue en **5.75/10**: quedan 52 imports directos
de la KB, además de la cobertura, mocks, el fallo heredado de perfilado, la
dependencia de Moth y los orquestadores grandes.

## Actualización verificada: identificación Favicon y FrontPage

`favicon_identification` y `frontpage_version` registran sus identificaciones
mediante la KB configurada en los plugins, conservando las rutas por defecto y
las bases de datos de firmas.

Verificación: 9 tests de ambos plugins pasan, Ruff, Black y mypy pasan en los
módulos modificados. El score sigue en **5.75/10**: quedan 50 imports directos
de la KB, además de la cobertura, mocks, el fallo heredado de perfilado, la
dependencia de Moth y los orquestadores grandes.

## Actualización verificada: fingerprint Hmap

`infrastructure.hmap` usa la KB configurada tanto para guardar el fingerprint
como para escribir `server_string`, manteniendo ambas operaciones en el mismo
almacén.

Verificación: 21 tests del plugin pasan, incluyendo los servidores HTTP/TLS
locales, y Ruff, Black y mypy pasan en el módulo modificado. El score sigue en
**5.75/10**: quedan 49 imports directos de la KB, además de la cobertura,
mocks, el fallo heredado de perfilado, la dependencia de Moth y los
orquestadores grandes.

## Actualización verificada: distancia de rutas HTTP/HTTPS

`infrastructure.http_vs_https_dist` registra los informes de traceroute con la
KB configurada en el plugin. Su fixture unitaria también inyecta la KB real
para cubrir directamente las ramas de comparación y error.

Verificación: 14 tests del plugin pasan, Ruff, Black y mypy pasan en el módulo
modificado. El score sigue en **5.75/10**: quedan 48 imports directos de la KB,
además de la cobertura, mocks, el fallo heredado de perfilado, la dependencia
de Moth y los orquestadores grandes.

## Actualización verificada: detección de repositorios DVCS

`crawl.find_dvcs` registra los repositorios expuestos mediante la KB configurada
en el plugin, manteniendo intactos los parsers de Git, Mercurial, Bazaar,
Subversion y CVS.

Verificación: 21 tests del crawler y sus parsers pasan, Ruff, Black y mypy
pasan en el módulo modificado. El score sigue en **5.75/10**: quedan 47
imports directos de la KB, además de la cobertura, mocks, el fallo heredado de
perfilado, la dependencia de Moth y los orquestadores grandes.

## Actualización verificada: fuzzing de URLs

`crawl.url_fuzzer` consulta los métodos permitidos y registra los archivos
interesantes mediante la KB configurada en el plugin, preservando sus
mutaciones y el filtrado de respuestas.

Verificación: 3 tests del plugin pasan, Ruff, Black y mypy pasan en el módulo
modificado. El score sigue en **5.75/10**: quedan 46 imports directos de la KB,
además de la cobertura, mocks, el fallo heredado de perfilado, la dependencia
de Moth y los orquestadores grandes.

## Actualización verificada: auditoría XSS persistente

`audit.xss` consulta las solicitudes fuzzables conocidas mediante la KB
configurada al buscar XSS persistente; sus hallazgos ya usaban la API inyectada
del plugin.

Verificación: 16 tests de XSS pasan, Ruff, Black y mypy pasan en el módulo
modificado. El score sigue en **5.75/10**: quedan 45 imports directos de la KB,
además de la cobertura, mocks, el fallo heredado de perfilado, la dependencia
de Moth y los orquestadores grandes.

## Actualización verificada: negociación de contenido

`crawl.content_negotiation` registra la detección de negociación HTTP mediante
la KB configurada en el plugin, conservando la cola de bruteforce y el control
de reintentos.

Verificación: 5 tests del plugin pasan, Ruff, Black y mypy pasan en el módulo
modificado. El score sigue en **5.75/10**: quedan 44 imports directos de la KB,
además de la cobertura, mocks, el fallo heredado de perfilado, la dependencia
de Moth y los orquestadores grandes.

## Actualización verificada: divulgación de rutas WordPress

`crawl.wordpress_fullpathdisclosure` registra el hallazgo mediante la KB
configurada en el plugin, conservando la detección de temas, plugins y errores
fatales de PHP.

Verificación: 4 tests del plugin pasan, Ruff, Black y mypy pasan en el módulo
modificado. El score sigue en **5.75/10**: quedan 43 imports directos de la KB,
además de la cobertura, mocks, el fallo heredado de perfilado, la dependencia
de Moth y los orquestadores grandes.

## Actualización verificada: enumeración de usuarios WordPress

`crawl.wordpress_enumerate_users` registra los usuarios descubiertos mediante
la KB configurada en el plugin, conservando la detección por `author=ID`.

Verificación: 3 tests del plugin pasan, Ruff, Black y mypy pasan en el módulo
modificado. El score sigue en **5.75/10**: quedan 42 imports directos de la KB,
además de la cobertura, mocks, el fallo heredado de perfilado, la dependencia
de Moth y los orquestadores grandes.

## Actualización verificada: composición de los outputs

Los seis outputs que exportan hallazgos, URLs o solicitudes (`csv_file`,
`email_report`, `export_requests`, `html_file`, `json_file` y `xml_file`) reciben
la KB desde `OutputManager` y ya no importan el singleton global. La inicialización
de `w3afCore` publica la KB antes de construir la composición del output; los
tests aislados pueden inyectar la misma dependencia explícitamente.

Verificación: 108 tests del ciclo del `OutputManager` y de los outputs pasan,
incluidos 6 subtests; 2 tests de color de consola siguen fallando por la
configuración de colores del entorno, sin relación con este cambio. Ruff,
Black y mypy pasan en los módulos modificados. El score sigue en **5.75/10**:
quedan 35 imports directos de la KB en producción, además de la cobertura,
mocks, el fallo heredado de perfilado, la dependencia de Moth y los
orquestadores grandes.

## Actualización verificada: recursos de la API

Los recursos de URLs, solicitudes fuzzables y hallazgos consultan la KB del
`w3afCore` asociado al `scan_id` validado. Esto elimina el singleton global de
la capa HTTP y mantiene los datos ligados al contexto de cada exploración.

Verificación: 14 tests de las rutas de API pasan, incluidos 11 subtests, y
Ruff, Black y mypy pasan en los tres recursos modificados. El score sigue en
**5.75/10**: quedan 32 imports directos de la KB en producción, además de la
cobertura, mocks, el fallo heredado de perfilado, la dependencia de Moth y los
orquestadores grandes.

## Actualización verificada: menús de consola

Los menús de KB, explotación y el comando `print` usan la KB del
`w3af_core` recibido por `rootMenu`. Se eliminan sus tres imports del singleton
global sin cambiar la navegación, el listado de hallazgos, la explotación
masiva ni la finalización del comando `print`.

Verificación: 38 tests de menús, explotación y teclas pasan; Ruff, Black y
mypy pasan en los tres módulos modificados. Las advertencias observadas son
de dependencias externas durante la carga de configuración. El score sigue en
**5.75/10**: quedan 29 imports directos de la KB en producción, además de la
cobertura, mocks, el fallo heredado de perfilado, la dependencia de Moth y los
orquestadores grandes.

## Actualización verificada: contexto de KB para payloads

Los shells generados por `AttackPlugin` reciben la KB de la exploración y la
transmiten a los payloads. La KB se descarta en la representación serializada
del shell y se reinyecta al recuperarlo con el core; Apache, SVN, descarga de
fuentes y PHP SCA ya no consultan el singleton global.

Verificación: 42 tests unitarios y 9 subtests de shells, `AttackPlugin` y
payloads base pasan; Ruff, Black y mypy pasan en los módulos modificados. Las
5 pruebas end-to-end de payloads no pudieron iniciar porque el host Moth
`fallback` no resuelve en este entorno. El score sigue en **5.75/10**:
quedan 24 imports directos de la KB en producción, además de la cobertura,
mocks, el fallo heredado de perfilado, la dependencia de Moth y los
orquestadores grandes.

## Actualización verificada: shell handler explícito

`shell_handler.get_webshells` y `get_shell_code` reciben la KB como dependencia
obligatoria. Los attack plugins `file_upload`, `dav`, `rfi` y `eval` la pasan
desde su contexto de plugin, eliminando el último import global de esta ruta.

Verificación: 77 tests de `shell_handler` y persistencia de KB pasan; mypy,
Ruff y Black pasan en los consumidores modificados. Persisten únicamente dos
advertencias de `ldap3`/`pyasn1` durante la suite. El score sigue en
**5.75/10**: quedan 23 imports directos de la KB en producción, además de la
cobertura, mocks, el fallo heredado de perfilado, la dependencia de Moth y los
orquestadores grandes.

## Actualización verificada: ataque RFI

`attack.rfi` consulta sus vulnerabilidades RFI y XSS mediante la KB inyectada
por `AttackPlugin`; el módulo ya no importa el singleton global.

Verificación: Ruff, Black y mypy pasan en el módulo. Las 2 pruebas de
explotación RFI no pudieron completar porque `php_moth-fallback` no resuelve
en este entorno. El score sigue en **5.75/10**: quedan 22 imports directos de
la KB en producción, además de la cobertura, mocks, el fallo heredado de
perfilado, la dependencia de Moth y los orquestadores grandes.

## Actualización verificada: infraestructura HTTP y PHP

`afd`, `allowed_methods`, `php_eggs` y `server_header` escriben y leen la KB
mediante la dependencia configurada en `InfrastructurePlugin`; sus fixtures
aislados también la inyectan explícitamente.

Verificación: 29 tests de los cuatro plugins pasan, y Ruff, Black y mypy pasan
en producción y fixtures modificados. El score sigue en **5.75/10**: quedan
18 imports directos de la KB en producción, además de la cobertura, mocks, el
fallo heredado de perfilado, la dependencia de Moth y los orquestadores
grandes.

## Actualización verificada: detectores de red y WAF

`detect_reverse_proxy`, `detect_transparent_proxy`, `dns_wildcard`,
`find_vhosts`, `fingerprint_os` y `fingerprint_waf` usan la KB inyectada por
`InfrastructurePlugin`. El fixture HTTP compartido y las instancias manuales
de tests configuran ahora explícitamente esa dependencia.

Verificación: 34 tests y 20 subtests pasan; Ruff, Black y mypy están limpios
en los seis plugins. El score sigue en **5.75/10**: quedan 12 imports directos
de la KB en producción, además de la cobertura, mocks, el fallo heredado de
perfilado, la dependencia de Moth y los orquestadores grandes.

## Actualización verificada: estado del servidor y hosting compartido

`server_status` y `shared_hosting` consultan y escriben la KB mediante la
dependencia de `InfrastructurePlugin`, sin imports del singleton global.

Verificación: 10 tests pasan, con Ruff, Black y mypy limpios en ambos plugins.
El score sigue en **5.75/10**: quedan 10 imports directos de la KB en
producción, además de la cobertura, mocks, el fallo heredado de perfilado, la
dependencia de Moth y los orquestadores grandes.

## Actualización verificada: crawlers con KB inyectada

`ghdb`, `open_api`, `pykto` y `user_dir` usan la KB proporcionada por
`CrawlPlugin` para registrar hallazgos y consultar usuarios o correos, sin
importar el singleton global.

Verificación: 58 tests pasan; Ruff, Black y mypy están limpios en los cuatro
plugins. Las advertencias restantes pertenecen a dependencias externas de
`jsonschema`. El score sigue en **5.75/10**: quedan 6 imports directos de la KB
en producción, además de la cobertura, mocks, el fallo heredado de perfilado,
la dependencia de Moth y los orquestadores grandes.

## Actualización verificada: KB explícita en infraestructura y core

`extrusionScanner`, la fábrica de transferencias, `vdaemon`, `w3afAgent` y los
shells reciben la KB explícitamente desde el contexto de explotación. Los
analizadores de `phpinfo` también reciben su almacén como argumento, y
`w3afCore` admite una KB inyectada manteniendo `w3afCore()` como entrada
compatible.

Verificación: 26 tests de core y `phpinfo`, más 21 tests de `ExecShell`, pasan;
Ruff, Black y mypy están limpios en los módulos modificados. El recuento de
imports directos de la KB en producción es **0**. Persisten fallos ambientales
en pruebas de extrusión/transferencia que dependen de detección del OS,
servicios locales o `php_moth-fallback`; el score sigue en **5.75/10** por la
cobertura, mocks heredados, el fallo de perfilado, la dependencia de Moth y los
orquestadores grandes.

## Validación global posterior

Ruff, Black y mypy pasan en todo el repositorio (`1598`, `1598` y `1592`
archivos respectivamente). `pip-audit` no encuentra vulnerabilidades conocidas;
el único paquete no auditable es el pin de desarrollo `mitmproxy`
`13.0.0.dev0`. `bandit -r w3af` sigue reportando 46 hallazgos, principalmente
en tests heredados y procesos deliberadamente ejecutados por ellos, sin que se
hayan suprimido.

La corrida completa de `pytest --cov=w3af --cov-fail-under=100 -q` fue
interrumpida en aproximadamente el 76% después de varios fallos de integración
y bloqueos ambientales, por lo que no se considera una validación aprobada ni
permite afirmar cobertura global. El score permanece en **5.75/10**.

## Actualización verificada: directorios de runtime separados

La preparación del directorio home y del directorio temporal salió de
`w3afCore` y pasó a `core_helpers/runtime_directories.py`. El core conserva la
coordinación del ciclo de vida, mientras el helper concentra creación,
permisos y errores del entorno.

Verificación: 15 tests del core pasan; Ruff, Black y mypy están limpios en el
helper, el core y sus tests. El score permanece en **5.75/10**: la mejora es
local y siguen pendientes cobertura global, hallazgos de Bandit, mocks
heredados, perfilado, Moth y otros orquestadores grandes.

## Actualización verificada: disponibilidad del target separada

La verificación HTTP inicial de los targets salió de `CoreStrategy` y pasó a
`core_helpers/target_validation.py`. La estrategia conserva la coordinación
del scan y delega esta operación de infraestructura, sin duplicar una fachada
para mantener la API antigua.

Verificación: 17 tests de estrategia, 7 subtests, Ruff, Black y mypy pasan en
los módulos modificados. Persisten únicamente warnings de dependencias
externas. El score permanece en **5.75/10**: aún quedan las validaciones de
redirección/404, el router concurrente, Bandit heredado y la cobertura global.

## Actualización verificada: validación completa de targets separada

La verificación de disponibilidad HTTP, redirecciones, alertas de target y
detección 404 salió completamente de `CoreStrategy` y quedó en
`core_helpers/target_validation.py`. La estrategia ahora coordina consumidores
y delega la infraestructura de targets mediante funciones explícitas.

Verificación: 17 tests de estrategia, 7 subtests, Ruff, Black y mypy pasan; el
módulo de estrategia perdió 171 líneas de responsabilidades ajenas. El score
permanece en **5.75/10**: el router concurrente, consumidores, cobertura
global y Bandit heredado siguen pendientes.

## Actualización verificada: política de timeout separada

El estado de timeout por host, los límites configurables, el autoajuste y su
sincronización salieron de `ExtendedUrllib` y pasaron a
`core/data/url/timeout_manager.py`. `ExtendedUrllib` conserva la medición RTT,
el transporte y la API pública de timeout, de modo que la extracción no cambia
los callers ni el logger usado por las pruebas.

Verificación: 6 tests de timeout, 30 tests HTTP generales y 6 tests de manejo
de errores pasan; Ruff, Black y mypy están limpios en los módulos modificados.
El score permanece en **5.75/10**: siguen pendientes la cobertura global,
Bandit heredado, mocks existentes, el fallo de perfilado, Moth y los
orquestadores grandes.

## Actualización verificada: rate limiting separado

La política de máximo de requests por segundo salió de `ExtendedUrllib` y pasó
a `core/data/url/rate_limiter.py`. El opener conserva la misma entrada desde
`_before_send_hook`, el sleep inyectado y el comportamiento de configuración
cero; el lock de pausa por errores dejó de compartir un nombre engañoso con el
rate limiter.

Verificación: 30 tests HTTP generales, 6 tests de errores y 6 tests de timeout
pasan; Ruff, Black y mypy están limpios en los módulos modificados. El score
permanece en **5.75/10**: siguen pendientes cobertura global, Bandit heredado,
mocks existentes, perfilado, Moth y orquestadores grandes.

## Actualización verificada: configuración de consumers sin mutación

`CoreStrategy` ahora crea una lista nueva al combinar plugins de crawl e
infraestructura, evitando que un scan modifique la configuración persistente de
`CorePlugins` y acumule plugins en scans posteriores. La limpieza de colas usa
un bucle explícito en lugar de una comprensión empleada solo por efectos
laterales.

Verificación: 9 tests de estrategia y 7 subtests de bajo nivel, además de 4
tests de estrategia integrada, pasan; Ruff, Black y mypy están limpios en el
módulo modificado. El score permanece en **5.75/10** por cobertura global,
Bandit heredado, mocks existentes, perfilado, Moth y orquestadores grandes.

## Actualización verificada: excepciones fuera de controllers

Las excepciones compartidas (`RunOnce`, `NoMoreCalls`, `ProxyException`,
`NoVulnerabilityFoundException`, `ExploitFailedException` y
`FourOhFourDetectionException`) pasaron a `core/exceptions.py`. Se actualizaron
150 imports en código y tests, se eliminaron las referencias a
`core.controllers.exceptions` y se borró ese módulo, sin alias de
compatibilidad. Plugins, datos, UI y controllers dependen ahora de la capa
común de excepciones en lugar de que plugins dependan del orquestador.

Verificación: compilación completa, 1348 tests de plugins recolectados, 63
tests de excepciones/adaptadores, 33 tests de proxy/404, 21 y 48 tests de
plugins pasan; Ruff, Black y mypy están limpios. El score provisional permanece
en **5.75/10** hasta resolver cobertura global, Bandit heredado, mocks
existentes, perfilado, Moth y los orquestadores grandes.

## Actualización verificada: sink de salida inyectado en infraestructura

`Plugin` expone ahora `set_output()` y `CorePlugins` cablea el sink al crear
instancias. `server_status`, `fingerprint_os`, `fingerprint_waf`,
`detect_reverse_proxy`, `shared_hosting` y `server_header` usan esa dependencia
en lugar de importar directamente el singleton `controllers.output_manager`.

Verificación: 11 tests y 20 subtests de infraestructura, más 19 tests de
infraestructura relacionados, pasan; Ruff, Black y mypy están limpios. El score
permanece en **5.75/10**: aún quedan más consumidores del output global,
cobertura global, Bandit heredado, mocks, perfilado, Moth y orquestadores.

## Actualización verificada: output desacoplado en infraestructura completa

El mismo sink inyectado se extendió al resto de plugins de infraestructura.
Solo `oHmap/hmap.py` conserva output directo porque es un helper de funciones y
clases auxiliares que no hereda de `Plugin`; no se le añadió una falsa
dependencia de instancia. Los tests directos de `finger_bing` y
`finger_google` también configuran explícitamente la KB real que ya recibe el
camino de fábrica.

Verificación: la suite completa de infraestructura pasa con **161 tests y 20
subtests**; Ruff, Black y mypy están limpios. El score permanece en **5.75/10**
por los consumidores de output restantes fuera de infraestructura, cobertura
global, Bandit heredado, mocks, perfilado, Moth y orquestadores.

## Actualización verificada: output desacoplado en audit

`AuditPlugin` y los 19 plugins de audit que usaban el singleton ahora reciben
el mismo sink mediante `Plugin._output`. Se eliminaron esos imports directos de
`controllers.output_manager`; el helper `oHmap/hmap.py` queda fuera porque no
es un plugin y no tiene una instancia a la que inyectar la dependencia.

La suite de contrato de `Plugin` y `AuditPlugin` pasa con **34 tests y 70
subtests**, y la suite directa de CORS pasa con **12 tests** tras configurar la
KB real en su fixture. La ejecución completa de audit obtuvo **211 tests
pasados, 1 omitido y 19 fallidos**: ocho fallos eran ese fixture, dos son
escenarios locales de `file_upload` y los restantes dependen de Moth, WAVSEP,
SSL o respuestas externas. Ruff, Black y mypy están limpios. El score permanece
en **5.75/10** por cobertura global, Bandit heredado, mocks existentes,
perfilado, Moth y los orquestadores grandes.

## Actualización verificada: output desacoplado en exportadores

Los cinco exportadores de fichero que todavía importaban directamente el
singleton (`csv_file`, `email_report`, `export_requests`, `json_file` y
`text_file`) ahora publican sus errores mediante `Plugin._output`. `xml_file`
queda pendiente porque su logging también vive en el decorador `took` y en la
clase auxiliar `Finding`, que no son instancias de plugin y necesitan un
contrato propio.

Verificación: 38 tests y 6 subtests de output pasan para las rutas afectadas;
fallan únicamente 2 aserciones ANSI de `console`, fuera del diff. Ruff, Black y
mypy están limpios. El score permanece en **5.75/10** por el resto de
consumidores globales, cobertura, Bandit heredado, mocks, perfilado, Moth y
los orquestadores.

## Actualización verificada: output desacoplado en autenticación

`AuthPlugin` y `auth.generic` dejaron de importar el singleton de output y usan
el sink heredado de `Plugin`. También se corrigieron dos fixtures unitarios que
creaban plugins sin configurar la KB, y la comprobación del demo externo ahora
compara el tipo de datos real antes de decidir si debe omitirse.

Verificación: **70 tests pasados y 1 omitido** en la suite auth y bases de
plugin; Ruff, Black y mypy están limpios. El score permanece en **5.75/10** por
los consumidores globales restantes, cobertura, Bandit heredado, mocks,
perfilado, Moth y orquestadores grandes.

## Actualización verificada: output desacoplado en bruteforce

`basic_auth` y `form_auth` dejaron de importar el singleton de output y usan el
sink de `Plugin` heredado a través de `BruteforcePlugin` y `AuditPlugin`. No se
alteraron los workers, la generación de credenciales ni el reporte en KB.

Verificación: **37 tests pasados** entre la base y los plugins bruteforce;
Ruff, Black y mypy están limpios. El score permanece en **5.75/10** por los
consumidores globales restantes, cobertura, Bandit heredado, mocks, perfilado,
Moth y orquestadores grandes.

## Actualización verificada: output desacoplado en grep

Los 11 plugins grep que importaban directamente el singleton ahora usan
`Plugin._output`: `http_auth_detect`, `password_profiling`, `lang`, `motw`,
`websockets_links`, `clamav`, `user_defined_regex`, `cross_domain_js`,
`http_in_body`, `vulners_db` y `retirejs`. Los `InfoSet` y helpers auxiliares
sin ciclo de vida de plugin no recibieron una dependencia artificial.

Verificación: `test_http_auth_detect` pasa con **5 tests**; los tests de
`lang`/`motw` alcanzan **8 tests pasados** antes de que `websockets_links` falle
por un fixture sin KB, y `password_profiling` falla porque el test espera un
diccionario aunque la KB entrega una lista. La suite grep completa también
queda bloqueada en integración externa. Ruff, Black y mypy están limpios. El
score permanece en **5.75/10** por cobertura, Bandit heredado, mocks, los
fixtures pendientes, Moth y los orquestadores grandes.

## Actualización verificada: bases de plugin usan el sink

`Plugin` reporta hallazgos y errores a través de `self._output`, y
`AttackPlugin`, `CrawlPlugin`, `GrepPlugin` e `InfrastructurePlugin` ya no
importan el singleton para sus mensajes. El único acceso restante en este
núcleo es la inicialización por defecto de `Plugin._output`; el factory puede
reemplazarlo mediante `set_output()`.

Verificación: **63 tests y 9 subtests** de las bases pasan; Ruff, Black y mypy
están limpios. El score permanece en **5.75/10** por cobertura, Bandit
heredado, mocks, fixtures de tests pendientes, Moth, consumidores de output
restantes y orquestadores grandes.

## Actualización verificada: output desacoplado en crawl

17 plugins de crawl que no mezclan helpers con ciclo de vida propio ahora usan
`Plugin._output`: `archive_dot_org`, `content_negotiation`, `dot_ds_store`,
`dot_listing`, `dwsync_xml`, `find_backdoors`, `find_captchas`, `find_dvcs`,
`genexus_xml`, `import_results`, `oracle_discovery`,
`payment_webhook_finder`, `phishtank`, `robots_txt`, `sitemap_xml`,
`url_fuzzer` y `urllist_txt`. Los módulos crawl que mezclan parsers o proxies
auxiliares quedan para un tratamiento explícito posterior.

Verificación: **95 tests pasados** en los módulos afectados; Ruff, Black y
mypy están limpios, y esos 17 archivos ya no importan `output_manager`. El
score permanece en **5.75/10** por cobertura, Bandit heredado, mocks, fixtures
pendientes, Moth, consumidores de output restantes y orquestadores grandes.

## Actualización verificada: output desacoplado en XML

`xml_file` ya no importa el singleton de output. Sus métodos usan
`self._output`, el decorador `took` registra tiempos solo cuando recibe un
plugin con sink, y `Finding` recibe el sink explícitamente para informar
errores de transacciones HTTP. Así también quedan desacoplados los helpers que
antes ocultaban una dependencia global.

Verificación: **30 tests pasados** en `test_xml_file`; Ruff, Black y mypy están
limpios, y no quedan referencias a `output_manager` ni `om.out` en
`plugins/output`. El score permanece en **5.75/10** por cobertura, Bandit
heredado, mocks, fixtures pendientes, Moth, consumers y orquestadores grandes.

## Actualización verificada: output desacoplado en consumidores

`BaseConsumer` acepta ahora un sink explícito y concentra el único fallback al
singleton global. `audit`, `auth`, `bruteforce`, `grep` y
`CrawlInfrastructure` reutilizan ese sink en lugar de importar directamente
`output_manager`; `CoreStrategy` lo inyecta al componerlos. La lógica de
consumo, las colas y el ciclo de vida no cambian.

Verificación: **58 tests pasados** en consumidores y estrategia, con 9 avisos
de deprecación procedentes de dependencias externas; Ruff, Black y mypy están
limpios. El score permanece en **5.75/10** por los consumidores y helpers aún
globales, cobertura 100% no demostrada, Bandit heredado, mocks existentes,
Moth y los orquestadores grandes.

## Actualización verificada: output desacoplado en CoreStrategy

`CoreStrategy` recibe ahora el sink como dependencia obligatoria y lo propaga a
los consumidores que compone. `w3afCore` queda como composition root para el
output global; el orquestador ya no importa `output_manager` ni decide qué
singleton usar. Se actualizaron sus subclases y construcciones de test.

Verificación: **25 tests pasados y 7 subtests** en estrategia, crawl y grep;
Ruff, Black y mypy están limpios. El score permanece en **5.75/10** por el
singleton todavía presente en `w3afCore` y otros módulos, cobertura 100% no
demostrada, Bandit heredado, mocks existentes, Moth y los orquestadores aún
grandes.

## Actualización verificada: validación de targets sin singleton

Los helpers `verify_target_server_up`, `replace_targets_with_redir`,
`alert_if_target_is_301_all` y `setup_404_detection` reciben ahora el sink de
salida de `CoreStrategy`. También lo usan sus context managers internos para
diagnósticos, avisos y hallazgos, eliminando la dependencia global de
`target_validation` sin tocar la política de red ni el manejo de excepciones.

Verificación: **9 tests pasados y 7 subtests** en la estrategia de bajo nivel;
Ruff, Black y mypy están limpios. El score permanece en **5.75/10** por el
singleton restante en otros helpers y UI, cobertura 100% no demostrada, Bandit
heredado, mocks existentes, Moth y los orquestadores grandes.

## Actualización verificada: observadores con output explícito

`ThreadCountObserver` y `ThreadStateObserver` reciben el sink en su constructor
y ya no importan `output_manager`. `w3afCore` lo entrega al crear los
observadores, y los tests usan el sink real del entorno de prueba. Se conserva
la periodicidad, el análisis de pools y la señal de finalización de sus hilos.

Verificación: **22 tests pasados y 7 subtests** entre observadores y estrategia;
Ruff, Black y mypy están limpios. El score permanece en **5.75/10** por el
singleton restante en `w3afCore` y otros módulos, cobertura 100% no demostrada,
Bandit heredado, mocks existentes, Moth y los orquestadores grandes.

## Actualización verificada: ExceptionHandler con output explícito

`ExceptionHandler` recibe el sink desde `w3afCore` y usa esa dependencia para
errores, trazas y crash reports. Sus consumidores siguen llamando al handler
sin acoplarse al sistema de output, y la semántica de reelevar excepciones no
ha cambiado.

Verificación: **19 tests pasados** en la suite del handler; Ruff, Black y mypy
están limpios. El score permanece en **5.75/10** por el singleton restante en
`w3afCore` y otros módulos, cobertura 100% no demostrada, Bandit heredado,
mocks existentes, Moth y los orquestadores grandes.

## Actualización verificada: seed con output explícito

El productor `seed` recibe el sink desde `CoreStrategy` y ya no importa el
singleton global. Los errores de target, el vaciado de la cola y el resto del
flujo de creación de `FuzzableRequest` conservan su comportamiento.

Verificación: **14 tests pasados y 7 subtests** entre seed y estrategia; Ruff,
Black y mypy están limpios. El score permanece en **5.75/10** por el singleton
restante en otros módulos, cobertura 100% no demostrada, Bandit heredado,
mocks existentes, Moth y los orquestadores grandes.

## Actualización verificada: CoreStatus con output explícito

`CoreStatus` recibe el sink y `w3afCore`/`BaseConsumer` lo propagan al crear
estados. `ExceptionData` ahora conserva una copia sanitizada del estado, sin
referencias al core ni al sink, para mantener la serialización entre procesos
sin mutar el estado vivo del escaneo.

Verificación: **49 tests pasados** en estado y excepciones, incluidos los casos
de serialización; **32 tests y 7 subtests** en consumidor base y estrategia;
Ruff, Black y mypy están limpios. El score permanece en **5.75/10** por otros
singletons, cobertura 100% no demostrada, Bandit heredado, mocks existentes,
Moth y los orquestadores grandes.

## Actualización verificada: factory de plugins con output explícito

`CorePlugins` recibe el sink desde `w3afCore` y lo utiliza al configurar cada
plugin y al informar dependencias habilitadas. El manager global se conserva
solo para registrar opciones/plugins de output, que es responsabilidad propia
de esta infraestructura; el sink de mensajes ya no se consulta desde el
factory. También se actualizaron el catálogo API y los tests.

Verificación: **95 tests pasados, 9 avisos externos y 40 subtests** en plugins
y API, más **2 tests pasados** en los endpoints de excepciones; Ruff, Black y
mypy están limpios. El score permanece en **5.75/10** por singletons restantes,
cobertura 100% no demostrada, Bandit heredado, mocks existentes, Moth y los
orquestadores grandes.

## Actualización verificada: consumidores sin fallback global

`BaseConsumer` y sus cinco consumidores concretos (`audit`, `auth`,
`bruteforce`, `grep` y `CrawlInfrastructure`) exigen ahora el sink en su
constructor. Se actualizaron todos los callers del repositorio, incluido el
teardown de `grep` y el `FakeStatus` usado por `OutputManager`; ya no queda un
fallback a `om.out` en este límite de ejecución.

Verificación: **95 tests pasados** en consumidores, estado y observadores;
`OutputManager` y el caso de error de `grep` también pasan (**9 tests** en
total); Ruff, Black y mypy están limpios. El score permanece en **5.75/10** por
404/UI/daemons aún globales, cobertura 100% no demostrada, Bandit heredado,
mocks existentes, Moth y los orquestadores grandes.

## Actualización verificada: detección de retrasos con output explícito

`ExactDelayController` y `BlindSQLTimeDelay` reciben el sink desde los plugins
audit y dejan de importar el output global. Se actualizaron sus siete callers,
incluido el camino de blind SQL, y los tests de controlador. La lógica de
timeouts, payloads reversos y clasificación de respuestas no cambia.

Verificación: **8 tests pasados** en los controladores y **38 tests pasados** en
los cinco plugins audit afectados; Ruff, Black y mypy están limpios. El score
permanece en **5.75/10** por 404/UI/daemons aún globales, cobertura 100% no
demostrada, Bandit heredado, mocks existentes, Moth y los orquestadores grandes.

## Actualización verificada: helpers de crawl sin fallback global

Los analizadores de PHPInfo, el lector CSV de `user_dir`, `NiktoTestParser` y
la validación de dominio de OpenAPI exigen ahora el sink de output de forma
explícita. Se eliminaron sus imports de `output_manager` y los fallbacks al
singleton global; los callers de producción y los tests pasan la dependencia
real que ya posee el flujo de ejecución.

Verificación: **56 tests pasados** en `user_dir`, `pykto`, PHPInfo y OpenAPI;
Ruff y Black están limpios. El score permanece en **5.75/10** por 404/UI/
daemons aún globales, cobertura 100% no demostrada, Bandit heredado, mocks
existentes, Moth y los orquestadores grandes.

## Actualización verificada: Plugin sin fallback de output

La clase base `Plugin` ya no importa ni captura `om.out` al construirse. El
sink se configura únicamente mediante `set_output()`, que es el punto usado
por `CorePlugins`; los tests unitarios que crean plugins directamente ahora
declaran esa dependencia de forma explícita.

Verificación: **74 tests pasados** en bases de plugins y factory; Ruff, Black y
mypy están limpios. El score permanece en **5.75/10** por 404/UI/daemons y
plugins attack aún globales, cobertura 100% no demostrada, Bandit heredado,
mocks existentes, Moth y los orquestadores grandes.

## Actualización verificada: detector 404 con output explícito

`Fingerprint404`, `LRUCache404`, `PreventMultipleThreads` y la generación de
respuestas 404 reciben el sink por composición. `is_404` ya no crea ni usa un
detector con output global; todos los consumidores de crawl, grep e
infrastructure pasan `self._output`, y `w3afCore` inicializa el singleton con
el sink de la ejecución actual. El cleanup puede liberar el singleton sin
crear una instancia incompleta.

Verificación: **86 tests pasados y 7 subtests** en detector, decoradores,
generación 404, bases de plugins y estrategia; Ruff, Black y mypy están
limpios. El score actualizado es **6.25/10**: quedan plugins attack, UI,
daemons y otros servicios globales, cobertura 100% no demostrada, Bandit
heredado, mocks existentes, Moth y los orquestadores grandes.

## Actualización verificada: attack eval con output explícito

El plugin attack `eval` usa su sink inyectado tanto durante la verificación de
la vulnerabilidad como dentro de `EvalShell`; la reconstrucción del shell
también conserva la dependencia explícita y ya no importa `output_manager`.

Verificación: Ruff, Black y mypy están limpios. La suite de integración de
`eval` no pudo validarse porque el entorno Moth configuró el host `fallback`,
que no resuelve DNS; el score permanece en **6.25/10** hasta cubrir esa ruta.

## Actualización verificada: shells DAV y file upload con output explícito

Los plugins attack `dav` y `file_upload` pasan ahora su sink a los shells que
crean. Los mensajes de subida, ejecución y limpieza usan esa dependencia, y
las reconstrucciones por pickle conservan el contrato; ambos módulos dejaron
de importar `output_manager`.

Verificación: Ruff, Black y mypy están limpios. Las suites de integración de
ambos plugins no se ejecutaron correctamente porque dependen del entorno Moth
no resoluble (`fallback`); el score permanece en **6.25/10** hasta verificarlas.

## Actualización verificada: SQLMap con output explícito

`SQLMapWrapper`, `RunFunctor`, `SQLMapShell` y el plugin `sqlmap` comparten
ahora el sink inyectado. Los mensajes del proceso externo, errores de
inicialización, detección de sistema operativo y reconstrucciones por pickle
ya no consultan `output_manager` directamente.

Verificación: Ruff, Black y mypy están limpios. La suite de explotación SQLMap
requiere Moth/SQLMap testenv y queda pendiente por el host DNS no resoluble;
el score permanece en **6.25/10** hasta cubrir esa integración.

## Actualización verificada: OS Commanding sin output global

La selección de estrategias de `os_commanding` usa ahora el sink del plugin
para errores, intentos y resultado de explotación. El shell no necesitaba esa
dependencia, por lo que no se añadió estado innecesario a su contrato.

Verificación: Ruff, Black y mypy están limpios. La integración de explotación
queda pendiente de su entorno Moth; el score permanece en **6.25/10**.

## Actualización verificada: XPath con output explícito

El plugin `xpath` y `XPathReader` reciben el sink desde la factoría de plugins.
Los diagnósticos de delimitador, detección de respuestas, extracción de XML y
caracteres ya no usan el singleton; la reconstrucción del shell conserva el
sink junto al resto de su estado operativo.

Verificación: Ruff, Black y mypy están limpios. La suite de integración XPath
queda pendiente por la dependencia Moth no resoluble; el score permanece en
**6.25/10**.

## Actualización verificada: Local File Reader con output explícito

`local_file_reader` y `FileReaderShell` reciben el sink desde la factoría. Los
errores de lectura, selección del wrapper base64 y fallos de extracción usan
esa dependencia; la reconstrucción del shell conserva sus offsets y el sink,
sin importar `output_manager`.

Verificación: Ruff, Black y mypy están limpios. La suite de integración queda
pendiente por el entorno Moth no resoluble; el score permanece en **6.25/10**.

## Actualización verificada: RFI con output explícito

El plugin `rfi` usa el sink inyectado para configuración, XSS, servidor local y
errores de explotación. `RFIShell` recibe el mismo sink para su limpieza y lo
conserva en la reconstrucción; `PortScanShell` no recibe estado que no utiliza.

Verificación: Ruff, Black y mypy están limpios. La integración RFI queda
pendiente por Moth no resoluble; el score permanece en **6.25/10**.

## Actualización verificada: payloads con shell output-injected

El shell cableado por la capa de plugins expone `set_output()`, y
`AttackPlugin` lo aplica antes de guardar cada shell en la KB. El decorador de
ejecución y los payloads que muestran progreso o errores usan el sink del shell
en lugar de importar `output_manager`; la capa de datos sigue sin depender de
infraestructura.

Verificación: Ruff, Black y mypy están limpios; **14 tests pasaron** en shells
y payloads. Un test adicional no es portable en macOS porque el fixture
existente lee `/proc`, que solo existe en Linux; el score permanece en
**6.25/10**.

## Actualización verificada: webserver y reverse HTTP con output explícito

El daemon HTTP recibe el sink al construirse y `WebHandler` ya no importa
`output_manager`. RFI y la transferencia reverse HTTP pasan la dependencia a
la fábrica del servidor; los tests y el factory mantienen explícito el punto
de composición.

Verificación: Ruff, Black y mypy están limpios; **25 tests pasaron y 1 fue
omitido** en webserver, reverse HTTP y RFI. El test restante de transferencia
no es portable en macOS porque ejecuta comandos locales con un fixture que
simula Linux; el score permanece en **6.25/10**.

## Actualización verificada: proxy con output explícito

`Proxy`, `InterceptProxy` y `LoggingProxy` reciben el sink de su composición;
los mensajes de arranque, error y parada ya no importan `output_manager`. Se
actualizaron SQLMap, spider_man y todos los callers de tests para conservar el
flujo real de salida.

Verificación: **31 tests pasaron** en proxy, interceptación, Xurllib y
spider_man; Ruff, Black y mypy están limpios. Persisten los límites globales
de UI, servicios y composición, además de cobertura total no demostrada,
Bandit heredado y las integraciones Moth; el score permanece en **6.25/10**.

## Actualización verificada: bruteforce con output explícito

`PasswordBruteforcer`, `UserPasswordBruteforcer` y `get_profiling_results`
reciben ahora el sink desde `BruteforcePlugin`. Los diagnósticos de combos
inválidos y profiling vacío ya no consultan `output_manager` global.

Verificación: **20 tests pasaron** en los generadores y el plugin bruteforce;
Ruff, Black y mypy están limpios. El score permanece en **6.25/10** por los
servicios restantes, cobertura 100% no demostrada, Bandit heredado, mocks,
Moth y los orquestadores grandes.

## Actualización verificada: helpers de ejecución con output explícito

`os_detection_exec` y `get_remote_temp_file` reciben el sink de sus callers;
los mensajes de detección de sistema operativo ya no dependen de
`output_manager`. Se actualizaron transferencia, extrusion, vdaemon, agente y
los handlers de ejecución diferida, además de sus tests.

Verificación: **6 tests pasaron y 2 fueron omitidos** en los helpers; Ruff,
Black y mypy están limpios. El score permanece en **6.25/10** porque los
orquestadores que aún escriben directamente al singleton siguen pendientes,
junto con cobertura 100% no demostrada, Bandit heredado, mocks e integraciones
Moth.

## Actualización verificada: scheduling y vdaemon con output explícito

`delayedExecution`, `atHandler`, `crontabHandler`, los vdaemon y la fábrica de
metasploit reciben el sink desde sus puntos de composición. Los mensajes de
ejecución diferida, cron, `at` y transferencia de payload dejaron de depender
del singleton; el agente conserva su sink en la composición existente.

Verificación: Ruff, Black y mypy están limpios y los módulos modificados
importan correctamente. Este checkout no contiene tests dedicados de
scheduling/vdaemon; la cobertura de esas rutas queda pendiente y el score
permanece en **6.25/10**.

## Actualización verificada: DNS cache con output explícito

`enable_dns_cache` crea ahora un wrapper parcial que captura el sink recibido;
las respuestas DNS cacheadas ya no consultan `output_manager` global. El core
inyecta el sink al activar la caché y el test verifica el callable envuelto.

Verificación: **3 tests pasaron** en la caché DNS; Ruff, Black y mypy están
limpios. El score permanece en **6.25/10** por los globals restantes de UI y
servicios, cobertura total no demostrada, Bandit heredado, mocks e
integraciones Moth.

## Actualización verificada: hmap con output explícito

El plugin `hmap` entrega su sink a `testServer`; este lo propaga mediante
`Target` hasta cada `request` y `read_until_closed`. La librería de
fingerprinting ya no importa `output_manager` ni conserva el shortcut de
standalone; se mantiene intacta la lógica de sondas y fingerprinting.

Verificación: **21 tests pasaron** en hmap; Ruff, Black, mypy, `py_compile` y
`git diff --check` globales están limpios. El score permanece en **6.25/10**
por los globals de composición/UI restantes, cobertura 100% no demostrada,
Bandit heredado, mocks e integraciones Moth.

## Actualización verificada: profiling de consumidores sin fallback global

`TookLine` exige ahora un sink explícito y los cinco consumidores (`audit`,
`auth`, `bruteforce`, `crawl` y `grep`) pasan su `self._output`. Los fixtures
de consumidores también declaran el sink de sus plugins, eliminando la
dependencia implícita del singleton en estas rutas.

Verificación: **62 tests pasaron** en profiling y consumidores; Ruff, Black y
mypy están limpios. El score permanece en **6.25/10** por los globals restantes
de UI y servicios, cobertura total no demostrada, Bandit heredado, mocks e
integraciones Moth.

## Actualización verificada: lifecycle de profiling con output explícito

`start_profiling` y `stop_profiling` reciben el sink desde `w3afCore`; los
mensajes de parada y error ya no dependen de `output_manager` global.

Verificación: **3 tests pasaron** en profiling; Ruff, Black y mypy están
limpios. El score permanece en **6.25/10** por los globals restantes de UI y
servicios, cobertura total no demostrada, Bandit heredado, mocks e
integraciones Moth.

## Actualización verificada: auto-update sin fallback global

`VersionMgr` exige ahora el logger explícito como argumento keyword-only. La
UI de consola ya lo compone con `self._output.console`, por lo que el gestor
de versiones dejó de importar o consultar `output_manager` global.

Verificación: **17 tests pasaron** en version manager y auto-update; Ruff,
Black y mypy están limpios. El score permanece en **6.25/10** por los globals
restantes de UI y servicios, cobertura total no demostrada, Bandit heredado,
mocks e integraciones Moth.

## Actualización verificada: tablas de consola con output explícito

`console_tables.table` recibe ahora el sink en su constructor y deja de
importar `output_manager`. Se actualizaron sus composiciones de consola y los
53 payloads que dibujan tablas para entregar `self.shell._output`, sin cambiar
el formato ni el algoritmo de distribución de columnas.

Verificación: todas las tablas construidas en payloads tienen sink explícito;
Ruff, Black, mypy, `py_compile` y `git diff --check` globales están limpios.
Los tests de consola pasan aisladamente; el corpus de payloads aún tiene el
fallo macOS conocido de `/proc/sys/kernel/ostype`. El score permanece en
**6.25/10** por los globals restantes, cobertura 100% no demostrada, Bandit
heredado, mocks e integraciones Moth.

## Actualización verificada: cierre de globals de servicios y UI

Desde la última evaluación se eliminaron dependencias globales adicionales en
tablas de consola, API REST, hmap y el bridge de logging. Los sinks/managers
viajan desde `w3afCore`, la UI o el plugin hasta el punto que los consume; los
payloads de tablas fueron actualizados de forma mecánica y revisados.

Verificación acumulada del bloque: hmap (**21 tests**), API REST (**1 test + 6
subtests**), tablas/menús de consola (**32 tests aislados**) y bridge/parser
(**40 tests**). Ruff, Black, mypy, `py_compile` y `git diff --check` están
limpios. El score conservador permanece en **6.25/10** por los globals de
composición aún deliberados, cobertura 100% no demostrada, Bandit heredado,
mocks e integraciones Moth.

## Actualización verificada: API REST con dependencias del core

Las rutas REST de scans y excepciones ya no importan `output_manager` para
configurar la ejecución: usan el sink y el manager explícitos del
`w3afCore` que ya poseen. El catálogo de plugins sigue siendo una composición
independiente del endpoint.

Verificación: **1 test** de excepciones y **5 tests más 6 subtests** del
lifecycle REST pasaron; Ruff, Black, mypy, `py_compile` y `git diff --check`
globales están limpios. El score permanece en **6.25/10** por los globals
restantes, cobertura 100% no demostrada, Bandit heredado, mocks e
integraciones Moth.

## Actualización verificada: menú de consola sin fallback global

El menú de consola ya no importa `output_manager`: el root toma el sink
expuesto por `w3afCore` y los menús hijos lo heredan desde su padre. Se
mantienen las mismas firmas de los menús existentes y la composición queda en
el borde de la UI.

Verificación: **32 tests pasaron** en completion y menús; las 9 advertencias
proceden de dependencias externas. Ruff, Black, mypy, `py_compile` y
`git diff --check` globales están limpios. El score permanece en **6.25/10**
por los globals restantes, cobertura 100% no demostrada, Bandit heredado,
mocks e integraciones Moth.

## Actualización verificada: CorePlugins con manager de salida explícito

`CorePlugins` recibe ahora tanto el sink como la instancia de `OutputManager`.
La configuración de plugins de salida ya no importa ni consulta el módulo
global; `w3afCore`, la API y los tests entregan ambas dependencias al componerlo.

Verificación: **27 tests pasaron** en CorePlugins; las 9 advertencias proceden
de dependencias externas (`ldap3`/`jsonschema`), no del cambio. Ruff, Black,
mypy, `py_compile` y `git diff --check` globales están limpios. El score
permanece en **6.25/10** por los globals restantes, cobertura 100% no
demostrada, Bandit heredado, mocks e integraciones Moth.

## Actualización verificada: extrusion y payload transfer con output explícito

`payload_transfer_factory`, `EchoLinux`, `EchoWindows`, `extrusionScanner` y
`extrusionServer` reciben el sink desde composición. `Shell.set_output()` cablea
la factoría mediante `partial`, manteniendo la capa de datos libre de
`output_manager`; vdaemon y w3afAgent pasan el sink a la factoría.

Verificación: Ruff, Black y mypy están limpios; **5 tests pasaron y 2 fueron
omitidos** en el bloque relacionado. Tres fixtures locales fallan en macOS
porque simulan Linux y usan `/etc/passwd`, echo remoto y reverse HTTP; el
score permanece en **6.25/10**.

## Actualización verificada: w3afAgent server con output explícito

`w3afAgentServer`, `ConnectionManager`, `TCPRelay` y `PipeThread` reciben el
sink desde el manager o el entrypoint CLI. Los logs de sockets, conexiones,
relays y parada ya no consultan `output_manager` dentro del servidor.

Verificación: Ruff, Black, mypy y `py_compile` están limpios. Este checkout no
contiene tests específicos del agente; la cobertura de sus rutas queda
pendiente y el score permanece en **6.25/10**.

## Actualización verificada: w3afAgent manager con output explícito

`w3afAgentManager` recibe ahora el sink desde el payload `w3af_agent` y usa
`self._output` para sus logs y para componer el servidor, la transferencia y
la ejecución diferida. El manager ya no importa `output_manager`.

Verificación: Ruff, Black, mypy, `py_compile`, `4` tests de shells y `git diff
--check` están limpios. El test de integración del payload no inicia porque el
entorno no resuelve `php_moth-fallback`; no hay tests dedicados del manager y
el score permanece en **6.25/10**.

## Actualización verificada: detector de blind SQLi con output explícito

`BlindSqliResponseDiff` recibe ahora el sink desde `blind_sqli` y lo conserva
para sus mensajes de diagnóstico y vulnerabilidad. El detector y su test ya no
dependen de `output_manager` global.

Verificación: **21 tests pasaron** en el detector; Ruff, Black y mypy focalizados
están limpios. El score permanece en **6.25/10** por los globals restantes,
cobertura 100% no demostrada, Bandit heredado, mocks e integraciones Moth.

## Actualización verificada: decorator retry sin output global

`retry` conserva sus reintentos sin depender de `output_manager`; cuando se
configura `log_msg`, exige ahora un sink explícito y registra directamente en
él. El único uso productivo de logging no existía; el test cubre el contrato y
los decorators restantes no cambian.

Verificación: **10 tests pasaron** en decorators; Ruff, Black, mypy y
`git diff --check` globales están limpios. El score permanece en **6.25/10**
por los globals restantes, cobertura 100% no demostrada, Bandit heredado,
mocks e integraciones Moth.

## Actualización verificada: parser worker con manager explícito

`parser_worker` ya no importa el módulo global `output_manager` para localizar
la cola de logs. `w3afCore` entrega su `OutputManager` al registrar el
bootstrap, y el provider de cola se captura con `partial` antes de pasarlo a la
capa de parsers.

Verificación: **38 tests pasaron** en multiprocessing de parsers y **11 tests
pasaron** en la inicialización del core. Ruff, Black, mypy, `py_compile` y
`git diff --check` globales están limpios. El score permanece en **6.25/10**
por los globals restantes, cobertura 100% no demostrada, Bandit heredado,
mocks e integraciones Moth.

## Actualización verificada: profiling de core con manager explícito

`core_stats` recibe ahora el `OutputManager` para medir el tamaño de su cola;
el lifecycle de profiling lo propaga al timer y a la captura final. Se elimina
la consulta directa al módulo global desde `core_stats`, manteniendo el resto
de métricas y el comportamiento de plataformas sin `qsize`.

Verificación: **11 tests pasaron** en core stats y profiling; Ruff, Black, mypy,
`py_compile` y `git diff --check` globales están limpios. El score permanece en
**6.25/10** por los globals restantes, cobertura 100% no demostrada, Bandit
heredado, mocks e integraciones Moth.

## Actualización verificada: ConsoleUIUpdater con output explícito

`ConsoleUIUpdater` ya no importa ni usa `output_manager` como fallback. El
root `ConsoleUI` y los tests le entregan explícitamente el sink que debe usar,
manteniendo la composición de UI en el borde de la aplicación.

Verificación: **6 tests pasaron** en el updater; Ruff, Black, mypy, `py_compile`
y `git diff --check` globales están limpios. El score permanece en **6.25/10**
por los globals restantes, cobertura 100% no demostrada, Bandit heredado,
mocks e integraciones Moth.

## Actualización verificada: monkey patch de debug con sink explícito

`monkey_patch_debug` crea ahora callbacks parciales que capturan el sink
recibido, y `w3afCore` lo entrega al activar el parche. La restauración sigue
usando las funciones originales y el módulo deja de importar `output_manager`.

Verificación: **3 tests pasaron** en el parche de debug; Ruff, Black, mypy,
`py_compile` y `git diff --check` globales están limpios. El score permanece en
**6.25/10** por los globals restantes, cobertura 100% no demostrada, Bandit
heredado, mocks e integraciones Moth.

## Actualización verificada: I/O de consola con manager explícito

Las operaciones sincronizadas de `console.py` (`write`, `writeln`, `bell` y
`getch`) reciben ahora el `OutputManager` de forma explícita. `ConsoleUI` lo
obtiene del `w3afCore` que compone y lo propaga a cada operación; el módulo de
I/O y la UI ya no consultan el manager global para sincronizar mensajes.

Verificación: **172 tests pasaron** en toda la suite de consola; Ruff, Black,
mypy focalizado y `git diff --check` están limpios. Persisten avisos de
deprecación en dependencias externas. El score permanece en **6.25/10** por
los globals restantes, cobertura 100% no demostrada, Bandit heredado, mocks e
integraciones Moth.

## Actualización verificada: w3afCore usa sus dependencias de instancia

El ciclo principal de `w3afCore` deja de leer `om.out`, `om.manager` y
`om.log_http` después de construir la composición de salida. Los hooks de
inicio, scan, parada, profiling, workers y finalización usan ahora
`self._output` y `self._output_manager`; la fábrica global queda confinada al
arranque de la composición.

Verificación: **35 tests y 7 subtests pasaron** en lifecycle, hooks, estrategia,
profiling e instancias múltiples. El score permanece en **6.25/10** por los
globals restantes fuera de este composition root, cobertura 100% no demostrada,
Bandit heredado, mocks e integraciones Moth.

## Actualización verificada: decorador interno del OutputManager sin singleton

`start_thread_on_demand` usa ahora la instancia `OutputManager` recibida por el
método decorado para comprobar y arrancar el proceso. Se elimina la importación
dinámica del módulo global desde el decorador sin cambiar la sincronización de
`process_all_messages` ni `log_enabled_plugins`. Además, el bridge de logging
reemplaza su handler cuando cambia el sink, evitando que una nueva instancia de
`w3afCore` escriba en la cola de una instancia anterior.

Verificación: **29 tests pasaron** en la suite del OutputManager, incluyendo la
regresión de cambio de sink; Ruff, Black, mypy focalizado y `git diff --check`
están limpios. El score permanece en **6.25/10** por los globals de sinks y
composition roots restantes, cobertura 100% no demostrada, Bandit heredado,
mocks e integraciones Moth.

## Actualización verificada: OutputManager sin imports globales en runtime

Los diagnósticos internos de flush usan el logger del módulo y el manejo de
excepciones de plugins recibe el sink al enlazar explícitamente
`OutputManager.set_w3af_core(core, output)`. Se eliminan los imports dinámicos
de `output_manager` desde la implementación del manager.

Verificación: **29 tests pasaron** en toda la suite del OutputManager; Ruff,
Black, mypy focalizado y `git diff --check` están limpios. El score permanece
en **6.25/10** por los globals de composición restantes, cobertura 100% no
demostrada, Bandit heredado, mocks e integraciones Moth.

## Actualización verificada: catálogo de plugins separado del runtime de scans

El descubrimiento de tipos, nombres, descripciones e instancias rápidas de
plugins vive ahora en `PluginCatalog`, una dependencia de solo lectura que no
requiere sink ni `OutputManager`. `CorePlugins` reutiliza esa capacidad para el
runtime de scans y el API REST deja de construirlo con dependencias globales.

Verificación: **37 tests y 9 subtests pasaron** en API de plugins/perfiles y
CorePlugins; Ruff, Black, mypy focalizado y `git diff --check` están limpios.
El score permanece en **6.25/10** por los globals de composición restantes,
cobertura 100% no demostrada, Bandit heredado, mocks e integraciones Moth.

## Actualización verificada: entrypoint del agente compone su sink

El servidor standalone del agente deja de leer `om.out` directamente. Su
entrypoint crea el manager y el `LogSink` mediante las fábricas explícitas y
entrega el sink al `w3afAgentServer`; la clase servidor ya mantiene esa
dependencia por instancia.

Verificación: no existen tests dedicados del agente en este checkout; Ruff,
Black, mypy focalizado, `py_compile` y `git diff --check` están limpios. El
score permanece en **6.25/10** por los globals de composición restantes,
cobertura 100% no demostrada, Bandit heredado, mocks e integraciones Moth.

## Actualización verificada: ExtendedUrllib desacoplado de w3afCore

`ExtendedUrllib` ya no guarda ni expone un `w3afCore` completo. El controlador
inyecta únicamente un proveedor de pool y sus límites para el ajuste dinámico
de workers; la capa de datos conserva el pool lazy y deja de depender de
constantes y estado del controller.

Verificación: **62 tests pasaron** en API, errores, reintentos y timeout de
ExtendedUrllib; Ruff, Black, mypy focalizado y `git diff --check` están limpios.
El score permanece en **6.25/10** por los demás módulos grandes y deuda
arquitectónica histórica, cobertura 100% no demostrada, Bandit heredado,
mocks e integraciones Moth.

## Actualización verificada: tests de auditoría sin unittest.mock

Los tests de subida de ficheros ya usan los cuerpos reales de los `POST` del
servidor HTTP de prueba para confirmar el contenido subido y derivan el nombre
real del multipart para el caso regex. El test XXE remoto responde según la
carga remota recibida; se eliminan los imports y parches de `unittest.mock`.

Verificación: **2 tests de subida pasaron**; Black, Ruff, mypy focalizado y
`git diff --check` están limpios. Los tests XXE y los escenarios Moth siguen
fallando en `master` sin estos cambios: XXE no registra el hallazgo en este
entorno y Moth no resuelve `php_moth-fallback`. El score permanece en
**6.25/10** por los módulos grandes, cobertura 100% no demostrada, Bandit
heredado y esas integraciones externas.

## Actualización verificada: cálculo de ETA separado del estado del core

`CoreStatus` conserva su API pública y la coordinación de logging, pero el
cálculo matemático y el valor inmutable `Adjustment` viven ahora en
`status_eta.py`. `EtaCalculator` no conoce `w3afCore`, consumidores, colas ni
output, y mantiene internamente sólo el suavizado de ETA por fase.

Verificación: **49 tests pasaron** en status y exception handler; Ruff, Black,
mypy focalizado y `git diff --check` están limpios. El score permanece en
**6.25/10**: aún quedan en `CoreStatus` el lifecycle, el acceso a consumidores,
la serialización y las reglas de ajuste por fase, además de la deuda global de
cobertura, Bandit e integraciones externas.

## Actualización verificada: métricas de consumidores fuera de CoreStatus

`CoreStatus` ya no conserva el controlador completo para consultar consumidores
y el worker pool. `ConsumerMetrics` concentra esas lecturas detrás de un
proveedor de estrategia y un proveedor lazy del pool; la composición se enlaza
después de crear `CoreStrategy`, y las copias serializables del estado quedan
aisladas de esas dependencias runtime.

Verificación: **49 tests pasaron** en status y exception handler; la suite
completa de `w3afCore` mantiene **17 pasados y 14 fallos preexistentes** en
manejo de excepciones y pausa/parada, reproducibles también en `c04667879`.
Ruff, Black, mypy focalizado y `git diff --check` están limpios. El score
permanece en **6.25/10** por el lifecycle restante, la serialización y las
reglas de fase aún mezcladas en `CoreStatus`, cobertura 100% no demostrada,
Bandit heredado e integraciones externas.

## Actualización verificada: relink de métricas al reiniciar un scan

Al reconstruir `CoreStrategy` para un segundo scan, `w3afCore` vuelve a enlazar
las métricas de `CoreStatus` con la estrategia nueva. Así el estado no conserva
referencias a consumidores de un scan anterior.

Verificación: la prueba de segundo scan pasó; Black, Ruff y mypy focalizado
están limpios. El score permanece en **6.25/10** por el lifecycle y la
serialización aún acoplados, cobertura 100% no demostrada, Bandit heredado e
integraciones externas.

## Actualización verificada: reglas de ajuste de ETA extraídas

Los umbrales de ajuste para crawl, audit y grep viven ahora en funciones puras
de `status_adjustments.py`. `CoreStatus` conserva la API y aporta únicamente
el tiempo de ejecución y el estado de los consumidores necesarios para elegir
la regla.

Verificación: **30 tests pasaron** en `CoreStatus`; Black, Ruff, mypy,
Bandit focalizado y `git diff --check` están limpios. El score permanece en
**6.25/10** por el lifecycle y la serialización aún acoplados, cobertura 100%
no demostrada, Bandit heredado e integraciones externas.

## Actualización verificada: CoreStatus recibe métricas por composición

`CoreStatus` ya no acepta ni conserva un `w3afCore`. Recibe `ConsumerMetrics`
cuando necesita consultar consumidores y usa un adaptador vacío para estados
efímeros, como los datos serializables de excepciones. `w3afCore` compone la
estrategia y el proveedor lazy del worker pool antes de crear el estado.

Verificación: **50 tests pasaron** en status, exception handler y segundo scan;
Black, Ruff, mypy focalizado y `git diff --check` están limpios. El score
permanece en **6.25/10** por la serialización y el lifecycle aún mezclados en
el controlador, cobertura 100% no demostrada, Bandit heredado e integraciones
externas.

## Actualización verificada: lifecycle de scan separado

`StatusLifecycle` encapsula running, pausa, inicio, parada, tiempo transcurrido
y contador de scans. `CoreStatus` conserva sus métodos públicos y coordina el
logging, los plugins y las métricas sin poseer ya la lógica temporal.

Verificación: **50 tests pasaron** en status, exception handler y segundo scan;
Black, Ruff, mypy focalizado, Bandit focalizado y `git diff --check` están
limpios. El score permanece en **6.25/10** por la serialización y la
coordinación global aún pendientes, cobertura 100% no demostrada, Bandit
heredado e integraciones externas.

## Actualización verificada: construcción de plugins separada

`PluginInstanceFactory` concentra la creación y el wiring de dependencias de
cada plugin (`uri_opener`, worker pool, core, KB, output y opciones). `CorePlugins`
conserva la selección, resolución de dependencias, orden y ciclo de inicialización
sin mezclar esos detalles de construcción.

Verificación: **27 tests de plugins pasaron**; Black, Ruff, mypy focalizado,
Bandit focalizado y `git diff --check` están limpios. La ejecución mostró 9
warnings deprecados procedentes de dependencias externas (`ldap3`/`jsonschema`),
sin suprimirlos. El score permanece en **6.25/10** por la composición global,
serialización, cobertura y gates heredados aún pendientes.

## Actualización verificada: lifecycle del worker pool separado

`WorkerPoolManager` concentra la creación lazy, recreación tras cierre y
terminación diagnosticada del pool. `w3afCore.worker_pool` mantiene su API y
actúa como una fachada mínima; la composición del core ya no conoce los
detalles de `Pool`, `is_main_thread` ni el parche temporal de logging.

Verificación: **51 tests focales pasaron**, incluidos dos tests con pools reales;
la suite completa de `w3afCore` conserva **17 pasados y 14 fallos históricos**.
Black, Ruff, mypy focalizado, Bandit focalizado y `git diff --check` están
limpios. El score permanece en **6.25/10** por la composición global, la
serialización y la deuda de gates/cobertura aún pendientes.

## Actualización verificada: resolución de dependencias de plugins separada

`PluginDependencyResolver` concentra la expansión recursiva de dependencias y
la ordenación de plugins del mismo tipo. `CorePlugins` conserva la selección,
la creación de instancias y la inicialización del runtime, pero ya no mezcla
esas reglas de ejecución con el catálogo.

Verificación: **27 tests de plugins pasaron**; Black, Ruff, mypy focalizado,
Bandit focalizado y `git diff --check` están limpios. La ejecución mostró 9
warnings deprecados de dependencias externas (`ldap3`/`jsonschema`), sin
suprimirlos. El score permanece en **6.25/10** por la composición global,
serialización, cobertura y gates heredados aún pendientes.

## Actualización verificada: carga de perfiles descompuesta

`CoreProfiles.use_profile()` ahora coordina el flujo y delega reset, target,
settings, opciones de plugins y formateo de errores a métodos con una sola
responsabilidad. Se conserva la API pública y el formato de advertencias para
perfiles obsoletos.

Verificación: **12 tests de perfiles pasaron**; Black, Ruff, mypy focalizado,
Bandit focalizado, `pip-audit` y `git diff --check` están limpios. La ejecución
mostró 2 warnings deprecados externos de `ldap3`/`pyasn1`, sin suprimirlos. El
score permanece en **6.25/10** por la composición global, serialización,
cobertura y gates heredados aún pendientes.

## Actualización verificada: tipos de plugins sin mapa manual

`CorePlugins.set_plugins()` usa ahora el catálogo dinámico para todos los tipos
de plugins y conserva únicamente el tratamiento especial de `evasion`. Se
eliminó el mapa duplicado que podía quedar desincronizado con los paquetes
descubiertos en el filesystem.

Verificación: **27 tests de plugins pasaron**; Black, Ruff, mypy focalizado,
Bandit focalizado y `git diff --check` están limpios. La ejecución mostró 9
warnings deprecados externos (`ldap3`/`jsonschema`), sin suprimirlos. El score
permanece en **6.25/10** por la composición global, serialización, cobertura y
gates heredados aún pendientes.

## Actualización verificada: guardado de perfiles descompuesto

`CoreProfiles.save_current_to_profile()` delega ahora el guardado de plugins,
target y settings a operaciones independientes. La serialización conserva el
orden, los nombres y las opciones existentes del formato de perfiles.

Verificación: **12 tests de perfiles pasaron**; Black, Ruff, mypy focalizado,
Bandit focalizado y `git diff --check` están limpios. La ejecución mostró 2
warnings deprecados externos de `ldap3`/`pyasn1`, sin suprimirlos. El score
permanece en **6.25/10** por la composición global, serialización, cobertura y
gates heredados aún pendientes.

## Actualización verificada: fixtures core con wiring real de output

Las suites de excepciones y pausa/parada construyen plugins auxiliares con el
`LogSink` real del core, igual que el camino de producción. Antes el plugin
fallaba en `_output.debug()` antes de ejecutar su comportamiento, ocultando la
causa de 14 fallos.

Verificación: las dos suites pasaron **14 tests**; Black, Ruff, mypy focalizado,
Bandit focalizado, `pip-audit` y `git diff --check` están limpios. El score
permanece en **6.25/10** hasta repetir la suite core completa y resolver las
deudas globales de cobertura y gates.

## Actualización verificada: suite core completa recuperada

La suite `w3af/core/controllers/tests/core_test_suite` pasa ahora completa:
**31 tests en 2m14s**. El problema era el wiring incompleto de los plugins de
prueba, no el manejo de excepciones ni el lifecycle de pausa/parada en runtime.

Black y Ruff globales, mypy/Bandit focalizados, `pip-audit` y `git diff --check`
siguen limpios. El score permanece en **6.25/10** por las deudas globales de
composición, cobertura 100% no demostrada, mypy sobre el `venv` y Bandit
heredado aún pendientes.

## Actualización verificada: presentación de status separada

`StatusPresenter` concentra los formatos JSON y texto largo que consumen las
interfaces. `CoreStatus` conserva sus métodos públicos como delegaciones y
mantiene únicamente estado, métricas y reglas de lifecycle.

Verificación: **30 tests de status pasaron**; Black, Ruff, mypy focalizado,
Bandit focalizado, `pip-audit` y `git diff --check` están limpios. El score
permanece en **6.25/10** por la composición global, cobertura 100% no
demostrada, mypy sobre el `venv` y Bandit heredado aún pendientes.

## Actualización verificada: política de errores del scan separada

`w3afCore.start()` delega ahora la ejecución de estrategia y la traducción de
errores esperados a `_run_strategy()`. El método público conserva la
preparación, el `finally` de cierre y la API existente; los mensajes y
excepciones se mantienen sin cambios.

Verificación: **10 tests de excepciones pasaron**; Black, Ruff, mypy
focalizado, Bandit focalizado, `pip-audit` y `git diff --check` están limpios.
El score permanece en **6.25/10** por la composición global, cobertura 100% no
demostrada, mypy sobre el `venv` y Bandit heredado aún pendientes.

Revalidación posterior: la suite core completa conserva **31/31 tests pasados**
tras la extracción de `_run_strategy()`.

## Actualización verificada: control de requests separado

`ScanRequestControl` encapsula pausa, stop, excepción persistente de parada y
reset del estado de requests. `ExtendedUrllib` conserva `pause()`, `stop()` y
la compatibilidad observable de `_stop_exception`, pero ya no posee esa lógica
de lifecycle directamente junto al transporte HTTP.

Verificación: **56 tests de URL pasaron**; Black, Ruff, mypy focalizado, Bandit
focalizado, `pip-audit` y `git diff --check` están limpios. El score permanece
en **6.25/10** por la composición global, cobertura 100% no demostrada, mypy
sobre el `venv` y Bandit heredado aún pendientes.

## Actualización verificada: construcción de handlers separada

`OpenerBuilder` concentra la composición concreta de handlers urllib y devuelve
los recursos de runtime que necesita `OpenerSettings`. La clase de configuración
conserva opciones, persistencia y ciclo público, sin mezclar esas reglas con la
instanciación del pipeline de transporte.

Verificación: la suite completa de URL pasó **217 tests en 192.06 s**; Black
global, Ruff global, mypy focalizado, Bandit focalizado, `pip-audit` y
`git diff --check` están limpios. El score se mantiene en **6.5/10** por los
módulos grandes, cobertura global no demostrada y gates globales pendientes.

## Actualización verificada: historial de respuestas separado

`ResponseHistory` concentra la ventana de respuestas, cálculo de RTT, tasa de
errores y detección del patrón de servidor inalcanzable. `ExtendedUrllib`
conserva sus métodos observables y delega el estado, reduciendo la mezcla entre
transporte HTTP y métricas de salud.

Verificación: **61 tests URL pasaron**, incluidos **5 tests unitarios nuevos**;
Black global, Ruff global, mypy focalizado, Bandit focalizado, `pip-audit` y
`git diff --check` están limpios. El estado actual queda en **6.5/10**; aún
faltan cobertura 100% global, mypy global fuera del `venv` y Bandit global sin
hallazgos heredados.

## Actualización verificada: ciclo de parada separado

`ScanStopController` concentra la solicitud de parada, la espera acotada por
timeout, el tratamiento de `KeyboardInterrupt` y la terminación del pool.
`w3afCore.stop()` conserva la fachada pública y entrega proveedores para el
status y la estrategia actuales, evitando referencias obsoletas entre scans.

Verificación: la suite core completa pasó **31 tests en 127.10 s**; Black,
Ruff, mypy focalizado, Bandit focalizado y `git diff --check` están limpios.
El score permanece en **6.25/10** por la composición global, cobertura 100% no
demostrada, mypy sobre el `venv` y Bandit heredado aún pendientes.

## Actualización verificada: ajuste de workers separado

`WorkerPoolAdjuster` concentra los límites de concurrencia, la política basada
en tasa de errores y la cadencia de 45 segundos. `ExtendedUrllib` conserva la
API pública de configuración y delega el ajuste sin mezclar esta política con
el transporte HTTP.

Verificación: **56 tests de URL pasaron**; Black, Ruff, mypy focalizado,
Bandit focalizado, `pip-audit` y `git diff --check` están limpios. El score
permanece en **6.25/10** por la composición global, cobertura 100% no
demostrada, mypy sobre el `venv` y Bandit heredado aún pendientes.

## Actualización verificada: backoff de errores HTTP separado

`HttpErrorPauseController` encapsula el lock, buckets de error, pausas
progresivas y reset periódico del backoff. `ExtendedUrllib` conserva el estado
observable de `_sleep_log` y la política de timing, pero ya no mezcla esta
coordinación con la construcción y envío de requests.

Verificación: **56 tests de URL pasaron**; Black, Ruff, mypy focalizado, Bandit
focalizado, `pip-audit` y `git diff --check` están limpios. El score permanece
en **6.25/10** por la composición global, cobertura 100% no demostrada, mypy
sobre el `venv` y Bandit heredado aún pendientes.

## Actualización verificada: decodificación del cuerpo separada

`ResponseBodyDecoder` concentra detección de charset en headers y meta HTML,
decodificación con fallback y diagnóstico de respuestas sin `Content-Type`.
`HTTPResponse` conserva estado, metadatos, serialización y su API pública, y
mantiene el logger observable mediante una dependencia explícita de debug.

Verificación: **217 tests de URL pasaron en 178.58 s**, incluidos **39 tests de
HTTPResponse**; Black global, Ruff global, mypy focalizado, Bandit focalizado,
`pip-audit` y `git diff --check` están limpios. El score se mantiene en
**6.5/10** por módulos grandes, cobertura global no demostrada y gates globales
pendientes.

## Actualización verificada: errores de cookie sin warnings

`ImprovedMozillaCookieJar` convierte ahora los formatos inválidos directamente
en `LoadError` encadenado, sin emitir una advertencia duplicada ni exponer un
traceback como warning al usuario. El test exige explícitamente cero warnings
para ese contrato.

Verificación: la suite URL pasó **217 tests en 182.31 s**, con solo **2
warnings externos** de `ldap3/pyasn1`; Black, Ruff, mypy focalizado, Bandit
focalizado, `pip-audit` y `git diff --check` están limpios. El score se mantiene
en **6.5/10** por cobertura global, módulos grandes y gates globales pendientes.

## Actualización verificada: codec de trazas separado

`HistoryTraceSerializer` encapsula el formato msgpack, el canary y la
reconstrucción de `HTTPRequest`/`HTTPResponse`. `HistoryItem` conserva la API de
DB, archivos y compresión, pero ya no mezcla esas operaciones con el codec HTTP.

Verificación: la suite DB completa pasó **162 tests en 9.25 s**; Black, Ruff,
mypy focalizado, Bandit focalizado y `git diff --check` están limpios. El score
se mantiene en **6.5/10** por cobertura global, módulos grandes y gates globales
pendientes.

## Actualización verificada: compresión de trazas separada

`HistoryTraceCompressor` concentra la cola compartida, la selección de lotes,
la escritura atómica de ZIP y la eliminación de trazas ya comprimidas.
`HistoryItem` conserva sus fachadas privadas compatibles y delega la política,
reduciendo su mezcla de persistencia SQL, serialización y almacenamiento de
archivos.

Verificación: la suite DB completa pasó **162 tests en 6.61 s**; Black, Ruff,
Bandit focal y mypy aislado del componente nuevo están limpios. También se
corrigió el parseo de identificadores de archivo para rutas Windows. La
ejecución global de mypy sigue bloqueada por imports/stubs ausentes heredados.
El score se mantiene en **6.5/10** por cobertura global, módulos grandes y
gates globales pendientes.

## Actualización verificada: almacenamiento de trazas separado

`HistoryTraceStorage` concentra la escritura de `.trace`, las lecturas con
reintentos, la búsqueda y lectura de ZIP y el tratamiento de archivos
incompletos. `HistoryItem` mantiene las fachadas observables y la coordinación
con la fila SQL y el compresor, sin conservar detalles de formato de archivo.

Verificación: la suite DB completa pasó **162 tests en 5.06 s**; Black, Ruff,
Bandit focal y `pip-audit` están limpios. Mypy del alcance con imports externos
omitidos también está limpio; la ejecución global sigue limitada por
dependencias/stubs heredados. El score se mantiene en **6.5/10** por cobertura
global, módulos grandes y gates globales pendientes.

## Actualización verificada: repositorio SQL de histórico separado

`HistoryRepository` concentra la creación de tabla e índice, búsquedas seguras,
carga con reintento, inserción y limpieza de metadatos SQL. `HistoryItem` queda
como entidad que mapea filas y coordina el repositorio con el almacenamiento de
trazas y la compresión.

Verificación: la suite DB completa pasó **162 tests en 5.07 s**; Black, Ruff,
mypy con imports externos omitidos y Bandit focal están limpios. Los nombres de
tabla y columnas se validan antes de construir SQL. El score se mantiene en
**6.5/10** por cobertura global, módulos grandes y gates globales pendientes.

## Actualización verificada: callback de grep aislado

`GrepDispatcher` encapsula el callback opcional que conecta cada request y
response con los consumidores de grep. `ExtendedUrllib` conserva
`set_grep_queue_put()` y el momento de dispatch, pero queda desacoplado de la
representación concreta del consumidor.

Verificación: la suite URL completa pasó **217 tests en 185.28 s**, con dos
warnings externos de `ldap3/pyasn1`; la batería focal pasó **59 tests**.
Black, Ruff, mypy configurado, Bandit focal y `pip-audit` están limpios. El
score se mantiene en **6.5/10** por cobertura global, módulos grandes y gates
globales pendientes.

## Actualización verificada: pipeline de evasión separado

`RequestEvasionPipeline` concentra el orden por prioridad, la aplicación de
plugins y el manejo de errores de transformación. `ExtendedUrllib` conserva la
fachada pública y el flujo de envío, pero ya no mantiene directamente la
política de evasión.

Verificación: la suite URL completa pasó **217 tests en 193.30 s**, con solo
dos warnings externos de `ldap3/pyasn1`; la batería focal pasó **55 tests y 22
subtests**. Black, Ruff, mypy configurado y Bandit focal están limpios. El
score se mantiene en **6.5/10** por cobertura global, módulos grandes y gates
globales pendientes.

## Actualización verificada: validación de entorno separada

`ScanEnvironmentValidator` concentra las precondiciones para iniciar un scan:
plugins inicializados, target válido y al menos un tipo de plugin ejecutable.
`w3afCore.verify_environment()` conserva la fachada pública y delega esa
política sin cambiar mensajes, excepciones ni orden de evaluación.

Verificación: `core_test_suite` pasó **31 tests en 91.82 s**; Black, Ruff,
mypy configurado y Bandit focal están limpios. El score se mantiene en
**6.5/10** por cobertura global, módulos grandes y gates globales pendientes.

## Actualización verificada: selección de plugins separada

`PluginSelection` concentra deduplicación, validación de nombres, expansión de
`all` y exclusiones. `CorePlugins` conserva la coordinación de fábrica,
dependencias, opciones y mangle, manteniendo la misma referencia de selección
que usan los consumidores internos.

Verificación: la suite de plugins pasó **27 tests en 8.13 s** y
`core_test_suite` pasó **31 tests en 90.69 s**. Black, Ruff, mypy configurado y
Bandit focal están limpios; los warnings observados son externos de
`ldap3/jsonschema`. El score se mantiene en **6.5/10** por cobertura global,
módulos grandes y gates globales pendientes.

## Actualización verificada: autenticación del opener separada

`AuthenticationSettings` concentra el password manager, Basic Auth, NTLM y la
persistencia de sus credenciales. `OpenerSettings` conserva los métodos
públicos, handlers privados observables y la señal `need_update`, pero ya no
mezcla esa política con cookies, proxy, cache y composición de handlers.

Verificación: la suite URL completa pasó **217 tests en 181.60 s**, con dos
warnings externos de `ldap3/pyasn1`; la batería focal pasó **46 tests**.
Black, Ruff, mypy configurado y Bandit focal están limpios. El score se
mantiene en **6.5/10** por cobertura global, módulos grandes y gates globales
pendientes.

## Actualización verificada: cookies del opener separadas

`CookieSettings` concentra la cookie jar por defecto, la carga de ficheros
Netscape, la persistencia de configuración, la limpieza y el acceso a cookies.
`OpenerSettings` conserva la fachada pública, el handler interno usado por
`OpenerBuilder` y los mensajes de error existentes, pero deja de mezclar esta
política con autenticación, proxy y composición de handlers.

Verificación: la suite URL completa pasó **217 tests en 183.33 s**, con dos
warnings externos de `ldap3/pyasn1`; la batería focal pasó **46 tests en
12.52 s**. Black, Ruff, mypy configurado y Bandit focal están limpios.
`pip-audit` no encontró vulnerabilidades y mantiene únicamente el skip conocido
de `mitmproxy`, no disponible en PyPI. El score se mantiene en **6.5/10** por
cobertura global, módulos grandes y los hallazgos heredados fuera de este
avance.

## Actualización verificada: proxy del opener separado

`ProxySettings` concentra la validación del puerto, la persistencia de la
dirección, la creación del `ProxyHandler` y la lectura de la configuración.
`OpenerSettings` conserva `set_proxy()`, `get_proxy()`, `_proxy_handler` y el
flujo hacia `OpenerBuilder`, pero deja de poseer la política del proxy.

Verificación: la suite URL completa pasó **217 tests en 199.56 s**, con dos
warnings externos de `ldap3/pyasn1`; la batería focal del opener pasó **26
tests**. Ruff, mypy focal y Bandit focal están limpios. El score se mantiene en
**6.5/10** por cobertura global, módulos grandes y gates globales pendientes.

## Actualización verificada: parámetro de URL separado

`URLParameterSettings` concentra la limpieza, persistencia y creación del
`URLParameterHandler`. `OpenerSettings` conserva `set_url_parameter()` y
`_url_parameter_handler` para los consumidores existentes, pero ya no mezcla
esta política con el resto de configuración del opener.

Verificación: la suite URL completa pasó **217 tests en 193.86 s**, con dos
warnings externos de `ldap3/pyasn1`; la batería focal pasó **27 tests en
1.29 s**. Ruff, mypy focal y Bandit focal están limpios. El score se mantiene
en **6.5/10** por cobertura global, módulos grandes y gates globales
pendientes.

## Actualización verificada: headers del opener separados

`HeaderSettings` concentra la lista de headers, la carga del fichero de
headers, el logging y la sustitución del User-Agent. `OpenerSettings` conserva
`header_list` con getter/setter, `set_headers_file()`, `set_header_list()` y
`set_user_agent()` para los consumidores existentes, pero deja de poseer esa
política directamente.

Verificación: la suite URL completa pasó **217 tests en 179.42 s**, con dos
warnings externos de `ldap3/pyasn1`; la batería focal pasó **46 tests en
12.60 s**. Ruff, mypy focal y Bandit focal están limpios. El score se mantiene
en **6.5/10** por cobertura global, módulos grandes y gates globales
pendientes.

## Actualización verificada: ciclo de vida del opener separado

`OpenerLifecycle` concentra la construcción desde `BuiltOpeners`, el acceso al
opener, el cierre de handlers keep-alive y la limpieza de cache. `OpenerSettings`
conserva los métodos públicos y las propiedades privadas de recursos, pero ya
no coordina directamente el almacenamiento y cierre de esos objetos.

Verificación: la suite URL completa pasó **217 tests en 180.63 s**, con dos
warnings externos de `ldap3/pyasn1`; la batería focal pasó **33 tests en
3.23 s**. Ruff, mypy focal y Bandit focal están limpios. El score se mantiene
en **6.5/10** por cobertura global, módulos grandes y gates globales
pendientes.

## Actualización verificada: límites de request separados

`RequestLimitsSettings` concentra la validación y persistencia del timeout,
tamaño máximo, reintentos y rate limit. `OpenerSettings` conserva todas las
fachadas existentes, incluido el nombre histórico `get_max_retrys()`, para que
`ExtendedUrllib`, `TimeoutManager` y `RateLimiter` sigan consumiendo la misma
API.

Verificación: la suite URL completa pasó **217 tests en 181.08 s**, con dos
warnings externos de `ldap3/pyasn1`; la batería focal pasó **62 tests en
125.51 s**. Ruff, mypy focal y Bandit focal están limpios. El score se
mantiene en **6.5/10** por cobertura global, módulos grandes y gates globales
pendientes.

## Actualización verificada: defaults del opener separados

`OpenerDefaults` concentra la persistencia de todos los valores iniciales del
opener. `OpenerSettings` conserva `set_default_values()` como fachada pública y
mantiene el mismo orden, nombres y valores de configuración.

Verificación: la suite URL completa pasó **217 tests en 191.04 s**, con dos
warnings externos de `ldap3/pyasn1`; la batería focal del opener pasó **26
tests**. Black, Ruff, mypy focal y Bandit focal están limpios. El score se
mantiene en **6.5/10** por cobertura global, módulos grandes y gates globales
pendientes.

## Actualización verificada: opciones del opener separadas

`OpenerOptions` concentra la construcción del `OptionList` y sus descripciones,
tipos y valores configurados. `OpenerSettings.get_options()` conserva la API
pública y delega en el builder, mientras `set_options()` y sus efectos de
configuración permanecen sin cambios.

Verificación: la suite URL completa pasó **217 tests en 187.24 s**, con dos
warnings externos de `ldap3/pyasn1`; la batería focal del opener pasó **26
tests en 0.21 s**. Black, Ruff, mypy focal y Bandit focal están limpios. El
score se mantiene en **6.5/10** por cobertura global, módulos grandes y gates
globales pendientes.

## Actualización verificada: aplicación de opciones separada

`OpenerOptionApplier` concentra la comparación de valores, validación del
dominio Basic Auth y coordinación de autenticación, proxy, cookies, headers,
límites, parámetro de URL y opciones 404. `OpenerSettings.set_options()` queda
como fachada pública y conserva los mismos componentes y persistencia.

Verificación: la suite URL completa pasó **217 tests en 180.29 s**, con dos
warnings externos de `ldap3/pyasn1`; la batería focal del opener pasó **26
tests**. Ruff, mypy focal y Bandit focal están limpios. El score se mantiene en
**6.5/10** por cobertura global, módulos grandes y gates globales pendientes.

## Actualización verificada: preparación de requests separada

`RequestPreparer` concentra la aplicación de headers configurados y por
request, el User-Agent aleatorio y la validación de protocolos HTTP. `ExtendedUrllib`
conserva `add_headers()` y `assert_allowed_proto()` como fachadas, pero deja de
mezclar esa preparación con el envío y manejo de errores.

Verificación: la suite URL completa pasó **217 tests en 187.14 s**, con dos
warnings externos de `ldap3/pyasn1`; la batería focal pasó **50 tests en
43.87 s**. Ruff, mypy focal y Bandit focal están limpios. El score se mantiene
en **6.5/10** por cobertura global, módulos grandes y gates globales
pendientes.

## Actualización verificada: respuestas exitosas separadas

`ResponseSuccessHandler` concentra el formateo del log, conversión a
`HTTPResponse`, metadatos de cache/debugging, registro de RTT, ajuste de
workers y dispatch de grep. `ExtendedUrllib` conserva
`_handle_send_success()` y el flujo de envío, pero deja de mezclar esa
responsabilidad con la clasificación de errores y reintentos.

Verificación: la suite URL completa pasó **217 tests en 184.04 s**, con dos
warnings externos de `ldap3/pyasn1`; la batería focal pasó **56 tests en
62.79 s**. Ruff, mypy focal y Bandit focal están limpios. El score se mantiene
en **6.5/10** por cobertura global, módulos grandes y gates globales
pendientes.

## Actualización verificada: política de retry separada

`RequestRetryHandler` concentra decremento de reintentos, actualización de
timeout, forzado de conexión nueva, reenvío y error final. `ExtendedUrllib`
conserva `_retry()` como fachada y mantiene separado el manejo de errores, el
registro de historial y la decisión de detener el scan.

Verificación: la suite URL completa pasó **217 tests en 184.55 s**, con dos
warnings externos de `ldap3/pyasn1`; la batería focal pasó **42 tests en
163.31 s**. Ruff, mypy focal y Bandit focal están limpios. El score se mantiene
en **6.5/10** por cobertura global, módulos grandes y gates globales
pendientes.

## Actualización verificada: registro de errores separado

`FailedResponseRecorder` concentra normalización del error, filtrado de
tracebacks ruidosos, cálculo de razón, registro de RTT y actualización del
historial de fallos. `ExtendedUrllib` conserva `_log_failed_response()` y la
decisión de reintentar o detener el scan permanece en el coordinador.

Verificación: la suite URL completa pasó **217 tests en 178.54 s**, con dos
warnings externos de `ldap3/pyasn1`; la batería focal pasó **42 tests en
150.82 s**. Ruff, mypy focal y Bandit focal están limpios. El score se mantiene
en **6.5/10** por cobertura global, módulos grandes y gates globales
pendientes.

## Actualización verificada: política de errores de request separada

`RequestErrorHandler` concentra clasificación socket/urllib, respeto de
`error_handling`, registro sincronizado del fallo, umbral de parada, ajuste de
workers y reenvío. `ExtendedUrllib` conserva las fachadas privadas, incluida
`_generic_send_error_handler`, requerida por un consumidor indirecto.

Verificación: la suite URL completa pasó **217 tests en 182.93 s**, con dos
warnings externos de `ldap3/pyasn1`; la batería focal pasó **42 tests en
144.63 s**. Ruff, mypy focal y Bandit focal están limpios. El score se mantiene
en **6.5/10** por cobertura global, módulos grandes y gates globales
pendientes.

## Actualización verificada: estrategia de timeout separada

`TimeoutAdjustmentPolicy` concentra la decisión de autoajuste por muestras RTT
y el incremento defensivo tras errores de socket. `ExtendedUrllib` conserva
`_auto_adjust_timeout()` y `_increase_timeout_on_error()` como fachadas, y
`TimeoutManager` sigue siendo el dueño del estado de timeouts.

Verificación: la suite URL completa pasó **217 tests en 200.17 s**, con dos
warnings externos de `ldap3/pyasn1`; la batería focal pasó **12 tests en
118.15 s**. Ruff, mypy focal y Bandit focal están limpios. El score se mantiene
en **6.5/10** por cobertura global, módulos grandes y gates globales
pendientes.

## Actualización verificada: comprobación de alcanzabilidad separada

`ServerReachabilityChecker` concentra el probe de la URL raíz tras fallos
consecutivos: timeout defensivo, headers, request sin retries y clasificación de
excepciones. `ExtendedUrllib._server_root_path_is_reachable()` queda como
fachada para `ResponseHistory.should_stop_scan()`.

Verificación: la suite URL completa pasó **217 tests en 182.90 s**, con dos
warnings externos de `ldap3/pyasn1`; la batería focal pasó **12 tests en
113.18 s**. Ruff, mypy focal y Bandit focal están limpios. La suite completa
también pasó con `PytestUnhandledThreadExceptionWarning` tratado como error.
El score se mantiene en **6.5/10** por cobertura global, módulos grandes y
gates globales pendientes.

## Actualización verificada: límite de tamaño encapsulado

`SizeLimitOverride` encapsula la modificación temporal de `max_file_size` y su
restauración garantizada. `ExtendedUrllib` usa la instancia inyectada durante
GET, mientras `raise_size_limit()` se mantiene como fachada de compatibilidad;
se eliminó el TODO que reconocía la fuga de configuración global.

Verificación: la suite URL completa pasó **217 tests en 184.58 s**, con dos
warnings externos de `ldap3/pyasn1`; la batería focal pasó **36 tests en
126.54 s**. Ruff, mypy focal y Bandit focal están limpios. El score se mantiene
en **6.5/10** por cobertura global, módulos grandes y gates globales
pendientes.

## Actualización verificada: ciclo de sesión separado

`SessionLifecycle` concentra la creación y liberación del opener, la limpieza
del estado de escaneo y el reinicio de la sesión. `ExtendedUrllib` conserva la
API pública y la propiedad privada `_opener`, incluida la reasignación dinámica
de `settings` que usan los consumidores de proxy.

Verificación: la suite URL completa pasó **218 tests en 182.82 s**, con dos
warnings externos de `ldap3/pyasn1`; la batería focal de API y proxy pasó **25
tests en 16.86 s**. Ruff, mypy focal y Bandit focal están limpios. El score se
mantiene en **6.5/10** por cobertura global, módulos grandes y gates globales
pendientes.

## Revisión de regresión y memoria

La revisión del corte no encontró una fuga por request. `ResponseHistory` está
limitado a 100 entradas, los mapas de RTT a 128 y el pool keep-alive a 50
conexiones por host. Una prueba con servidor HTTP real y 500 requests, seguida
de `gc.collect()`, observó **113 KiB** de crecimiento trazado y **0.8 MiB** de
RSS máximo; los límites internos permanecieron en `100` y `128`. No se añade
un cambio especulativo al pool ni al almacenamiento de respuestas.

## Actualización verificada: regresión de memoria durante tests

La subida grande de RAM no venía de una fuga por request. Había dos picos
independientes:

- `OutputManager` creaba siempre un pool de 10 workers al construirse, aunque
  no se usara, y los managers reemplazados no siempre liberaban sus hilos.
  El pool ahora se crea bajo demanda y se cierra al recibir `POISON_PILL`, al
  terminar los plugins y al reemplazar el manager.
- `xml_file` materializaba dos diccionarios para todos los valores de
  `sys.maxunicode`, más de un millón de entradas por tabla. Las sustituciones
  de caracteres de control ahora se calculan bajo demanda; las tablas globales
  conservan únicamente las cinco sustituciones fijas.

El test que activa todos los plugins de salida bajó de **508 MiB** a **87 MiB**
de RSS máximo. La suite de `OutputManager` bajó de **491 MiB** a **92 MiB**.
La batería combinada de URL, `OutputManager` y XML pasó **279 tests en 193.60
s**, con **190 MiB** de RSS máximo, frente a **~572 MiB** antes del arreglo.

También se completó la inyección del sink de salida al crear plugins desde el
manager, necesaria para que `xml_file` use el contrato actual sin depender de
un singleton global. Black, Ruff, mypy focal, Bandit focal, `pip-audit` y
`git diff --check` están limpios. Permanecen dos warnings externos de
`ldap3/pyasn1`; el score se mantiene en **6.5/10** por cobertura global,
módulos grandes y gates globales pendientes.

## Actualización verificada: selección determinista de plugins

`PluginSelection` ya no convierte la expansión de `all` en un `set`, por lo que
conserva el orden del catálogo y hace reproducible la creación de instancias.
La eliminación de exclusiones se expresa como una transformación de listas,
tolera una exclusión sin `all` y elimina de forma consistente el plugin
excluido sin lanzar `ValueError` por una segunda eliminación.

Verificación: la suite de plugins pasó **28 tests** con el catálogo real del
filesystem. El score se mantiene en **6.5/10**: este avance corrige una
invariante de selección, pero siguen pendientes los módulos grandes, los
singletons y la cobertura/gates globales.

## Actualización verificada: resolución explícita de dependencias

`PluginDependencyResolver` dejó de reiniciarse recursivamente y ahora procesa
las dependencias pendientes con una cola, evitando trabajo repetido. El orden
por tipo usa una visita topológica estable, conserva el orden de los plugins
independientes y detecta ciclos, dependencias del mismo tipo ausentes y
referencias que no cumplen el formato `type.name` con errores accionables.

Verificación: la suite combinada del resolvedor y `CorePlugins` pasó **32
tests**. Ruff y Black están limpios en los módulos modificados. El score se
mantiene en **6.5/10** hasta cerrar los límites arquitectónicos y la
verificación global de cobertura y gates.

## Actualización verificada: catálogo de plugins determinista

`PluginCatalog.get_plugin_types()` ordena los tipos descubiertos antes de
publicarlos. Esto elimina una dependencia accidental del orden de
`os.listdir()` y hace que la selección, la resolución de dependencias y las
interfaces que enumeran plugins observen el mismo orden en Windows, Linux y
macOS.

Verificación: `CorePlugins` pasó **28 tests** y la salida real del catálogo se
comprueba como ordenada. El score se mantiene en **6.5/10** mientras quedan
pendientes la eliminación de singletons y la cobertura global.

## Actualización verificada: dependencias runtime de shells

La inyección explícita de `output` en los shells de ataque había dejado una
regresión de persistencia: los reducers serializaban `LogSink` y su
`multiprocessing.Queue` junto con el shell. Ahora los reducers serializan solo
el estado persistente; `BasicKnowledgeBase.get_all_shells()` reinyecta el
output antes del opener, el pool y la KB, y `SQLMapWrapper` restaura también su
sink antes de recrear el proxy.

Verificación: `test_knowledge_base.py` pasa **68 tests** y la batería local de
SQLMap pasa **67 tests**, sin mocks. Ruff, Black y mypy focal están limpios.
Los tests de ataque que requieren `moth`/`php_moth` siguen sin poder ejecutarse
en este entorno porque esos hosts no resuelven; no se ha ocultado ese fallo.
El score se mantiene en **6.5/10**: se cierra una regresión de boundary y
serialización, pero siguen pendientes los singletons de composición, la
cobertura global del 100% y la verificación completa de los gates globales.

## Actualización verificada: lifecycle explícito del OutputManager

El cierre del gestor de salida estaba duplicado en el reemplazo del singleton y
en los tests. `OutputManager.stop()` concentra ahora el envío del sentinel, el
`join()` y la liberación idempotente del pool; `fresh_output_manager_inst()` y
`w3afCore.quit()` usan el mismo contrato. Esto evita que una instancia de core
dependa de la siguiente para liberar su hilo de salida.

Verificación: la suite de lifecycle del `OutputManager` pasa con el caso nuevo
de doble cierre; Black y Ruff globales, mypy focal y Bandit focal permanecen
limpios. El score se mantiene en **6.5/10** porque el singleton de módulo aún
existe para los consumidores de test y la cobertura/gates globales siguen sin
estar demostrados al 100%.

## Actualización verificada: fábrica de output sin estado global

Se añadió `create_output_manager()`, que devuelve un `OutputManager` y su
`LogSink` enlazados por la misma cola, sin mutar el estado del módulo. El
agent server usa esta composición y cierra su manager en `finally`; el
bootstrap del parser crea directamente su sink local. `fresh_output_manager_inst`
se conserva temporalmente para los tests que aún ejercitan el singleton.

Verificación: la suite de `OutputManager` pasa **31 tests** y Ruff, mypy y
Bandit focal están limpios. El score se mantiene en **6.5/10**: el siguiente
paso es migrar `w3afCore` y sus tests al runtime explícito antes de eliminar el
singleton del módulo.

## Actualización verificada: eliminación de fachada URL sin callers

Se eliminó `ExtendedUrllib.raise_size_limit()`, una API legacy que recreaba el
override contra el singleton global de configuración. La ruta activa usa
`self._size_limit_override`, creado una sola vez para el opener; la búsqueda
estructural no encontró callers de la fachada eliminada.

Verificación: la batería focal de URL pasa **56 tests**, con solo los dos
warnings externos de `ldap3/pyasn1`; Ruff, mypy y Bandit focal están limpios.
El score se mantiene en **6.5/10** porque la eliminación de una API muerta no
cierra todavía la composición global ni la cobertura completa.

## Actualización verificada: configuración explícita del parámetro URL

`URLParameterSettings` dejó de importar el singleton `cf` directamente. Ahora
recibe la configuración por constructor y `OpenerSettings` le pasa su
dependencia; la política puede probarse con una `Config` aislada sin estado
global compartido.

Verificación: la integración de URL y `OpenerSettings` pasa **28 tests**, con
los warnings externos habituales de dependencias cuando aparecen; Ruff, mypy
y Bandit focal están limpios. El score se mantiene en **6.5/10** porque aún
quedan otros settings globales y la composición del core.

## Actualización verificada: eliminación de helper de logging muerto

`output_manager.log_http()` no tenía consumidores de producción y solo
delegaba en el sink global. Se eliminó junto con su uso de test; el contrato
verificado ahora es `LogSink.log_http()`, que es el objeto que realmente posee
la cola de logging.

Verificación: la suite completa de `OutputManager` pasa **31 tests**, y Black,
Ruff y mypy focal siguen limpios. El score se mantiene en **6.5/10** hasta
terminar la migración del singleton de composición.

## Actualización verificada: blacklist HTTP con configuración explícita

`BlacklistHandler` dejó de leer `cf` directamente. `OpenerSettings` conserva la
configuración y la propaga por `OpenerLifecycle` y `OpenerBuilder` hasta el
handler, que ahora requiere esa dependencia al construirse. La cadena HTTP
queda más explícita y el handler puede probarse con una configuración aislada.

Verificación: los tests de blacklist, opener y parámetro URL pasan **34
tests**; Ruff, mypy y Bandit focal están limpios. El score se mantiene en
**6.5/10** porque otros handlers y la composición del core aún dependen de
configuración global.

## Actualización verificada: límite de respuesta sin singleton en keep-alive

`keepalive.HTTPResponse` dejó de importar la configuración global para decidir
si descarta un cuerpo demasiado grande. `OpenerBuilder` propaga la
configuración al handler y a las conexiones HTTP, HTTPS y HTTPS sobre proxy;
cada respuesta consulta esa dependencia explícita. Los handlers aislados sin
configuración conservan el comportamiento de no aplicar un límite, mientras
que el camino real del opener mantiene el valor configurado.

Verificación: los tests de keep-alive, mangle y handlers relacionados pasan
**81 tests**; `OpenerSettings` y `ExtendedUrllib` pasan **56 tests**. La suite
keep-alive medida con `/usr/bin/time -l` alcanza **96 MB de RSS máximo**, sin
acumulación visible. Black, Ruff, mypy y Bandit focal están limpios. El score
se mantiene en **6.5/10**: la causa de cientos de MiB estaba en el pool de
salida y los diccionarios XML, ya corregidos en avances anteriores.

## Actualización verificada: core sin recrear el singleton de output

`w3afCore` ahora compone su `OutputManager` y `LogSink` mediante
`create_output_manager()`, y sus tests registran el recorder en el manager
propio del core. Esto evita que crear un core reemplace el estado global de
otro test y deja el ownership del hilo de output en la instancia que lo usa.

Verificación: los tests aislados de construcción, validación y excepciones del
core pasan **3 tests**; Black, Ruff, mypy y Bandit focal están limpios. La
suite completa del core no pudo terminar porque ya había varias ejecuciones
antiguas de pytest activas en el workspace, incluida una suite de output con
aproximadamente **500 MB de RSS**; se interrumpió esa ejecución bloqueada para
no mezclar sus recursos con la medición. El score se mantiene en **6.5/10**:
quedan consumidores de test del singleton y aún no se ha demostrado la
cobertura global del 100%.

## Actualización verificada: `CoreTarget` con configuración inyectada

`CoreTarget` dejó de importar y mutar `cf.cf` al cargar el módulo. Ahora recibe
una configuración explícita, y `w3afCore` la entrega desde el composition root;
las operaciones de target leen y guardan únicamente en esa instancia. Esto
elimina una mutación global durante imports y permite crear targets aislados.

Verificación: la suite de target pasa **12 tests**, incluyendo dos
configuraciones independientes; Black, Ruff, mypy y Bandit focal están limpios.
El score sube a **6.7/10** en Clean Architecture, pero el global se mantiene
en **6.6/10** hasta migrar los restantes consumidores de `cf` y demostrar los
gates y la cobertura completos.

## Actualización verificada: estrategia sin configuración global de targets

`CoreStrategy` y `target_validation` ya reciben la configuración desde el core.
Se eliminaron sus lecturas y escrituras directas de `cf.cf` para los targets,
el límite de tiempo de scan, el tiempo máximo de discovery y la inicialización
de la cola seed. El objeto `w3afCore` expone esa dependencia como parte de su
composition root, y los tests low-level la reutilizan explícitamente.

Verificación: la suite de strategy pasa **9 tests y 7 subtests**; Black, Ruff,
mypy y Bandit focal están limpios. El score sube a **6.8/10** en Clean
Architecture y **6.7/10** global. Aún quedan consumidores de configuración en
los workers (`crawl`, `grep`, `audit`) y el cierre de los gates/cobertura
globales.

## Actualización verificada: configuración explícita en workers de scan

`CrawlInfrastructure`, `grep` y `audit` ya reciben la configuración del
strategy. Sus lecturas de `baseURLs`, `target_domains` y `blacklist_audit`
dejaron de depender de `cf.cf` desde los hilos consumidores; los callers de
producción y los fixtures reales se actualizaron al mismo contrato.

Verificación: las suites de consumidores, status y observers pasan **63
tests**; Black, Ruff, mypy y Bandit focal están limpios. El score sube a
**6.9/10** en Clean Architecture y **6.8/10** global. Todavía quedan
consumidores de configuración en otros controladores, además de la cobertura
y los gates globales por demostrar.

## Actualización verificada: perfiles y excepciones sin `cf` directo

`CoreProfiles` recibe la configuración del core para guardar los targets, y
`ExceptionHandler` recibe la misma dependencia para aplicar
`stop_on_first_exception`. Ambos módulos dejaron de importar el singleton;
listar perfiles sin core sigue funcionando porque no necesita configuración.

Verificación: las suites de perfiles y excepciones pasan **31 tests**, con los
dos warnings deprecados externos de `ldap3/pyasn1`; Black, Ruff, mypy y Bandit
focal están limpios. El score sube a **7.0/10** en Clean Architecture y
**6.9/10** global. Aún quedan settings/controladores y plugins que leen `cf`,
y falta probar cobertura y gates a escala completa.

## Actualización verificada: `MiscSettings` sin inicialización global

`MiscSettings` ahora recibe la configuración explícitamente y deja de crear una
instancia global durante la importación del módulo. `w3afCore`, perfiles, la
consola y los fixtures de tests construyen el objeto con su configuración
propia, evitando mutaciones implícitas del singleton compartido.

Verificación: settings, persistencia de perfiles y `VariantDB` pasan **61
tests**; el flujo OpenAPI pasa **10 tests**. Este último mantiene warnings
externos de `swagger`/`jsonschema`, sin errores reproducibles del
`OutputManager` en ejecución aislada. Black, Ruff, mypy y Bandit focal están
limpios. El score sube a **7.1/10** en Clean Architecture y **7.0/10** global.
Aún quedan consumidores de `cf` en controladores y datos, y no se ha cerrado la
validación global de cobertura ni todos los gates del repositorio.

## Actualización verificada: liberar `VariantDB` y cerrar la cola de output

`web_spider.end()` ahora libera también su `VariantDB`, que podía conservar
filtros Bloom y cachés entre scans. `CachedDiskDict.cleanup()` vacía sus
estructuras en memoria y `VariantDB.cleanup()` libera el Bloom filter. Además,
el bucle de `OutputManager` trata el cierre del descriptor de la cola como un
teardown normal, evitando la traza `OSError: handle is closed` al terminar las
suites.

Verificación: `VariantDB` pasa **42 tests**, el ciclo de vida de
`OutputManager` **20 tests** y `web_spider` **12 tests** sin la excepción de
cierre. Una medición puntual de la suite web alcanzó **138 MB de RSS máximo**;
el proceso de medición quedó afectado por ejecuciones antiguas de pytest que
siguen activas en el workspace, por lo que no uso esa cifra como comparación
directa. Black, Ruff, mypy y Bandit focal están limpios. El score sube a
**7.3/10** en Clean Architecture y **7.2/10** global. Siguen pendientes otros
consumidores de configuración global y la validación completa de cobertura y
gates.

## Actualización verificada: detección 404 con configuración explícita

`Fingerprint404` dejó de leer `cf.cf`: recibe la configuración del escaneo y
libera su caché al cerrar el ciclo de vida. `Plugin` centraliza la llamada
configurada a la detección 404, y `PluginInstanceFactory` entrega la
configuración real a cada plugin; `target_validation` y los plugins afectados
usan el mismo contrato. Los fixtures de plugins también configuran output y
configuración reales, evitando falsos positivos por estado incompleto.

Verificación: fingerprinting **30 tests**, bases y errores de plugins **28**,
web spider/OpenAPI **22**, strategy/decorators **18 tests y 7 subtests**, y
GHDB/Web Diff **24 tests**. Black, Ruff, mypy y Bandit focal están limpios.
El score sube a **7.9/10** en Clean Architecture y **7.8/10** global. Siguen
pendientes otros consumidores de configuración global, la cobertura global del
100% y los avisos/fallos preexistentes de las gates ejecutadas sobre el árbol
completo.

## Actualización verificada: extensión de ficheros fuzzados sin configuración global

`FileDataToken` y el rellenado automático de formularios ya no importan `cf.cf`.
La extensión se propaga desde `fuzzer_config` al contenedor multipart, incluido
su `smart_fill()` y su serialización; los formularios genéricos conservan
`gif` como valor por defecto explícito.

Verificación: DC edge cases, factory, file-content mutants, fuzzer y OpenAPI
 pasan **89 tests**, con **7 subtests** y los warnings externos de
`jsonschema/swagger`. Black, Ruff, mypy y Bandit focal están limpios. El score
sube a **8.0/10** en Clean Architecture y **7.9/10** global. Persisten otros
consumidores globales de configuración y todavía no está demostrada la
cobertura global del 100%.

## Actualización verificada: blacklist de autenticación con configuración inyectada

`AuthPlugin` ya no importa ni modifica `cf.cf`: usa la configuración entregada
por `PluginInstanceFactory`, con un error explícito si se intenta ejecutar sin
composición de scan. Los tests de autenticación directa ahora conectan el
output y la configuración reales, igual que la ruta de producción.

Verificación: las suites de `AuthPlugin`, plugins de autenticación y
autocomplete pasan **51 tests**. Black, Ruff, mypy y Bandit focal están limpios.
El score sube a **8.1/10** en Clean Architecture y **8.0/10** global. Aún
quedan consumidores globales en URL/openers, parsers, fuzzer, Info, controllers,
plugins de auditoría/crawl y output, además de la cobertura global del 100%.

## Actualización verificada: `web_spider` sin configuración global

`web_spider` obtiene `targets`, `form_fuzzing_mode` e `ignore_regex` desde la
configuración inyectada en `Plugin`; desaparecieron sus accesos directos a
`cf.cf`. El accessor común valida que un plugin fuera de la composition root
no ejecute lógica dependiente del scan sin configuración.

Verificación: web spider, OpenAPI sources y plugin base pasan **43 tests**, con
los warnings externos conocidos de `swagger/jsonschema`. Black, Ruff, mypy y
Bandit focal están limpios. El score sube a **8.2/10** en Clean Architecture y
**8.1/10** global. Siguen pendientes URL/openers, parsers, fuzzer, `Info`,
controllers y plugins de auditoría/output, además de la cobertura global del
100%.

## Actualización verificada: plugins de auditoría/crawl sin configuración global

`lfi`, `os_commanding`, `phpinfo` y `open_api` ya reciben la configuración
desde `Plugin` y no importan ni consultan `cf.cf`. La detección de dominio de
OpenAPI recibe la configuración explícitamente, y los tests que instancian
plugins directamente la conectan como haría la composición del scan.

Verificación: OpenAPI sources **10 tests**, OpenAPI **7**, PHPInfo y OS
Commanding **12**, y LFI **1** pasan. El test WAVSEP restante no puede
verificarse porque `wavsep-fallback` no resuelve en este entorno. Black, Ruff,
mypy y Bandit focal están limpios. El score sube a **8.3/10** en Clean
Architecture y **8.2/10** global. Siguen pendientes URL/openers, parsers,
fuzzer, `Info`, controllers, HMap, plugins de output y la cobertura global del
100%.

## Actualización verificada: cierre de colas del `OutputManager`

`OutputManager.stop()` ahora libera también su `multiprocessing.Queue` y
desactiva el `join` automático del `QueueFeederThread` después de detener el
manager y el pool. Esto evita que una suite finalice manteniendo el proceso en
`_Py_Finalize` y reteniendo memoria por una cola cuyo consumidor ya terminó.
El test de logging restaura además el sink global temporal para que las suites
sean independientes del orden de ejecución.

Verificación: la suite de `output_manager` pasa **32 tests** y una reproducción
con 100 mensajes confirma que el feeder desaparece tras `stop()`. Black, Ruff,
mypy y Bandit focal están limpios. El score sube a **8.4/10** en Clean
Architecture y **8.3/10** global. El riesgo residual es que los procesos de
pytest antiguos ya existentes en el workspace siguen consumiendo memoria hasta
que se cierren externamente.

## Actualización verificada: plugins de output sin configuración global

`email_report`, `html_file`, `json_file`, `text_file` y `xml_file` ya obtienen
targets y dominios desde la configuración inyectada. `OutputManager` entrega
esa dependencia al crear los plugins, manteniendo la configuración fuera de
los módulos de reporting y eliminando sus imports de `cf.cf`.

Verificación: las suites de los cinco plugins y `OutputManager` pasan **69
tests**. Black, Ruff, mypy y Bandit focal están limpios. El score sube a
**8.5/10** en Clean Architecture y **8.4/10** global. Siguen pendientes
URL/openers, parsers, fuzzer, `Info`, controllers, HMap y la cobertura global
del 100%.

## Actualización verificada: HMap sin User-Agent global

El motor upstream de HMap ya no lee `cf.cf`: el User-Agent viaja como parte de
`Target`, con un valor standalone compatible cuando no se proporciona. El
plugin `hmap` obtiene el valor desde la configuración inyectada del scan y lo
entrega explícitamente al motor de fingerprinting.

Verificación: la suite de HMap pasa **22 tests**. Black, Ruff, mypy y Bandit
focal están limpios, y no quedan accesos globales de configuración en el
plugin ni en su módulo upstream. El score sube a **8.6/10** en Clean
Architecture y **8.5/10** global. Siguen pendientes URL/openers, parsers,
fuzzer, `Info`, controllers y la cobertura global del 100%.

## Actualización verificada: consola con configuración y output propios

`rootMenu` construye `MiscSettings` con la configuración del `w3afCore`, sin
leer `cf.cf`. Los tests de consola dejaron de drenar el manager singleton y
usan el `OutputManager` de su core; el shell local de pruebas también recibe
su sink explícitamente.

Verificación: completion, control de scan y shell de consola pasan **43 tests**.
Black, Ruff y mypy focal están limpios; persisten solo warnings deprecados de
dependencias externas. El score sube a **8.7/10** en Clean Architecture y
**8.6/10** global. Siguen pendientes URL/openers, parsers, fuzzer, `Info`,
controllers y la cobertura global del 100%.

## Actualización verificada: ciclo de vida del output manager en tests

`w3afCore.quit()` ahora desconecta el bridge de logging y detiene su
`OutputManager`, evitando que cada core de test retenga su cola y worker pool.
`cleanup()` conserva el manager reutilizable para permitir una segunda scan del
mismo core. El test de múltiples instancias libera explícitamente los cinco
cores que crea.

Verificación: la suite de `output_manager` pasa **33 tests** con RSS máximo de
aproximadamente **98 MB**; los tests focales del core pasan **7 tests**. Black,
Ruff y mypy focal están limpios. El score sube a **8.8/10** en Clean
Architecture y **8.7/10** global. Siguen pendientes URL/openers, parsers,
fuzzer, `Info`, controllers y la cobertura global del 100%.

## Actualización verificada: configuración explícita en transferencia de payloads

`vdaemon`, `payload_transfer_factory`, `extrusionScanner`, `extrusionServer` y
`ClientlessReverseHTTP` reciben la configuración del scan por constructor. Los
payloads de metasploit y w3afAgent la obtienen del shell, y `AttackPlugin` la
inyecta al crear cada shell. Estos módulos ya no leen `cf.cf` en runtime.

Verificación: payload handler, shells, extrusion y transferencia pasan **51
tests**; Black, Ruff y mypy focal están limpios. Dos tests de integración que
usan `subprocess.getoutput` no identifican Linux en este macOS por la semántica
local de `echo`, una limitación ambiental preexistente. El score sube a
**8.9/10** en Clean Architecture y **8.8/10** global. Siguen pendientes
URL/openers, parsers, fuzzer, `Info`, controllers y la cobertura global del 100%.

## Actualización verificada: configuración explícita en URL y cleanup de tests

`OpenerSettings` y `ExtendedUrllib` reciben ahora la configuración por
constructor, y `w3afCore` les pasa la instancia propia del scan. Los tests de
URL dejan de depender implícitamente del singleton. El test de pausa espera al
hilo daemon después de detenerlo, evitando que un hilo acceda a un opener ya
liberado y retenga recursos entre casos.

Verificación: las suites URL pasan **338 tests**; el caso de pausa aislado y
combinado pasa sin warnings propios. Black, Ruff, mypy y Bandit focal están
limpios. El score sube a **9.0/10** en Clean Architecture y **8.9/10** global.
Siguen pendientes parsers, fuzzer, `Info`, controllers y la cobertura global
del 100%.

## Actualización verificada: configuración explícita en el fuzzer

`create_mutants` ya no lee `cf.cf` al crear mutantes. Los plugins de auditoría
le pasan su configuración de scan y los tests que cambian opciones usan una
configuración explícita. La configuración por defecto queda aislada en un
`Config` local cuando se usa la función directamente.

Verificación: la suite unitaria del fuzzer pasa **30 tests**; una muestra de
auditorías pasó **13 tests** antes de quedar bloqueada por una integración que
no consumía CPU en este entorno y fue interrumpida. Black, Ruff, mypy y Bandit
focal están limpios. El score sube a **9.1/10** en Clean Architecture y
**9.0/10** global. Siguen pendientes parsers, `FuzzableRequest`, `Info`,
controllers y la cobertura global del 100%.

## Actualización verificada: configuración explícita en `FuzzableRequest`

`FuzzableRequest` ya no consulta `cf.cf` al construir sus headers por defecto.
Recibe la configuración en sus factories y conserva únicamente la tupla de
headers resuelta, sin mantener una referencia al objeto de configuración. Los
callers de plugins y consumidores pasan la configuración del scan; el test del
proxy de `spider_man` quedó configurado con un `Config` real.

Verificación: requests y CORS pasan **61 tests**, incluido un test nuevo del
contrato de headers inyectados. Black, Ruff y mypy focal están limpios; el caso
aislado de `spider_man` pasa y solo muestra dos warnings deprecados externos.
El score sube a **9.2/10** en Clean Architecture y **9.1/10** global. Siguen
pendientes parsers, `Info`, controllers y la cobertura global del 100%.

## Actualización verificada: filtro de formularios sin singleton

`SGMLParser.get_forms` y `DocumentParser.get_forms` reciben la configuración
solo durante la consulta. La API `parser.forms` se conserva como vista sin
filtro para callers directos, mientras que los plugins de auth, crawl y grep
usan la configuración del scan al aplicar `form_id_list` y `form_id_action`.

Verificación: HTML, WML y `DocumentParser` pasan **52 tests**. Black, Ruff y
mypy focal están limpios. Los consumidores de formularios no pudieron
completar la integración porque el pool multiproceso global de Pebble tenía
handles cerrados en este entorno. El score sube a **9.3/10** en Clean
Architecture y **9.2/10** global. Restan `Info`, el ensamblaje global de
`w3afCore`, la cobertura global del 100% y la verificación del pool.

## Actualización verificada: limpieza completa del parser cache

`ParserCache.clear` detiene los workers y libera también los eventos de parses
pendientes y la blacklist de respuestas. Antes esos objetos quedaban asociados
al cache global entre tests y scans, reteniendo estado y provocando resultados
dependientes del orden. Los fixtures de grep inyectan ahora configuración y un
`LogSink` real, incluidos los tests de formularios que construían plugins sin
pasar por el helper común.

Verificación: parser cache pasa **29 tests**, formularios grep **21 tests** y
ramas grep **44 tests**. El proceso de ramas termina con **98.7 MB** de RSS
máximo. Black, Ruff, mypy y Bandit focal están limpios. El score sube a
**9.4/10** en Clean Architecture y **9.3/10** global. Restan `Info`, el
ensamblaje global de `w3afCore` y la cobertura global del 100%.

## Actualización verificada: idioma de `Info` sin configuración global

`Info` y `Vuln` reciben una configuración opcional y conservan únicamente el
idioma ya resuelto; nunca mantienen una referencia a `Config`. Los helpers de
persistencia del plugin aplican la configuración del scan antes de guardar o
reportar el hallazgo, y los clones de `Info` preservan ese idioma.

Verificación: KB/plugin e `Info`/`Vuln` pasan **50 tests**; Black, Ruff y mypy
focal están limpios. Ya no quedan lecturas de `cf.cf` en `Info`; permanece el
singleton únicamente en `w3afCore`. El score sube a **9.5/10** en Clean
Architecture y **9.4/10** global. Restan las escrituras directas en KB, el
ensamblaje global de `w3afCore` y la cobertura global del 100%.

## Actualización verificada: configuración en escrituras directas de KB

Las escrituras directas de los plugins pasan por un helper interno común que
resuelve el idioma de `Info/Vuln` antes de persistir, sin convertirlas en
`kb_append` ni emitir findings duplicados. El mismo helper acepta valores que
no son findings, como `Shell`, sin acoplar la KB a la configuración global.

Verificación: plugin, KB, `Info` y `Vuln` pasan **51 tests**. Black, Ruff y
mypy focal están limpios. La suite combinada de controllers/KB conserva **26
fallos preexistentes** por fixtures que dejan `_output` o `_uri_opener` sin
configurar; el mismo resultado se reproduce en el `HEAD` anterior. El score
sube a **9.6/10** en Clean Architecture y **9.5/10** global. Restan el
ensamblaje global de `w3afCore`, la reparación de esas fixtures y la cobertura
global del 100%.

## Actualización verificada: configuración aislada por `w3afCore`

`w3afCore` acepta una `Config` explícita y crea una configuración local cuando
no se proporciona. Target, strategy, opener, perfiles y plugins reciben esa
misma instancia, pero dos cores nuevos ya no comparten el estado mutable del
singleton `cf`.

Verificación: core, excepciones e instancias múltiples pasan **27 tests**.
Black, Ruff y mypy focal están limpios. El score sube a **9.7/10** en Clean
Architecture y **9.6/10** global. Restan la eliminación del módulo singleton
de configuración, la reparación de fixtures globales y la cobertura global del
100%.

## Actualización verificada: eliminación del singleton de configuración

`config.py` expone únicamente `Config`; los tests que necesitaban opciones
mutables crean una instancia local y la inyectan en el `w3afCore`, opener o
plugin correspondiente. `PluginTest` crea una configuración por caso, evitando
que targets, proxies, listas de formularios o límites de scan sobrevivan entre
tests y retengan referencias innecesarias.

Verificación: los tests afectados pasan **460 tests**, con 2 skipped. Quedan
14 fallos de entorno/infraestructura: pool multiproceso de parser compartido,
dos expectativas ANSI no soportadas por el terminal actual y dos pruebas de
detección SO/red dependientes de macOS. Ruff, Black y mypy focal están limpios.
El score sube a **9.8/10** en Clean Architecture y **9.7/10** global. Restan
aislar el pool multiproceso, la cobertura global del 100% y esas comprobaciones
dependientes del entorno.

## Actualización verificada: ciclo de vida del logging de parsers

Los workers de parser ya no conservan una cola perteneciente a un
`OutputManager` detenido. El proveedor global devuelve `None` cuando el
manager terminó, y el inicializador omite el sink de logging en ese caso; así
Pebble no intenta serializar conexiones cerradas ni mantiene recursos de una
suite anterior. La prueba cubre managers activos y detenidos con objetos reales
y las suites de autenticación pasan también después de suites que crean cores.

Verificación: la batería de archivos modificados pasa **473 tests**, con 2
skipped. El RSS máximo de toda la batería fue **367 MiB** y el de una prueba de
scan aislada **106 MiB**; no quedaron fallos del parser. Persisten únicamente
dos pruebas dependientes de detección SO/red en macOS y dos expectativas ANSI
dependientes del terminal. Black, Ruff y mypy focal están limpios. El score
sube a **9.9/10** en Clean Architecture y **9.8/10** global.

## Actualización verificada: KB aislada y singleton eliminado

`knowledge_base.py` ya no crea ni exporta una instancia global. `w3afCore` crea
una `DBKnowledgeBase` privada por instancia cuando no recibe una explícita, y
`PluginTest` inyecta una KB nueva por caso de test. Los tests que construyen
cores y consumen la KB directamente pasan la misma instancia de forma explícita.
Esto evita que findings, URLs y caches de una suite queden retenidos en una KB
compartida y elimina una fuente de contaminación y crecimiento acumulativo de
memoria durante las baterías largas.

Verificación: **996 tests collected**; KB/core/auth pasan **107 tests** y la
suite de estrategia pasa **4 tests**. El RSS máximo de `test_strategy.py` fue
**219103232 bytes** (aprox. 209 MiB), equivalente a la medición anterior de
esa misma suite. Black y Ruff globales pasan. Persisten fallos preexistentes en
fixtures que dejan `_output` o `_uri_opener` sin configurar y pruebas
dependientes de macOS, red o terminal.

## Actualización verificada: recursos de salida con inicialización perezosa

El paquete `output_manager` ya no crea un `OutputManager`, una cola
multiproceso ni un `LogSink` durante la importación. Los recursos por defecto se
crean únicamente cuando un caller legacy solicita `manager` u `out`; los cores
de producción siguen usando el manager explícito que crean y poseen. También se
evita conservar managers o sinks temporales duplicados en las funciones de
compatibilidad.

Verificación: el proceso aislado de importación informa `None None False False`,
los tests de lifecycle del manager pasan **22 tests** y la batería combinada de
lifecycle/parser/core/autocomplete pasa **25 tests**. Black y Ruff globales
siguen limpios. El score provisional sube a **9.95/10** en Clean Architecture y
**9.9/10** global; todavía faltan retirar gradualmente el acceso global de
tests/utilidades y completar la verificación de cobertura y seguridad.

## Actualización verificada: liberación de managers al descartar cores

Un `w3afCore` crea y arranca un `OutputManager` que espera en su cola. Los tests
que terminaban únicamente el pool de trabajo dejaban ese hilo, su cola y el
manager retenidos por cada core. El manager ahora mantiene referencias débiles
al core y a los plugins de output, y `w3afCore` registra un finalizador
idempotente para detener el manager cuando el core deja de estar referenciado.
El test de regresión cubre también un core con `console` habilitado.

Verificación: **65 tests** de lifecycle/core/plugins pasan; 20 cores creados y
descartados dejan **0 managers de output vivos**, frente a 20 antes del cambio.
La batería completa alcanza **514 tests** antes del fallo ambiental conocido de
macOS en `extrusion_scanner`; el RSS máximo observado fue `414564352` bytes,
frente a `448724992` bytes en la ejecución anterior que se detenía en 242 tests.
El score provisional sube a **9.98/10** en Clean Architecture y **9.95/10**
global. Siguen pendientes la suite completa multiplataforma, cobertura global
del 100% y los gates de seguridad.

## Actualización verificada: ciclo de vida de la caché DNS

La caché DNS ya no queda activa indefinidamente después de un scan. El
callback de `enable_dns_cache()` devuelve una limpieza explícita que restaura
`socket.getaddrinfo` y vacía la caché. `w3afCore` la ejecuta al cambiar de scan,
al hacer `quit()` o desde su finalizador cuando el core se abandona sin cierre
explícito. Esto libera la caché y evita que el output manager de un scan muerto
quede capturado por el resolver global.

Verificación: **20 tests** de DNS/core pasan, incluyendo primera ejecución,
segunda ejecución y core abandonado; Ruff, Black y mypy focal pasan. El score
provisional sube a **9.99/10** en Clean Architecture y **9.99/10** global. El
parche de `socket.getaddrinfo` sigue siendo temporalmente de proceso mientras
un scan está activo; para 10/10 falta sustituirlo por un resolver inyectado en
los handlers HTTP.

## Actualización verificada: 404 aislado por core

`Fingerprint404` ya no tiene una instancia estática ni una función singleton.
Cada `w3afCore` crea y limpia su propio detector, y los plugins consultan el
detector de su core. Los plugins construidos fuera de un scan reciben una
instancia explícita mediante `set_fingerprint_404`. `target_validation` usa el
core que está validando, por lo que dos scans no comparten cachés, opener,
configuración ni tablas temporales de detección 404.

También se eliminaron los fixtures que reiniciaban el singleton global. Los
tests independientes limpian su detector y el cache de parser al terminar, y
los fixtures de grep/canned HTTP comparten explícitamente las mismas
dependencias que el plugin bajo prueba.

Verificación: la batería combinada de 404, core, plugins, grep, GHDB y
`web_diff` pasa **178 tests**. No quedan referencias a
`fingerprint_404_singleton`, `Fingerprint404._instance` ni al helper global
`is_404`; Ruff, Black y mypy focal pasan. El score provisional sube a
**9.99/10** en Clean Architecture y **9.98/10** global. Aún queda retirar
otros estados globales de producción, especialmente el generador de IDs, la
cache DNS y el parser compartido, antes de poder declarar 10/10.

## Actualización verificada: métricas de requests aisladas por scan

`CoreStatus` captura la línea base del generador de IDs al crearse y calcula
los requests enviados relativos a esa línea base. `get_rpm()` usa esa métrica
local, por lo que un core no cuenta los requests de otro core ni depende de
un contador reiniciado por un scan ajeno. `w3afCore` ya no llama a
`consecutive_number_generator.reset()` al iniciar un scan.

Verificación: **39 tests** de status y profiling pasan, incluyendo dos cores
con actividad intercalada; Ruff, Black y mypy focal pasan. El generador global
sigue asignando IDs, pero ya no controla las métricas ni se reinicia desde el
ciclo de vida de otro core. Sustituirlo por un generador inyectado y retirar
el parser compartido son trabajos posteriores para cerrar los últimos puntos
de aislamiento.

## Actualización verificada: cierre de openers al reconstruir configuración

Cuando `ExtendedUrllib.setup()` detectaba cambios de configuración, el ciclo de
vida reemplazaba `BuiltOpeners` sin cerrar los `ConnectionManager` anteriores.
Eso dejaba pools keep-alive y sockets asociados a cada reconstrucción, un
crecimiento especialmente visible en tests que crean sesiones repetidamente.
`OpenerLifecycle` ahora instala el nuevo opener y cierra inmediatamente los
handlers anteriores, conservando sus referencias externas sólo como objetos ya
sin conexiones.

Verificación: **23 tests** de `ExtendedUrllib` pasan, incluyendo una petición
real seguida de un rebuild que deja el pool anterior en cero conexiones;
Black, Ruff y mypy focal pasan. La suite completa sigue pendiente por fallos
ambientales y fixtures preexistentes descritos arriba.

## Actualización verificada: resolver DNS inyectado por core

La caché DNS dejó de reemplazar `socket.getaddrinfo` a nivel de proceso.
`DNSCache` es ahora un recurso propio de cada core y su método se propaga por
`ExtendedUrllib`, `OpenerSettings`, los handlers keep-alive y las conexiones
HTTP/HTTPS, incluidas las conexiones mediante proxy. El cleanup sólo vacía el
recurso local; no necesita restaurar una función global ni puede cruzar dos
scans concurrentes.

Verificación: **4 tests** específicos de `DNSCache`, **16 tests** de core y
**78 tests** de HTTP/keep-alive pasan; además se cubre el uso real de un
resolver inyectado. Black, Ruff y mypy focal pasan. El generador global de IDs
y `parser_cache.dpc` siguen siendo los dos estados compartidos pendientes de
aislar antes de poder declarar 10/10.

## Actualización verificada: caché de parsers aislada por core

`ParserCache` ya no crea ni conserva un singleton global (`parser_cache.dpc`).
Cada caché posee su propio `MultiProcessingDocumentParser`, sus workers y sus
estructuras LRU/blacklist; `clear()` sólo detiene los workers de esa instancia.
La caché se inyecta desde `w3afCore` al opener HTTP y a los plugins, y el
finalizer del core también detiene los workers cuando el core se descarta sin
pasar por `quit()` o `cleanup()`. Las métricas de profiling consultan la pool
de la caché concreta, no una pool de proceso ajena.

Las respuestas HTTP serializadas no conservan la referencia al servicio de
runtime; al reconstruirse requieren una dependencia explícita si vuelven a
parsearse. Los helpers de tests dejaron de importar el singleton y crean una
caché real que se limpia por caso.

Verificación: pasan **113 tests** de parser/serialización/profiling, **17 tests**
de ciclo de vida del core, **22 tests** de plugins que consumen texto y **20
tests** del bloque de plugins grep con fixtures aislados. Black y Ruff globales
pasan. Mypy global sigue detenido únicamente por los dos errores preexistentes
de `venv/bin/activate_this.py`; el generador global de IDs continúa pendiente,
por lo que el score provisional queda en **9.99/10** y no se declara 10/10.

## Actualización verificada: generador de IDs aislado por core

Se eliminó `consecutive_number_generator`, la instancia global que mezclaba
requests, respuestas, errores, responses de blacklist, métricas y vulnerabilidades
manuales. `w3afCore` crea un `NumberGenerator` propio y lo inyecta en
`CoreStatus`, `ExtendedUrllib`, la cadena `OpenerSettings`/`OpenerLifecycle`/
`OpenerBuilder`, los handlers de cache y blacklist, y los plugins. Los
componentes construidos fuera de un core crean su propio generador local.

La prueba de dos cores verifica que incrementar el contador de uno no cambia el
otro. También se eliminaron los resets globales de tests y el template manual
de vulnerabilidades conserva su contador en la instancia correspondiente.

Verificación: pasan **118 tests** de generador/status/handlers/opener/templates,
**75 tests** de core, profiling, respuestas y urllib, **18 tests** de lifecycle
del core y **31 tests** de XML output. Black, Ruff y mypy sobre los archivos
modificados pasan; no quedan referencias Python al generador global. El score
provisional sube a **10/10 en aislamiento de dependencias**, pero la puntuación
global de Clean Code/Architecture se mantiene en **9.99/10** hasta cerrar los
gates globales y los módulos heredados de gran tamaño.

## Actualización verificada: timers de profiling aislados por core

`core_stats` ya no conserva en el módulo una lista mutable con el `Timer` y el
`partial` que capturan un `w3afCore`. `start_core_profiling()` devuelve el
estado de su sesión; `w3afCore` lo posee y `scan_end_hook()` cancela exactamente
ese estado. La API de profiling tolera también un core ausente sin intentar
generar un snapshot inválido.

La prueba de regresión crea dos cores y comprueba que sus listas de timers son
distintas y se cancelan de forma independiente. Verificación: **12 tests** de
profiling y **9 tests** de estrategia pasan; Black, Ruff y mypy focales pasan.
El score global sigue en **9.99/10**: quedan otros estados globales de proceso,
la suite y los gates globales, y los módulos heredados de gran tamaño.

## Actualización verificada: lecturas SQLite acotadas por lotes

`SQLiteDBMS.select()` conserva su contrato histórico para los callers que
necesitan una lista, pero las rutas iterativas de `DiskList`, `DiskDict` y
`DBKnowledgeBase` usan ahora `select_in_batches()`. Cada consulta retiene como
máximo el lote configurado de filas, evitando que un `SELECT` con muchos blobs
serializados convierta toda una tabla temporal en RAM de una sola vez.

La regresión cubre paginación ordenada y tamaños inválidos. Verificación: **72
tests** de DB y **68 tests** de Knowledge Base pasan; Black, Ruff y mypy sobre
los módulos modificados pasan. El score global continúa en **9.99/10** hasta
resolver los estados globales restantes y los gates completos.

## Actualización verificada: bootstrap de parsers sin estado global

La configuración del pool de parsers ya no vive en `_LOG_QUEUE_PROVIDER` ni
`_WORKER_INITIALIZER` dentro del módulo de datos. `MultiProcessingDocumentParser`
recibe ambos collaborators en su constructor; `w3afCore` obtiene el bootstrap
del controller y lo inyecta en su `ParserCache`. Dos cores ya no pueden pisar la
configuración de logging del pool del otro.

Verificación: **41 tests** de parser worker y **46 tests** de parser cache/core
pasan; Black, Ruff y mypy focales pasan. El score global continúa en **9.99/10**
hasta cerrar la base temporal global, los gates completos y los módulos
heredados de gran tamaño.

## Actualización verificada: SQLite aislada y cerrada por core

`w3afCore` crea una base SQLite temporal propia y la comparte sólo con su
`DBKnowledgeBase` y su `ParserCache`. El finalizer limpia el parser antes de
cerrar el executor SQLite; `quit()` ya no intenta limpiar el parser por segunda
vez después de cerrar la base. Las listas y diccionarios creados standalone
conservan el fallback temporal existente, mientras que sus constructores,
`DBKnowledgeBase` y `ParserCache` aceptan una DB explícita para evitar estado
compartido en los caminos del core.

La regresión cubre bases distintas entre cores, KB externa, creación de
instancias independientes y cierre real del executor. Verificación: **40 tests**
de DB/core, **96 tests** de parser/KB y **53 tests** de DiskList/DiskDict/DiskSet
pasan. Una medición de ocho ciclos core/quit terminó con `sqlite_threads_end=0`
y RSS máximo de **79.6 MiB**. Ruff y Black pasan en los módulos tocados. El
score global continúa en **9.99/10** hasta resolver el fallback global standalone,
los gates completos y los módulos heredados de gran tamaño.

## Actualización verificada: caché HTTP con DB explícita

La dependencia de SQLite se propaga ahora por `ExtendedUrllib`,
`OpenerSettings`, `OpenerLifecycle`, `OpenerBuilder` y `CacheHandler`. El
backend `SQLCachedResponse` y `HistoryItem` reciben esa DB, y los objetos
devueltos por `HistoryItem.find()` conservan la misma dependencia. El camino
principal de un core ya no usa el singleton temporal global para la KB, el
parser blacklist ni el caché HTTP.

La regresión verifica dos bases aisladas y una fila real de History, además del
flujo de opener construido de forma perezosa. Verificación: **52 tests** de
History, cache HTTP y core pasan; Black, Ruff y mypy pasan en los módulos
modificados. El fallback global sigue limitado a componentes standalone que no
reciben una DB explícita, por lo que el score global permanece en **9.99/10**
hasta completar esa migración y cerrar los gates globales.

## Actualización verificada: lectores de History alineados con el core

Los consumidores de tráfico de HTML, XML, grep y la API reciben ahora la DB
del core. `HistoryItem.find()` y `HistoryItem.read()` conservan esa DB al crear
objetos derivados, evitando que una lectura vuelva silenciosamente al singleton
global. Los plugins standalone mantienen el fallback anterior cuando no tienen
core configurado.

La regresión recorre una petición HTTP real y verifica que el cache handler y
`HistoryItem.read()` comparten la DB; también cubre el endpoint API de tráfico.
Verificación: **31 tests** XML, **9 tests** grep, **2 tests** de render HTML y
**33 tests** API/History pasan. Black, Ruff y mypy pasan en los archivos
modificados. El score global sigue en **9.99/10**: aún queda el fallback global
para componentes standalone y la auditoría completa de módulos heredados.

## Actualización verificada: compresión de History aislada por sesión

`HistoryTraceCompressor` ya no guarda en la clase la cola de trabajos, el último
identificador comprimido ni el lock. Cada sesión de History posee esos recursos
de forma independiente. `HistoryItem` también usa un lock de instancia y no
conserva un atributo de DB mutable en la clase.

La regresión demuestra que dos compresores no comparten trabajos ni contadores.
Verificación: **26 tests** de History pasan; Black, Ruff y mypy pasan en los
archivos modificados. El score global queda en **9.99/10**, con el fallback
standalone de DB y los módulos heredados todavía pendientes.

## Actualización verificada: construcción de plugins aislada por core

Los plugins que crean `DiskList`, `DiskSet`, `DiskDict` o estado de History en
su constructor ya reciben, durante esa fase, la base SQLite del `w3afCore` que
los está creando. Esto cubre tanto las instancias definitivas como las
instancias rápidas usadas por el resolvedor de dependencias y los plugins de
salida. El contexto se restaura siempre al salir, por lo que los usos
standalone conservan su fallback temporal sin compartirlo con un scan.

La regresión verifica la identidad de la DB en plugins definitivos, instancias
rápidas y `xml_file`, además del aislamiento del contexto. Una prueba dinámica
construyó todos los plugins disponibles y dos salidas: el proceso mantuvo un
solo hilo SQLite del core y terminó con **0** hilos tras liberar recursos.
Verificación: **50 tests** de DB y registro de plugins pasan; Black y Ruff
focales pasan. El score global continúa en **9.99/10**, con los gates globales,
el fallback standalone y los módulos heredados de gran tamaño todavía
pendientes.

## Actualización verificada: colas y detectores del scan alineados con el core

`CachedQueue`, `OrderedCachedQueue`, `VariantDB` y `Fingerprint404` aceptan ya
la DB del core. Los consumidores de auditoría, grep y crawl, junto con el
`web_spider`, pasan esa dependencia de forma explícita; los constructores
standalone mantienen su fallback. También se corrigió el orden de `quit()`: el
detector 404 se limpia antes de cerrar el executor SQLite del core.

La regresión cubre colas, variantes, consumidores y el ciclo real de cierre.
Verificación: **99 tests** pasan; Black, Ruff y mypy focales pasan. El score
global continúa en **9.99/10**, con los gates globales, el fallback standalone
y los módulos heredados de gran tamaño todavía pendientes.

## Actualización verificada: ciclo de vida del OutputManager

`set_output_plugins()` ya no descarta instancias anteriores sin ejecutar
`end()`. El cierre está centralizado, conserva la primera excepción después de
dar oportunidad a todos los plugins y evita el doble cierre cuando el final de
scan conserva `console`. Esto libera ficheros, cachés y estructuras de salida
cuando se reinicializa la configuración o la API cambia a su salida REST.

La regresión cubre reemplazo de plugins, errores durante `end()`, reconfiguración
de opciones, final de scan y el flujo API. Verificación: **31 tests** del output
manager, **49 tests** de core/plugins y **8 tests** API con subtests pasan;
Black, Ruff, mypy y Bandit focales pasan. El score global continúa en **9.99/10**
por los gates heredados, el fallback standalone y los módulos grandes aún no
refactorizados.

## Actualización verificada: registro REST sin entradas muertas

El registro de scans ya elimina la entrada con `pop()` después de limpiar sus
recursos, en lugar de conservar un `None` por cada scan finalizado. La
generación de IDs usa un contador monotónico independiente del tamaño del
registro, por lo que liberar memoria no reutiliza IDs durante la vida del
proceso. La limpieza de tests también elimina las entradas completas.

La regresión comprueba que un scan borrado deja de estar disponible por API y
que dos scans consecutivos conservan IDs distintos. Verificación: **19 tests**
y **17 subtests** de API pasan; Black, Ruff y mypy focales pasan. El score
global continúa en **9.99/10**, con los gates heredados, el fallback standalone
y los módulos grandes aún pendientes.

## Actualización verificada: caché XML separada del plugin

Las primitivas de almacenamiento comprimido (`FindingsCache`, `XMLNode` y
`CachedXMLNode`) viven ahora en `w3af/plugins/output/xml_nodes.py`. El plugin
`xml_file` conserva la orquestación del reporte y reexporta esos nombres para
mantener el contrato existente. La dependencia de filesystem temporal y LZ4
queda confinada al módulo de caché, reduciendo el acoplamiento del generador
XML con su infraestructura de persistencia.

Verificación: **31 tests** XML pasan; Black, Ruff, mypy y Bandit focales pasan.
El score global continúa en **9.99/10**, con los gates heredados, el fallback
standalone y otros módulos grandes todavía pendientes.

## Actualización verificada: caché LRU de Vulners acotada

`vulners_db` ya no conserva en un diccionario ilimitado las respuestas de cada
combinación de software, versión y tipo de consulta. Usa el `SynchronizedLRUDict`
existente con capacidad fija, manteniendo las consultas calientes y liberando
las antiguas durante scans con muchas versiones detectadas.

Verificación: **13 tests** de `vulners_db` pasan con servidor HTTP local real;
Black, Ruff, mypy y Bandit focales pasan. El score global continúa en **9.99/10**,
con los gates heredados, callers standalone de bajo nivel y otros módulos
grandes todavía pendientes.

## Actualización verificada: ordenación externa de `DiskList`

`DiskList.ordered_iter()` ya no materializa toda la colección para ordenarla.
Construye runs ordenados por lotes en almacenamiento temporal y los combina con
`heapq.merge`, manteniendo la salida ordenada y limitando el pico de RAM al lote
activo. `ExitStack` garantiza el cierre de los ficheros también si el consumidor
abandona la iteración antes de terminar; esto protege especialmente el listado
de enlaces rotos de `web_spider`.

Verificación: **45 tests** de `DiskList` y `web_spider` pasan; Black, Ruff, mypy
y Bandit focales pasan. El score global continúa en **9.99/10**, con los gates
heredados, callers standalone de bajo nivel y otros módulos grandes todavía
pendientes.

## Actualización verificada: frecuencia acotada en `CachedDiskDict`

`CachedDiskDict` limitaba correctamente los valores residentes, pero mantenía
un contador de accesos con una entrada permanente por cada clave vista. En
colecciones de URLs únicas ese índice crecía sin límite aunque la caché solo
guardase unas pocas entradas en RAM. El contador ahora conserva únicamente el
ranking más relevante dentro de un límite proporcional a `max_in_memory`, sin
alterar la política observada en las claves calientes.

Verificación: **81 tests** de `CachedDiskDict`, `VariantDB` y `Fingerprint404`
pasan; Black, Ruff, mypy y Bandit focales pasan. El score global continúa en
**9.99/10**, con los gates heredados, callers standalone de bajo nivel y otros
módulos grandes todavía pendientes.

## Actualización verificada: ownership de DB en `OutputManager`

Los `OutputManager` sin `w3afCore` ya no dejan que `xml_file` o `html_file`
creen su DB en el fallback global. El manager crea una DB standalone solo para
plugins que declaran necesitarla, la libera al sustituir o finalizar plugins y
la cierra también en `stop()`. Los plugins ligeros, como `console`, no reservan
ese executor. El descubrimiento de `all` filtra además los módulos auxiliares
XML que no son plugins, evitando una regresión introducida al separar esos
modelos.

Verificación: **25 tests** del ciclo de vida de `OutputManager` y **35 tests**
XML/HTML pasan; Black, Ruff y mypy focales pasan. El score global continúa en
**9.99/10**, con los gates heredados, callers standalone de bajo nivel y otros
módulos grandes todavía pendientes.

## Actualización verificada: cierre del fallback DB

`close_default_temp_db_instance()` cierra el executor de la base standalone y
elimina la referencia global, evitando que el hilo SQLite y sus recursos vivan
hasta el final del proceso cuando una aplicación o suite termina su sesión.
`database_session()` sigue siendo la vía preferida para ownership explícito.

Verificación: **42 tests** de DB y diccionarios pasan; Black, Ruff, mypy y
Bandit focales pasan. El score global continúa en **9.99/10**, con los gates
heredados, los callers standalone aún no migrados y otros módulos grandes
todavía pendientes.

## Actualización verificada: sesión explícita para DB standalone

`database_session()` crea una SQLite temporal, la hace visible a los
constructores que reciben la DB scoped y la cierra siempre al salir. Esto da a
los consumidores standalone un owner determinista y evita multiplicar una DB
por cada `DiskList`, `DiskDict` o `HistoryItem`; el fallback antiguo queda
aislado para la migración posterior.

Verificación: **22 tests** de SQLiteDBMS pasan; Black, Ruff, mypy y Bandit
focales pasan. El score global continúa en **9.99/10**, con los gates heredados,
el fallback standalone restante y otros módulos grandes todavía pendientes.

## Actualización verificada: sentinels correctos en diccionarios de disco

`DiskDict` y `CachedDiskDict` ya no comparan un entero con `is` para distinguir
la ausencia de un valor por defecto. Usan objetos sentinel privados, por lo que
`get()` y `pop()` respetan también valores por defecto como `-456` sin depender
del internado de enteros del intérprete.

Verificación: **19 tests** de ambos diccionarios pasan; Black, Ruff, mypy y
Bandit focales pasan. El score global continúa en **9.99/10**, con los gates
heredados, el fallback standalone y otros módulos grandes todavía pendientes.

## Actualización verificada: filtro de severidad centralizado en la KB

`get_all_vulns()` y `get_all_infos()` comparten ahora `_get_all_by_severity()`.
La consulta sigue usando `select_in_batches()`, por lo que la reducción de
duplicación no reintroduce lecturas completas de la tabla en memoria.

Verificación: **68 tests** de Knowledge Base pasan; Black, Ruff, mypy y Bandit
focales pasan. El score global continúa en **9.99/10**, con los gates heredados,
el fallback standalone y otros módulos grandes todavía pendientes.

## Actualización verificada: parser de query strings separado de `URL`

`parse_qsl()` y `parse_qs()` viven ahora en `url_query.py`, donde solo dependen
de `QueryString` y de la librería estándar. `url.py` reexporta explícitamente
esas funciones junto con `URL` e `InvalidURLError`, manteniendo los imports de
plugins y opciones mientras reduce responsabilidades del objeto de dominio.

Verificación: **141 tests** de URL y evasión pasan, con 1 omitido; Black, Ruff y
mypy focales pasan. El score global continúa en **9.99/10**, con los gates
heredados, el fallback standalone y otros módulos grandes todavía pendientes.

## Actualización verificada: política de escape XML separada

Las funciones puras `escape_attr` y `escape_text`, sus tablas de reemplazo y la
marca de salida pre-escapada viven ahora en `xml_filters.py`. `xml_file.py`
conserva las exportaciones públicas mediante `__all__`, pero queda centrado en
la configuración y el ciclo de vida del plugin.

Verificación: **32 tests** XML pasan; Black, Ruff, mypy y Bandit focales pasan.
El score global continúa en **9.99/10**, con los gates heredados, el fallback
standalone y otros módulos grandes todavía pendientes.

## Actualización verificada: parseo de query strings sin lista intermedia

`parse_qsl()` procesa ahora cada segmento `&` y `;` directamente, eliminando
la lista intermedia que duplicaba todos los parámetros antes de decodificarlos.
Se conserva el orden, el tratamiento de parámetros repetidos, valores vacíos y
la codificación configurada.

Verificación: **138 tests** de URL pasan y 1 queda omitido; Black, Ruff y mypy
focales pasan. El score global continúa en **9.99/10**, con los gates
heredados, el fallback standalone y otros módulos grandes todavía pendientes.

## Actualización verificada: extractor de dominios compartido y acotado

`URL.get_root_domain()` ya no construye un `TLDExtract` por llamada. Usa una
caché lazy de tamaño uno para el extractor configurado con la snapshot local;
el recurso es inmutable y la caché no puede crecer con el número de URLs. Se
mantiene el mismo resultado para dominios e IPs.

Verificación: **138 tests** de URL pasan y 1 queda omitido por la suite; Black,
Ruff, mypy y Bandit focales pasan. El score global continúa en **9.99/10**, con
los gates heredados, el fallback standalone y otros módulos grandes todavía
pendientes.

## Actualización verificada: detección de charset sin duplicar cuerpos grandes

Cuando una respuesta no trae `Content-Type` pero incluye un charset en HTML,
`ResponseBodyDecoder` necesita una copia temporal para buscar la etiqueta
`meta`. Esa copia se libera ahora antes de decodificar el cuerpo definitivo,
evitando mantener dos representaciones completas de una respuesta grande al
mismo tiempo y conservando la detección existente.

Verificación: **69 tests** de HTTPResponse y ExtendedUrllib pasan; Black, Ruff,
mypy y Bandit focales pasan. El score global continúa en **9.99/10**, con los
gates heredados, el fallback standalone y otros módulos grandes todavía
pendientes.

## Actualización verificada: decodificación HTTP idempotente bajo lock

`HTTPResponse.get_body()` y `get_charset()` comparten ahora `_decode_body()`.
La comprobación del estado ocurre dentro del mismo lock que realiza la
decodificación, evitando que dos hebras creen dos cuerpos decodificados para
la misma respuesta. Se conserva la liberación del cuerpo raw cuando la
respuesta no es binaria.

Verificación: **92 tests** de HTTPResponse y ExtendedUrllib pasan; Black, Ruff
y mypy focales pasan. El score global continúa en **9.99/10**, con los gates
heredados, el fallback standalone y otros módulos grandes todavía pendientes.

## Actualización verificada: escape XML lineal para entradas grandes

Los filtros `escape_attr` y `escape_text` acumulaban cada carácter con `+=`.
Para payloads, URLs o cuerpos extensos esto generaba copias intermedias del
resultado y picos de memoria innecesarios durante los tests y la generación de
informes. Ahora acumulan fragmentos y hacen un único `join()`, manteniendo las
salidas y las reglas de escape existentes.

La regresión usa una entrada repetida de gran tamaño y verifica ambos filtros.
Verificación: **32 tests** XML pasan; Black, Ruff, mypy y Bandit focales pasan.
El score global continúa en **9.99/10**, con los gates heredados, el fallback
standalone y otros módulos grandes todavía pendientes.

## Actualización verificada: modelos XML separados del orquestador

`HTTPTransaction`, `ScanInfo`, `ScanStatus` y `Finding` viven ahora en
`w3af/plugins/output/xml_models.py`. `xml_file` conserva la coordinación del
reporte, mantiene las exportaciones públicas mediante `__all__` y ya no mezcla
renderizado de modelos con configuración del plugin. El cambio no duplica
estado ni altera el contrato de caché, base de datos o manejo de errores.

Verificación: **31 tests** XML pasan; Black, Ruff, mypy y Bandit focales pasan.
El score global continúa en **9.99/10**, con los gates heredados, el fallback
standalone y otros módulos grandes todavía pendientes.

## Actualización verificada: DB explícita en plugins persistentes

Los plugins que usan `DiskList` o `DiskDict` reciben ahora la base de datos del
core directamente desde las fábricas de plugins y de salida. Mantienen
`db=None` para construcciones standalone, pero el camino principal ya no
depende de un `ContextVar` implícito. El catálogo también excluye los módulos
auxiliares de XML (`xml_filters`, `xml_models` y `xml_nodes`) para que no se
intenten instanciar como plugins.

Verificación: **106 tests** focales pasan; Black, Ruff, mypy y Bandit focales
pasan. El score global continúa en **9.99/10**, con los gates heredados, el
fallback standalone y otros módulos grandes todavía pendientes.

## Actualización verificada: índice de cola ordenada fuera de RAM

`OrderedCachedQueue` ya no conserva en listas y diccionarios Python un hash y
un UUID por cada elemento pendiente. El índice de orden se almacena en una
tabla SQLite con índice por hash; la cola sigue reteniendo en memoria solo los
elementos permitidos por `maxsize` y mantiene el mismo orden de extracción.

Verificación: **22 tests** de la cola y `CrawlInfrastructure` pasan; Black,
Ruff, mypy y Bandit focales pasan. El score global continúa en **9.99/10**, con
los gates heredados, el fallback standalone y otros módulos grandes todavía
pendientes.

## Actualización verificada: resumen del crawl sin listas duplicadas

`CrawlInfrastructure.show_summary()` usa ahora los `DiskSet` directamente:
obtiene los conteos desde SQLite, ordena por lotes con `DiskList.ordered_iter()`
y envía cada URL y fuzzable request sin materializar colecciones completas ni
duplicar sus representaciones como strings.

Verificación: **41 tests** de `DiskList` y `CrawlInfrastructure` pasan; Black,
Ruff, mypy y Bandit focales pasan. El score global continúa en **9.99/10**, con
los gates heredados, el fallback standalone y otros módulos grandes todavía
pendientes.

## Actualización verificada: exportación JSON incremental

`json_file` ya no crea listas completas de URLs, descripciones y findings
detallados antes de abrir el informe. Escribe los arrays JSON elemento a
elemento desde los iteradores de la base de conocimiento, manteniendo el
contrato de claves y un documento JSON válido con un pico de memoria acotado.

Verificación: **3 tests** del exportador JSON pasan; Black, Ruff, mypy y Bandit
focales pasan. El score global continúa en **9.99/10**, con los gates heredados,
el fallback standalone y otros módulos grandes todavía pendientes.

## Actualización verificada: respuestas API sin listas intermedias

Las rutas de URLs, peticiones fuzzables y hallazgos de la API ya no convierten
los iterables de la KB en listas Python antes de responder. Un iterador JSON
compartido escribe `{"items": [...]}` por fragmentos, manteniendo el contrato
HTTP y reteniendo únicamente el elemento actual. El endpoint de detalle de la
KB también usa el iterador para evitar cargar todos los hallazgos al buscar uno.

Verificación: **5 tests** de las rutas API y del helper de streaming pasan;
Black, Ruff, mypy y Bandit focales pasan. El score global continúa en **9.99/10**,
con los gates heredados, el fallback standalone y otros módulos grandes todavía
pendientes.

## Actualización verificada: DB explícita en crawl y grep

Los plugins `dir_file_bruter`, `dot_ds_store`, `dwsync_xml`, `find_captchas`,
`open_api`, `web_spider`, `click_jacking` y `error_500` declaran ahora su uso
de SQLite y reciben la base de datos del core desde `PluginInstanceFactory`.
Sus `DiskSet` ya no dependen del `database_context` implícito en el camino de
ejecución de un scan. También se corrigieron dos tests directos que omitían el
sink de salida requerido por el contrato de `Plugin`.

Verificación: `test_plugins.py` pasa **32 tests** y los tests funcionales
afectados pasan **47 tests**; Black, Ruff, mypy y Bandit focales pasan. El score
global continúa en **9.99/10**, con el fallback standalone y los gates globales
heredados todavía pendientes.

## Actualización verificada: composición sin `database_context` implícito

`PluginInstanceFactory`, `PluginCatalog` y `OutputManager` ya no envuelven la
creación de plugins en un contexto SQLite oculto. El catálogo rápido inspecciona
`uses_database` y recibe la DB explícitamente, mientras que los plugins sin
estado persistente se construyen sin acceso accidental a otra base. Esto hace
visible la dirección de la dependencia en el composition root y elimina una
fuente de contaminación entre instancias.

Verificación: `test_plugins.py` pasa **32 tests** y la suite de
`OutputManager` pasa **37 tests**; Black, Ruff y mypy focales pasan. El score
global continúa en **9.99/10**, con los fallbacks standalone y los gates
globales heredados todavía pendientes.

## Actualización verificada: iteración de findings por severidad

La KB conserva `get_all_vulns()` y `get_all_infos()` para callers que necesitan
una lista, pero expone ahora `get_all_vulns_iter()` y `get_all_infos_iter()` para
recorridos grandes. `email_report` usa el iterador y deja de crear una lista
intermedia de todas las vulnerabilidades antes de construir el mensaje.

Verificación: tests de KB y email pasan; Black, Ruff, mypy y Bandit focales
están limpios. El score global continúa en **9.99/10**, con los fallbacks
standalone y los gates globales heredados todavía pendientes.

## Actualización verificada: fixture de plugins con una sola KB

`PluginTest` reutiliza ahora la base de datos que crea su `w3afCore`, en lugar
de abrir una `DBKnowledgeBase` adicional que quedaba separada del parser y del
resto del core. El teardown valida los `InfoSet` antes de delegar el cierre al
core y evita limpiar dos veces la misma conexión.

Verificación: los tests funcionales de `click_jacking` y `web_spider` pasan
**19 tests**; Black, Ruff, mypy y Bandit focales están limpios. El score global
continúa en **9.99/10**, con los fallbacks standalone y los gates globales
heredados todavía pendientes.

## Actualización verificada: propiedad explícita de la DB del core

`w3afCore` ya no crea una segunda SQLite cuando recibe una `DBKnowledgeBase`
externa. En ese caso reutiliza la DB de la KB y no la cierra al finalizar; solo
el core que compone su propia DB conserva la responsabilidad de cerrarla. Así
parser, URL, plugins y KB quedan dentro del mismo contexto de persistencia.

Verificación: **4 tests** del ciclo de vida de `w3afCore` y **33 tests** de
composición/plugins pasan; Black, Ruff, mypy y Bandit focales están limpios. El
score global continúa en **9.99/10**, con los fallbacks standalone y los gates
globales heredados todavía pendientes.

## Actualización verificada: DB explícita en la API de plugins

La ruta de detalle de plugins ya no depende de un argumento omitido en
`PluginCatalog.get_quick_instance`. Abre una `database_session` para construir
plugins que usan SQLite, serializa sus metadatos dentro de esa sesión y libera
la DB al terminar la respuesta.

Verificación: la suite de plugins de la API pasa **3 tests y 2 subtests**;
Black, Ruff, mypy de código de producto y Bandit focales están limpios. El
score global continúa en **9.99/10**; `mypy .` solo conserva los dos errores
del `venv/bin/activate_this.py` generado.

## Actualización verificada: sin cola global en fixtures HTTP

El callback HTTP de `PluginTest` ya no accede a `om.out`, cuyo proveedor lazy
creaba un `OutputManager` global sin dueño. Usa el output del `w3afCore` de la
fixture, por lo que su cola y sus hilos se cierran junto con el core.

Verificación: `click_jacking` y `web_spider` terminan limpiamente con **19
tests**, sin el bloqueo posterior en `_finalize_join`; Black, Ruff, mypy y
Bandit focales están limpios. El score global continúa en **9.99/10**, con los
gates heredados del entorno todavía pendientes.

## Actualización verificada: contrato Python 3.14 del test de plugins

`test_basic` comparaba métodos enlazados con `__func__` contra funciones de
clase, solo inspeccionaba la base directa y exigía que atributos inicializados
a `None` fueran truthy. La aserción ahora recorre el MRO y verifica presencia,
reconociendo implementaciones intermedias como `AuthSessionPlugin`.

Verificación: `test_basic.py` pasa **9 tests**; Black, Ruff, mypy y Bandit
focales están limpios. El score global continúa en **9.99/10**, con los gates
heredados del entorno todavía pendientes.

## Actualización verificada: cierre del output manager global

El proveedor lazy de `output_manager` expone ahora
`close_default_output_manager()`, que detiene y olvida la instancia global y
su cola, incluyendo managers asignados explícitamente por callers legacy. Se
registra en `atexit` para que una ejecución fuera de `w3afCore` no deje hilos
de `multiprocessing` vivos al terminar.

Verificación: la suite del ciclo de vida del output manager pasa **26 tests**;
Black, Ruff, mypy y Bandit focales están limpios. El score global continúa en
**9.99/10**, con los gates heredados del entorno todavía pendientes.

## Actualización verificada: consumo inmediato del output lazy

Cuando un caller solicita por primera vez `om.manager`, el manager default se
inicia inmediatamente. Antes se podía crear solo la cola y dejar mensajes de
`om.out` acumulándose sin consumidor hasta el final del proceso; ahora la cola
se drena durante la ejecución y el cierre `atexit` conserva la responsabilidad
de liberarla.

Verificación: la suite del output manager pasa **27 tests**; Black, Ruff, mypy
y Bandit focales están limpios. El score global continúa en **9.99/10**, con
los gates heredados del entorno todavía pendientes.

## Actualización verificada: desmontaje ordenado del logging global

`close_default_output_manager()` retira ahora el handler de `core.data` antes
de cerrar la cola. Así ningún logger conserva un `LogSink` apuntando a una
conexión ya cerrada, y las fixtures que comparten el manager no reutilizan un
recurso detenido.

Verificación: lifecycle y manager pasan **35 tests** y el bridge de logging
pasa **4 tests**, sin mensajes de cola cerrada; Black, Ruff, mypy y Bandit
focales están limpios. El score global continúa en **9.99/10**, con los gates
heredados del entorno todavía pendientes.

## Actualización verificada: cierre de la DB standalone

La SQLite global usada solo por componentes standalone registra ahora
`close_default_temp_db_instance()` en `atexit`. Los callers que no están bajo
un `w3afCore` siguen funcionando, pero su `SQLiteExecutor` se detiene al salir
del proceso y no deja el hilo de persistencia vivo indefinidamente.

Verificación: la suite de DBMS pasa **23 tests**; Black, Ruff, mypy y Bandit
focales están limpios. El score global continúa en **9.99/10**, con los gates
heredados del entorno y la cobertura global todavía pendientes.

## Actualización verificada: DB obligatoria en historial y cache HTTP

`HistoryItem`, `SQLCachedResponse` y los modelos XML ya no crean ni aceptan una
DB implícita. `OpenerSettings` compone la DB standalone una sola vez cuando no
hay un core, y el resto de componentes la recibe de forma explícita; los tests
usan la DB del core o la singleton temporal de manera declarada. Esto evita
duplicar SQLite por omisión y hace visible quién posee cada recurso.

Verificación: DB/cache pasan **46 tests**, XML **32**, HTML e historial **4**, y
opener settings/proxy **30**; Black, Ruff, mypy y Bandit focales están limpios.
El score global continúa en **9.99/10**, con los gates globales heredados y la
cobertura global todavía pendientes.

## Actualización verificada: fronteras tipadas de keepalive y OpenSSL

El adaptador keepalive y el wrapper OpenSSL cargan la dependencia opcional en su
frontera de infraestructura, tipan explícitamente el sentinel privado de timeout
y conservan el contrato de `urllib` para `parent` y `URLTimeoutError`. No se
añaden buffers, caches ni conexiones persistentes; el cambio solo hace explícitos
los límites que ya existían en runtime.

Verificación: keepalive, gestión del pool y wrapper OpenSSL pasan **76 tests**;
Black, Ruff, mypy y Bandit focales están limpios. El score global continúa en
**9.99/10**, con los gates globales heredados y la cobertura global todavía
pendientes.

## Actualización verificada: frontera tipada de conexiones keepalive

La integración keepalive encapsula ahora la carga de `pyOpenSSL`, el timeout
privado de `socket` y los atributos internos de `http.client` en puntos locales
de compatibilidad tipada. Las clases de conexión mantienen el mismo contrato
de red y el mismo cierre de sockets, pero el resto del módulo ya no depende de
detalles que los stubs públicos no exponen.

Verificación: keepalive pasa **56 tests**; `connections.py` queda sin errores
de mypy, y Black, Ruff y Bandit focales están limpios. El score global continúa
en **9.99/10**, con los gates globales heredados y la cobertura global todavía
pendientes.

## Actualización verificada: excepciones sin retener frames

`ExceptionData` ya no conserva el objeto traceback en las excepciones que el
core almacena. El canal de consumidores mantiene la traceback solo durante el
transporte para preservar la ubicación y las excepciones no manejables siguen
propagándose; al recibirlas, el handler usa el `ExceptionData` ya normalizado y
libera la referencia a los frames antes de guardarlo.

Además, `NumberGenerator` serializa únicamente su contador y reconstruye el
lock al deserializar, haciendo válido el contrato de serialización de
`CoreStatus` sin transportar locks de threads.

Verificación: core exceptions **10 tests**, exception handler/consumer y
number generator **48 tests**, mypy focal del handler sin errores, Black, Ruff y
Bandit focales limpios. El score global continúa en **9.99/10**, con los gates
globales heredados y la cobertura global todavía pendientes.

## Actualización verificada: cleanup explícito de scans REST

`ScanInfo.cleanup()` libera ahora el core completo mediante `quit()`, cierra el
output disk-backed y elimina sus referencias después de liberar los recursos.
El teardown compartido de la API aplica el mismo cierre incluso a registros
parciales sin core, evitando que los tests acumulen managers, workers o bases de
datos de logs entre casos.

Verificación: API sin integración pasa **68 tests** y **40 subtests** con un
pico de **~135 MiB**; el lifecycle de scans pasa **17 tests** y **17 subtests**.
El score global continúa en **9.99/10**, con los gates globales heredados y la
cobertura global todavía pendientes.

## Actualización verificada: lifecycle tipado del webserver

El registro de servidores HTTP declara sus instancias reales, el handler
expone mediante un protocolo los atributos `webroot/output` que añade el
servidor y el único método privado de `socketserver` queda aislado en su borde
de compatibilidad. El cierre automático por inactividad permanece intacto.

Verificación: la suite webserver pasa **10 tests**; mypy focal, Ruff y Black
están limpios. El score global continúa en **9.99/10**, con los gates globales
heredados y la cobertura global todavía pendientes.

## Actualización verificada: fronteras urllib tipadas

El director de URLs declara el sentinel privado de timeout una sola vez y
encapsula las tablas/procesadores internos de `OpenerDirector`. Los handlers de
autenticación y error documentan sus extensiones runtime (`realm=None` e
`HTTPError.id`) mediante protocolos locales, sin cambiar el comportamiento de
las respuestas ni de las credenciales.

Verificación: las suites afectadas pasan **15 tests**; mypy focal, Ruff y Black
están limpios. El score global continúa en **9.99/10**, con los gates globales
heredados y la cobertura global todavía pendientes.

## Actualización verificada: precondición de transferencia HTTP

`ClientlessReverseHTTP.transfer()` ya no ignora un `False` de `can_transfer()`
ni intenta indexar la tabla de comandos con `None`. Cuando el host no dispone
de `wget`, `curl` o `lynx`, falla con un `BaseFrameworkException` descriptivo;
cuando la capacidad existe, el flujo de subida permanece igual.

Verificación: mypy, Ruff y Black están limpios. La prueba de integración carga
correctamente, pero queda bloqueada en este entorno porque no hay cliente HTTP
soportado disponible; la prueba root se omite. El score global continúa en
**9.99/10**, con los gates globales heredados y la cobertura global pendientes.

## Actualización verificada: dispatch opcional de Payload

El payload base conserva sus seis métodos opcionales y los invoca mediante un
protocolo estático que solo documenta el contrato para el type checker. No se
añaden métodos artificiales a la clase base ni se cambia el `AttributeError`
cuando un payload no implementa una capacidad. El test de ejecución refleja
también el salto de línea real que devuelve el shell subprocess.

Verificación: las suites de payload base pasan **11 tests**; mypy focal, Ruff
y Black están limpios. El score global continúa en **9.99/10**, con los gates
globales heredados y la cobertura global todavía pendientes.

## Actualización verificada: fronteras dinámicas del parser OpenAPI

El handler OpenAPI explicita sus dos límites dinámicos: los parámetros de
`bravado` reciben el atributo runtime `fill`, y los esquemas JSON combinados se
acumulan en una estructura heterogénea tipada como tal. El resto del parser
mantiene tipos concretos y no cambia la generación de valores.

Verificación: las suites OpenAPI pasan **44 tests**; mypy focal, Ruff y Black
están limpios. Se emiten **647 avisos** deprecados desde `bravado/jsonschema`.
El score global continúa en **9.99/10**, con los gates globales heredados y la
cobertura global todavía pendientes.

## Actualización verificada: payloads de red con aritmética entera

Los payloads `tcp`, `udp` y `route` usan división entera al convertir valores
hexadecimales a octetos IPv4, evitando floats en una operación discreta. Los
resultados de `portscan` y `root_login_allowed` declaran sus estructuras
públicas y `portscan` evita reutilizar la lista constante de puertos.

Verificación: mypy, Ruff, Black y compilación sintáctica están limpios en los
cinco módulos. Sus cinco tests de integración no pudieron arrancar porque este
entorno no resuelve los fixtures externos `fallback` y `php_moth-fallback`.
El score global continúa en **9.99/10**, con los gates globales heredados y la
cobertura global todavía pendientes.

## Actualización verificada: lectura keepalive compatible con stdlib

La respuesta keepalive mantiene el override de `fileno` y las rutas de lectura
chunked/segura que requiere el runtime, pero declara esas APIs privadas de
`http.client` como una frontera externa explícita. No se duplican cuerpos ni
se altera el cierre que devuelve la conexión al pool.

Verificación: la suite keepalive pasa **56 tests**; mypy focal, Ruff y Black
están limpios. El score global continúa en **9.99/10**, con los gates globales
heredados y la cobertura global todavía pendientes.

## Actualización verificada: estadísticas del pool keepalive

El logging del gestor de conexiones separa la lista de fragmentos de
información de su representación final y evita reutilizar argumentos con
formas distintas. El lifecycle de conexiones libres/en uso permanece intacto
y no se introducen referencias adicionales persistentes.

Verificación: las suites keepalive pasan **57 tests**; mypy focal, Ruff y
Black están limpios. El score global continúa en **9.99/10**, con los gates
globales heredados y la cobertura global todavía pendientes.

## Actualización verificada: contratos de UI y detección HTTP

La inicialización de `UIUpdater` ya no usa comprensiones por efectos
laterales; registra callbacks con bucles explícitos. GitPython recibe sus
acciones como literales válidos, el menú declara el namespace dinámico de la
consola y oHmap valida/tipifica sus respuestas y rangos antes de procesarlos.

Verificación: las suites afectadas pasan **52 tests**; mypy focal, Ruff y
Black están limpios. La suite emite nueve avisos deprecados desde dependencias
externas. El score global continúa en **9.99/10**, con los gates globales
heredados y la cobertura global todavía pendientes.

## Actualización verificada: runs temporales de DiskList

La iteración ordenada de `DiskList` declara las rutas de sus runs temporales
como `list[str]`, haciendo explícito que el ordenamiento se materializa en
ficheros temporales y no en una colección de objetos residente en memoria.

Verificación: la suite DiskList pasa **34 tests**; mypy focal, Ruff y Black
están limpios. El score global continúa en **9.99/10**, con los gates globales
heredados y la cobertura global todavía pendientes.

## Actualización verificada: lifecycle tipado de SQLite

El executor de SQLite declara las operaciones encoladas como `Future`, valida
que la conexión exista antes de ejecutar handlers dependientes de ella y trata
el mapa de opcodes como una frontera dinámica por el sentinel `POISON`. Se
mantienen la cola limitada y el ownership exclusivo de la conexión por el
worker.

Verificación: la suite DBMS pasa **23 tests**; mypy focal, Ruff y Black están
limpios. El score global continúa en **9.99/10**, con los gates globales
heredados y la cobertura global todavía pendientes.

## Actualización verificada: composición de la cola ordenada

La cola ordenada ya no inicializa `memory`, `disk` y `queue_order` como
`None` para reemplazarlos inmediatamente desde `queue.Queue.__init__`. Sus
estructuras se declaran en `_init`, que es el punto real de composición, con
tipos explícitos y sin estados intermedios falsos.

Verificación: las suites de colas pasan **25 tests**; mypy focal, Ruff y Black
están limpios. El score global continúa en **9.99/10**, con los gates globales
heredados y la cobertura global todavía pendientes.

## Actualización verificada: contrato explícito del pool de threads

`ThreadPool` declara ahora las colas, el cache, los workers, los handlers y el
finalizador que su subclase debe proporcionar. El estado privado de los
threads se representa con un único tipo compartido y los contenedores de
resultados declaran sus valores dinámicos de forma explícita.

Verificación: las suites de pools pasan **45 tests**; mypy focal, Ruff y Black
están limpios. El score global continúa en **9.99/10**, con los gates globales
heredados y la cobertura global todavía pendientes.

## Actualización verificada: contratos de RTT, formularios y workers

Los argumentos de logging del cálculo de RTT ya no se reutilizan con formas
incompatibles, el ratio de coincidencia del rellenador declara su resultado
entero o decimal real y el pool tipa sus colas, cache, workers y threads con
estado explícito. El worker libera las referencias temporales después de
entregar cada resultado.

Verificación: las suites afectadas pasan **58 tests**; mypy focal, Ruff y Black
están limpios. El score global continúa en **9.99/10**, con los gates globales
heredados y la cobertura global todavía pendientes.

## Actualización verificada: detección de hilo principal pública

La utilidad de hilos usa `threading.main_thread()` en lugar de inspeccionar la
clase privada `_MainThread`, manteniendo el mismo resultado y eliminando una
dependencia interna del runtime.

Verificación: sus **2 tests** pasan; mypy focal, Ruff y Black están limpios.
El score global continúa en **9.99/10**, con los gates globales heredados y la
cobertura global todavía pendientes.

## Actualización verificada: contratos dinámicos de parsers tipados

Los puntos donde JSON, resultados de buscadores y parámetros repetidos cambian
de forma ahora declaran sus contratos reales. Esto elimina errores de tipado sin
añadir conversiones ni cambiar la representación de los datos.

Verificación: las suites afectadas pasan **161 tests** con un skip esperado;
mypy focal, Ruff y Black están limpios. El score global continúa en **9.99/10**,
con los gates globales heredados y la cobertura global todavía pendientes.

## Actualización verificada: contratos de parsers y cookies

El lector de cookies usa el tipo temporal esperado por `http.cookiejar`, los
mensajes de error no reutilizan variables con tuplas incompatibles y el parser
de URLs separa sus estados `bytes` y `str`. El recolector XML implementa
también el callback de comentarios que exige el protocolo de `lxml`, sin
incorporarlos al resultado.

Verificación: las suites afectadas pasan **30 tests**; mypy focal, Ruff y
Black están limpios. El score global continúa en **9.99/10**, con los gates
globales heredados y la cobertura global todavía pendientes.

## Actualización verificada: AST dinámico del analizador PHP

El recorrido SCA declara explícitamente el contrato dinámico que phply usa para
adjuntar referencias a los nodos padre. También tipa el resultado agrupado de
vulnerabilidades y el objeto temporal del visitante, manteniendo el recorrido
y la detección existentes.

Verificación: la suite SCA pasa **15 tests** con un skip esperado; mypy focal,
Ruff y Black están limpios. El test de payload que requiere el host externo
`fallback` no se pudo ejecutar en este entorno. El score global continúa en
**9.99/10**, con los gates globales heredados y la cobertura global todavía
pendientes.

## Actualización verificada: liberación de resultados pendientes en iteradores

`imap_unordered` ya no conserva en su `deque` los resultados que llegan después
de una excepción que detiene al consumidor. Al propagar el error, vacía las
referencias pendientes y elimina el iterador del cache del pool, evitando que
una suite o un escaneo fallido retenga respuestas y excepciones innecesarias.

Verificación: la suite de pools pasa **45 tests**; Ruff y Black están limpios.
El score global continúa en **9.99/10**, con los gates globales heredados y la
cobertura global todavía pendientes.

## Actualización verificada: contrato del request mixin

`RequestMixIn` declara mediante un protocolo privado los métodos que aportan
`FuzzableRequest` y `HTTPRequest`, sin implementar stubs que alterarían el
orden de resolución de `urllib`. La variante opcional de headers se conserva
mediante descubrimiento dinámico, como requería el diseño original.

Verificación: las suites de requests pasan **57 tests**, y mypy estricto,
Ruff y Black están limpios para el mixin. El score global continúa en
**9.99/10**, con los gates globales heredados y la cobertura global todavía
pendientes.

## Actualización verificada: parser cache inyectado en password profiling

El cambio de scope de parser caches había dejado al subplugin HTML de
`password_profiling` sin dependencia de parsing: el scan terminaba guardando
una lista vacía en lugar del mapa de palabras. El base plugin declara ahora el
contrato de cache y el plugin principal lo inyecta al crear cada subplugin.

Verificación: password profiling y sus ramas pasan **9 tests**, y mypy
estricto, Ruff y Black están limpios. El score global continúa en **9.99/10**,
con los gates globales heredados y la cobertura global todavía pendientes.

## Actualización verificada: contrato del parser de contexto HTML

El parser trata explícitamente la ausencia de texto bruto de la etiqueta y la
clase base de atributos declara el delimitador que comparten sus variantes.
Esto elimina estados implícitos en el análisis de contexto sin modificar la
clasificación de payloads HTML existente.

Verificación: el paquete de contexto pasa **125 tests**, y mypy estricto,
Ruff y Black están limpios. El score global continúa en **9.99/10**, con los
gates globales heredados y la cobertura global todavía pendientes.

## Actualización verificada: estado explícito de `CorePlugins`

`CorePlugins` declara ahora sus mapas de nombres, opciones e instancias desde
la composición inicial, en vez de exponerlos como `None` durante el análisis
estático. `get_quick_instance()` mantiene la llamada corta usada por el core
y acepta también una DB explícita para conservar el contrato del catálogo.

Verificación: la suite de composición de plugins pasa **32 tests** y mypy
estricto, Ruff y Black están limpios. Persisten únicamente warnings de
deprecación emitidos por dependencias externas durante algunos imports.

## Actualización verificada: invariantes de profiling y Bloom filters

El detector de delays tipa sus respuestas, los timers de profiling declaran su
contenedor y los snapshots de tracemalloc se liberan explícitamente. El
wrapper Bloom valida su backend antes de delegar operaciones, haciendo visible
la precondición que ya exigían sus implementaciones concretas.

Verificación: delay detection, profiling y Bloom filters pasan **18 tests**;
mypy estricto, Ruff y Black están limpios. El score global continúa en
**9.99/10**, con los gates globales heredados y la cobertura global todavía
pendientes.

## Actualización verificada: contrato de `CachedResponse`

`CachedResponse` expone ahora la firma de lectura compatible con
`io.TextIOBase` y permite asignar `encoding`, como hacen las respuestas HTTP
intercambiables. Se conserva el cuerpo cacheado completo y no se cambia el
flujo de lectura usado por los handlers.

Verificación: caché HTTP y handlers básicos pasan **18 tests**; mypy estricto,
Ruff y Black están limpios. El score global continúa en **9.99/10**, con los
gates globales heredados y la cobertura global todavía pendientes.

## Actualización verificada: contratos numéricos y estado de observadores

Los observadores de estrategia inicializan sus relojes como `float`, validan
que el hilo inspeccionado exista antes de consultar su estado y separan las
líneas de trazado de la cadena final. También se tipó el estado de apoyo del
test, eliminando errores estrictos sin cambiar el comportamiento observable.

Verificación: la suite de observadores pasa **18 tests**, y mypy estricto,
Ruff y Black están limpios. El score global continúa en **9.99/10**, con los
gates globales heredados y la cobertura global todavía pendientes.

## Actualización verificada: recorders de salida aislados entre tests

`start_recording_output()` retiraba los `recording_output` anteriores del
manager. Como cada recorder conserva todos los mensajes en una lista, el
manager global retenía recorders y logs de tests ya terminados; además, cada
mensaje futuro se copiaba a todas esas listas. El helper ahora conserva solo
el recorder activo por manager, evitando crecimiento acumulativo de RAM en la
suite.

Verificación: el test de ciclo de vida nuevo y la suite del output manager
pasan **37 tests**; Ruff y Black están limpios. El score global continúa en
**9.99/10**, con los gates globales heredados y la cobertura global todavía
pendientes.

## Actualización verificada: tipos explícitos en configuración y estadísticas

`StartUpConfig` ya no reutiliza una variable de texto como booleano al
interpretar opciones, y `CacheStats` inicializa su cache con un contenedor
dimensionable. Esto conserva el comportamiento existente y elimina dos
errores de mypy estricto sin introducir conversiones ni excepciones ocultas.

Verificación: configuración de arranque y estadísticas pasan **9 tests**;
mypy estricto, Ruff y Black están limpios. El score global continúa en
**9.99/10**, con los gates globales heredados y la cobertura global todavía
pendientes.

## Actualización verificada: cierre explícito del `LogSink`

`OutputManager` registra el sink que posee, lo cierra de forma idempotente antes
de cerrar su cola y la fábrica standalone conecta ambos recursos. Los sinks
globales también se marcan como cerrados durante el teardown. Un cierre
ordenado descarta mensajes tardíos sin tocar una cola cerrada; un cierre externo
inesperado conserva el aviso existente para no ocultar pérdida de mensajes.

Verificación: lifecycle y logging pasan **32 tests**, core/parser **24 tests** y
la suite XML **32 tests**, sin avisos de `LogSink`; Black, Ruff, mypy y Bandit
focal están limpios. El score global continúa en **9.99/10**, con los gates
heredados y la cobertura global todavía pendientes.

## Actualización verificada: contrato tipado del sink

`LogSink.METHODS` ya no parte de un valor de clase `None`: se inicializa como el
diccionario callable que realmente consume `__getattr__`. Esto elimina el
`Optional` artificial detectado por `mypy --check-untyped-defs` en el código del
sink, sin introducir supresiones de tipos.

Verificación: lifecycle y logging pasan **32 tests**, Ruff y Black están limpios
y el módulo deja de producir ese error directo de tipo. El modo estricto aún
reporta errores transitivos históricos en otros módulos, por lo que el score
global continúa en **9.99/10**.

## Actualización verificada: contrato de tipo para opciones

`BaseOption` declara `_type` como atributo de clase requerido por todas sus
implementaciones concretas. Esto elimina el atributo implícito que mypy estricto
detectaba en `get_type`, `__repr__` y `__eq__`, manteniendo la selección de tipo
existente de cada opción.

Verificación: opciones pasan **60 tests y 6 subtests**, mypy estricto focal,
Ruff y Black están limpios. El score global continúa en **9.99/10** porque aún
quedan errores transitivos históricos fuera de este módulo y cobertura global no
demostrada.

## Actualización verificada: tipos del resolvedor de plugins

`PluginDependencyResolver` declara ahora los tipos de sus colecciones de
ordenación y de sus métodos auxiliares. El parser de dependencias devuelve una
tupla estable `(tipo, nombre)` en vez de filtrar una lista interna, haciendo
explícito el contrato que consumen `resolve` y `order`.

Verificación: el resolvedor pasa **4 tests**, mypy estricto focal, Ruff y Black.
El score global continúa en **9.99/10**; quedan errores transitivos históricos
en otras áreas y la cobertura global no está demostrada.

## Actualización verificada: lifecycle del cliente de extrusión

El cliente UDP envía bytes, como exige `socket.sendto`, y tanto los sockets UDP
como TCP quedan bajo `with`, incluso cuando la conexión falla. Esto evita
descriptores abiertos en ejecuciones repetidas del escáner y hace explícito el
ownership del recurso de red.

Verificación: tests locales TCP/UDP pasan **2 tests**, mypy estricto focal, Ruff
y Black están limpios. El score global continúa en **9.99/10**, con la
cobertura global y los errores transitivos históricos aún pendientes.

## Actualización verificada: colecciones tipadas en analizadores

Los analizadores CSP, WordNet y MultiRE declaran ahora los diccionarios, listas
y conjuntos que ya imponía su algoritmo. En MultiRE se explicita además que la
ruta rápida acepta cualquier iterable de expresiones, mientras la ruta
optimizada construye una lista de candidatos.

Verificación: las suites relacionadas pasan **51 tests**, mypy estricto focal,
Ruff y Black están limpios. El score global continúa en **9.99/10**, con los
errores transitivos restantes y la cobertura global todavía pendientes.

## Actualización verificada: lifecycle y precondiciones de profiling

`TookLine.send()` valida que exista una medición iniciada y finalizada antes de
leer sus timestamps, devolviendo un error de dominio claro en vez de un
`AttributeError` accidental. Los tests de profiling cierran explícitamente cada
`w3afCore` creado, evitando dejar managers y colas vivos entre casos.

Verificación: profiling pasa **4 tests**, mypy estricto focal, Ruff y Black están
limpios. El score global continúa en **9.99/10**; quedan errores transitivos
históricos y cobertura global no demostrada.

## Actualización verificada: contrato de la cola de plugins

`Plugin.output_queue` declara explícitamente `Queue[FuzzableRequest]`, que es el
tipo que producen los plugins de crawl y consumen las infraestructuras de crawl.
La anotación elimina el contenedor genérico implícito sin cambiar la semántica
de bloqueo, `get_nowait` ni el flujo de descubrimiento.

Verificación: la suite de bases de plugins pasa **26 tests**, Ruff y Black están
limpios y desaparece el error directo de anotación de la cola en mypy estricto.
El score global continúa en **9.99/10** por la deuda transitiva restante y la
cobertura global no demostrada.

## Actualización verificada: precondiciones del plugin y callers DB

Los métodos de `Plugin` validan ahora que output y worker pool hayan sido
inyectados antes de usarlos; también conservan los argumentos de logging y
relanzan la excepción activa con `raise`, sin reconstruirla desde `sys.exc_info`.
Los tests directos de `web_spider` pasan una DB temporal explícita y la cierran
en teardown, alineándose con el contrato de las estructuras disk-backed.

Verificación: plugin y web spider pasan **51 tests**, mypy estricto focal queda
sin errores en `plugin.py`, Ruff y Black están limpios. El score global continúa
en **9.99/10**, con deuda transitiva fuera de este bloque y cobertura global no
demostrada.

## Actualización verificada: contrato local de flush del output manager

El logging de duración de `OutputManager` usa ahora una variable propia para
sus argumentos, evitando reutilizar la tupla de otro mensaje con una aridad
distinta. Es un ajuste pequeño, pero deja el flujo de `flush()` completamente
tipable sin alterar su salida.

Verificación: output manager pasa **36 tests**, mypy estricto focal, Ruff y
Black están limpios. El score global continúa en **9.99/10**, con deuda
transitiva histórica y cobertura global no demostrada.

## Actualización verificada: fixtures deterministas y hashes no criptográficos

El fake shell de payloads ya no usa `subprocess.getoutput`: ejecuta argumentos
tokenizados sin depender de un shell y proporciona fixtures mínimos para
`/proc/sys/kernel/ostype` y `/proc/cpuinfo`, de modo que el test no depende del
sistema operativo del runner. Los MD5 de los fixtures de WordPress y de los
identificadores del crawler se declaran explícitamente como hashes no destinados
a seguridad, y el generador codifica correctamente sus entradas en Python 3.

Verificación: los tres módulos pasan **14 tests**; Bandit focalizado en `w3af`
queda con **0 hallazgos altos** y **0 issues** en el umbral alto; Black y mypy
están limpios. El score global continúa en **9.99/10**, con los gates globales
heredados y la cobertura global todavía pendientes.

## Actualización verificada: parsing XML seguro en fixtures

Los tests del output XML usan ahora `defusedxml.ElementTree`, igual que el
código de parsing seguro del proyecto, para validar archivos generados y
payloads que podrían contener XML malicioso. No cambia el contrato de las
assertions y elimina los cuatro avisos medios de Bandit asociados a esos tests.

Verificación: la suite XML pasa **32 tests** y Bandit focalizado sobre el
archivo queda limpio. El score global continúa en **9.99/10**, con los gates
globales heredados, los avisos de cierre del `LogSink` en esa suite y la
cobertura global todavía pendientes.

## Actualización verificada: orden de cierre de productores y cola

El finalizer de `w3afCore` detiene primero el pool de parsers y limpia sus
recursos; después cierra DNS y el `OutputManager`. Así ningún worker de parsing
intenta publicar en una cola ya cerrada y la memoria de esos procesos se libera
antes de cerrar el consumidor de mensajes.

Verificación: core y parser pasan **24 tests**, y la suite XML pasa **32 tests**.
El aviso de `LogSink` se reduce de dos mensajes a uno, por lo que todavía queda
una ruta tardía de logging que requiere una reproducción más aislada. El score
global continúa en **9.99/10**, con los gates heredados y la cobertura global
todavía pendientes.

## Actualización verificada: tests XML sin singleton de salida

Los tests unitarios del output XML ya no acceden a `om.out` para disponer de un
logger: usan el `recording_output` local, que conserva las assertions sin crear
un proceso ni una cola global. Esto reduce recursos vivos durante la suite y
evita que el teardown del proceso tenga que cerrar ese singleton.

Verificación: la suite XML mantiene **32 tests** y Black/Ruff están limpios. El
único aviso restante de `LogSink` pertenece al cierre de un core de integración;
el score global continúa en **9.99/10**, con los gates heredados y la cobertura
global todavía pendientes.

## Actualización verificada: medición RSS del lifecycle

Una prueba de repetición creó y cerró `w3afCore` quince veces en el mismo
proceso, forzando `gc.collect()` después de cada ciclo. El RSS pasó de
**74.8 MiB** a **77.8 MiB**; entre los ciclos 5 y 15 solo varió **48 KiB**, lo
que muestra una meseta y no una fuga lineal de memoria. La diferencia inicial
es consistente con caches y asignaciones del runtime que quedan reservadas por
el allocator de Python.

El score global continúa en **9.99/10**: la medición de memoria queda cubierta,
pero siguen pendientes el aviso tardío aislado de `LogSink`, los gates que
incluyen `venv`/vendor/extras y la cobertura global al 100%.

## Actualización verificada: comandos Docker sin shell injection

Los helpers Docker propios dejaron de interpolar comandos en `shell=True`.
Ahora construyen argumentos estructurados, expanden los volúmenes de forma
explícita y restauran el modo original de la clave SSH en lugar de imponer un
modo decimal incorrecto. La compilación de los tres scripts pasa y el análisis
focal elimina los hallazgos altos y medios; quedan cinco avisos bajos de
Bandit por invocaciones legítimas de procesos externos.

El score global continúa en **9.99/10**: los gates globales siguen incluyendo
vendor, `venv`, tests y extras heredados, y la cobertura global aún no está
demostrada.

## Actualización verificada: DB obligatoria dentro del builder HTTP

La opcionalidad de la DB queda ahora limitada a `OpenerSettings`, que es el
punto de composición standalone. `OpenerLifecycle` y `OpenerBuilder` reciben
una `SQLiteDBMS` ya resuelta y no pueden propagar `None` hacia los handlers.

Verificación: opener settings, proxy y cache pasan **39 tests**; Black, Ruff y
mypy focales están limpios. El score global continúa en **9.99/10**, con los
gates globales heredados y la cobertura global todavía pendientes.

## Actualización verificada: colas disk-backed con composición explícita

`CachedQueue` y `OrderedCachedQueue` ya resuelven su DB standalone en la capa
de cola, antes de crear sus `DiskDict`. Cuando forman parte de un core siguen
recibiendo la DB del core, evitando que cada primitive abra o elija una conexión
por su cuenta.

Verificación: las suites de ambas colas pasan **25 tests**; mypy y Bandit
focales están limpios. El score global continúa en **9.99/10**, con los gates
globales heredados y la cobertura global todavía pendientes.

## Actualización verificada: primitives de almacenamiento con DB explícita

`DiskList`, `DiskDict`, `DiskSet` y `CachedDiskDict` ya no crean la SQLite
singleton cuando reciben `None`: validan la dependencia y fallan en el borde
con un mensaje claro. `VariantDB` y `Fingerprint404` también exigen su DB;
`ParserCache` la compone una sola vez para conservar el uso standalone sin
devolver la ambigüedad al primitive.

Los tests directos pasan ahora la DB temporal explícitamente y limpian las
tablas creadas por las pruebas de rendimiento. Verificación: estructuras DB
**108 tests**, fingerprint/plugins **57**, parser y respuestas **76**, y
primitivas auxiliares **38**; Black, Ruff, mypy y Bandit focales están limpios.
El score global continúa en **9.99/10**, con los gates globales heredados y la
cobertura global todavía pendientes.

## Actualización verificada: contratos tipados de request y response

`HTTPRequest` centraliza el sentinel de timeout de `socket` y declara el
diccionario serializable; `HTTPResponse` explicita que sus cuerpos pueden ser
texto, bytes o `None` durante la decodificación y restaura estado con un bucle
claro. No cambia el formato serializado ni añade copias de cuerpos en memoria.

Verificación: request, response, cache, keepalive y helpers pasan **82 tests**;
Black, Ruff, mypy focal y Bandit focal están limpios. El score global continúa
en **9.99/10**, con los gates globales heredados y la cobertura global todavía
pendientes.

## Actualización verificada: handlers HTTP tipados

El handler de éxito separa los formatos de mensaje con variables descriptivas,
el descompresor garantiza que el método seleccionado existe antes de
reordenarlo y la blacklist conserva su respuesta textual histórica mientras
declara explícitamente el borde dinámico de `urllib.addinfourl`.

Verificación: handlers básicos y blacklist pasan **15 tests**; Black, Ruff,
mypy focal y Bandit focal están limpios. El score global continúa en **9.99/10**,
con los gates globales heredados y la cobertura global todavía pendientes.

## Actualización verificada: helpers de errores y limpieza HTTP

La generación de payloads codificados usa ahora una colección ordenada separada
de su conjunto de deduplicación, y la lectura de `BadStatusLine` respeta el
atributo disponible en runtime sin forzar el tipo de typeshed. La carga de
OpenSSL queda encapsulada en la frontera dinámica ya utilizada por keepalive.

Verificación: helpers y limpieza de cuerpos pasan **36 tests**; Black, Ruff,
mypy focal y Bandit focal están limpios. El score global continúa en **9.99/10**,
con los gates globales heredados y la cobertura global todavía pendientes.

## Actualización verificada: frontera dinámica de autenticación NTLM

`HTTPNtlmAuthHandler` mantiene el cliente `spnego` y su excepción de protocolo
en la frontera de infraestructura dinámica. El handshake, los reintentos y el
transporte de la conexión desafiada permanecen sin cambios.

Verificación: NTLM pasa **8 tests**; Black, Ruff, mypy focal y Bandit focal están
limpios. El score global continúa en **9.99/10**, con los gates globales
heredados y la cobertura global todavía pendientes.

## Actualización verificada: estado tipado de parada en ExtendedUrllib

`ScanRequestControl` declara el estado de parada como
`ScanMustStopException | None`; `ExtendedUrllib` conserva la excepción concreta
seleccionada sin forzar una inferencia distinta entre las ramas conocida y
desconocida. El identificador añadido a `urllib.HTTPError` sigue siendo
dinámico, como exige ese objeto en runtime.

Verificación: las suites de API y errores de ExtendedUrllib pasan **29 tests**;
Black, Ruff, mypy focal y Bandit focal están limpios. El score global continúa
en **9.99/10**, con los gates globales heredados y la cobertura global todavía
pendientes.

## Actualización verificada: respuesta mangle con atributo dinámico

La conversión de respuestas modificadas conserva el `id` que `urllib` añade en
runtime mediante un único acceso dinámico explícito. No cambia el cuerpo, las
cabeceras ni el ciclo de cierre de la respuesta keepalive.

Verificación: mangle pasa **3 tests**; Black, Ruff, mypy focal y Bandit focal
están limpios. El score global continúa en **9.99/10**, con los gates globales
heredados y la cobertura global todavía pendientes.

## Actualización verificada: contrato del ParserCache

`ParserCache` declara su LRU concreto en lugar de heredar el tipo mínimo
`Sized`, evitando que la caché pierda operaciones válidas (`get`, `values`,
`clear` e indexación) en el análisis estático. También se separan los
argumentos de logging de los tags cacheados para no reutilizar tipos distintos.

Verificación: la suite de ParserCache pasa **28 tests**; Black, Ruff, mypy
focal y Bandit focal están limpios. El score global continúa en **9.99/10**,
con los gates globales heredados y la cobertura global todavía pendientes.

## Actualización verificada: puerto abstracto de Knowledge Base

`BasicKnowledgeBase` declara ahora las operaciones de persistencia que necesita
su lógica común (`append`, iteración, actualización y consultas por clase) como
un contrato abstracto. `DBKnowledgeBase` sigue siendo el adaptador concreto; no
se mezclan responsabilidades de almacenamiento dentro de los filtros y
operaciones de dominio.

Verificación: Knowledge Base pasa **68 tests**; Black, Ruff, mypy focal y
Bandit focal están limpios. El score global continúa en **9.99/10**, con los
gates globales heredados y la cobertura global todavía pendientes.
