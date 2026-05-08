# JDK Switcher

JDK Switcher es una aplicación de escritorio para Windows que detecta automáticamente los JDK instalados en el equipo y permite cambiar `JAVA_HOME` con un click.

La app está hecha en Python con `tkinter`, no requiere permisos de administrador y modifica únicamente las variables de entorno del usuario actual.

## Características

- Detecta instalaciones locales de JDK automáticamente.
- Permite activar un JDK desde una interfaz gráfica simple.
- Actualiza `JAVA_HOME` del usuario.
- Actualiza el `Path` del usuario para usar `%JAVA_HOME%\bin`.
- No modifica variables de entorno del sistema.
- No requiere permisos de administrador.
- Incluye build portable como `.exe` usando PyInstaller.

## Capturas

Agrega aquí una captura si quieres mostrar la interfaz en GitHub:

```markdown
![JDK Switcher](docs/screenshot.png)
```

## Uso

### Opción recomendada: ejecutable

Descarga `JDKSwitcher.exe` desde la sección de Releases del repositorio y ejecútalo.

Después de activar un JDK, abre una terminal nueva y verifica:

```powershell
java -version
echo $env:JAVA_HOME
```

### Desde código fuente

Requisitos:

- Windows
- Python 3.11 o superior

Ejecutar:

```powershell
python jdk_switcher.py
```

También puedes usar el lanzador:

```powershell
.\run_jdk_switcher.bat
```

## Crear el ejecutable

Instala PyInstaller:

```powershell
python -m pip install pyinstaller
```

Genera el `.exe`:

```powershell
python -m PyInstaller --onefile --windowed --name "JDKSwitcher" "jdk_switcher.py"
```

El ejecutable queda en:

```text
dist\JDKSwitcher.exe
```

## Qué modifica

La aplicación modifica variables de entorno del usuario actual:

- `JAVA_HOME`: apunta al JDK seleccionado.
- `Path`: agrega `%JAVA_HOME%\bin` al inicio del `Path` de usuario y elimina entradas previas de JDK detectadas en el mismo `Path` de usuario.

No modifica el `Path` del sistema ni requiere permisos de administrador.

## Detección automática

Busca JDK válidos en rutas comunes como:

- `C:\Program Files\Java`
- `C:\Program Files\Eclipse Adoptium`
- `C:\Program Files\Amazon Corretto`
- `C:\Program Files\Microsoft`
- `C:\Program Files\Zulu`
- `JAVA_HOME` actual
- entradas existentes del `PATH`

Un directorio se considera JDK válido si contiene:

- `bin\java.exe`
- `bin\javac.exe`

## Limitaciones

- El cambio aplica a terminales, IDEs y procesos abiertos después del switch.
- Las aplicaciones ya abiertas no reciben el nuevo `JAVA_HOME`; reinícialas si hace falta.
- Si existe una ruta Java en el `Path` del sistema con mayor prioridad, algunos procesos podrían seguir tomando esa ruta para `java`. Las herramientas que respetan `JAVA_HOME` sí usarán el JDK seleccionado.

## Qué subir a GitHub

Recomendado para el repositorio:

- `jdk_switcher.py`
- `run_jdk_switcher.bat`
- `README.md`
- `.gitignore`

No recomendado para commits normales:

- `dist/`
- `build/`
- `*.spec`
- `__pycache__/`

El `.exe` conviene publicarlo como asset de una Release de GitHub, no commitearlo al repositorio. Así el código fuente queda limpio y los usuarios pueden descargar el binario desde Releases.

## Publicar en GitHub

Inicializa el repo local:

```powershell
git init
git add jdk_switcher.py run_jdk_switcher.bat README.md .gitignore
git commit -m "Add JDK Switcher desktop app"
```

Crea un repositorio vacío en GitHub y conecta el remoto:

```powershell
git branch -M main
git remote add origin https://github.com/TU_USUARIO/JDKSwitch.git
git push -u origin main
```

Para publicar el ejecutable:

1. En GitHub, entra al repositorio.
2. Ve a `Releases`.
3. Crea una nueva release, por ejemplo `v1.0.0`.
4. Adjunta `dist\JDKSwitcher.exe` como archivo descargable.
5. Publica la release.

## Licencia

Define una licencia antes de publicar si quieres que otros puedan usar o modificar el proyecto. Una opción común para proyectos pequeños es MIT.
