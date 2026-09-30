from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import permissions as perm
from .models import Cliente, Rol, Usuario


def seed_roles(session: Session) -> None:
    """Crea los roles super_admin/admin/user si no existen. Idempotente."""
    existentes = {r.nombre_rol for r in session.execute(select(Rol)).scalars().all()}
    if perm.ROL_SUPER_ADMIN not in existentes:
        session.add(
            Rol(
                nombre_rol=perm.ROL_SUPER_ADMIN,
                descripcion="Full access: creates clients, campaigns and users; sees any client's data.",
                permisos=perm.PERMISOS_SUPER_ADMIN,
            )
        )
    if perm.ROL_ADMIN not in existentes:
        session.add(
            Rol(
                nombre_rol=perm.ROL_ADMIN,
                descripcion="Creates users and assigns them to their own client.",
                permisos=perm.PERMISOS_ADMIN,
            )
        )
    if perm.ROL_USER not in existentes:
        session.add(
            Rol(
                nombre_rol=perm.ROL_USER,
                descripcion="Only sees and uploads data for their assigned client.",
                permisos=perm.PERMISOS_USER,
            )
        )
    session.flush()


def get_or_create_super_admin(session: Session, email: str, nombre_usuario: str) -> Usuario:
    existing = session.execute(select(Usuario).where(Usuario.email == email)).scalar_one_or_none()
    if existing is not None:
        return existing
    rol = session.execute(select(Rol).where(Rol.nombre_rol == perm.ROL_SUPER_ADMIN)).scalar_one()
    usuario = Usuario(
        nombre_usuario=nombre_usuario,
        email=email,
        id_rol=rol.id_rol,
        fecha_creacion=dt.datetime.now(),
        activo=True,
    )
    session.add(usuario)
    session.flush()
    return usuario


def get_usuario_by_email(session: Session, email: str) -> Usuario | None:
    return session.execute(select(Usuario).where(Usuario.email == email)).scalar_one_or_none()


def get_usuario_by_id(session: Session, id_usuario: int) -> Usuario | None:
    return session.get(Usuario, id_usuario)


def list_clientes(session: Session) -> list[Cliente]:
    return list(session.execute(select(Cliente).order_by(Cliente.nombre_cliente)).scalars().all())


def get_cliente(session: Session, id_cliente: int) -> Cliente | None:
    return session.get(Cliente, id_cliente)


def create_cliente(session: Session, *, nombre_cliente: str, db_name: str) -> Cliente:
    cliente = Cliente(
        nombre_cliente=nombre_cliente,
        db_name=db_name,
        fecha_registro=dt.date.today(),
        activo=True,
    )
    session.add(cliente)
    session.flush()
    return cliente


def update_cliente(
    session: Session, cliente: Cliente, *, nombre_cliente: str | None = None, activo: bool | None = None
) -> Cliente:
    if nombre_cliente is not None:
        cliente.nombre_cliente = nombre_cliente
    if activo is not None:
        cliente.activo = activo
    session.flush()
    return cliente


def list_usuarios(session: Session, *, id_clientes: list[int] | None = None) -> list[Usuario]:
    stmt = select(Usuario).order_by(Usuario.nombre_usuario)
    if id_clientes is not None:
        stmt = stmt.where(Usuario.clientes.any(Cliente.id_cliente.in_(id_clientes)))
    return list(session.execute(stmt).scalars().all())


def _clientes_por_id(session: Session, id_clientes: list[int]) -> list[Cliente]:
    if not id_clientes:
        return []
    return list(session.execute(select(Cliente).where(Cliente.id_cliente.in_(id_clientes))).scalars().all())


def create_usuario(
    session: Session, *, nombre_usuario: str, email: str, id_rol: int, id_clientes: list[int]
) -> Usuario:
    usuario = Usuario(
        nombre_usuario=nombre_usuario,
        email=email,
        id_rol=id_rol,
        clientes=_clientes_por_id(session, id_clientes),
        fecha_creacion=dt.datetime.now(),
        activo=True,
    )
    session.add(usuario)
    session.flush()
    return usuario


_UNSET = object()


def update_usuario(
    session: Session,
    usuario: Usuario,
    *,
    nombre_usuario: str | None = None,
    id_rol: int | None = None,
    id_clientes: list[int] | None = _UNSET,  # type: ignore[assignment]
    activo: bool | None = None,
) -> Usuario:
    """`id_clientes` usa un sentinel: pasar una lista (incluida `[]`) reemplaza
    por completo los clientes asignados; no pasar el argumento los deja igual."""
    if nombre_usuario is not None:
        usuario.nombre_usuario = nombre_usuario
    if id_rol is not None:
        usuario.id_rol = id_rol
    if id_clientes is not _UNSET:
        usuario.clientes = _clientes_por_id(session, id_clientes)
    if activo is not None:
        usuario.activo = activo
    session.flush()
    return usuario


def list_roles(session: Session) -> list[Rol]:
    return list(session.execute(select(Rol)).scalars().all())


def get_rol(session: Session, id_rol: int) -> Rol | None:
    return session.get(Rol, id_rol)
