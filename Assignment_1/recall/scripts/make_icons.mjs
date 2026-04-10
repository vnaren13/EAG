// Generate simple placeholder PNGs for the extension toolbar.
// Pure-Node, no dependencies — uses zlib for the IDAT chunk.
//
// Three sizes (16, 48, 128) with a solid blue background and a white "R"
// glyph drawn from a 5×7 bitmap. Good enough until real icons land.

import { writeFileSync, mkdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { deflateSync } from 'node:zlib';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT_DIR = join(__dirname, '..', 'public', 'icons');
mkdirSync(OUT_DIR, { recursive: true });

// 5×7 bitmap for the letter 'R'.
const R_GLYPH = [
  '#### ',
  '#   #',
  '#   #',
  '#### ',
  '## . ',
  '#  # ',
  '#   #',
];

const BG = [37, 99, 235];   // tailwind blue-600
const FG = [255, 255, 255]; // white

function makePngBuffer(size) {
  const W = size;
  const H = size;
  const px = new Uint8Array(W * H * 4);

  // Fill background.
  for (let i = 0; i < W * H; i++) {
    px[i * 4 + 0] = BG[0];
    px[i * 4 + 1] = BG[1];
    px[i * 4 + 2] = BG[2];
    px[i * 4 + 3] = 255;
  }

  // Draw the R glyph centered, scaled to ~60% of the icon.
  const glyphH = R_GLYPH.length;
  const glyphW = R_GLYPH[0].length;
  const scale = Math.max(1, Math.floor((size * 0.6) / Math.max(glyphH, glyphW)));
  const drawW = glyphW * scale;
  const drawH = glyphH * scale;
  const offX = Math.floor((W - drawW) / 2);
  const offY = Math.floor((H - drawH) / 2);

  for (let gy = 0; gy < glyphH; gy++) {
    for (let gx = 0; gx < glyphW; gx++) {
      if (R_GLYPH[gy][gx] !== '#') continue;
      for (let dy = 0; dy < scale; dy++) {
        for (let dx = 0; dx < scale; dx++) {
          const x = offX + gx * scale + dx;
          const y = offY + gy * scale + dy;
          if (x < 0 || y < 0 || x >= W || y >= H) continue;
          const idx = (y * W + x) * 4;
          px[idx + 0] = FG[0];
          px[idx + 1] = FG[1];
          px[idx + 2] = FG[2];
          px[idx + 3] = 255;
        }
      }
    }
  }

  // Encode as PNG.
  const filtered = new Uint8Array(H * (W * 4 + 1));
  for (let y = 0; y < H; y++) {
    filtered[y * (W * 4 + 1)] = 0; // filter type "none"
    filtered.set(px.subarray(y * W * 4, (y + 1) * W * 4), y * (W * 4 + 1) + 1);
  }
  const idatData = deflateSync(filtered);

  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(W, 0);
  ihdr.writeUInt32BE(H, 4);
  ihdr[8] = 8;   // bit depth
  ihdr[9] = 6;   // color type RGBA
  ihdr[10] = 0;  // compression
  ihdr[11] = 0;  // filter
  ihdr[12] = 0;  // interlace

  const SIG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  return Buffer.concat([
    SIG,
    chunk('IHDR', ihdr),
    chunk('IDAT', idatData),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length, 0);
  const typeBuf = Buffer.from(type, 'ascii');
  const crcBuf = Buffer.alloc(4);
  crcBuf.writeUInt32BE(crc32(Buffer.concat([typeBuf, data])), 0);
  return Buffer.concat([len, typeBuf, data, crcBuf]);
}

// Tiny CRC32 implementation (PNG spec).
const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();
function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

for (const size of [16, 48, 128]) {
  const out = join(OUT_DIR, `icon-${size}.png`);
  writeFileSync(out, makePngBuffer(size));
  console.log('wrote', out);
}
