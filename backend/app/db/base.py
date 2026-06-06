from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

__all__ = [name for name in globals() if not name.startswith('_')]
