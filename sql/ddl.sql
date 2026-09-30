-- Esquema para la automatización de ingesta de conversaciones CDR de WhatsApp.
-- Ver Documento_Levantamiento_Automatizacion_CDR_WhatsApp.md para el contexto de negocio.
-- Esta es la base de datos de UN cliente (una base por cliente, ver
-- sql/control_ddl.sql para la base de identidad/asignación compartida).

CREATE TABLE IF NOT EXISTS campanas (
    id_campana      BIGINT AUTO_INCREMENT PRIMARY KEY,
    nombre_campana  VARCHAR(150) NOT NULL,
    fecha_inicio    DATE NULL,
    estado          VARCHAR(50) NOT NULL DEFAULT 'ACTIVA',
    -- Parámetros de detección de señales (botones, regex de plantillas del bot,
    -- cortesías) para esta campaña. NULL = usa los defaults del bot de venta de
    -- cupos actual (ver analysis/rules_config.py). Otros tipos de campaña
    -- (cobranza, asesoría) necesitarán además su propio set de categorías —
    -- eso todavía no está soportado, ver docs/criterios_clasificacion.md.
    configuracion   JSON NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS imports (
    id                          BIGINT AUTO_INCREMENT PRIMARY KEY,
    campana_id                  BIGINT NULL,
    file_name                   VARCHAR(255) NOT NULL,
    file_hash                   CHAR(64) NULL,
    status                      ENUM('PROCESSING', 'COMPLETED', 'COMPLETED_WITH_WARNINGS', 'ERROR')
                                    NOT NULL DEFAULT 'PROCESSING',
    rows_received                INT NOT NULL DEFAULT 0,
    rows_processed                INT NOT NULL DEFAULT 0,
    rows_error                     INT NOT NULL DEFAULT 0,
    conversations_created            INT NOT NULL DEFAULT 0,
    conversations_updated             INT NOT NULL DEFAULT 0,
    messages_created                   INT NOT NULL DEFAULT 0,
    messages_skipped_duplicate          INT NOT NULL DEFAULT 0,
    started_at                           DATETIME NOT NULL,
    finished_at                           DATETIME NULL,
    error_summary                          JSON NULL,
    warning_summary                         JSON NULL,
    created_at                               DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_imports_campana FOREIGN KEY (campana_id) REFERENCES campanas(id_campana),
    INDEX idx_imports_file_hash (file_hash),
    INDEX idx_imports_status (status),
    INDEX idx_imports_campana_id (campana_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS staging_messages (
    id                    BIGINT AUTO_INCREMENT PRIMARY KEY,
    import_id             BIGINT NOT NULL,
    source_row            INT NOT NULL,
    session_id            VARCHAR(255) NOT NULL,
    channel                VARCHAR(64) NULL,
    rp_id                   VARCHAR(64) NULL,
    row_date                 DATETIME NULL,
    customer_name              VARCHAR(255) NULL,
    customer_email               VARCHAR(255) NULL,
    customer_phone_raw             VARCHAR(64) NULL,
    customer_query                   TEXT NULL,
    routing_answer                     TEXT NULL,
    customer_id                          VARCHAR(64) NULL,
    conn_id                                VARCHAR(64) NULL,
    bsuid                                    VARCHAR(64) NULL,
    created_at                                 DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_staging_import FOREIGN KEY (import_id) REFERENCES imports(id),
    INDEX idx_staging_import_id (import_id),
    INDEX idx_staging_session_id (session_id),
    INDEX idx_staging_customer_phone (customer_phone_raw)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS conversations (
    id                    BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id             VARCHAR(255) NOT NULL,
    session_pattern          ENUM('REAL', 'BROADCAST_LONG_NUMERIC', 'BROADCAST_DOTTED') NOT NULL,
    -- Se fija al crear la conversación (a partir del campana_id del import que
    -- la originó) y nunca se reescribe, igual que first_import_id.
    campana_id                BIGINT NULL,
    customer_phone             VARCHAR(32) NULL,
    customer_name                 VARCHAR(255) NULL,
    customer_email                   VARCHAR(255) NULL,
    channel                             VARCHAR(64) NULL,
    rp_id                                 VARCHAR(64) NULL,
    started_at                             DATETIME NOT NULL,
    ended_at                                 DATETIME NOT NULL,
    message_count                             INT NOT NULL DEFAULT 0,
    conn_id_count                               INT NOT NULL DEFAULT 1,
    -- Quién mandó el primer mensaje de la sesión; se fija una sola vez, igual
    -- que session_pattern/campana_id.
    iniciada_por                                  ENUM('CUSTOMER', 'BOT', 'SYSTEM') NOT NULL,
    -- El texto literal "Array" apareció en algún mensaje (bug de renderizado
    -- del bot). A diferencia de iniciada_por, una carga posterior sí puede
    -- pasarlo de FALSE a TRUE (nunca al revés).
    contiene_array                                  BOOLEAN NOT NULL DEFAULT FALSE,
    first_import_id                               BIGINT NOT NULL,
    last_import_id                                  BIGINT NOT NULL,
    created_at                                        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at                                          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                                                            ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_conv_campana FOREIGN KEY (campana_id) REFERENCES campanas(id_campana),
    CONSTRAINT fk_conv_first_import FOREIGN KEY (first_import_id) REFERENCES imports(id),
    CONSTRAINT fk_conv_last_import FOREIGN KEY (last_import_id) REFERENCES imports(id),
    UNIQUE KEY uq_conversations_session_id (session_id),
    INDEX idx_conversations_customer_phone (customer_phone),
    INDEX idx_conversations_started_at (started_at),
    INDEX idx_conversations_iniciada_por (iniciada_por),
    INDEX idx_conversations_contiene_array (contiene_array),
    INDEX idx_conversations_campana_id (campana_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS messages (
    id                    BIGINT AUTO_INCREMENT PRIMARY KEY,
    conversation_id        BIGINT NOT NULL,
    conn_id                  VARCHAR(64) NULL,
    message_timestamp          DATETIME NOT NULL,
    sequence_number               INT NOT NULL,
    sender                          ENUM('CUSTOMER', 'BOT', 'SYSTEM') NOT NULL,
    message_type                      ENUM('TEXT', 'PROACTIVE', 'SYSTEM_EVENT') NOT NULL,
    message                             TEXT NOT NULL,
    source_row                            INT NOT NULL,
    source_import_id                        BIGINT NOT NULL,
    dedup_hash                                CHAR(64) NOT NULL,
    created_at                                  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_msg_conversation FOREIGN KEY (conversation_id) REFERENCES conversations(id),
    CONSTRAINT fk_msg_import FOREIGN KEY (source_import_id) REFERENCES imports(id),
    UNIQUE KEY uq_messages_dedup_hash (dedup_hash),
    INDEX idx_messages_conversation_id_seq (conversation_id, sequence_number),
    INDEX idx_messages_conn_id (conn_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Fase 2: clasificación de la conversación.
-- Criterios definidos en docs/criterios_clasificacion.md
CREATE TABLE IF NOT EXISTS conversation_analysis (
    id                    BIGINT AUTO_INCREMENT PRIMARY KEY,
    conversation_id        BIGINT NOT NULL,

    -- String, no ENUM: cada campaña puede definir sus propias categorías (ver
    -- analysis/schema.py) — el set fijo de Acme (SIN_RESPUESTA, INTERESADO,
    -- RESOLVIO_DUDAS, NO_INTERESADO, SIN_CLASIFICAR) es solo el default.
    categoria_final          VARCHAR(50) NOT NULL,

    -- Segundo nivel opcional (ej. motivo del interés); NULL si el esquema de la
    -- campaña no define subcategorías o no aplica a esta categoría.
    subcategoria              VARCHAR(50) NULL,

    -- Señales genéricas por indicador (ver analysis/schema.py / schema_engine.py),
    -- siempre poblado. Las 6 columnas booleanas de abajo son la vista legada,
    -- específica de Acme.
    senales                   JSON NULL,

    -- Señales independientes: se conservan para no perder información al
    -- colapsar la jerarquía en una sola categoría.
    interes_declarado          BOOLEAN NOT NULL DEFAULT FALSE,
    interes_confirmado           BOOLEAN NOT NULL DEFAULT FALSE,
    -- Obtuvo información del producto, la haya preguntado o no.
    busco_informacion              BOOLEAN NOT NULL DEFAULT FALSE,
    rechazo_explicito                BOOLEAN NOT NULL DEFAULT FALSE,
    bot_no_resolvio                    BOOLEAN NOT NULL DEFAULT FALSE,
    -- El número de la campaña pertenece a una empresa (autorespondedor de WhatsApp),
    -- no a una persona. Útil para depurar la base de contactos.
    es_autorespondedor                   BOOLEAN NOT NULL DEFAULT FALSE,

    -- Auditoría: permite explicar por qué quedó en esta categoría.
    metodo                               ENUM('RULE', 'AI') NOT NULL,
    regla_aplicada                         VARCHAR(100) NULL,
    modelo_ia                                VARCHAR(100) NULL,
    justificacion                              TEXT NULL,
    raw_response                                 JSON NULL,

    analyzed_at                                    DATETIME NOT NULL,
    created_at                                       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_analysis_conversation FOREIGN KEY (conversation_id) REFERENCES conversations(id),
    UNIQUE KEY uq_analysis_conversation (conversation_id),
    INDEX idx_analysis_categoria (categoria_final),
    INDEX idx_analysis_subcategoria (subcategoria),
    INDEX idx_analysis_metodo (metodo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Un renglón por cada llamada a la API de OpenAI — para poder sumar tokens y
-- estimar costo (ver analysis/pricing.py). conversation_id va poblado para
-- clasificaciones, NULL para llamadas que no son por conversación (ej.
-- generar un esquema de campaña con IA).
CREATE TABLE IF NOT EXISTS ai_usage (
    id                    BIGINT AUTO_INCREMENT PRIMARY KEY,
    ocurrido_en             DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modelo                    VARCHAR(100) NOT NULL,
    tipo                        VARCHAR(30) NOT NULL,
    tokens_prompt                 INT NOT NULL,
    tokens_completion                INT NOT NULL,
    conversation_id                    BIGINT NULL,
    campana_id                            BIGINT NULL,
    CONSTRAINT fk_ai_usage_conversation FOREIGN KEY (conversation_id) REFERENCES conversations(id),
    CONSTRAINT fk_ai_usage_campana FOREIGN KEY (campana_id) REFERENCES campanas(id_campana),
    INDEX idx_ai_usage_modelo (modelo),
    INDEX idx_ai_usage_tipo (tipo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
