from pocketbase import PocketBase
import logging

LOGGER = logging.getLogger(__name__)

class BeszelApiClient:
    def __init__(self, url, username, password):
        self._url = url.rstrip("/")
        self._username = username
        self._password = password
        self._client = None

    def _ensure_client(self):
        """Initialize the PocketBase client if not already done"""
        if self._client is None:
            try:
                self._client = PocketBase(self._url)
                self._client.collection("users").auth_with_password(self._username, self._password)
            except Exception as e:
                LOGGER.error(f"Failed to initialize PocketBase client: {e}")
                raise

    def get_systems(self):
        try:
            self._ensure_client()
            records = self._client.collection("systems").get_full_list()
            return records
        except Exception as e:
            LOGGER.error(f"Failed to fetch systems: {e}")
            raise

    def get_system_stats(self, system_id):
        """Get the latest system stats for a specific system"""
        try:
            self._ensure_client()
            # Get the latest record for the specific system
            records = self._client.collection("system_stats").get_list(
                1, 1, {"filter": f"system = '{system_id}'", "sort": "-created"}
            )
            if records.items:
                return records.items[0]
            return None
        except Exception as e:
            LOGGER.error(f"Failed to fetch stats for system {system_id}: {e}")
            # Return None if no stats found or error occurs
            return None
