// SPDX-License-Identifier: AGPL-3.0-only
#pragma once

#include <cstddef>
#include <cstdint>

namespace esphome {
namespace kis_segito_ui {

// Unpacks zlib data (RFC 1950/1951) into out, which must hold exactly
// out_len bytes. Returns true when the data unpacked to out_len bytes.
bool zlib_inflate(const uint8_t *in, size_t in_len, uint8_t *out, size_t out_len);

}  // namespace kis_segito_ui
}  // namespace esphome
