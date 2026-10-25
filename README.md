# Sistema Web de Votaciones · Festival de la Leyenda Vallenata 2027

Proyecto académico de la asignatura **Desarrollo Web** (Areandina) — Entrega 2.
Aplicación web en **Python + Django (patrón MVT) + MySQL** que implementa la estructura
configurable definida en la Entrega 1:

```
EDICIÓN → CATEGORÍA → VOTACIÓN → OPCIÓN
```

## Funcionalidades de esta entrega

| Funcionalidad | Dónde está |
|---|---|
| Proyecto Django con dos aplicaciones (`cuentas`, `votaciones`) | `config/`, `cuentas/`, `votaciones/` |
| Conexión a MySQL por variables de entorno | `config/settings.py`, `.env.example` |
| Modelos relacionados y migraciones | `votaciones/models.py`, `cuentas/models.py`, `*/migrations/` |
| Registro, inicio y cierre de sesión | `cuentas/forms.py`, `cuentas/views.py`, `cuentas/backends.py` |
| Administración con Django Admin | `votaciones/admin.py` (`/admin/`) |
| Interfaz pública con datos reales de MySQL | `votaciones/views.py`, `templates/` |
| Datos de prueba | `python manage.py cargar_datos_prueba` |
| 23 pruebas automáticas | `votaciones/tests.py`, `cuentas/tests.py` |

## Requisitos

- Python 3.11 o superior
- MySQL 8 (o MariaDB 10.6+) en ejecución
- Git

## Instalación y ejecución

```bash
# 1. Clonar el repositorio
git clone <URL-DEL-REPOSITORIO>
cd festival-votaciones

# 2. Crear y activar entorno virtual
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux / macOS:
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt
```

### 4. Crear la base de datos en MySQL

Entre a MySQL como administrador (`mysql -u root -p`, MySQL Workbench o phpMyAdmin) y ejecute,
reemplazando `SU_CLAVE` por una clave propia:

```sql
CREATE DATABASE festival_votaciones CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'festival_app'@'localhost' IDENTIFIED BY 'SU_CLAVE';
GRANT ALL PRIVILEGES ON festival_votaciones.* TO 'festival_app'@'localhost';
GRANT ALL PRIVILEGES ON test_festival_votaciones.* TO 'festival_app'@'localhost';
FLUSH PRIVILEGES;
```

(El segundo `GRANT` permite que `manage.py test` cree la base de datos temporal de pruebas.)

### 5. Configurar variables de entorno

```bash
# Windows
copy .env.example .env
# Linux / macOS
cp .env.example .env
```

Edite `.env` y escriba `DB_PASSWORD` y una `DJANGO_SECRET_KEY` propia.
**Nunca suba el archivo `.env` al repositorio.**

### 6. Migrar, cargar datos y crear administrador

```bash
python manage.py migrate
python manage.py cargar_datos_prueba
python manage.py createsuperuser
python manage.py runserver
```

- Sitio público: <http://127.0.0.1:8000/>
- Administración: <http://127.0.0.1:8000/admin/>

### 7. Ejecutar las pruebas

```bash
python manage.py test -v 2
```

## Rutas principales

| URL | Vista | Descripción |
|---|---|---|
| `/` | `inicio` | Edición vigente, votaciones abiertas y próximas |
| `/ediciones/` | `ediciones` | Ediciones publicadas |
| `/ediciones/<año>/` | `edicion_detalle` | Categorías activas de la edición |
| `/categorias/<id>/` | `categoria_detalle` | Votaciones de la categoría |
| `/votaciones/<id>/` | `votacion_detalle` | Detalle, fechas, estado y opciones |
| `/cuentas/registro/` | `registro` | Crear cuenta de votante |
| `/cuentas/ingresar/` | `IngresoView` | Iniciar sesión con correo |
| `/cuentas/salir/` | `SalidaView` | Cerrar sesión (POST) |
| `/admin/` | Django Admin | Gestión de ediciones, categorías, votaciones y opciones |

## Reglas que ya aplica el sistema

- **RN-01**: cada opción pertenece a una votación, cada votación a una categoría y cada categoría a una edición.
- **RN-03 (parcial)**: una votación solo se considera abierta si su estado es *Abierta* y la fecha actual está entre apertura y cierre.
- **RN-07**: no se pueden borrar ediciones, categorías ni votaciones que tengan registros asociados (`on_delete=PROTECT`); se desactivan.
- **RN-09**: el registro exige aceptar el tratamiento de datos (Ley 1581 de 2012) y guarda la fecha de autorización.
- Lo que está en borrador o inactivo no aparece en la interfaz pública.

## Notas para MySQL en Windows

- Si `pip install mysqlclient` falla, actualice pip (`python -m pip install --upgrade pip`) y vuelva a intentar; existen ruedas precompiladas para Windows.
- No se usa `date_hierarchy` en el admin porque exige tener cargadas las tablas de zonas horarias de MySQL.

## Pendiente para próximas entregas

Modelo `Voto` con restricción única (usuario, votación), emisión y confirmación del voto (CU-04),
resultados (CU-07), bloqueo por intentos fallidos de inicio de sesión, verificación de correo,
auditoría y despliegue.

## Integrantes

- Jorge Alberto Díaz Peña
- Jordi Marín Sepúlveda
- Michael Esteven Campos León

Los datos de canciones, agrupaciones y personas cargados por `cargar_datos_prueba` son ficticios.
