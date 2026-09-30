-- Esquema de la base de control: identidad y asignación de clientes.
-- Es una base separada de las bases de datos (una por cliente) que contienen
-- imports/conversations/messages/conversation_analysis. Ver plan de
-- multi-cliente para el contexto completo.

CREATE TABLE IF NOT EXISTS roles (
    id_rol          BIGINT AUTO_INCREMENT PRIMARY KEY,
    nombre_rol      VARCHAR(100) NOT NULL,
    descripcion     TEXT NULL,
    -- Lista de strings evaluada por el backend, ej. ["usuarios.crear", "clientes.crear"].
    permisos        JSON NOT NULL,
    UNIQUE KEY uq_roles_nombre_rol (nombre_rol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS clientes (
    id_cliente      BIGINT AUTO_INCREMENT PRIMARY KEY,
    nombre_cliente  VARCHAR(150) NOT NULL,
    -- Nombre de la base de datos de este cliente en el mismo servidor MySQL.
    db_name         VARCHAR(64) NOT NULL,
    fecha_registro  DATE NOT NULL,
    activo          BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE KEY uq_clientes_db_name (db_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario      BIGINT AUTO_INCREMENT PRIMARY KEY,
    nombre_usuario  VARCHAR(150) NOT NULL,
    email           VARCHAR(255) NOT NULL,
    -- ID estable de Google (sub del id_token). Se completa en el primer login.
    google_sub      VARCHAR(255) NULL,
    id_rol          BIGINT NOT NULL,
    fecha_creacion  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    activo          BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_usuarios_rol FOREIGN KEY (id_rol) REFERENCES roles(id_rol),
    UNIQUE KEY uq_usuarios_email (email),
    UNIQUE KEY uq_usuarios_google_sub (google_sub)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Un usuario puede tener acceso a varios clientes (y un cliente, a varios
-- usuarios). Sin clientes asignados = super admin, o un usuario mal
-- configurado que queda bloqueado hasta que se le asigne uno.
CREATE TABLE IF NOT EXISTS usuario_clientes (
    id_usuario  BIGINT NOT NULL,
    id_cliente  BIGINT NOT NULL,
    PRIMARY KEY (id_usuario, id_cliente),
    CONSTRAINT fk_usuario_clientes_usuario FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario),
    CONSTRAINT fk_usuario_clientes_cliente FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente),
    INDEX idx_usuario_clientes_cliente (id_cliente)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
