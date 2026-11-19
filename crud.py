"""A reusable CRUD router: list / get / create / update / delete for one table.

Each school table gets these five endpoints from `crud_router(...)`, so the
logic lives in one place. Table-specific rules are passed in as hooks.
"""

import inspect
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db

# Hook signature: (db, data_dict, existing_row_or_None) -> data_dict
Hook = Callable[[Session, dict[str, Any], Any], dict[str, Any]]


def integrity_error(exc: IntegrityError) -> HTTPException:
    """Turn a database constraint error into a readable 409/400 response."""
    msg = str(exc.orig).split("\n")[0]
    code = getattr(exc.orig, "sqlstate", None)
    if code == "23505":  # unique_violation
        detail = (exc.orig.diag.message_detail or msg) if hasattr(exc.orig, "diag") else msg
        return HTTPException(status.HTTP_409_CONFLICT, f"Already exists: {detail}")
    if code == "23503":  # foreign_key_violation
        detail = (exc.orig.diag.message_detail or msg) if hasattr(exc.orig, "diag") else msg
        return HTTPException(status.HTTP_400_BAD_REQUEST, f"Related record not found: {detail}")
    return HTTPException(status.HTTP_400_BAD_REQUEST, msg)


def get_or_404(db: Session, model, item_id: int, label: str):
    row = db.get(model, item_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} {item_id} not found")
    return row


def crud_router(
    *,
    model,
    create_schema: type[BaseModel],
    update_schema: type[BaseModel],
    out_schema: type[BaseModel],
    prefix: str,
    tag: str,
    label: str,
    filters: dict[str, type] | None = None,
    order_by=None,
    before_save: Hook | None = None,
    dependencies: list | None = None,
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag], dependencies=dependencies or [])
    pk = model.__mapper__.primary_key[0]
    filters = filters or {}

    # ---- LIST (with optional filters that appear in /docs) ----
    def list_items(db: Session = Depends(get_db), skip: int = 0, limit: int = 100, **kwargs):
        stmt = select(model)
        for name, value in kwargs.items():
            if value is not None:
                stmt = stmt.where(getattr(model, name) == value)
        stmt = stmt.order_by(order_by if order_by is not None else pk).offset(skip).limit(min(limit, 500))
        return db.scalars(stmt).all()

    params = [
        inspect.Parameter("db", inspect.Parameter.KEYWORD_ONLY, default=Depends(get_db), annotation=Session),
        inspect.Parameter("skip", inspect.Parameter.KEYWORD_ONLY, default=Query(0, ge=0), annotation=int),
        inspect.Parameter("limit", inspect.Parameter.KEYWORD_ONLY, default=Query(100, ge=1, le=500), annotation=int),
    ] + [
        inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, default=Query(None), annotation=typ | None)
        for name, typ in filters.items()
    ]
    list_items.__signature__ = inspect.Signature(params)
    router.add_api_route(
        "", list_items, methods=["GET"], response_model=list[out_schema],
        summary=f"List {tag.lower()}" + (f" (filter by {', '.join(filters)})" if filters else ""),
    )

    # ---- GET ONE ----
    @router.get("/{item_id}", response_model=out_schema, summary=f"Get one {label.lower()}")
    def get_item(item_id: int, db: Session = Depends(get_db)):
        return get_or_404(db, model, item_id, label)

    # ---- CREATE ----
    @router.post("", response_model=out_schema, status_code=status.HTTP_201_CREATED, summary=f"Create {label.lower()}")
    def create_item(body: create_schema, db: Session = Depends(get_db)):  # type: ignore[valid-type]
        data = body.model_dump()
        if before_save:
            data = before_save(db, data, None)
        row = model(**data)
        db.add(row)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise integrity_error(exc)
        db.refresh(row)
        return row

    # ---- UPDATE (partial) ----
    @router.patch("/{item_id}", response_model=out_schema, summary=f"Update {label.lower()} (send only changed fields)")
    def update_item(item_id: int, body: update_schema, db: Session = Depends(get_db)):  # type: ignore[valid-type]
        row = get_or_404(db, model, item_id, label)
        data = body.model_dump(exclude_unset=True)
        if not data:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")
        if before_save:
            data = before_save(db, data, row)
        for key, value in data.items():
            setattr(row, key, value)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise integrity_error(exc)
        db.refresh(row)
        return row

    # ---- DELETE ----
    @router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary=f"Delete {label.lower()}")
    def delete_item(item_id: int, db: Session = Depends(get_db)):
        row = get_or_404(db, model, item_id, label)
        db.delete(row)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise integrity_error(exc)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
