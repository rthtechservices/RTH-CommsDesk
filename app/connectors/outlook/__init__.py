from app.connectors.base import BaseConnector


class OutlookConnector(BaseConnector):
    source_type = "outlook"

    def fetch_recent_messages(self, limit: int = 100, since=None):
        return []
