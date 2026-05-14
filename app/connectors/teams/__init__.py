from app.connectors.base import BaseConnector


class TeamsConnector(BaseConnector):
    source_type = "teams"

    def fetch_recent_messages(self, limit: int = 100, since=None):
        return []
