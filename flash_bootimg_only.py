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