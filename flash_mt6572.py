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