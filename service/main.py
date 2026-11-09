import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from service.database import connect, initialize_database

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.database_path = Path(
        os.environ.get("PAYMENT_DB_PATH", str(PROJECT_ROOT / "data/development.db"))
    ).resolve()
    initialize_database(app.state.database_path)
    yield


app = FastAPI(lifespan=lifespan)


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    display_name: str = Field(pattern=r"^DEMO_[A-Za-z0-9_]{1,40}$")


TestRunId = Annotated[
    str, Header(alias="X-Test-Run-ID", pattern=r"^[A-Za-z0-9_-]{1,64}$")
]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/hea")
def health() -> dict[str, str]:
    return {"msg": "ok"}


@app.post("/users", status_code=201)
def create_user(body: UserCreate, request: Request, test_run_id: TestRunId):
    user = {"user_id": str(uuid4()), "display_name": body.display_name, "status": "NEW"}
    with connect(request.app.state.database_path) as connection:
        connection.execute(
            "INSERT INTO users (user_id, test_run_id, display_name, status) VALUES (?, ?, ?, ?)",
            (user["user_id"], test_run_id, user["display_name"], user["status"]),
        )
    return user


@app.get("/users/{user_id}")
def get_user(user_id: str, request: Request, test_run_id: TestRunId):
    with connect(request.app.state.database_path) as connection:
        row = connection.execute(
            "SELECT user_id, display_name, status FROM users WHERE user_id = ? AND test_run_id = ?",
            (user_id, test_run_id),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row)


class VerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    verification_name: str = Field(pattern=r"^DEMO_PERSON_[0-9]{2}$")
    identity_token: str = Field(pattern=r"^DEMO_ID_[0-9]{2}$")


@app.post("/users/{user_id}/verification")
def verify_user(user_id: str, body: VerificationRequest, request: Request, test_run_id: TestRunId):
    with connect(request.app.state.database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT * FROM users WHERE user_id = ? AND test_run_id = ?",
                                 (user_id, test_run_id)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="User not found")
        if (body.verification_name, body.identity_token) != ("DEMO_PERSON_01", "DEMO_ID_01"):
            raise HTTPException(status_code=409, detail="Demo verification rejected")
        if row['status'] == 'VERIFIED':
            if (row['verification_name'], row['identity_token']) != (body.verification_name, body.identity_token):
                raise HTTPException(status_code=409, detail="Verification identity conflict")
        else:
            connection.execute(
                "UPDATE users SET status = 'VERIFIED', verification_name = ?, identity_token = ? "
                "WHERE user_id = ? AND test_run_id = ? AND status = 'NEW'",
                (body.verification_name, body.identity_token, user_id, test_run_id),
            )
    return {"user_id": user_id, "display_name": row['display_name'], "status": "VERIFIED"}


class CardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    card_token: Literal["DEMO_CARD_OK", "DEMO_CARD_DECLINED", "DEMO_CARD_001"]


@app.post("/users/{user_id}/cards", status_code=201)
def bind_card(user_id: str, body: CardRequest, request: Request, test_run_id: TestRunId):
    with connect(request.app.state.database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        user = connection.execute("SELECT status FROM users WHERE user_id = ? AND test_run_id = ?",
                                  (user_id, test_run_id)).fetchone()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        if user['status'] != 'VERIFIED':
            raise HTTPException(status_code=409, detail="User must be verified")
        if connection.execute("SELECT card_id FROM cards WHERE user_id = ? AND card_token = ?",
                              (user_id, body.card_token)).fetchone():
            raise HTTPException(status_code=409, detail="Card already bound")
        card = {"card_id": str(uuid4()), "user_id": user_id, "card_token": body.card_token, "status": "BOUND"}
        connection.execute("INSERT INTO cards (card_id, user_id, test_run_id, card_token, status) VALUES (?, ?, ?, ?, ?)",
                           (card['card_id'], user_id, test_run_id, body.card_token, card['status']))
    return card


@app.get("/users/{user_id}/cards")
def get_cards(user_id: str, request: Request, test_run_id: TestRunId):
    with connect(request.app.state.database_path) as connection:
        user = connection.execute("SELECT user_id FROM users WHERE user_id = ? AND test_run_id = ?",
                                  (user_id, test_run_id)).fetchone()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        rows = connection.execute(
            "SELECT card_id, user_id, card_token, status FROM cards WHERE user_id = ? AND test_run_id = ? ORDER BY card_id",
            (user_id, test_run_id)).fetchall()
    return [dict(row) for row in rows]


class PaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    user_id: str = Field(min_length=1, max_length=64)
    card_id: str = Field(min_length=1, max_length=64)
    amount_cent: int = Field(ge=1, le=1000000)


IdempotencyKey = Annotated[
    str, Header(alias="Idempotency-Key", pattern=r"^DEMO_[A-Za-z0-9_-]{1,59}$")
]
PAYMENT_FIELDS = "payment_id, user_id, card_id, amount_cent, status"


@app.post("/payments", status_code=201)
def create_payment(body: PaymentRequest, request: Request, test_run_id: TestRunId, idempotency_key: IdempotencyKey):
    with connect(request.app.state.database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")  # 先取得写事务，再查重和写入
        previous = connection.execute(
            f"SELECT {PAYMENT_FIELDS} FROM payments WHERE test_run_id = ? AND idempotency_key = ?",
            (test_run_id, idempotency_key),
        ).fetchone()
        if previous is not None:
            if (previous['user_id'], previous['card_id'], previous['amount_cent']) != (body.user_id, body.card_id, body.amount_cent):
                raise HTTPException(status_code=409, detail="Idempotency key conflicts with payment parameters")
            return dict(previous)  # 同资源、同响应内容、原状态码 201
        user = connection.execute("SELECT status FROM users WHERE user_id = ? AND test_run_id = ?",
                                  (body.user_id, test_run_id)).fetchone()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        if user['status'] != 'VERIFIED':
            raise HTTPException(status_code=409, detail="User must be verified")
        card = connection.execute(
            "SELECT card_token, status FROM cards WHERE card_id = ? AND user_id = ? AND test_run_id = ?",
            (body.card_id, body.user_id, test_run_id),
        ).fetchone()
        if card is None or card['status'] != 'BOUND':
            raise HTTPException(status_code=409, detail="Bound card does not belong to user")
        if card['card_token'] == 'DEMO_CARD_DECLINED':
            raise HTTPException(status_code=409, detail="Demo payment declined")
        payment = {"payment_id": str(uuid4()), "user_id": body.user_id, "card_id": body.card_id,
                   "amount_cent": body.amount_cent, "status": "SUCCEEDED"}
        connection.execute(
            "INSERT INTO payments (payment_id, test_run_id, idempotency_key, user_id, card_id, amount_cent, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (payment['payment_id'], test_run_id, idempotency_key, body.user_id, body.card_id, body.amount_cent, payment['status']),
        )
    return payment  # 退出 connect 的事务并提交后才响应


@app.get("/payments/{payment_id}")
def get_payment(payment_id: str, request: Request, test_run_id: TestRunId):
    with connect(request.app.state.database_path) as connection:
        row = connection.execute(
            f"SELECT {PAYMENT_FIELDS} FROM payments WHERE payment_id = ? AND test_run_id = ?",
            (payment_id, test_run_id),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return dict(row)
