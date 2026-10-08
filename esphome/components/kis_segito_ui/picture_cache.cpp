// SPDX-License-Identifier: AGPL-3.0-only

#include "picture_cache.h"

#include <cstring>

#include <esp_heap_caps.h>
#include <esp_rom_crc.h>

#include "esphome/core/log.h"

namespace esphome::kis_segito_ui {

static const char *const TAG = "kis_segito_ui.cache";

static constexpr uint32_t SECTOR = 4096;
static constexpr char MAGIC[4] = {'K', 'S', 'C', '1'};

struct Header {
  char magic[4];
  uint32_t seq;
  uint32_t size;
  uint32_t data_crc;
  char key[80];
  char etag[44];
  uint32_t header_crc;  // over everything above
};

static uint32_t header_crc(const Header &h) {
  return esp_rom_crc32_le(0, reinterpret_cast<const uint8_t *>(&h), offsetof(Header, header_crc));
}

uint32_t PictureCache::sectors_(uint32_t size) const { return (sizeof(Header) + size + SECTOR - 1) / SECTOR; }

bool PictureCache::begin() {
  this->part_ = esp_partition_find_first(ESP_PARTITION_TYPE_DATA, static_cast<esp_partition_subtype_t>(0x40),
                                         "ks_cache");
  if (this->part_ == nullptr) {
    ESP_LOGW(TAG, "No picture cache partition: pictures are downloaded after every start. Flash the factory "
                  "firmware over USB once to add it.");
    return false;
  }
  const uint32_t total = this->part_->size / SECTOR;
  uint32_t best_seq = 0;
  Header h;
  for (uint32_t s = 0; s < total;) {
    if (esp_partition_read(this->part_, s * SECTOR, &h, sizeof(h)) != ESP_OK)
      break;
    if (memcmp(h.magic, MAGIC, 4) != 0 || h.header_crc != header_crc(h) || h.size == 0 ||
        s + this->sectors_(h.size) > total) {
      s++;
      continue;
    }
    h.key[sizeof(h.key) - 1] = 0;
    h.etag[sizeof(h.etag) - 1] = 0;
    auto it = this->index_.find(h.key);
    if (it == this->index_.end() || it->second.seq < h.seq)
      this->index_[h.key] = {s * SECTOR, h.size, h.seq, h.data_crc, h.etag};
    if (h.seq >= best_seq) {
      best_seq = h.seq;
      this->head_ = (s + this->sectors_(h.size)) % total;
    }
    s += this->sectors_(h.size);
  }
  this->next_seq_ = best_seq + 1;
  ESP_LOGI(TAG, "Picture cache: %u pictures, %u KB partition", (unsigned) this->index_.size(),
           (unsigned) (this->part_->size / 1024));
  return true;
}

// Forgets the entries that start in [from, to) (their header is erased).
void PictureCache::drop_range_(uint32_t from, uint32_t to) {
  for (auto it = this->index_.begin(); it != this->index_.end();) {
    if (it->second.offset >= from && it->second.offset < to) {
      it = this->index_.erase(it);
    } else {
      ++it;
    }
  }
}

uint8_t *PictureCache::read(const std::string &key, size_t *size, std::string *etag) {
  if (this->part_ == nullptr)
    return nullptr;
  auto it = this->index_.find(key);
  if (it == this->index_.end())
    return nullptr;
  const Entry e = it->second;
  auto *buf = static_cast<uint8_t *>(heap_caps_malloc(e.size, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  if (buf == nullptr)
    return nullptr;
  if (esp_partition_read(this->part_, e.offset + sizeof(Header), buf, e.size) != ESP_OK ||
      esp_rom_crc32_le(0, buf, e.size) != e.crc) {
    ESP_LOGW(TAG, "Cached picture %s is damaged; downloading it again", key.c_str());
    heap_caps_free(buf);
    this->index_.erase(key);
    return nullptr;
  }
  *size = e.size;
  *etag = e.etag;
  // Used again shortly before the ring would erase it: keep it by writing it
  // again at the head.
  const uint32_t ahead = (e.offset + this->part_->size - this->head_) % this->part_->size;
  if (ahead < this->part_->size / 4)
    this->write(key, e.etag, buf, e.size);
  return buf;
}

bool PictureCache::write(const std::string &key, const std::string &etag, const uint8_t *data, size_t size) {
  if (this->part_ == nullptr || size == 0 || key.size() >= sizeof(Header::key) ||
      etag.size() >= sizeof(Header::etag))
    return false;
  const uint32_t total = this->part_->size / SECTOR;
  const uint32_t n = this->sectors_(size);
  if (n > total / 2)
    return false;
  uint32_t start = this->head_;
  if (start + n > total)
    start = 0;  // entries never wrap around the end
  const uint32_t from = start * SECTOR, to = (start + n) * SECTOR;
  this->drop_range_(from, to);
  if (esp_partition_erase_range(this->part_, from, to - from) != ESP_OK ||
      esp_partition_write(this->part_, from + sizeof(Header), data, size) != ESP_OK) {
    ESP_LOGW(TAG, "Writing picture %s to the cache failed", key.c_str());
    return false;
  }
  Header h{};
  memcpy(h.magic, MAGIC, 4);
  h.seq = this->next_seq_++;
  h.size = size;
  h.data_crc = esp_rom_crc32_le(0, data, size);
  strncpy(h.key, key.c_str(), sizeof(h.key) - 1);
  strncpy(h.etag, etag.c_str(), sizeof(h.etag) - 1);
  h.header_crc = header_crc(h);
  if (esp_partition_write(this->part_, from, &h, sizeof(h)) != ESP_OK)
    return false;
  this->index_[key] = {from, static_cast<uint32_t>(size), h.seq, h.data_crc, etag};
  this->head_ = (start + n) % total;
  return true;
}

}  // namespace esphome::kis_segito_ui
