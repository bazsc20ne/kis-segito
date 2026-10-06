# SPDX-License-Identifier: AGPL-3.0-only
"""Kis Segito child UI for the round 480x480 knob display (LVGL 9).

The component draws every screen itself (carousels, token piles, routine time
track, confirmation) and is driven from YAML through its C++ methods:
``rotate(dir)``, ``click()``, ``long_press()``, ``start()`` and
``set_connected(bool)``. Until Home Assistant sends real data it shows built-in
test data.
"""

import esphome.codegen as cg
from esphome.components import font, image
import esphome.config_validation as cv
from esphome.const import CONF_ID

CODEOWNERS = ["@bazsc20ne"]
DEPENDENCIES = ["lvgl"]

CONF_IMAGES = "images"
CONF_NUMBER_FONT = "number_font"

kis_segito_ui_ns = cg.esphome_ns.namespace("kis_segito_ui")
KisSegitoUI = kis_segito_ui_ns.class_("KisSegitoUI", cg.Component)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(KisSegitoUI),
        # Icon id (e.g. "fn_rewards_160") -> image component.
        cv.Required(CONF_IMAGES): cv.Schema({cv.string: cv.use_id(image.Image_)}),
        cv.Required(CONF_NUMBER_FONT): cv.use_id(font.Font),
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    for key, image_id in config[CONF_IMAGES].items():
        img = await cg.get_variable(image_id)
        cg.add(var.add_image(key, img))
    number_font = await cg.get_variable(config[CONF_NUMBER_FONT])
    cg.add(var.set_number_font(number_font))
