# Verificacion LLM de vulnerabilidades

## Resumen

Cada `Vuln` puede verificarse de forma automatica y asincrona mediante un
proveedor LLM configurable. El LLM analiza el hallazgo, propone una POC HTTP
estructurada y w3af ejecuta solo acciones limitadas al mismo origen y flujo
del hallazgo.

## Diseno

- El servicio de verificacion se conecta al `PluginRuntimeContext`, sin acoplar
  la logica de dominio a un proveedor concreto.
- Ollama, LM Studio, Grok/xAI, Gemini, OpenAI y Anthropic implementan un
  contrato HTTP comun. El proveedor activo, modelo y URL se configuran por
  opciones de escaneo; las claves solo se leen de variables de entorno.
- Las verificaciones se guardan en tablas SQLite independientes de los
  pickles de la KB, con estados `pending`, `running`, `confirmed`,
  `not_confirmed`, `inconclusive` y `failed`.
- La API REST permite consultar, reintentar y revisar la evidencia de una
  verificacion.
- Las POC no pueden ejecutar shell ni codigo arbitrario. Sus peticiones se
  limitan al mismo origen del hallazgo, con un maximo de pasos, tiempo y
  tamano de respuesta.

## Seguridad y operacion

La configuracion solicitada permite enviar datos completos, incluidas
cabeceras, cookies y tokens, al proveedor seleccionado. Esto queda advertido
explicitamente porque puede exponer credenciales a proveedores cloud.
El executor tiene workers limitados para no competir sin control con el
escaneo y se apaga junto con el core.

## Verificacion

Se cubren los proveedores, respuestas invalidas, persistencia, deduplicacion,
validacion de alcance de POC, ejecucion HTTP y endpoints REST con tests reales
contra servidores locales, sin mocks.
