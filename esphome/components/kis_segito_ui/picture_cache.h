// SPDX-License-Identifier: AGPL-3.0-only
//
// Flash cache for the pictures the knob downloads from Home Assistant, on its
// own data partition ("ks_cache"). The partition is a ring: new pictures are
// written at the head, erasing the oldest ones. A picture that is used again
// while it is close to being erased is written again at the head, so the
// pictures in use stay (least recently used ones go first).
//
// Each entry starts on a 4 KB sector with a header (key, Home Assistant's
// ETag, size, checksums), followed by the picture data. The header is written
// last, so an entry cut short by a power loss is never read.
//
// Used only from the picture download task.

#pragma once

#include <cstddef>
#include <cstdint>
#include <map>
#include <string>

#include <esp_partition.h>

namespace esphome::kis_segito_ui {

class PictureCache {
 public:
  // Finds the partition and reads the entries; false without the partition
  // (a knob first installed with an older version keeps its old partition
  // table until it is flashed over USB).
  bool begin();
  bool ready() const { return this->part_ != nullptr; }
  // Size of a cached picture, 0 when it is not cached.
  size_t size(const std::string &key) const;
  // A cached picture in a new PSRAM buffer (free with heap_caps_free), or
  // nullptr. `etag` receives the ETag it was stored with.
  uint8_t *read(const std::string &key, size_t *size, std::string *etag);
  bool write(const std::string &key, const std::string &etag, const uint8_t *data, size_t size);

 protected:
  struct Entry {
    uint32_t offset;
    uint32_t size;
    uint32_t seq;
    uint32_t crc;
    std::string etag;
  };
  uint32_t sectors_(uint32_t size) const;
  void drop_range_(uint32_t from, uint32_t to);

  const esp_partition_t *part_{nullptr};
  std::map<std::string, Entry> index_;
  uint32_t head_{0};
  uint32_t next_seq_{1};
};

}  // namespace esphome::kis_segito_ui
