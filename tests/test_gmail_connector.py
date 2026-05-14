from datetime import UTC, datetime

from app.connectors.gmail.client import GmailConnector


class FakeMessagesAPI:
    def list(self, **kwargs):
        self._method = "list"
        return self

    def get(self, **kwargs):
        self._method = "get"
        self._id = kwargs["id"]
        return self

    def execute(self):
        if self._method == "list":
            return {"messages": [{"id": "m1"}]}
        return {
            "id": "m1",
            "threadId": "t1",
            "internalDate": str(int(datetime(2026, 1, 1, tzinfo=UTC).timestamp() * 1000)),
            "snippet": "Hello there",
            "labelIds": ["INBOX", "UNREAD"],
            "payload": {
                "headers": [
                    {"name": "From", "value": "Alice <alice@example.com>"},
                    {"name": "Subject", "value": "Question"},
                    {"name": "List-Unsubscribe", "value": "<mailto:unsubscribe@example.com>"},
                    {"name": "Precedence", "value": "bulk"},
                    {"name": "Auto-Submitted", "value": "auto-generated"},
                    {"name": "Reply-To", "value": "no-reply@example.com"},
                ],
                "parts": [],
            },
        }


class FakeUsersAPI:
    def messages(self):
        return FakeMessagesAPI()


class FakeService:
    def users(self):
        return FakeUsersAPI()


def test_gmail_connector_fetch_recent_messages():
    connector = GmailConnector(service=FakeService())
    messages = connector.fetch_recent_messages(limit=1)
    assert len(messages) == 1
    msg = messages[0]
    assert msg.source_message_id == "m1"
    assert msg.sender_email == "alice@example.com"
    assert msg.subject == "Question"
    assert msg.body_text is None
    assert msg.headers is not None
    assert msg.headers["list-unsubscribe"] == "<mailto:unsubscribe@example.com>"
    assert msg.headers["precedence"] == "bulk"
