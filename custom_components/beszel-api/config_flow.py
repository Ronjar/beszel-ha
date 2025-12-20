import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN, CONF_URL, CONF_USERNAME, CONF_PASSWORD, CONF_VERIFY_SSL

class BeszelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            return self.async_create_entry(
                title="Beszel API",
                data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_URL): str,
                vol.Optional(CONF_USERNAME): str,
                vol.Optional(CONF_PASSWORD): str,
                vol.Optional(CONF_VERIFY_SSL, default=True): bool,
            }),
            errors=errors,
        )
