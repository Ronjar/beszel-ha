import logging

import httpx
from pocketbase import PocketBase

LOGGER = logging.getLogger(__name__)


class BeszelApiClient:
    def __init__(
        self,
        url,
        username: str | None = None,
        password: str | None = None,
        verify_ssl: bool = True,
    ):
        self._url = url.rstrip("/")
        self._username = username
        self._password = password
        self._verify_ssl = verify_ssl
        self._client = None

    def _ensure_client(self):
        """Initialize the PocketBase client if not already done"""
        if self._client is None:
            try:
                httpx_client = httpx.Client(verify=self._verify_ssl)
                self._client = PocketBase(self._url, http_client=httpx_client)
                if self._username and self._password:
                    self._client.collection("users").auth_with_password(
                        self._username,
                        self._password,
                    )
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


class BeszelUpdateApi:

    def __init__(self, url: str, timeout: int = 10):
        self.base_url = url.rstrip("/") if url else url
        self.timeout = timeout

    def _remove_version_prefix(self, v: str | None) -> str | None:
        if not v:
            return None
        return v.lstrip("v").strip()

    def _to_tuple(self, v: str | None) -> tuple:
        """
        Converts "0.16.1" into a tuple of ints (0,16,1).
        """
        if not v:
            return ()
        parts = []
        for p in v.split("."):
            try:
                parts.append(int(p))
            except Exception:
                break
        return tuple(parts)

    def get_hub_version(self) -> str | None:
        """Fetch the base URL and extract HUB_VERSION from HTML."""
        import requests
        import re

        if not self.base_url:
            LOGGER.debug("No base_url configured for BeszelUpdateApi")
            return None

        url = self.base_url if self.base_url.startswith(("http://", "https://")) else f"http://{self.base_url}"
        try:
            r = requests.get(url, timeout=self.timeout)
            r.raise_for_status()
            match = re.search(r'HUB_VERSION\s*:\s*"([^"]+)"', r.text)
            if match:
                version = self._remove_version_prefix(match.group(1))
                return version
            LOGGER.debug("HUB_VERSION not found")
            return None
        except Exception as e:
            LOGGER.error("Error fetching hub HTML: %s", e)
            return None

    def get_latest_release(self) -> tuple[str | None, str | None]:
        """Query GitHub releases API and return (tag_name, html_url)."""
        import requests
        api_url = f"https://api.github.com/repos/henrygd/beszel/releases/latest"
        headers = {"Accept": "application/vnd.github.v3+json"}
        try:
            r = requests.get(api_url, headers=headers, timeout=self.timeout)
            r.raise_for_status()
            j = r.json()
            tag = j.get("tag_name")
            html = j.get("html_url")
            tag_norm = self._remove_version_prefix(tag)
            LOGGER.debug("GitHub latest release: %s (%s)", tag_norm, html)
            return tag_norm, html
        except Exception as e:
            LOGGER.error("Error fetching latest GitHub release: %s", e)
            return None, None

    def get_update_info(self) -> dict:
        """
        Returns:
          {
            "hub_version": <installed version or None>,
            "latest_version": <latest release tag or None>,
            "latest_release_url": <html_url or None>,
            "update_available": <bool>
          }
        """
        installed = self.get_hub_version()
        latest, latest_url = self.get_latest_release()

        installed_t = self._to_tuple(installed)
        latest_t = self._to_tuple(latest)

        update_available = False
        try:
            if installed_t and latest_t:
                update_available = latest_t > installed_t
        except Exception as e:
            LOGGER.debug("Version comparison failed: %s", e)
            update_available = False

        return {
            "hub_version": installed,
            "latest_version": latest,
            "latest_release_url": latest_url,
            "update_available": update_available,
        }