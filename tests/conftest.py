import os

os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("ALLOW_DEV_LOGIN", "true")
os.environ.setdefault("RESEND_API_KEY", "test-api-key")
os.environ.setdefault("RESEND_SENDER_EMAIL", "test-sender@example.com")

import boto3  # noqa: E402
import pytest  # noqa: E402
from moto import mock_aws  # noqa: E402

from app.config import settings  # noqa: E402


@pytest.fixture(autouse=True)
def mock_send_email(monkeypatch):
    """No test should ever hit a real email provider -- record sent emails instead."""
    sent = []

    def _fake_send_email(to_address, subject, body):
        sent.append({"to_address": to_address, "subject": subject, "body": body})

    monkeypatch.setattr("app.services.verification_service.send_email", _fake_send_email)
    monkeypatch.setattr("app.services.password_reset_service.send_email", _fake_send_email)
    return sent


@pytest.fixture
def dynamodb_tables():
    with mock_aws():
        client = boto3.client("dynamodb", region_name=settings.aws_region)

        client.create_table(
            TableName=settings.users_table,
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "display_name_lower", "AttributeType": "S"},
                {"AttributeName": "email_lower", "AttributeType": "S"},
            ],
            KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "byDisplayNameLower",
                    "KeySchema": [{"AttributeName": "display_name_lower", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "byEmailLower",
                    "KeySchema": [{"AttributeName": "email_lower", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        client.create_table(
            TableName=settings.identities_table,
            AttributeDefinitions=[
                {"AttributeName": "provider", "AttributeType": "S"},
                {"AttributeName": "provider_subject", "AttributeType": "S"},
                {"AttributeName": "user_id", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "provider", "KeyType": "HASH"},
                {"AttributeName": "provider_subject", "KeyType": "RANGE"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "byUserId",
                    "KeySchema": [{"AttributeName": "user_id", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        client.create_table(
            TableName=settings.puzzles_table,
            AttributeDefinitions=[{"AttributeName": "puzzle_id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "puzzle_id", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        client.create_table(
            TableName=settings.scores_table,
            AttributeDefinitions=[
                {"AttributeName": "puzzle_id", "AttributeType": "S"},
                {"AttributeName": "user_id", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "puzzle_id", "KeyType": "HASH"},
                {"AttributeName": "user_id", "KeyType": "RANGE"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        client.create_table(
            TableName=settings.friendships_table,
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "friend_id", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "friend_id", "KeyType": "RANGE"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        client.create_table(
            TableName=settings.friend_requests_table,
            AttributeDefinitions=[
                {"AttributeName": "to_user_id", "AttributeType": "S"},
                {"AttributeName": "from_user_id", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "to_user_id", "KeyType": "HASH"},
                {"AttributeName": "from_user_id", "KeyType": "RANGE"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "byFromUserId",
                    "KeySchema": [{"AttributeName": "from_user_id", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        client.create_table(
            TableName=settings.verification_codes_table,
            AttributeDefinitions=[{"AttributeName": "user_id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        client.create_table(
            TableName=settings.password_reset_codes_table,
            AttributeDefinitions=[{"AttributeName": "user_id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        client.create_table(
            TableName=settings.achievements_table,
            AttributeDefinitions=[{"AttributeName": "user_id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield


@pytest.fixture
def client(dynamodb_tables):
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    def _login(display_name: str) -> dict:
        response = client.post("/v1/auth/dev-login", json={"display_name": display_name})
        assert response.status_code == 200, response.text
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _login


@pytest.fixture
def seed_puzzle(dynamodb_tables):
    """Inserts a puzzle whose board is guaranteed to spell `word` starting at cell 0,
    going rightward -- avoids depending on luck with the randomly-seeded daily board.
    """

    def _seed(puzzle_id: str, word: str, game: str = "boggle", date: str = "2026-01-01") -> str:
        from app.db import puzzles_table

        board = ["X"] * 25
        for i, letter in enumerate(word.upper()):
            board[i] = letter

        puzzles_table.put_item(
            Item={
                "puzzle_id": puzzle_id,
                "game": game,
                "date": date,
                "board": board,
                "duration_seconds": 180,
            }
        )
        return puzzle_id

    return _seed
