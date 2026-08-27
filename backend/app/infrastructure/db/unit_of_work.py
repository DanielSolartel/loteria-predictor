from __future__ import annotations

from sqlalchemy.orm import Session

from app.application.interfaces.unit_of_work import UnitOfWork


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session: Session):
        self._session = session

    def confirmar(self) -> None:
        self._session.commit()
