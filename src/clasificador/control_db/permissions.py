"""Catálogo de permisos evaluados por `webapp.authz.require_permission`.

Cada rol guarda su propia lista de estos strings en `roles.permisos` (JSON).
Agregar un permiso nuevo no requiere migración: solo aparece en la lista del
rol que deba tenerlo.
"""

from __future__ import annotations

USUARIOS_CREAR = "usuarios.crear"
USUARIOS_EDITAR = "usuarios.editar"
USUARIOS_ASIGNAR_CLIENTE = "usuarios.asignar_cliente"
USUARIOS_ASIGNAR_CLIENTE_PROPIO = "usuarios.asignar_cliente_propio"
CLIENTES_CREAR = "clientes.crear"
CLIENTES_EDITAR = "clientes.editar"
CAMPANAS_CREAR = "campanas.crear"
# Habilita la pestaña "Configuración" y el acceso a los datos de cualquier cliente.
ADMINISTRACION_ACCESO = "administracion.acceso"
# Borrado destructivo de conversaciones/mensajes por fecha (para reprocesar una
# carga con datos incorrectos) — deliberadamente separado de ADMINISTRACION_ACCESO
# para poder acotarlo más adelante si algún día se necesita.
CONVERSACIONES_ELIMINAR = "conversaciones.eliminar"

ROL_SUPER_ADMIN = "super_admin"
ROL_ADMIN = "admin"
ROL_USER = "user"

PERMISOS_SUPER_ADMIN = [
    CLIENTES_CREAR,
    CLIENTES_EDITAR,
    CAMPANAS_CREAR,
    USUARIOS_CREAR,
    USUARIOS_EDITAR,
    USUARIOS_ASIGNAR_CLIENTE,
    ADMINISTRACION_ACCESO,
    CONVERSACIONES_ELIMINAR,
]

PERMISOS_ADMIN = [
    USUARIOS_CREAR,
    USUARIOS_ASIGNAR_CLIENTE_PROPIO,
]

# Rol base: solo ve/carga los datos de su cliente asignado, sin permisos de
# administración (no crea usuarios, no entra a Configuración).
PERMISOS_USER: list[str] = []
