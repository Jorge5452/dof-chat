---
applyTo: "**/*.py"
---
# 🛠️ Reglas para revisión de código Python (Pull Request) 🐍

## 1. Nomenclatura y estilo
- **snake_case** en funciones y variables; **PascalCase** en clases.  
- Nombres descriptivos, sin abreviaturas confusas.  
- Cumplimiento estricto de **PEP8**: indentación de 4 espacios, líneas ≤79 caracteres, comillas consistentes, espacios alrededor de operadores.

## 2. Tipado y documentación
- Uso adecuado de **typing** y comprobación con **mypy** (`def foo(x: int) -> str:`).  
- Cada función y clase debe tener **docstrings** según Google o NumPy style.  
- Archivos de módulos deben incluir descripción de propósito y dependencias.

## 3. Calidad de la lógica
- **Complejidad ciclomática**: funciones con alto cyclomatic complexity (múltiples ramas) deben refactorizarse.  
- Detectar **lógica duplicada** o muy parecida: extraer a utilidades compartidas.  
- Señalar **código muerto** o ramas de `if/else` inalcanzables.  
- Identificar **código no utilizado** (imports, variables, funciones).

## 4. Robustez y seguridad
- Verificación de condiciones de error en I/O, parseo JSON, llamadas HTTP, acceso a base de datos — usar `try/except` o validaciones previas.  
- Uso de **with** para manejo de recursos (archivos, conexiones, locks).  
- Evitar **números mágicos**: definir constantes con nombre (`MAX_RETRIES = 5`).  
- Revisar posibles vulnerabilidades: inyección de SQL, XSS, manejo de credenciales en código.

## 5. Rendimiento y eficiencia
- Señalar bucles ineficientes o comprensiones con costes altos; sugerir alternativas (itertools, generadores).  
- Revisar uso de estructuras adecuadas (list vs. set vs. dict) según complejidad de acceso.  
- Detectar operaciones repetitivas en bucles que podrían salir de ellos.

## 6. Pruebas y cobertura
- Confirmar que hay **tests unitarios** o de integración para cambios críticos.  
- Revisar que **cobertura de tests** cubra nuevos casos, especialmente bordes y errores.  
- Asegurarse de que los nombres de tests sean descriptivos y correspondan a la funcionalidad.

## 7. Mantenimiento y modularidad
- Extraer **funciones o clases** cuando crecen >50 líneas o tienen más de 3 niveles de anidación.  
- Revisar cohesión de módulos: un solo propósito por archivo/clase.  
- Confirmar que los **scripts de arranque** (`if __name__ == "__main__"`) estén bien aislados.

## 8. Dependencias y compatibilidad
- Revisar versiones de librerías en `requirements.txt` o `pyproject.toml`.  
- Verificar compatibilidad con versiones soportadas de Python (e.g., 3.8+).  
- Evitar importar paquetes innecesarios o evitar crear dependencias circulares.

## 9. Logs y métricas
- Uso de **logging** en lugar de `print()`, con niveles adecuados (DEBUG, INFO, WARNING, ERROR).  
- Verificar que no se filtren datos sensibles en logs.  
- Añadir métricas o contadores si aplica (ej.: número de reintentos, tiempo de ejecución).

## 10. Revisión de estilo de comentarios
- Comentarios claros y sólo cuando la intención no sea obvia en el código.  
- Eliminar comentarios obsoletos o incorrectos que puedan confundir.

---

❓ **Checklist opcional para el agente**  
- ¿Hay funciones duplicadas? ¿Pueden fusionarse?  
- ¿Existen pruebas que fallen o faltantes?  
- ¿Se respeta el estándar de código de la organización?  
- ¿Alguna pieza de código requiere benchmarks o profiling adicional?  
- ¿Se deben agregar ejemplos de uso o snippets en la documentación?
