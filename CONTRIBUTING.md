# Contribuir y continuar el desarrollo

## Antes de trabajar

1. Leer `PROJECT_STATE.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `ROADMAP.md` y `SESSION_STATE.md`.
2. Revisar `git status --short --branch`, `git log --oneline --decorate -20` y las ramas remotas.
3. No inferir que una especificacion historica es el contrato actual. Verificar codigo y tests.
4. Identificar si el cambio afecta el nucleo, persistencia, CLI, cartografia o evidencia experimental.

## Entorno de desarrollo

Python 3.10 o superior. Para desarrollo completo:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[cartografia]" pytest build ruff
.venv\Scripts\ruff.exe check src\la_caja\cli.py src\la_caja\core.py tests\test_cli.py tests\test_core.py
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe -m build
```

El nucleo no depende de NetworkX ni NumPy. La extra `cartografia` instala ambas dependencias. El chequeo Ruff se aplica a los modulos modificados; el resto del repositorio conserva deuda de estilo historica.

## Reglas de implementacion

- Cada mutacion persistente debe pasar por un metodo de PiscinaPersistente y tener replay determinista.
- Toda nueva semantica debe tener pruebas que cubran el caso normal, limites y reconstruccion tras reinicio.
- La pertenencia a un nodo representa activacion; la arista explicita representa navegacion. No mezclar ambas capas.
- La traza dormida no debe alimentar navegacion ni primado. Rehidratacion solo por re-observacion real.
- Cartografia es de solo lectura. Los candidatos no se convierten automaticamente en relaciones.
- No agregar dependencias al nucleo cuando puedan vivir en una extra opcional.
- Mantener los experimentos negativos, nulos y positivos; no borrar resultados que contradigan una hipotesis.
- No afirmar validacion organica a partir del fixture de cartografia.
- Actualizar README, ARCHITECTURE, PROJECT_STATE, CHANGELOG y ROADMAP cuando cambie el contrato o el estado del proyecto.

## Flujo de integracion

Trabajar en una rama descriptiva. Ejecutar Ruff, la suite, construir el wheel, instalarlo en un entorno limpio y probar el entry point CLI. Revisar el diff completo. La persona que implementa no debe ser la unica revisora; obtener una revision independiente antes de mergear.

## Publicacion

La version de paquete y el tag Git deben cambiar juntos. El workflow de PyPI publica al crear un tag `v*`; no crear tags de publicacion hasta que CI y wheel/sdist esten verificados.
