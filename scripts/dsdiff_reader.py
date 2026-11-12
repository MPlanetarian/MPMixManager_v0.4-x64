"""Read DSDIFF (.dff) audio by presenting it to FFmpeg as a DSF stream.

FFmpeg ships a DSF demuxer and DSD decoders but no DSDIFF demuxer, so a .dff
file opens as "Invalid data found when processing input". The two containers
carry the same 1-bit DSD payload with different framing:

  DSDIFF  the 'DSD ' chunk stores sample bytes interleaved per channel:
          c0 c1 c0 c1 ...
  DSF     the 'data' chunk stores whole blocks per channel:
          c0 block, c1 block, c0 block, ...

This module parses the DSDIFF header, rewrites the payload into DSF block
order and feeds it to FFmpeg through a pipe with ``-f dsf``. Uncompressed DSD
(a 'DSD ' CMPR chunk) is supported; the rarely used DST compression is not,
because FFmpeg has no DST decoder either.

Reference: DSDIFF File Format Specification v1.5, Sony DSF format 1.01.
"""

from __future__ import annotations

import os
import struct
from pathlib import Path
from typing import BinaryIO, Iterator, Optional, Union

# DSF stores fixed 4096-byte blocks per channel; DSDIFF has no block concept.
DSF_BLOCK_SIZE = 4096
# 0x69 is the usual DSD silence byte. Padding a short final block with zeros
# would produce a full-scale DC step and an audible click.
DSD_SILENCE_BYTE = 0x69
DSD_BASE_RATE = 2822400  # 44.1 kHz / 64, the rate of a standard SACD

_FRM8 = b"FRM8"
_FORM_DSD = b"DSD "

# Chunk ids whose bodies are nested chunks, not audio or plain values.
_PROP = b"PROP"
_SND = b"SND "


class DSDiffError(Exception):
    """The file is not a readable uncompressed DSDIFF stream."""


class DSDiffInfo:
    """Everything playback needs, read from the DSDIFF header."""

    __slots__ = ("path", "channels", "sample_rate", "data_offset", "data_size", "compression")

    def __init__(self, path: str, channels: int, sample_rate: int,
                 data_offset: int, data_size: int, compression: str):
        self.path = path
        self.channels = channels
        self.sample_rate = sample_rate
        self.data_offset = data_offset
        self.data_size = data_size
        self.compression = compression

    @property
    def is_compressed(self) -> bool:
        return self.compression.upper().startswith("DST")

    @property
    def bits_per_channel(self) -> int:
        """DSD data is 1 bit per sample per channel."""
        if self.channels <= 0:
            return 0
        return (self.data_size // self.channels) * 8

    @property
    def duration(self) -> float:
        if self.sample_rate <= 0:
            return 0.0
        return self.bits_per_channel / float(self.sample_rate)

    def block_bytes(self) -> int:
        """Bytes needed for one DSF block of every channel."""
        return DSF_BLOCK_SIZE * self.channels


def _read_exact(fh: BinaryIO, count: int) -> bytes:
    data = fh.read(count)
    if len(data) != count:
        raise DSDiffError("truncated DSDIFF header")
    return data


def _read_chunk_id(fh: BinaryIO) -> bytes:
    return _read_exact(fh, 4)


def _read_uint64(fh: BinaryIO) -> int:
    return struct.unpack(">Q", _read_exact(fh, 8))[0]


def _skip(fh: BinaryIO, size: int) -> None:
    """Chunks are padded to an even length."""
    fh.seek(size + (size & 1), os.SEEK_CUR)


def _parse_prop(fh: BinaryIO, size: int, info: dict) -> None:
    end = fh.tell() + size
    form = _read_exact(fh, 4)
    if form != _SND:
        fh.seek(end)
        return
    while fh.tell() + 12 <= end:
        cid = _read_chunk_id(fh)
        csize = _read_uint64(fh)
        if cid == b"FS  ":
            info["sample_rate"] = struct.unpack(">I", _read_exact(fh, 4))[0]
            _skip(fh, csize - 4)
        elif cid == b"CHNL":
            channels = struct.unpack(">H", _read_exact(fh, 2))[0]
            info["channels"] = channels
            _skip(fh, csize - 2)
        elif cid == b"CMPR":
            info["compression"] = _read_exact(fh, 4).decode("ascii", "replace").strip()
            _skip(fh, csize - 4)
        else:
            _skip(fh, csize)
    fh.seek(end)


def read_info(path: Union[str, Path]) -> DSDiffInfo:
    """Parse a DSDIFF header. Raises DSDiffError when it is not DSDIFF."""
    p = Path(path)
    try:
        fh = p.open("rb")
    except OSError as exc:
        raise DSDiffError(f"cannot open {p.name}: {exc}") from exc
    with fh:
        if _read_chunk_id(fh) != _FRM8:
            raise DSDiffError(f"{p.name} is not a DSDIFF (FRM8) file")
        form_size = _read_uint64(fh)
        del form_size  # only used to skip by whole chunks below
        if _read_exact(fh, 4) != _FORM_DSD:
            raise DSDiffError(f"{p.name} is not a DSDIFF DSD stream")

        info: dict = {"channels": 0, "sample_rate": 0, "compression": ""}
        while True:
            try:
                cid = _read_chunk_id(fh)
            except DSDiffError:
                break  # clean end of file
            try:
                csize = _read_uint64(fh)
            except DSDiffError:
                break
            if cid == _PROP:
                _parse_prop(fh, csize, info)
            elif cid == b"DSD ":
                offset = fh.tell()
                channels = int(info["channels"] or 0)
                rate = int(info["sample_rate"] or 0)
                if channels <= 0:
                    raise DSDiffError(f"{p.name} does not declare its channels")
                return DSDiffInfo(str(p), channels, rate, offset, csize,
                                  str(info["compression"] or "DSD"))
            else:
                _skip(fh, csize)
    raise DSDiffError(f"{p.name} has no DSD audio chunk")


def dsf_header(info: DSDiffInfo, start_block: int = 0) -> bytes:
    """A complete DSF header describing the DSDIFF payload from `start_block`."""
    block_size = DSF_BLOCK_SIZE
    # Round up: DSDIFF has no block alignment, so the last block is padded with
    # silence rather than dropping part of the final sample group.
    total_blocks = -(-info.data_size // info.block_bytes())
    start_block = max(0, min(int(start_block), total_blocks))
    remaining_blocks = total_blocks - start_block
    sample_count = remaining_blocks * block_size * 8
    fmt_size = 52
    data_size = remaining_blocks * info.block_bytes()
    file_size = 28 + (12 + fmt_size) + (12 + data_size)

    dsd = b"DSD " + struct.pack("<Q", 28) + struct.pack("<Q", file_size) + struct.pack("<Q", 0)
    fmt = b"fmt " + struct.pack("<Q", fmt_size)
    fmt += struct.pack("<I", 1)                      # format version
    fmt += struct.pack("<I", 0)                      # format id: DSD raw
    fmt += struct.pack("<I", min(info.channels, 7))  # channel type
    fmt += struct.pack("<I", info.channels)          # channel count
    fmt += struct.pack("<I", info.sample_rate or DSD_BASE_RATE)
    fmt += struct.pack("<I", 1)                      # bits per sample
    fmt += struct.pack("<Q", sample_count)
    fmt += struct.pack("<I", block_size)
    fmt += struct.pack("<I", 0)                      # reserved
    data = b"data" + struct.pack("<Q", data_size)
    return dsd + fmt + data


def block_count(info: DSDiffInfo) -> int:
    return -(-info.data_size // info.block_bytes())


def iter_dsf_stream(path: Union[str, Path], info: Optional[DSDiffInfo] = None,
                    chunk_blocks: int = 16, start_block: int = 0) -> Iterator[bytes]:
    """Yield a DSF header followed by the payload re-blocked for DSF."""
    info = info or read_info(path)
    if info.is_compressed:
        raise DSDiffError(
            f"{Path(path).name} uses DST compression, which FFmpeg cannot decode"
        )
    total = block_count(info)
    start_block = max(0, min(int(start_block), total))
    yield dsf_header(info, start_block)

    channels, block = info.channels, DSF_BLOCK_SIZE
    frame_bytes = channels * block
    skip = start_block * frame_bytes
    with open(path, "rb") as fh:
        fh.seek(info.data_offset + skip)
        remaining = info.data_size - skip
        while remaining > 0:
            group = min(chunk_blocks * frame_bytes, remaining)
            raw = fh.read(group)
            if not raw:
                break
            remaining -= len(raw)
            usable = (len(raw) // frame_bytes) * frame_bytes
            out = bytearray()
            for base in range(0, usable, frame_bytes):
                window = raw[base:base + frame_bytes]
                for ch in range(channels):
                    out += window[ch::channels]
            if usable < len(raw):
                # Re-block the final partial frame and pad it with DSD silence.
                partial = raw[usable:]
                tail = bytearray(frame_bytes)
                for index in range(channels):
                    mono = partial[index::channels]
                    start = index * block
                    tail[start:start + len(mono)] = mono
                    tail[start + len(mono):start + block] = bytes([DSD_SILENCE_BYTE]) * (block - len(mono))
                out += tail
            yield bytes(out)


def cached_dsf_path(path: Union[str, Path]) -> Optional[Path]:
    """A previously converted DSF sitting beside the source, if one exists."""
    source = Path(path)
    candidate = source.with_suffix(".dff.dsf")
    return candidate if candidate.is_file() else None


def convert_to_dsf(path: Union[str, Path], dest: Union[str, Path]) -> Path:
    """Write a DSF copy of a DSDIFF file. Used when a seekable copy is wanted."""
    target = Path(dest)
    tmp = target.with_suffix(target.suffix + ".part")
    info = read_info(path)
    with tmp.open("wb") as out:
        for chunk in iter_dsf_stream(path, info):
            out.write(chunk)
    tmp.replace(target)
    return target


def is_dsdiff(path: Union[str, Path, None]) -> bool:
    return os.path.splitext(str(path or ""))[1].lower() in (".dff", ".dsdiff")


if __name__ == "__main__":
    import sys
    target = sys.argv[1]
    details = read_info(target)
    print(f"{details.channels} ch  {details.sample_rate} Hz  "
          f"{details.duration:.2f}s  {details.data_size} bytes  {details.compression}")
