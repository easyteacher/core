"""Support for switches which integrates with other components."""

import voluptuous as vol

from homeassistant.components.switch import (
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    CONF_SWITCHES,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.script import Script

from .const import DOMAIN
from .template_entity import (
    TEMPLATE_ENTITY_COMMON_SCHEMA_LEGACY,
    TemplateEntity,
    rewrite_common_legacy_to_modern_conf,
)

_VALID_STATES = [STATE_ON, STATE_OFF, "true", "false"]

ON_ACTION = "turn_on"
OFF_ACTION = "turn_off"

SWITCH_SCHEMA = vol.All(
    cv.deprecated(ATTR_ENTITY_ID),
    vol.Schema(
        {
            vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
            vol.Required(ON_ACTION): cv.SCRIPT_SCHEMA,
            vol.Required(OFF_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
            vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    ).extend(TEMPLATE_ENTITY_COMMON_SCHEMA_LEGACY.schema),
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SWITCHES): cv.schema_with_slug_keys(SWITCH_SCHEMA)}
)


async def _async_create_entities(hass, config):
    """Create the Template switches."""
    switches = []

    for object_id, entity_config in config[CONF_SWITCHES].items():
        entity_config = rewrite_common_legacy_to_modern_conf(entity_config)
        unique_id = entity_config.get(CONF_UNIQUE_ID)

        switches.append(
            SwitchTemplate(
                hass,
                object_id,
                entity_config,
                unique_id,
            )
        )

    return switches


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the template switches."""
    async_add_entities(await _async_create_entities(hass, config))


class SwitchTemplate(TemplateEntity, SwitchEntity, RestoreEntity):
    """Representation of a Template switch."""

    def __init__(
        self,
        hass,
        object_id,
        config,
        unique_id,
    ):
        """Initialize the Template switch."""
        super().__init__(config=config)
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, object_id, hass=hass
        )
        self._name = friendly_name = config.get(ATTR_FRIENDLY_NAME, object_id)
        self._template = config.get(CONF_VALUE_TEMPLATE)
        self._on_script = Script(hass, config[ON_ACTION], friendly_name, DOMAIN)
        self._off_script = Script(hass, config[OFF_ACTION], friendly_name, DOMAIN)
        self._state = False
        self._unique_id = unique_id

    @callback
    def _update_state(self, result):
        super()._update_state(result)
        if isinstance(result, TemplateError):
            self._state = None
            return

        if isinstance(result, bool):
            self._state = result
            return

        if isinstance(result, str):
            self._state = result.lower() in ("true", STATE_ON)
            return

        self._state = False

    async def async_added_to_hass(self):
        """Register callbacks."""
        if self._template is None:

            # restore state after startup
            await super().async_added_to_hass()
            if state := await self.async_get_last_state():
                self._state = state.state == STATE_ON

            # no need to listen for events
        else:
            self.add_template_attribute(
                "_state", self._template, None, self._update_state
            )

        await super().async_added_to_hass()

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of this switch."""
        return self._unique_id

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    async def async_turn_on(self, **kwargs):
        """Fire the on action."""
        await self._on_script.async_run(context=self._context)
        if self._template is None:
            self._state = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Fire the off action."""
        await self._off_script.async_run(context=self._context)
        if self._template is None:
            self._state = False
            self.async_write_ha_state()

    @property
    def assumed_state(self):
        """State is assumed, if no template given."""
        return self._template is None
