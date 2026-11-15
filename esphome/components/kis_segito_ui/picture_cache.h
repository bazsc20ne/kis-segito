// SPDX-License-Identifier: AGPL-3.0-only
//
// Flash cache for the pictures the knob downloads from Home Assistant, on its
// own data partition ("ks_cache"). The partition is a ring: new pictures are
// written at the head, erasing the oldest ones. A picture that is used again
// while it is close to being erased is written again at the head, so the
// pictures in use stay (least recently used ones go first).
//
// Some pictures are kept (set_keep: the background, the children's avatars
// and photos, the children's own themes): when the ring reaches one, it is
// moved to the head instead of being erased, and a new picture is not stored
// when only kept pictures are left to make room for it.
//
// Each entry starts on a 4 KB sector with a header (key, Home Assistant's
// ETag, size, checksums), followed by the picture data. The header is written
// last, so an entry cut short by a power loss is never read.
//
// Used only from the picture download task.

#pragma once

#include <cstddef>
#include <cstdint>
#include <functional>
#include <map>
#include <mutex>
#include <vector>
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
  // The store's size in bytes (0 without the partition).
  size_t capacity() const { return this->part_ == nullptr ? 0 : this->part_->size; }
  // Size of a cached picture, 0 when it is not cached.
  size_t size(const std::string &key) const;
  // ETag a cached picture was stored with, empty when it is not cached.
  std::string etag(const std::string &key) const;
  // A cached picture in a new PSRAM buffer (free with heap_caps_free), or
  // nullptr. `etag` receives the ETag it was stored with.
  uint8_t *read(const std::string &key, size_t *size, std::string *etag);
  bool write(const std::string &key, const std::string &etag, const uint8_t *data, size_t size);
  // Key prefixes of the pictures to keep (any task may call it).
  void set_keep(std::vector<std::string> prefixes);
  // Writes a picture of `size` bytes that `read` delivers in pieces (it
  // returns the number of bytes put into the buffer, <= 0 on failure), using
  // only a small buffer instead of the whole picture in PSRAM. `crc_out`
  // receives the picture's checksum.
  // `also_keep`: one more key prefix kept while it writes (the pictures of a
  // theme being stored).
  bool write_stream(const std::string &key, const std::string &etag, size_t size,
                    const std::function<int(uint8_t *, int)> &read, uint32_t *crc_out = nullptr,
                    const std::string &also_keep = "");

 protected:
  struct Entry {
    uint32_t offset;
    uint32_t size;
    uint32_t seq;
    uint32_t crc;
    std::string etag;
  };
  uint32_t sectors_(uint32_t size) const;
  // Room for an entry of `size` bytes at the head: its offset, its erased
  // area forgotten; false when it does not fit.
  bool reserve_(size_t size, uint32_t *from, uint32_t *to, const std::string &key);
  bool write_stream_(const std::string &key, const std::string &etag, size_t size,
                     const std::function<int(uint8_t *, int)> &read, uint32_t *crc_out, uint32_t *from,
                     uint32_t *to);
  void commit_(const std::string &key, const std::string &etag, uint32_t from, uint32_t to, size_t size,
               uint32_t crc);
  void drop_range_(uint32_t from, uint32_t to);
  bool kept_(const std::string &key) const;
  // Writes the kept pictures that had to make room again at the head.
  void put_back_();
  struct Moved {
    std::string key;
    std::string etag;
    uint8_t *data;
    size_t size;
  };

  const esp_partition_t *part_{nullptr};
  std::map<std::string, Entry> index_;
  uint32_t head_{0};
  uint32_t next_seq_{1};
  mutable std::mutex keep_mutex_;
  std::vector<std::string> keep_;
  std::string also_keep_;
  std::vector<Moved> moved_;
  bool putting_back_{false};
};

}  // namespace esphome::kis_segito_ui
