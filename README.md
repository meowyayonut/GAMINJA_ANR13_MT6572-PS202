# MediaTek MT6572 / PS202 (ANR13) — Complete Bit-for-Bit Unbrick (boot1/boot2/user.bin), EMI 0x0B DA Fix, Modern ADB Fix & Permanent Boot-Time Root Patch

```
/*
 * Your warranty is now void.
 *
 * I am not responsible for bricked devices, dead SD cards, thermonuclear war, or
 * you getting fired because the alarm app failed. Please do some research if you
 * have any concerns about features included in this guide before flashing it!
 * YOU are choosing to make these modifications, and if you point the finger at me
 * for messing up your device, I will laugh at you.
 */
```

---

## 📌 Overview & Background

If you own a **MediaTek MT6572** device based on the **PS202 / ANR13** platform (`ps202_ans13_yl72_cwet_kk`, running Android 4.4.2 KitKat) and ended up with a hard-bricked device, a bootloop, or corrupted eMMC partitions, this guide is for you.

This release provides:
1. **Full 1:1 Factory eMMC Raw Dumps** (`boot1.bin`, `boot2.bin`, `user.bin`) to completely restore an eMMC from scratch.
   
   1a. [user.bin is too large to be uploaded on GitHub, use this direct link](https://buzzheavier.com/3800u4g6wxtp)
3. **The 0x0B EMI Handshake Fix**: Solves the dreaded DA hang when using `mtkclient` / open-source MTK flashing utilities on MT6572.
4. **The Modern ADB Freeze Fix**: Solves the mysterious `adb shell` / `adb root` timeout when running modern platform-tools on Linux.
5. **Permanent Boot-Time Root (`sbin/adbd` 2-byte patch)**: Bypasses production `ALLOW_ADBD_ROOT=0` build restrictions directly inside the ramdisk binary, giving you native `uid=0(root)` with full capabilities on every boot.

---

## 📱 Hardware & Partition Specifications

* **SoC:** MediaTek MT6572 (Cortex-A7 Dual-Core)
* **Target Board / Model:** PS202 / `ps202_ans13_yl72_cwet_kk` (ANR13)
* **USB BROM ID:** `0e8d:0003` (MediaTek Inc. MT6227 / BROM)
* **USB ADB ID:** `0bb4:0c03` (High Tech Computer Corp. / Android ADB)
* **OS Version:** Android 4.4.2 KitKat (Kernel 3.4.67)
* **eMMC Layout:**
  * **`boot1.bin`** (2,097,152 bytes / 2.0 MB): Hardware Boot Partition 1. Starts with `EMMC_BOOT` header at `0x000` and `MMM` MediaTek Preloader header at `0x800` (EMI Version `0x0B`).
  * **`boot2.bin`** (2,097,152 bytes / 2.0 MB): Hardware Boot Partition 2 (identical 1:1 duplicate of `boot1.bin`).
  * **`user.bin`** (3,875,536,896 bytes / ~3.7 GB): Full raw User Area eMMC image:
    * `0x00000000` (0 MB – 20 MB): Raw Preloader / PMT mirror
    * `0x01400000` (20 MB): Master Boot Record (`MBR.bin`)
    * `0x01480000` (20.5 MB): Extended Boot Record (`EBR1.bin`)
    * `0x03180000` (49.5 MB / Sector 101376): `BOOTIMG` partition (6 MB / `0x600000`)
    * Followed by `RECOVERY`, `SEC_RO`, `MISC`, `LOGO`, `EXPDB`, `ANDROID` (System EXT4), `CACHE`, `USRDATA`, and `FAT`.

---

## 🗂️ Package Contents & Downloads

Place your factory dumps and patched boot files in your working directory:

| Filename | Size | Description |
| :--- | :--- | :--- |
| `boot1.bin` | 2.0 MB | Hardware Boot Partition 1 (Native Preloader with EMI v11) |
| `boot2.bin` | 2.0 MB | Hardware Boot Partition 2 |
| `user.bin` | 3.7 GB | Full eMMC raw user dump (MBR, PMT, system, data, cache) |
| `BOOTIMG.bin` | 6.0 MB | Stock untouched Android 4.4.2 Boot Image |
| `bootimg_adb_root.bin` | 4.0 MB | Modified Boot Image (`default.prop` + patched `sbin/adbd` root) |

---

## 🚨 Critical Gotchas Solved

### Gotcha 1: The `0x0B` EMI DRAM Handshake Hang in `mtkclient`
When using standard `mtkclient` or generic DA loaders on MT6572, the tool extracts an EMI table of 1512 bytes from the preloader and attempts to send it to the legacy Download Agent (DA). The MT6572 legacy DA only expects the first **168 bytes (`0xa8`)** for EMI Version `0x0B`. Sending the full 1512 bytes triggers a checksum failure or infinite freeze:
```
DALegacy - Sending dram info ... EMI-Version 0xb
[FREEZE / TIMEOUT]
```
**Fix:** Truncate the EMI data to `0xa8` bytes before sending:
```python
daconfig.emi = daconfig.emi[:0xa8]
```

### Gotcha 2: Modern ADB (`ADB_LIBUSB=1`) Freezes on Android 4.4 Gadget
If you are running `adb` version 30+ (specifically `37.0.0p1-android-tools`), `adb devices -l` will detect the device, but any `adb shell`, `adb root`, or data transfer will hang indefinitely:
```bash
$ adb devices -l
List of devices attached
0123456789ABCDEF  device product:ps202_ans13_yl72_cwet_kk model:PS202
$ adb shell id
[HANGS / TIMEOUT]
```
**Fix:** Modern `adb` defaults to the `libusb` wrapper backend which breaks bulk endpoints on older 3.4.x Linux USB gadget drivers. Force native Linux `usbfs` by setting `ADB_LIBUSB=0`:
```bash
adb kill-server
ADB_LIBUSB=0 adb start-server
```

### Gotcha 3: Production `adbd` Drops Privileges (The `ALLOW_ADBD_ROOT=0` Trap)
Even if you set `ro.secure=0`, `ro.debuggable=1`, and `service.adb.root=1` in `default.prop`, stock MTK KitKat `adbd` was compiled with `ALLOW_ADBD_ROOT=0`. The binary does not even check `ro.secure`. Instead, `adb_main()` unconditionally drops root capabilities and calls:
```c
prctl(PR_CAPBSET_DROP, ...);
setgroups(10, groups);
setgid(2000); // AID_SHELL
setuid(2000); // AID_SHELL
```
If you run `adb root`, `adbd` sets `service.adb.root=1` and calls `exit(1)`, but upon respawn it still drops to `uid=2000(shell)` and crashes the USB transport.
**Fix:** A 2-byte Thumb-1 branch patch (`b.n 0x9390`) at VA `0x9308` in `sbin/adbd` completely skips the capability and UID/GID drop routine!

---

## 🛠️ Step-by-Step Instructions

### Step 1: Complete 100% Unbrick & Restoration

If your device is hard-bricked, in a bootloop, or has a destroyed partition table:

1. Connect the MT6572 device in **BROM mode** (power off, hold Volume Up or test-point, and plug USB cable into PC). `lsusb` should show:
   ```
   Bus 001 Device 026: ID 0e8d:0003 MediaTek Inc. MT6227 phone
   ```
2. Run the dedicated flash script containing the `0x0B` EMI fix. Below is the complete Python script (`flash_mt6572.py`):

```python
#!/usr/bin/env python3
import sys, os, time
from mtkclient.Library.mtk_main import Mtk
from mtkclient.config.mtk_config import MtkConfig
from mtkclient.Library.DA.daconfig import DAconfig

WORK_DIR = os.path.abspath(os.path.dirname(__file__))

def patch_emi_version_b():
    orig_extract_emi = DAconfig.extract_emi
    def patched_extract_emi(self, preloader):
        res = orig_extract_emi(self, preloader)
        if self.emiver == 0x0B and self.emi is not None:
            print(f"[*] Applying MT6572 0x0B EMI truncation fix: {len(self.emi)} -> 0xA8 bytes")
            self.emi = self.emi[:0xA8]
        return res
    DAconfig.extract_emi = patched_extract_emi

def flash_full():
    patch_emi_version_b()
    config = MtkConfig()
    config.preloader = os.path.join(WORK_DIR, "boot1.bin")
    
    print("[*] Initializing mtkclient DA interface...")
    mtk = Mtk(config=config, loglevel=20)
    
    if not mtk.init():
        print("[-] Failed to initialize device in BROM mode.")
        sys.exit(1)
        
    print("[+] BROM Handshake & DA Sync established!")
    
    partitions = [
        ("boot1", "boot1.bin"),
        ("boot2", "boot2.bin"),
        ("user",  "user.bin")
    ]
    
    for parttype, filename in partitions:
        filepath = os.path.join(WORK_DIR, filename)
        filesize = os.path.getsize(filepath)
        print(f"[*] Flashing {filename} ({filesize / (1024*1024):.2f} MB) to parttype: {parttype}...")
        start_t = time.time()
        # Flash starting from sector 0 of the partition type
        res = mtk.daloader.writeflash(addr=0, length=filesize, filename=filepath, parttype=parttype)
        if res:
            print(f"[+] {filename} flashed successfully in {time.time() - start_t:.2f}s!")
        else:
            print(f"[-] Error flashing {filename}")
            sys.exit(1)
            
    print("[*] Flashing complete! Rebooting device...")
    mtk.daloader.reset()
    print("[SUCCESS] Device restored bit-for-bit to factory stock!")

if __name__ == "__main__":
    flash_full()
```

Run:
```bash
python3 flash_mt6572.py
```
This writes `boot1.bin` (2MB), `boot2.bin` (2MB), and the entire `user.bin` (3.7GB) in one single continuous DA session, restoring every partition, NVRAM, and PMT.

---

### Step 2: Fixing ADB Communication on Modern Host Linux

Before interacting with the device over ADB, always ensure modern `android-tools` does not choke on KitKat's USB gadget:

```bash
# 1. Kill any existing ADB server
adb kill-server

# 2. Start ADB server with libusb disabled (forces usbfs)
ADB_LIBUSB=0 adb start-server

# 3. Verify device connection
adb devices -l
```
Output:
```
List of devices attached
0123456789ABCDEF  device usb:1-2 product:ps202_ans13_yl72_cwet_kk model:PS202 device:ps202_ans13_yl72_cwet_kk
```

---

### Step 3: Permanent Root ADB Implementation (Technical Deep-Dive)

To achieve native root access without requiring external rooting apps:

#### 1. Unpacking `BOOTIMG.bin`
The MTK boot image has a standard 2048-byte Android header followed by the kernel, followed by a **512-byte MTK header (`\x88\x16\x88\x58 ROOTFS`)** prepended to the gzip-compressed CPIO ramdisk.

#### 2. The `default.prop` Edits
In the unpacked ramdisk, replace `default.prop` with:
```properties
# ADDITIONAL_DEFAULT_PROPERTIES
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
```

#### 3. The 2-Byte Surgical `sbin/adbd` Binary Patch
Because `ALLOW_ADBD_ROOT=0` was hardcoded at compile time in this KitKat `adbd`, `adb_main()` drops capabilities and sets UID/GID to 2000.

Disassembling `sbin/adbd` around `0x9308` (Thumb-2):
```objdump
00009304 <.text+0x1204>:
    9304:    f019 ecbc     blx    0x22c80
    9308:    2400          movs   r4, #0          <--- Capability drop loop begins
    930a:    4625          mov    r5, r4
    930c:    2200          movs   r2, #0
    930e:    2017          movs   r0, #23         @ PR_CAPBSET_DROP
    ...
    9370:    f01d ecb0     blx    0x26cd4         @ setgroups()
    9378:    f44f 60fa     mov.w  r0, #2000       @ AID_SHELL (0x7d0)
    937c:    f01d ec9c     blx    0x26cb8         @ setgid(2000)
    9384:    f44f 60fa     mov.w  r0, #2000       @ AID_SHELL (0x7d0)
    9388:    f01d eca2     blx    0x26cd0         @ setuid(2000)
    9390:    4bc3          ldr    r3, [pc, #780]  <--- Normal adb_main continues
```

**The Patch:**
We replace the instruction at `0x9308` (`movs r4, #0` -> `0x2400`) with a 16-bit unconditional Thumb branch to `0x9390`:
* Offset calculation: `(0x9390 - (0x9308 + 4)) / 2 = 0x84 / 2 = 0x42`
* Opcode: `0xe042` (Little Endian: `42 e0`)

After patch:
```objdump
00009304 <.text+0x1204>:
    9304:    f019 ecbc     blx    0x22c80
    9308:    e042          b.n    0x9390          <--- Skips drop block cleanly!
    930a:    4625          mov    r5, r4
    ...
```

#### 4. Automated Python Patch & Repack Script
Here is the script to generate `bootimg_adb_root.bin`:

```python
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
```

---

### Step 4: Flashing the Patched Boot Image in Under 1 Second

You do not need to reflash the entire 3.7GB eMMC to update the boot partition. In the Partition Management Table (PMT), `BOOTIMG` resides at:
* **Offset:** `0x3180000` (Sector 101,376 / ~49.5 MB)
* **Size:** 6 MB (`0x600000`)

Use `flash_bootimg_only.py`:

```python
#!/usr/bin/env python3
import sys, os, time
from mtkclient.Library.mtk_main import Mtk
from mtkclient.config.mtk_config import MtkConfig
from mtkclient.Library.DA.daconfig import DAconfig

WORK_DIR = os.path.abspath(os.path.dirname(__file__))

def patch_emi():
    orig = DAconfig.extract_emi
    def _patched(self, pl):
        r = orig(self, pl)
        if self.emiver == 0x0B and self.emi is not None:
            self.emi = self.emi[:0xA8]
        return r
    DAconfig.extract_emi = _patched

def flash_boot():
    patch_emi()
    cfg = MtkConfig()
    cfg.preloader = os.path.join(WORK_DIR, "boot1.bin")
    mtk = Mtk(config=cfg, loglevel=20)
    
    print("[*] Waiting for device in BROM or Preloader mode...")
    if not mtk.init():
        print("[-] Init failed")
        sys.exit(1)
        
    bootimg = os.path.join(WORK_DIR, "bootimg_adb_root.bin")
    sz = os.path.getsize(bootimg)
    boot_offset = 0x3180000 # PMT BOOTIMG offset
    
    print(f"[*] Writing {sz} bytes to BOOTIMG @ 0x{boot_offset:X}...")
    t0 = time.time()
    res = mtk.daloader.writeflash(addr=boot_offset, length=sz, filename=bootimg, parttype="user")
    if res:
        print(f"[+] BOOTIMG flashed successfully in {time.time() - t0:.2f}s!")
        mtk.daloader.reset()
        print("[+] Device rebooting into Android!")

if __name__ == "__main__":
    flash_boot()
```

Run:
```bash
python3 flash_bootimg_only.py
```
**Flash time:** ~0.78 seconds!

---

## 🧪 Verification & Results

Once the handheld boots into Android:

```bash
$ export ADB_LIBUSB=0
$ adb shell id
```
**Output:**
```
uid=0(root) gid=0(root) groups=1003(graphics),1004(input),1007(log),1011(adb),1015(sdcard_rw),1028(sdcard_r),3001(net_bt_admin),3002(net_bt),3003(inet),3006(net_bw_stats) context=u:r:kernel:s0
```

* ✅ `uid=0(root)` immediately at boot — no `adb root` command needed!
* ✅ Full capabilities intact.
* ✅ `ro.secure=0` and `ro.debuggable=1`.
* ✅ USB mass storage and ADB enabled out of the box.

---

## 💬 Credits & Acknowledgments

* **bkerler** for the invaluable `mtkclient` project
* **MediaTek** for the indestructible BROM fallback
* **Gemini 4 Neon** for constructing most of the modifications here
* **Gemini 3.8 Flash** for not being a little bitch like Neon by not refusing to generate a basic guide after the fact
