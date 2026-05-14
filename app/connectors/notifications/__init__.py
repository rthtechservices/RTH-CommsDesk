from app.connectors.base import BaseConnector


class NotificationBridgeConnector(BaseConnector):
    source_type = "notifications"

    def fetch_recent_messages(self, limit: int = 100, since=None):
        return []
