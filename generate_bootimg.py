#!/usr/bin/env python3
import struct, gzip, hashlib, os

SRC = "BOOTIMG.bin"
DST = "bootimg_adb_root.bin"

NEW_DEFAULT_PROP = b"""#
# ADDITIONAL_DEFAULT_PROPERTIES
#
ro.secure=0
ro.allow.mock.location=0
persist.mtk.aee.aed=on
ro.debuggable=1
ro.adb.secure=0
persist.service.adb.enable=1
persist.sys.usb.config=mass_storage,adb
persist.service.acm.enable=0
ro.mount.fs=EXT4
ro.persist.partition.support=no
"""

def align(n, p): return ((n + p - 1) // p) * p

b = open(SRC, "rb").read()
k_size, k_addr, r_size, r_addr, s_size, s_addr, tags_addr, page_size = struct.unpack("<8I", b[8:40])
k_off = page_size
r_off = k_off + align(k_size, page_size)
kernel_data = b[k_off:k_off+k_size]

mtk_hdr = bytearray(b[r_off:r_off+512])
orig_gz_sz = struct.unpack("<I", mtk_hdr[4:8])[0]
cpio = gzip.decompress(b[r_off+512:r_off+512+orig_gz_sz])

# 1. Locate and patch sbin/adbd inside CPIO archive
# First extract adbd bytes
pos = 0
adbd_bytes = None
while pos < len(cpio):
    assert cpio[pos:pos+6] == b"070701"
    hdr = cpio[pos:pos+110]
    filesize = int(hdr[54:62], 16)
    namesize = int(hdr[94:102], 16)
    name_start = pos + 110
    name = cpio[name_start:name_start+namesize-1].decode("utf-8", errors="ignore")
    data_start = align(name_start + namesize, 4)
    data_end = data_start + filesize
    if name == "sbin/adbd":
        adbd_bytes = bytearray(cpio[data_start:data_end])
        break
    pos = align(data_end, 4)

assert adbd_bytes is not None

# Find ELF PT_LOAD segment for VA 0x9308
e_phoff = struct.unpack_from("<I", adbd_bytes, 28)[0]
e_phentsize, e_phnum = struct.unpack_from("<HH", adbd_bytes, 42)
file_off = None
for i in range(e_phnum):
    p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz = struct.unpack_from("<6I", adbd_bytes, e_phoff + i * e_phentsize)
    if p_type == 1 and p_vaddr <= 0x9308 < p_vaddr + p_filesz:
        file_off = p_offset + (0x9308 - p_vaddr)
        break

assert adbd_bytes[file_off:file_off+2] == bytes.fromhex("0024"), "Target bytes not matching!"
adbd_bytes[file_off:file_off+2] = bytes.fromhex("42e0") # b.n 0x9390
print(f"[+] Patched sbin/adbd at file offset 0x{file_off:x} -> 42 e0")

# 2. Rebuild CPIO with modified default.prop and patched sbin/adbd
out = bytearray()
pos = 0
replacements = {"default.prop": NEW_DEFAULT_PROP, "sbin/adbd": bytes(adbd_bytes)}
while pos < len(cpio):
    hdr = cpio[pos:pos+110]
    filesize = int(hdr[54:62], 16)
    namesize = int(hdr[94:102], 16)
    name_start = pos + 110
    name = cpio[name_start:name_start+namesize-1].decode("utf-8", errors="ignore")
    data_start = align(name_start + namesize, 4)
    data_end = data_start + filesize
    next_pos = align(data_end, 4)
    if name in replacements:
        rdata = replacements[name]
        new_hdr = hdr[:54] + f"{len(rdata):08x}".encode("ascii") + hdr[62:]
        out += new_hdr
        out += cpio[name_start:name_start+namesize]
        out += b"\x00" * (align(len(out), 4) - len(out))
        out += rdata
        out += b"\x00" * (align(len(out), 4) - len(out))
    else:
        out += cpio[pos:next_pos]
    pos = next_pos
    if name == "TRAILER!!!":
        out += b"\x00" * (align(len(out), 512) - len(out))
        break

new_gz = gzip.compress(bytes(out), compresslevel=9)
struct.pack_into("<I", mtk_hdr, 4, len(new_gz))
new_ramdisk = bytes(mtk_hdr) + new_gz
new_r_size = len(new_ramdisk)

new_hdr = bytearray(b[:page_size])
struct.pack_into("<I", new_hdr, 16, new_r_size)

# Update SHA1
sha = hashlib.sha1()
sha.update(kernel_data)
sha.update(struct.pack("<I", k_size))
sha.update(new_ramdisk)
sha.update(struct.pack("<I", new_r_size))
sha.update(b"")
sha.update(struct.pack("<I", s_size))
new_hdr[576:596] = sha.digest()

img = bytearray()
img += new_hdr
img += kernel_data + b"\x00" * (align(k_size, page_size) - k_size)
img += new_ramdisk + b"\x00" * (align(new_r_size, page_size) - new_r_size)

open(DST, "wb").write(img)
print(f"[+] Rebuilt {DST} ({len(img)} bytes) successfully!")