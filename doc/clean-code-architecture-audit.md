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

- El árbol contiene carpetas que sugieren capas, pero `w3af.core.data` importa
  controladores desde 113 archivos (179 coincidencias de import); esto acopla
  datos/dominio con detalles de aplicación e infraestructura.
  Esto acopla datos/dominio con detalles de aplicación e infraestructura.
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

## Revisión actualizada

La puntuación global permanece en **2.5/10** (Clean Code 3/10, Clean Architecture
2/10). Se trasladaron errores DB a la capa de datos, el parser URL y la KB
perdieron dos dependencias concretas de `controllers`, y los contratos Python 3
se corrigieron. Aún así, `core.data` importa ampliamente desde `controllers` y
las gates globales Ruff/mypy/Bandit fallan.

En las suites integradas de URL, DB, histórico y KB: **203 pasaron, 3 fueron
omitidas y no hubo fallos**. El archivo URL pasa con 113 pruebas y 2 omitidas;
las pruebas de caché, query strings, shell IDs y RFI también pasan en conjunto.
Persisten dos warnings de dependencias `ldap3/pyasn1`; no se suprimieron.

Esta verificación no cubre la suite completa ni acredita cobertura global del
100%. Quedan los defectos de lint/tipos/seguridad, y pruebas de plugins que
requieren el ejecutable externo `retire`.

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
