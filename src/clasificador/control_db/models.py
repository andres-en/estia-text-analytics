from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, BigInteger, Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

PkBigInteger = BigInteger().with_variant(Integer(), "sqlite")


class Base(DeclarativeBase):
    pass


class Rol(Base):
    __tablename__ = "roles"

    id_rol: Mapped[int] = mapped_column(PkBigInteger, primary_key=True, autoincrement=True)
    nombre_rol: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    permisos: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    usuarios: Mapped[list[Usuario]] = relationship(back_populates="rol")


# Tabla puente: un usuario puede tener acceso a varios clientes, y un cliente
# puede tener varios usuarios. Sin columnas propias — la PK compuesta ya
# evita asignaciones duplicadas.
usuario_clientes = Table(
    "usuario_clientes",
    Base.metadata,
    Column("id_usuario", BigInteger, ForeignKey("usuarios.id_usuario"), primary_key=True),
    Column("id_cliente", BigInteger, ForeignKey("clientes.id_cliente"), primary_key=True),
)


class Cliente(Base):
    __tablename__ = "clientes"

    id_cliente: Mapped[int] = mapped_column(PkBigInteger, primary_key=True, autoincrement=True)
    nombre_cliente: Mapped[str] = mapped_column(String(150), nullable=False)
    db_name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    fecha_registro: Mapped[dt.date] = mapped_column(DateTime, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    usuarios: Mapped[list[Usuario]] = relationship(secondary=usuario_clientes, back_populates="clientes")


class Usuario(Base):
    __tablename__ = "usuarios"

    id_usuario: Mapped[int] = mapped_column(PkBigInteger, primary_key=True, autoincrement=True)
    nombre_usuario: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    google_sub: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    id_rol: Mapped[int] = mapped_column(BigInteger, ForeignKey("roles.id_rol"), nullable=False)
    fecha_creacion: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    rol: Mapped[Rol] = relationship(back_populates="usuarios")
    # Sin clientes = super admin (ve todos) o un usuario mal configurado
    # (queda bloqueado hasta que se le asigne uno — ver webapp/tenancy.py).
    clientes: Mapped[list[Cliente]] = relationship(secondary=usuario_clientes, back_populates="usuarios")
