# Sistema Web de Votaciones · Festival de la Leyenda Vallenata 2027

Proyecto académico de la asignatura **Desarrollo Web** (Areandina).
Aplicación web en **Python + Django (patrón MVT) + MySQL** para que el público vote en las
categorías del Festival. Estructura configurable:

```
EDICIÓN → CATEGORÍA → VOTACIÓN (subevento) → OPCIÓN        y        VOTO (usuario + opción)
```

**Regla central:** cada usuario puede elegir **una sola opción por categoría y edición**.
Puede votar en otras categorías, pero no emitir un segundo voto en la misma categoría,
aunque esta tenga varias votaciones (subeventos).

## Tecnologías y versiones

| Componente | Versión probada |
|---|---|
| Python | 3.13 (funciona con 3.11 o superior) |
| Django | 5.2 |
| Base de datos | MySQL 8 (también probado con MariaDB 10.11) |
| Conector MySQL | mysqlclient 2.2+ |
| Otras dependencias | python-dotenv, Pillow (ver `requirements.txt`) |
| Interfaz | HTML5, Bootstrap 5.3 (incluido en `static/`), diseño para celular primero |

## Funcionalidades

| Entrega | Funcionalidad | Archivo principal |
|---|---|---|
| 2 | Ediciones, categorías, votaciones y opciones en MySQL | `votaciones/models.py` |
| 2 | Registro, inicio y cierre de sesión | `cuentas/` |
| 2 | Administración con Django Admin | `votaciones/admin.py` |
| 3 | **Modelo `Voto`** con restricción única (usuario, edición, categoría) | `votaciones/models.py` (clase `Voto`) |
| 3 | **Registro de voto**: seleccionar → confirmar → validar → guardar | `votaciones/views.py`, `votaciones/servicios.py` |
| 3 | **Validaciones del servidor** y control de duplicados/concurrencia | `votaciones/servicios.py` |
| 3 | **Mis votos**: categorías votadas y pendientes | `votaciones/views.py` → `mis_votos` |
| 3 | **Consulta administrativa de votos** (solo lectura) | `votaciones/admin.py` → `VotoAdmin` |
| 3 | **API `GET /api/categorias/`** en JSON | `votaciones/api.py` |
| 3 | Pruebas CP-01 a CP-10 | `votaciones/test_entrega3.py` |
| 4 | **Resultados**: conteo por opción calculado en MySQL (el público ve solo votaciones cerradas; el administrador ve también las abiertas) | `votaciones/views.py` → `resultados` |
| 4 | **Duplicar edición** para el año siguiente desde el admin (categorías, votaciones y opciones, sin votos, en borrador) | `votaciones/admin.py` → `duplicar_edicion` |
| 4 | **API JSON ampliada** (resumen, ediciones, categorías, votaciones, resultados y mis votos) | `votaciones/api.py` |
| 4 | **Panel de datos** (`/panel/`): visualización dinámica con JavaScript que consume la API y se refresca cada 15 s, sin librerías externas | `templates/votaciones/panel.html`, `static/js/panel.js` |

### Dónde se controla la unicidad de votos

1. **Base de datos (MySQL):** `votaciones/models.py`, clase `Voto`, `Meta.constraints` →
   `UniqueConstraint(fields=["usuario", "edicion", "categoria"], name="un_voto_por_usuario_categoria_edicion")`.
   Aplicada por la migración `votaciones/migrations/0002_voto.py`.
2. **Django:** `votaciones/servicios.py` → `validar_voto()` (rechaza si ya hay voto en la categoría) y
   `registrar_voto()` (transacción con `select_for_update()` sobre el usuario + captura de `IntegrityError`).

### Dónde está la API

`votaciones/api.py`; las rutas están en `votaciones/urls.py`. Todas son de solo lectura (GET) y
responden JSON; un POST recibe 405 y los errores tienen la forma `{"error": "..."}`.

| URL | Descripción | Acceso |
|---|---|---|
| `/api/categorias/` (`?edicion=2027`) | Categorías con sus votaciones y opciones | Público |
| `/api/resumen/` | Totales, votaciones por estado, participación por votación | Público |
| `/api/ediciones/` | Ediciones publicadas | Público |
| `/api/ediciones/<año>/categorias/` | Categorías activas de una edición | Público |
| `/api/categorias/<id>/votaciones/` | Votaciones visibles de una categoría | Público |
| `/api/votaciones/<id>/` | Detalle y opciones activas (`ya_voto_en_categoria` si hay sesión) | Público |
| `/api/votaciones/<id>/resultados/` | Votos y porcentaje por opción | Votación **cerrada**: público. Abierta o próxima: solo `is_staff` (403 para los demás) |
| `/api/mis-votos/` | Votos del usuario con sesión | Requiere sesión (401 si no) |

La regla de resultados es la misma de la página `/resultados/` (`puede_ver_resultados` en `views.py`):
el conteo parcial no se publica mientras se vota, para no influir en quienes aún no han votado.
`ya_voto_en_categoria` respeta la regla central: votar en cualquier subevento de la categoría cuenta.

## Instalación y ejecución

```bash
# 1. Clonar el repositorio
git clone <URL-DEL-REPOSITORIO>
cd festival-votaciones

# 2. Crear y activar entorno virtual
python -m venv venv
venv\Scripts\activate            # Windows (si PowerShell bloquea el script:
                                 #   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass)
# source venv/bin/activate       # Linux / macOS

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

El segundo `GRANT` permite que `manage.py test` cree la base temporal de pruebas.

### 5. Variables de entorno

```bash
copy .env.example .env           # Windows
# cp .env.example .env           # Linux / macOS
```

Edite `.env` y escriba `DB_PASSWORD` y una `DJANGO_SECRET_KEY` propia.
**El archivo `.env` nunca se sube al repositorio** (está en `.gitignore`).

### 6. Migraciones, datos de prueba y administrador

```bash
python manage.py migrate
python manage.py cargar_datos_prueba          # use --reiniciar para borrar y recargar
python manage.py createsuperuser
python manage.py runserver
```

`cargar_datos_prueba` crea 3 ediciones, 7 categorías, 7 votaciones, 16 opciones y algunos votos de
**votantes ficticios sin contraseña** (no pueden iniciar sesión; solo sirven para la consulta
administrativa). Para votar, registre su propio usuario en `/cuentas/registro/`.

| Dirección | Para qué |
|---|---|
| <http://127.0.0.1:8000/> | Sitio público |
| <http://127.0.0.1:8000/mis-votos/> | Participación del usuario |
| <http://127.0.0.1:8000/resultados/> | Resultados por categoría |
| <http://127.0.0.1:8000/panel/> | Panel de datos (visualización dinámica) |
| <http://127.0.0.1:8000/api/categorias/> | API JSON |
| <http://127.0.0.1:8000/admin/> | Administración (votos en *Votaciones → Votos*) |

### ¿Ya tenía la base de datos creada con una versión anterior?

La migración `0002_voto` cambió (el voto ahora lleva edición y categoría). Si su base MySQL ya había
aplicado la versión anterior, el sitio falla con `Unknown column 'votaciones_voto.edicion_id'`.
Arréglelo así (**se borran los votos existentes**, que en esa versión eran solo de prueba):

```bash
python manage.py migrate votaciones 0001   # elimina la tabla de votos antigua
python manage.py migrate                   # la crea con el esquema nuevo
python manage.py cargar_datos_prueba       # opcional: vuelve a cargar los datos de ejemplo
```

También sirve borrar y recrear la base (`DROP DATABASE festival_votaciones;` y repetir el paso 4).

## Rutas

| Método | URL | Descripción |
|---|---|---|
| GET | `/` | Edición vigente, votaciones abiertas y próximas |
| GET | `/ediciones/`, `/ediciones/<año>/` | Ediciones y sus categorías |
| GET | `/categorias/<id>/` | Votaciones (subeventos) de una categoría |
| GET | `/votaciones/<id>/` | Detalle y formulario de votación |
| POST | `/votaciones/<id>/votar/` | Paso 1: valida la opción y muestra la confirmación (no guarda) |
| POST | `/votaciones/<id>/confirmar/` | Paso 2: valida de nuevo y registra el voto en MySQL |
| GET | `/mis-votos/` | Categorías votadas y pendientes (requiere sesión) |
| GET | `/resultados/` | Resultados por categoría y votación (filtro `?edicion=2025`) |
| GET | `/panel/` | Panel de datos dinámico (consume la API con `fetch`) |
| GET | `/api/...` | API JSON de solo lectura (ver tabla de la API) |
| GET/POST | `/cuentas/registro/`, `/cuentas/ingresar/`, `/cuentas/salir/` | Autenticación |

Los dos POST de votación exigen sesión iniciada y token CSRF.

## Validaciones del servidor al votar

| Validación | Respuesta |
|---|---|
| Usuario sin sesión | Redirige a inicio de sesión; no se registra nada |
| Votación no abierta (próxima, cerrada, en borrador o categoría inactiva) | Rechazo con mensaje |
| Opción inexistente, inactiva o de otra votación/categoría | Rechazo con mensaje |
| Ya votó en esa categoría (en cualquier subevento) | Rechazo con mensaje |
| Dos o más solicitudes simultáneas | Solo una se registra (bloqueo + restricción única) |
| POST sin token CSRF | 403 |

## Pruebas

```bash
python manage.py test -v 2                          # todas (61)
python manage.py test votaciones.test_entrega3 -v 2  # CP-01 a CP-10 (13)
python manage.py test votaciones.test_entrega4 -v 2  # resultados y duplicar edición (6)
python manage.py test votaciones.test_api_panel -v 2 # API ampliada y panel (19)
```

Prueba de concurrencia por HTTP contra el servidor en ejecución (CP-09). Use un usuario que no haya
votado en la categoría; los ids se consultan en `/api/categorias/`:

```bash
python scripts/prueba_concurrencia_http.py --email su_correo@ejemplo.com \
    --intento 2:5 --intento 3:8 --intento 2:6 --intento 3:9
```

## Seguridad

- Las credenciales se leen de `.env` (no incluido). En el repositorio solo está `.env.example`.
- Contraseñas con hash PBKDF2 de Django. Formularios con CSRF. Cierre de sesión por POST.
- Los votos no se pueden crear, editar ni borrar desde el admin.
- La API es de solo lectura y no expone datos de otros usuarios; `/api/mis-votos/` solo devuelve los del usuario con sesión.
- El panel inserta los datos con `textContent` (nunca `innerHTML`), así que un texto con HTML en la base de datos no se ejecuta.
- Todos los datos de prueba son ficticios.

## Mejoras pendientes

Bloqueo por intentos fallidos de inicio de sesión, verificación de correo,
auditoría avanzada, pruebas de carga y despliegue.

## Integrantes

- Jorge Alberto Díaz Peña
- Jordi Marín Sepúlveda
- Michael Esteven Campos León
