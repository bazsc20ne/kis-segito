// SPDX-License-Identifier: AGPL-3.0-only
// A small deflate decoder for the compressed pictures Home Assistant sends.

#include "inflate.h"

#include <cstring>
#include <memory>
#include <new>

namespace esphome {
namespace kis_segito_ui {

namespace {

constexpr int MAX_BITS = 15;

struct Huffman {
  uint16_t count[MAX_BITS + 1];  // codes of each length
  uint16_t symbol[288];          // symbols ordered by code
};

class Inflater {
 public:
  Inflater(const uint8_t *in, size_t in_len, uint8_t *out, size_t out_len)
      : in_(in), in_len_(in_len), out_(out), out_len_(out_len) {}

  bool run() {
    bool last = false;
    while (!last) {
      last = bits_(1) == 1;
      const int type = bits_(2);
      bool ok = false;
      if (type == 0)
        ok = stored_();
      else if (type == 1)
        ok = fixed_();
      else if (type == 2)
        ok = dynamic_();
      if (!ok || error_)
        return false;
    }
    return out_pos_ == out_len_;
  }

 private:
  int bits_(int need) {
    uint32_t val = bit_buf_;
    while (bit_cnt_ < need) {
      if (in_pos_ >= in_len_) {
        error_ = true;
        return 0;
      }
      val |= static_cast<uint32_t>(in_[in_pos_++]) << bit_cnt_;
      bit_cnt_ += 8;
    }
    bit_buf_ = val >> need;
    bit_cnt_ -= need;
    return static_cast<int>(val & ((1u << need) - 1));
  }

  bool stored_() {
    bit_buf_ = 0;
    bit_cnt_ = 0;
    if (in_pos_ + 4 > in_len_)
      return false;
    const unsigned len = in_[in_pos_] | (in_[in_pos_ + 1] << 8);
    const unsigned nlen = in_[in_pos_ + 2] | (in_[in_pos_ + 3] << 8);
    in_pos_ += 4;
    if (len != (~nlen & 0xffff) || in_pos_ + len > in_len_ || out_pos_ + len > out_len_)
      return false;
    memcpy(out_ + out_pos_, in_ + in_pos_, len);
    in_pos_ += len;
    out_pos_ += len;
    return true;
  }

  // Builds a canonical Huffman table from code lengths. Returns false for an
  // over-subscribed set; an incomplete one is allowed (as deflate needs for a
  // single distance code).
  static bool build_(Huffman &h, const uint8_t *lengths, int n) {
    memset(h.count, 0, sizeof(h.count));
    for (int i = 0; i < n; i++)
      h.count[lengths[i]]++;
    if (h.count[0] == n)
      return true;
    int left = 1;
    for (int len = 1; len <= MAX_BITS; len++) {
      left <<= 1;
      left -= h.count[len];
      if (left < 0)
        return false;
    }
    uint16_t offs[MAX_BITS + 1];
    offs[1] = 0;
    for (int len = 1; len < MAX_BITS; len++)
      offs[len + 1] = offs[len] + h.count[len];
    for (int i = 0; i < n; i++)
      if (lengths[i] != 0)
        h.symbol[offs[lengths[i]]++] = i;
    return true;
  }

  int decode_(const Huffman &h) {
    int code = 0;   // bits read so far
    int first = 0;  // first code of this length
    int index = 0;  // index of that code in symbol[]
    for (int len = 1; len <= MAX_BITS; len++) {
      code |= bits_(1);
      if (error_)
        return -1;
      const int count = h.count[len];
      if (code - count < first)
        return h.symbol[index + (code - first)];
      index += count;
      first += count;
      first <<= 1;
      code <<= 1;
    }
    error_ = true;
    return -1;
  }

  bool codes_(const Huffman &lit, const Huffman &dist) {
    static const uint16_t LEN_BASE[29] = {3,  4,  5,  6,  7,  8,  9,  10, 11,  13,  15,  17,  19,  23, 27,
                                          31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258};
    static const uint8_t LEN_EXTRA[29] = {0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2,
                                          2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0};
    static const uint16_t DIST_BASE[30] = {1,   2,   3,   4,   5,   7,    9,    13,   17,   25,
                                           33,  49,  65,  97,  129, 193,  257,  385,  513,  769,
                                           1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577};
    static const uint8_t DIST_EXTRA[30] = {0, 0, 0, 0, 1, 1, 2, 2,  3,  3,  4,  4,  5,  5,  6,
                                           6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13};
    while (true) {
      int sym = decode_(lit);
      if (sym < 0)
        return false;
      if (sym < 256) {
        if (out_pos_ >= out_len_)
          return false;
        out_[out_pos_++] = static_cast<uint8_t>(sym);
        continue;
      }
      if (sym == 256)
        return true;
      sym -= 257;
      if (sym >= 29)
        return false;
      const size_t len = LEN_BASE[sym] + bits_(LEN_EXTRA[sym]);
      const int dsym = decode_(dist);
      if (dsym < 0 || dsym >= 30)
        return false;
      const size_t d = DIST_BASE[dsym] + bits_(DIST_EXTRA[dsym]);
      if (error_ || d > out_pos_ || out_pos_ + len > out_len_)
        return false;
      for (size_t i = 0; i < len; i++, out_pos_++)
        out_[out_pos_] = out_[out_pos_ - d];
    }
  }

  bool fixed_() {
    uint8_t lengths[288 + 30];
    int i = 0;
    for (; i < 144; i++)
      lengths[i] = 8;
    for (; i < 256; i++)
      lengths[i] = 9;
    for (; i < 280; i++)
      lengths[i] = 7;
    for (; i < 288; i++)
      lengths[i] = 8;
    for (; i < 288 + 30; i++)
      lengths[i] = 5;
    build_(lit_, lengths, 288);
    build_(dist_, lengths + 288, 30);
    return codes_(lit_, dist_);
  }

  bool dynamic_() {
    static const uint8_t ORDER[19] = {16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15};
    const int nlen = bits_(5) + 257;
    const int ndist = bits_(5) + 1;
    const int ncode = bits_(4) + 4;
    if (error_ || nlen > 286 || ndist > 30)
      return false;
    uint8_t lengths[286 + 30] = {0};
    for (int i = 0; i < ncode; i++)
      lengths[ORDER[i]] = bits_(3);
    if (!build_(lit_, lengths, 19))
      return false;
    int index = 0;
    while (index < nlen + ndist) {
      int sym = decode_(lit_);
      if (sym < 0)
        return false;
      if (sym < 16) {
        lengths[index++] = sym;
        continue;
      }
      uint8_t len = 0;
      int repeat;
      if (sym == 16) {
        if (index == 0)
          return false;
        len = lengths[index - 1];
        repeat = 3 + bits_(2);
      } else if (sym == 17) {
        repeat = 3 + bits_(3);
      } else {
        repeat = 11 + bits_(7);
      }
      if (error_ || index + repeat > nlen + ndist)
        return false;
      while (repeat--)
        lengths[index++] = len;
    }
    if (lengths[256] == 0)
      return false;
    if (!build_(lit_, lengths, nlen) || !build_(dist_, lengths + nlen, ndist))
      return false;
    return codes_(lit_, dist_);
  }

  const uint8_t *in_;
  size_t in_len_;
  size_t in_pos_{0};
  uint8_t *out_;
  size_t out_len_;
  size_t out_pos_{0};
  uint32_t bit_buf_{0};
  int bit_cnt_{0};
  bool error_{false};
  Huffman lit_;
  Huffman dist_;
};

}  // namespace

bool zlib_inflate(const uint8_t *in, size_t in_len, uint8_t *out, size_t out_len) {
  // zlib header: deflate method, no preset dictionary.
  if (in_len < 6 || (in[0] & 0x0f) != 8 || ((in[0] << 8) | in[1]) % 31 != 0 || (in[1] & 0x20) != 0)
    return false;
  // The tables live on the heap, not on the calling task's stack. The
  // Adler-32 sum at the end is not checked.
  std::unique_ptr<Inflater> inflater(new (std::nothrow) Inflater(in + 2, in_len - 6, out, out_len));
  return inflater != nullptr && inflater->run();
}

}  // namespace kis_segito_ui
}  // namespace esphome
