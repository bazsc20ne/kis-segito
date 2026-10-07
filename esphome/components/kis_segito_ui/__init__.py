# SPDX-License-Identifier: AGPL-3.0-only
"""Kis Segito child UI for the round 480x480 knob display (LVGL 9).

The component draws every screen itself (carousels, token piles, routine time
track, confirmation) and is driven from YAML through its C++ methods:
``rotate(dir)``, ``click()``, ``long_press()``, ``start()``,
``set_connected(bool)`` and ``set_state(json)``. Until Home Assistant sends real
data it shows built-in test data. Child actions are published as JSON on the
``action_sensor`` text sensor.
"""

import esphome.codegen as cg
from esphome.components import esp32, font, image, text_sensor
from esphome.components.lvgl import defines as lv_defines
import esphome.config_validation as cv
from esphome.const import CONF_ID

CODEOWNERS = ["@bazsc20ne"]
DEPENDENCIES = ["lvgl"]
AUTO_LOAD = ["json"]

CONF_IMAGES = "images"
CONF_NUMBER_FONT = "number_font"
CONF_ACTION_SENSOR = "action_sensor"

kis_segito_ui_ns = cg.esphome_ns.namespace("kis_segito_ui")
KisSegitoUI = kis_segito_ui_ns.class_("KisSegitoUI", cg.Component)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(KisSegitoUI),
        # Icon id (e.g. "fn_rewards_160") -> image component.
        cv.Required(CONF_IMAGES): cv.Schema({cv.string: cv.use_id(image.Image_)}),
        cv.Required(CONF_NUMBER_FONT): cv.use_id(font.Font),
        # Text sensor the child's actions are published on for Home Assistant.
        cv.Optional(CONF_ACTION_SENSOR): cv.use_id(text_sensor.TextSensor),
    }
).extend(cv.COMPONENT_SCHEMA)


def _final_validate(config):
    # ESPHome only compiles the LVGL features its YAML widgets use; this
    # component draws arcs, uses flex layouts and renders carousel slots into
    # images (snapshot) itself, and its images must be known to LVGL so their
    # colour format is enabled.
    lv_defines.add_lv_use("arc", "flex", "snapshot")
    lv_defines.get_lv_images_used().update(config[CONF_IMAGES].values())
    return config


FINAL_VALIDATE_SCHEMA = _final_validate


async def to_code(config):
    # Uploaded pictures are downloaded from Home Assistant over HTTP.
    esp32.include_builtin_idf_component("esp_http_client")
    esp32.include_builtin_idf_component("esp-tls")
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    for key, image_id in config[CONF_IMAGES].items():
        img = await cg.get_variable(image_id)
        cg.add(var.add_image(key, img))
    number_font = await cg.get_variable(config[CONF_NUMBER_FONT])
    cg.add(var.set_number_font(number_font))
    if CONF_ACTION_SENSOR in config:
        sensor = await cg.get_variable(config[CONF_ACTION_SENSOR])
        cg.add(var.set_action_sensor(sensor))
