# Estia — Smart Text Intelligence Analytics

[![CI](https://github.com/andres-en/estia-text-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/andres-en/estia-text-analytics/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3-000000?logo=flask)
![MySQL](https://img.shields.io/badge/MySQL-8.4-4479A1?logo=mysql&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)

*[Read in English](README.md)*

Analítica de conversaciones para chatbots de ventas de WhatsApp: una plataforma web multi-cliente que ingiere los exportes CDR (registro de detalle) de un chatbot de
ventas de WhatsApp, los reconstruye como conversaciones limpias y clasifica cada una con una
**cascada que usa primero reglas y después IA**, para que los equipos de negocio obtengan métricas
confiables del embudo (leads, fugas, fallos del bot) en lugar de una hoja con miles de filas
desordenadas.

> **Versión de portafolio.** Es una copia anonimizada de un sistema usado en producción. Se
> reemplazaron los nombres de la empresa y de los clientes, y los datos de ejemplo en
> `data/samples/` son sintéticos (`scripts/generate_sample_data.py`).

<!-- Capturas: agregar imágenes en docs/screenshots/ y descomentar.
![Dashboard](docs/screenshots/dashboard.png)
![Detalle de conversación](docs/screenshots/conversation.png)
-->

## Puntos destacados

- **Pipeline de ingesta idempotente.** Validación del Excel → copia cruda de auditoría
  (`staging_messages`) → `conversations` / `messages` estructurados. Reimportar el mismo archivo
  nunca duplica datos: las conversaciones son únicas por sesión y los mensajes se deduplican con un
  hash de su contenido.
- **Primero reglas, después IA.** Las reglas determinísticas clasifican ~98% de las conversaciones;
  solo la zona gris llega al LLM (OpenAI, salida JSON estructurada). Cada resultado guarda *cómo* se
  decidió (`RULE` o `AI`), qué regla se aplicó y la justificación del modelo: el objetivo es la
  **auditabilidad**. Los criterios y cómo se validaron están en
  [docs/classification-criteria.es.md](docs/classification-criteria.es.md).
- **Configurable por campaña.** Cada campaña tiene su propio esquema de clasificación (categorías,
  indicadores, árbol de decisión). Un administrador puede describir la campaña en lenguaje natural,
  obtener un borrador generado por el LLM y revisarlo antes de guardarlo.
- **Multi-cliente por diseño.** Una base de control guarda usuarios, roles y clientes; cada cliente
  tiene **su propia base de datos**, creada y migrada automáticamente desde la administración.
- **Seguridad.** Login con Google OAuth, cookies de sesión, control de acceso por permisos (super
  admin / admin / usuario) y aislamiento de datos por cliente. En producción la app no arranca sin
  `SECRET_KEY`.
- **Visibilidad de costos.** Se registran por cliente los tokens y el costo estimado de cada llamada
  a la IA.
- **Operación.** Análisis en segundo plano con progreso, exportación a Excel, script de retención
  para la tabla de auditoría y especificación OpenAPI 3 con Swagger UI en `/api/docs`.

## Arquitectura

```mermaid
flowchart LR
    user([Analista / Admin]) -->|navegador| spa[SPA React<br/>Vite · Tailwind · Recharts]
    spa -->|JSON /api| api[API Flask<br/>gunicorn]
    api -->|Google OAuth| google[(Google)]
    api --> control[(Base de control<br/>usuarios · roles · clientes)]
    api --> tenant[(Base por cliente<br/>imports · conversations · messages · analysis)]

    subgraph Ingesta
        xlsx[/Excel CDR/] --> reader[Lector de Excel<br/>+ validación] --> builder[Constructor de conversaciones<br/>normaliza · clasifica filas · deduplica]
    end
    api -- carga --> xlsx
    builder --> tenant

    subgraph clasificacion [Clasificación — hilo en segundo plano]
        rules[Reglas determinísticas] -->|solo zona gris| llm[OpenAI<br/>salida estructurada]
    end
    tenant --> rules
    rules --> tenant
    llm --> tenant
```

En producción, la API y el frontend compilado se sirven desde el mismo proceso Flask (una sola
imagen Docker con build multi-etapa). En desarrollo, Vite corre aparte y redirige `/api` a Flask.

## Stack

| Capa | Tecnologías |
|---|---|
| Backend | Python 3.12, Flask 3, SQLAlchemy 2, gunicorn |
| Datos | MySQL 8 (base de control + una base por cliente), SQLite para tests |
| IA | API de OpenAI con salidas estructuradas por JSON schema |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, TanStack Table, Recharts |
| Autenticación | Google OAuth 2.0, sesiones de Flask, modelo de roles y permisos |
| Calidad | pytest (unitarios, integración, API y MySQL), ruff, test de contrato OpenAPI |
| Entrega | Docker (multi-etapa), Docker Compose, GitHub Actions |

## Cómo empezar

### Con Docker Compose (recomendado)

```bash
cp .env.example .env            # definir SECRET_KEY y las credenciales de Google OAuth
docker compose up --build
docker compose exec web python scripts/create_super_admin.py tu@ejemplo.com "Tu Nombre"
```

Abrir <http://localhost:5050> e iniciar sesión con esa cuenta de Google. Crear un cliente desde la
pestaña **Settings** y cargar `data/samples/sample_cdr.xlsx`.

### Desarrollo local

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt && pip install -e .
cp .env.example .env

python -m clasificador.webapp                     # API en http://localhost:5050
cd frontend && npm install && npm run dev         # UI en http://localhost:5173 (redirige /api)
```

La importación y la clasificación también se pueden correr por línea de comandos:

```bash
python -m clasificador.cli data/samples/sample_cdr.xlsx --db-url sqlite:///./demo.db --create-tables
python -m clasificador.analysis.cli --db-url sqlite:///./demo.db --sin-ia     # solo reglas, sin llamar a la API
python -m clasificador.analysis.cli --db-url sqlite:///./demo.db --dry-run    # muestra qué iría a la IA
```

## Configuración

Toda la configuración viene de variables de entorno (ver [.env.example](.env.example)).

| Variable | Obligatoria | Descripción |
|---|---|---|
| `SECRET_KEY` | Sí (producción) | Firma la cookie de sesión. `python -c "import secrets; print(secrets.token_hex(32))"` |
| `CONTROL_DB_URL` | Sí (fuera de Compose) | URL de SQLAlchemy de la base de control. Compose usa por defecto el MySQL incluido |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Sí | Cliente de Google OAuth. URI de redirección: `http://<host>:<puerto>/api/auth/google/callback` |
| `OPENAI_API_KEY` | No | Activa la capa de IA. Sin ella, las reglas funcionan y la zona gris queda pendiente |
| `OPENAI_MODEL` | No | Por defecto `gpt-4o-mini` |
| `FLASK_HOST` / `FLASK_PORT` | No | Por defecto `127.0.0.1:5050` (`0.0.0.0` dentro de Docker) |
| `MYSQL_ROOT_PASSWORD` | No | Contraseña root del contenedor MySQL incluido |

## API

El contrato completo está en [`openapi.yaml`](src/clasificador/webapp/openapi.yaml) y se puede
explorar en **`/api/docs`** (Swagger UI) con la app corriendo. Endpoints principales:

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/auth/google/login` | Inicia el flujo de Google OAuth |
| `GET` | `/api/auth/me` | Usuario actual, permisos y clientes permitidos |
| `POST` | `/api/auth/session/cliente-activo` | Cambia el cliente activo |
| `POST` | `/api/upload` | Importa un Excel CDR e inicia la clasificación en segundo plano |
| `GET` | `/api/analyze/status` | Progreso de la clasificación en segundo plano |
| `GET` | `/api/conversations` | Lista de conversaciones paginada y filtrable |
| `GET` | `/api/conversations/export` | Exportación a Excel de la lista filtrada |
| `GET` | `/api/conversations/{session_id}` | Transcripción y clasificación completas de una conversación |
| `GET` | `/api/dashboard` | Indicadores de negocio, distribución por categoría y tendencia diaria |
| `GET/POST` | `/api/admin/clientes` | Clientes (crear uno aprovisiona su base de datos) |
| `GET/POST` | `/api/admin/usuarios` | Usuarios y sus clientes asignados |
| `GET/POST` | `/api/admin/campanas` | Campañas y sus esquemas de clasificación |
| `POST` | `/api/admin/campanas/generar-esquema` | Genera un borrador de esquema a partir de una descripción en lenguaje natural |
| `GET` | `/api/admin/uso-ia` | Uso de tokens de IA y costo estimado |

## Modelo de datos

- **Base de control:** `roles`, `usuarios`, `clientes` y la asignación usuario↔cliente.
- **Base de cada cliente** (esquema en [`sql/ddl.sql`](sql/ddl.sql)): `imports`, `staging_messages`
  (copia cruda de auditoría de cada fila), `conversations`, `messages`, `conversation_analysis`
  (categoría, señales, método, justificación), `campanas` y `ai_usage`.

Reglas de ingesta importantes:

- El formato del `SESSION_ID` distingue las conversaciones reales de los mensajes proactivos
  masivos; `CONN_ID` es solo una verificación cruzada y genera una advertencia, no un error, si no
  coinciden.
- Una conversación puede abarcar varios `CONN_ID`; `ended_at` siempre cubre la última fila de la
  sesión.
- `end_exit_chat` se guarda como evento `SYSTEM`, nunca como texto del bot.
- Los teléfonos siempre se normalizan a texto (soporta notación científica y artefactos de coma
  flotante).

## Pruebas

```bash
pytest                                  # unitarias, integración y API sobre SQLite
pytest --cov=clasificador               # con cobertura
MYSQL_TEST_URL=mysql+mysqlconnector://root:root@127.0.0.1:3306 pytest -m mysql   # MySQL real
```

La suite cubre cada regla de ingesta por separado, una importación de punta a punta de la muestra
sintética, la idempotencia al reimportar, la capa de reglas del clasificador, la autorización (quién
puede llegar a qué endpoint y a qué cliente), el aprovisionamiento de clientes en MySQL real y un
test de contrato que valida `openapi.yaml`. El CI ejecuta lint, los tests contra un servicio MySQL,
el build del frontend y el build de Docker en cada push.

## Estructura del proyecto

```
src/clasificador/
├── excel_reader.py · normalizer.py · row_classifier.py · message_classifier.py
├── conversation_builder.py      # agrupación, orden, deduplicación
├── importer.py                  # orquestador de la ingesta de punta a punta
├── analysis/                    # cascada reglas → IA, esquemas configurables, costos
├── control_db/                  # usuarios, roles, permisos, clientes
├── db/                          # modelos de cada cliente y repositorio idempotente
└── webapp/                      # API Flask, autenticación, multi-cliente, OpenAPI + Swagger UI
frontend/                        # SPA React + TypeScript
sql/ddl.sql                      # esquema de cada cliente
scripts/                         # alta del super admin, migraciones, retención, validación de IA, datos de ejemplo
tests/
```

## Notas de mantenimiento

- `staging_messages` nunca se deduplica (es la auditoría) y crece con cada carga. Conviene purgar las
  filas viejas periódicamente: `python scripts/purge_staging_messages.py --dry-run` y luego sin
  `--dry-run` (retención por defecto: 180 días).
- Con los índices actuales, MySQL maneja sin problema unos pocos millones de conversaciones. Más allá
  de eso, el siguiente paso serían tablas de agregados diarios para el dashboard.

## Autor

**Andres Estepa** — [github.com/andres-en](https://github.com/andres-en)

## Licencia

© 2026 Andres Estepa. Todos los derechos reservados. El código se publica con fines de portafolio;
no se otorga licencia para usarlo, copiarlo, modificarlo ni distribuirlo.
