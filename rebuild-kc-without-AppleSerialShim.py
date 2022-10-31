#!/usr/bin/env python3

import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
from typing import Callable

KC_NO_SHIM_PATH = "/Library/KernelCollections/kc.noshim.macho"


def run_cmd(*args, log: bool = True, **kwargs) -> str:
    args = (*args,)
    if log:
        print(f"Running: {' '.join(map(str, args))}", file=sys.stderr)
    r = subprocess.run(list(map(str, args)), capture_output=True, **kwargs)
    if r.returncode != 0:
        sys.stderr.buffer.write(r.stdout)
        sys.stderr.buffer.write(r.stderr)
        raise subprocess.CalledProcessError(r.returncode, args, r.stdout, r.stderr)
    try:
        r.out = r.stdout.decode()
    except UnicodeDecodeError:
        pass
    return r


def gen_cmd(bin_name: str) -> Callable:
    bin_path = shutil.which(bin_name)
    assert bin_path is not None
    return lambda *args, **kwargs: run_cmd(bin_path, *args, **kwargs)


diskutil = gen_cmd("diskutil")
kmutil = gen_cmd("kmutil")
uname = gen_cmd("uname")
sudo = gen_cmd("sudo")


def get_soc() -> str:
    return uname("-v").out.splitlines()[0].split("_")[-1].lower()


def get_base_kexts() -> list[str]:
    out = kmutil(
        "inspect",
        "-V",
        "release",
        "--no-header",
        "-p",
        "/System/Library/KernelCollections/BootKernelExtensions.kc",
    ).out.splitlines()
    hdr_idx = [i for i, e in enumerate(out) if e == "Extension Information:"]
    if len(hdr_idx) == 2:
        base_kexts = out[hdr_idx[0] + 1 : hdr_idx[1]]
    elif len(hdr_idx) == 1:
        base_kexts = out[hdr_idx[0] :]
    else:
        raise ValueError("kmutil kext processing broken")
    base_kexts = [l.split()[0] for l in base_kexts]
    return base_kexts


def generate_no_shim_kc() -> None:
    base_kexts = get_base_kexts()
    base_kexts_no_shim = [k for k in base_kexts if k != "com.apple.driver.AppleSerialShim"]
    kmutil_args = [
        "kmutil",
        "create",
        "-n",
        "boot",
        "-a",
        "arm64e",
        "-B",
        KC_NO_SHIM_PATH,
        "-V",
        "release",
        "-k",
        f"/System/Library/Kernels/kernel.release.{get_soc()}",
        "-r",
        "/System/Library/Extensions",
        "-r",
        "/System/Library/DriverExtensions",
        "-x",
    ]
    for base_kext in base_kexts_no_shim:
        kmutil_args.append("-b")
        kmutil_args.append(base_kext)
    sudo(*kmutil_args)


def get_sys_vol_uuid() -> str:
    info = plistlib.loads(diskutil("list", "-plist").stdout)
    for disk in info["AllDisksAndPartitions"]:
        if "APFSVolumes" not in disk:
            continue
        for vol in disk["APFSVolumes"]:
            if "MountedSnapshots" not in vol:
                continue
            for snap in vol["MountedSnapshots"]:
                if "SnapshotMountPoint" in snap and snap["SnapshotMountPoint"] == "/":
                    return vol["VolumeUUID"]
    raise ValueError("Can't find parent volume of snapshot mounted on '/'")


def generate_no_shim_kc_install_script(vol_uuid: str) -> None:
    script_path = KC_NO_SHIM_PATH + ".installer.sh"
    with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
        script = f"""\
#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail
set -o xtrace

info_tmp_path=$(mktemp)
diskutil info -plist {vol_uuid} > ${{info_tmp_path}}
mount_point=$(/usr/libexec/PlistBuddy -c "Print MountPoint" ${{info_tmp_path}})

{{ echo "Installing to \"${{mount_point}}\""; }} 2> /dev/null

kmutil configure-boot -c "${{mount_point}}/Library/KernelCollections/kc.noshim.macho" -C -v "${{mount_point}}"
"""
        tmp.write(script)
        os.fchmod(tmp.fileno(), 0o755)
        sudo("mv", tmp.name, script_path)


generate_no_shim_kc()

generate_no_shim_kc_install_script(get_sys_vol_uuid())
