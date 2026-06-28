"""
Build Configuration Module

Central configuration for the TX build system including toolchain setup,
Android NDK integration, paths, and build flags.
"""

import os
import json
import logging
import platform
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class BuildConfig:
    """Central build configuration for TX-Packages."""

    # Repository paths
    repo_root: Path = field(default_factory=lambda: Path(__file__).parent.parent)

    @property
    def recipes_dir(self) -> Path:
        return self.repo_root / "recipes"

    @property
    def patches_dir(self) -> Path:
        return self.repo_root / "patches"

    @property
    def downloads_dir(self) -> Path:
        return self.repo_root / "downloads"

    @property
    def sources_dir(self) -> Path:
        return self.repo_root / "sources"

    @property
    def cache_dir(self) -> Path:
        return self.repo_root / "cache"

    @property
    def packages_dir(self) -> Path:
        return self.repo_root / "packages"

    @property
    def bootstrap_dir(self) -> Path:
        return self.repo_root / "bootstrap"

    @property
    def repository_dir(self) -> Path:
        return self.repo_root / "repository"

    @property
    def artifacts_dir(self) -> Path:
        return self.repo_root / "artifacts"

    @property
    def output_dir(self) -> Path:
        return self.repo_root / "output"

    @property
    def profiles_dir(self) -> Path:
        return self.repo_root / "profiles"

    @property
    def scripts_dir(self) -> Path:
        return self.repo_root / "scripts"

    @property
    def toolchains_dir(self) -> Path:
        return self.repo_root / "toolchains"

    @property
    def configs_dir(self) -> Path:
        return self.repo_root / "configs"

    @property
    def tests_dir(self) -> Path:
        return self.repo_root / "tests"

    # Target platform
    target_arch: str = "aarch64"
    target_triple: str = "aarch64-linux-android"
    target_abi: str = "arm64-v8a"
    min_api_level: int = 29
    android_version: str = "10"

    # Toolchain
    ndk_path: Optional[Path] = None
    llvm_path: Optional[Path] = None
    clang_path: Optional[Path] = None
    clang_pp_path: Optional[Path] = None
    lld_path: Optional[Path] = None
    ar_path: Optional[Path] = None
    ranlib_path: Optional[Path] = None
    strip_path: Optional[Path] = None
    nm_path: Optional[Path] = None
    objdump_path: Optional[Path] = None
    readelf_path: Optional[Path] = None

    # Sysroot
    sysroot: Optional[Path] = None

    # Build flags
    cflags: List[str] = field(default_factory=list)
    cxxflags: List[str] = field(default_factory=list)
    ldflags: List[str] = field(default_factory=list)
    cppflags: List[str] = field(default_factory=list)

    # Build options
    parallel_jobs: int = field(default_factory=lambda: os.cpu_count() or 4)
    incremental: bool = True
    use_ccache: bool = True
    strip_binaries: bool = True
    optimize: str = "O2"  # O0, O1, O2, O3, Os, Oz
    debug: bool = False
    verbose: bool = False

    # Package options
    pkg_compression: str = "zst"  # gz, bz2, xz, zst
    pkg_compression_level: int = 19
    sign_packages: bool = False
    maintainer: str = "TX-Packages <packages@tx.dev>"

    # Repository options
    repo_name: str = "TX-Packages"
    repo_codename: str = "tx-main"
    repo_description: str = "TX Linux Userspace for Android"
    repo_components: List[str] = field(default_factory=lambda: ["main"])

    # URLs
    upstream_mirrors: List[str] = field(default_factory=lambda: [
        "https://ftp.gnu.org/gnu",
        "https://kernel.org/pub",
        "https://ftp.openssl.org/source",
        "https://www.python.org/ftp",
        "https://github.com",
    ])

    def __post_init__(self):
        """Post-initialization: discover NDK, setup toolchain, create directories."""
        self._ensure_directories()
        self._detect_ndk()
        self._setup_toolchain()
        self._setup_flags()

    def _ensure_directories(self) -> None:
        """Create all required directories if they don't exist."""
        dirs = [
            self.recipes_dir,
            self.patches_dir,
            self.downloads_dir,
            self.sources_dir,
            self.cache_dir,
            self.packages_dir,
            self.bootstrap_dir,
            self.repository_dir,
            self.artifacts_dir,
            self.output_dir,
            self.profiles_dir,
            self.scripts_dir,
            self.toolchains_dir,
            self.configs_dir,
            self.tests_dir,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory: {d}")

    def _detect_ndk(self) -> None:
        """Auto-detect Android NDK installation."""
        ndk_env = os.environ.get("ANDROID_NDK_HOME") or os.environ.get("ANDROID_NDK")
        if ndk_env:
            ndk_path = Path(ndk_env)
            if ndk_path.exists():
                self.ndk_path = ndk_path
                logger.info(f"Found NDK from environment: {ndk_path}")
                return

        # Check common NDK locations
        common_paths = [
            Path.home() / "Android/Sdk/ndk",
            Path.home() / "android-ndk",
            Path("/usr/local/android-ndk"),
            Path("/opt/android-ndk"),
            Path("/usr/lib/android-ndk"),
        ]

        for base in common_paths:
            if base.exists():
                # Find the newest NDK version
                versions = [d for d in base.iterdir() if d.is_dir()]
                if versions:
                    # Sort by version number
                    versions.sort(key=lambda x: x.name, reverse=True)
                    self.ndk_path = versions[0]
                    logger.info(f"Found NDK: {self.ndk_path}")
                    return
                else:
                    self.ndk_path = base
                    logger.info(f"Found NDK: {self.ndk_path}")
                    return

        logger.warning("Android NDK not found. Set ANDROID_NDK_HOME environment variable.")

    def _setup_toolchain(self) -> None:
        """Configure LLVM/Clang toolchain paths from NDK."""
        if not self.ndk_path:
            logger.error("Cannot setup toolchain without NDK")
            return

        # NDK LLVM toolchain path
        llvm_base = self.ndk_path / "toolchains/llvm/prebuilt"
        if not llvm_base.exists():
            logger.error(f"NDK LLVM toolchain not found at: {llvm_base}")
            return

        # Determine host platform
        host = platform.system().lower()
        machine = platform.machine()
        if host == "darwin":
            host_tag = "darwin-x86_64"
        elif host == "linux":
            if machine in ("x86_64", "amd64"):
                host_tag = "linux-x86_64"
            elif machine.startswith("aarch64"):
                host_tag = "linux-aarch64"
            else:
                host_tag = "linux-x86_64"
        else:
            host_tag = "linux-x86_64"

        self.llvm_path = llvm_base / host_tag / "bin"
        if not self.llvm_path.exists():
            # Try to find any available host
            hosts = [d.name for d in llvm_base.iterdir() if d.is_dir()]
            if hosts:
                self.llvm_path = llvm_base / hosts[0] / "bin"
            else:
                logger.error("No LLVM toolchain found for any host")
                return

        # Set tool paths
        triple_with_api = f"{self.target_triple}{self.min_api_level}"

        self.clang_path = self.llvm_path / f"clang"
        self.clang_pp_path = self.llvm_path / f"clang++"
        self.lld_path = self.llvm_path / "ld.lld"
        self.ar_path = self.llvm_path / "llvm-ar"
        self.ranlib_path = self.llvm_path / "llvm-ranlib"
        self.strip_path = self.llvm_path / f"llvm-strip"
        self.nm_path = self.llvm_path / "llvm-nm"
        self.objdump_path = self.llvm_path / "llvm-objdump"
        self.readelf_path = self.llvm_path / "llvm-readelf"

        # Sysroot
        self.sysroot = self.ndk_path / "toolchains/llvm/prebuilt" / self.llvm_path.parent.name / "sysroot"

        # Validate tools
        self._validate_tools()

    def _validate_tools(self) -> None:
        """Validate that all required toolchain binaries exist."""
        tools = {
            "clang": self.clang_path,
            "clang++": self.clang_pp_path,
            "ld.lld": self.lld_path,
            "llvm-ar": self.ar_path,
            "llvm-ranlib": self.ranlib_path,
            "llvm-strip": self.strip_path,
        }

        for name, path in tools.items():
            if path and path.exists():
                logger.debug(f"Tool verified: {name} -> {path}")
            else:
                logger.warning(f"Tool missing: {name} (expected at {path})")

    def _setup_flags(self) -> None:
        """Setup compiler and linker flags for Android cross-compilation."""
        triple_with_api = f"{self.target_triple}{self.min_api_level}"

        self.cflags = [
            f"--target={triple_with_api}",
            f"--sysroot={self.sysroot}",
            f"-march=armv8-a",
            f"-O{self.optimize.lstrip('O')}" if self.optimize.startswith('O') else f"-{self.optimize}",
            "-fPIC",
            "-fdata-sections",
            "-ffunction-sections",
            "-funwind-tables",
            "-fstack-protector-strong",
            "-no-canonical-prefixes",
            "-Wformat",
            "-Werror=format-security",
            "-Wno-error=implicit-function-declaration",
            "-Wno-error=implicit-int",
            "-Wno-error=deprecated-non-prototype",
            "-Wno-error=incompatible-function-pointer-types",
            "-Wno-error=int-conversion"
        ]

        self.cxxflags = self.cflags + [
            "-stdlib=libc++",
        ]

        self.ldflags = [
            f"--target={triple_with_api}",
            f"--sysroot={self.sysroot}",
            f"-L{self.artifacts_dir}/data/data/tx.packages/files/usr/lib",
            "-fuse-ld=lld",
            "-stdlib=libc++",
            "-Wl,--build-id=sha1",
            "-Wl,--no-rosegment",
            "-Wl,--gc-sections",
            "-Wl,--exclude-libs,libgcc.a",
            "-Wl,--exclude-libs,libgcc_real.a",
            "-Wl,--exclude-libs,libunwind.a",
            "-Wl,--undefined-version",
        ]

        self.cppflags = [
            f"-I{self.sysroot}/usr/include/{self.target_triple}",
            f"-I{self.artifacts_dir}/data/data/tx.packages/files/usr/include",
            f"-I{self.artifacts_dir}/data/data/tx.packages/files/usr/include/ncursesw",
            "-DANDROID",
            "-D_GNU_SOURCE",
        ]

        if self.debug:
            self.cflags.append("-g")
            self.cxxflags.append("-g")
            self.ldflags.append("-g")

        if self.use_ccache:
            ccache = shutil.which("ccache")
            if ccache:
                logger.info(f"ccache enabled: {ccache}")

    @property
    def env(self) -> Dict[str, str]:
        """Generate environment variables for build processes."""
        triple_with_api = f"{self.target_triple}{self.min_api_level}"

        env = {
            "ANDROID_NDK": str(self.ndk_path) if self.ndk_path else "",
            "ANDROID_NDK_HOME": str(self.ndk_path) if self.ndk_path else "",
            "ANDROID_API": str(self.min_api_level),
            "ANDROID_ABI": self.target_abi,

            "CC": f"{self.clang_path} --target={triple_with_api} --sysroot={self.sysroot}" if self.clang_path else "clang",
            "CXX": f"{self.clang_pp_path} --target={triple_with_api} --sysroot={self.sysroot}" if self.clang_pp_path else "clang++",
            "CPP": f"{self.clang_path} -E" if self.clang_path else "cpp",
            "LD": str(self.lld_path) if self.lld_path else "ld.lld",
            "AR": str(self.ar_path) if self.ar_path else "ar",
            "RANLIB": str(self.ranlib_path) if self.ranlib_path else "ranlib",
            "STRIP": str(self.strip_path) if self.strip_path else "strip",
            "NM": str(self.nm_path) if self.nm_path else "nm",
            "OBJDUMP": str(self.objdump_path) if self.objdump_path else "objdump",
            "READELF": str(self.readelf_path) if self.readelf_path else "readelf",
            "OBJCOPY": str(self.llvm_path / "llvm-objcopy") if self.llvm_path else "objcopy",

            "CFLAGS": " ".join(self.cflags),
            "CXXFLAGS": " ".join(self.cxxflags),
            "LDFLAGS": " ".join(self.ldflags),
            "CPPFLAGS": " ".join(self.cppflags),

            "PKG_CONFIG_PATH": f"{self.artifacts_dir}/data/data/tx.packages/files/usr/lib/pkgconfig:{self.artifacts_dir}/data/data/tx.packages/files/usr/lib64/pkgconfig:{self.artifacts_dir}/data/data/tx.packages/files/usr/share/pkgconfig",
            "PKG_CONFIG_LIBDIR": f"{self.artifacts_dir}/data/data/tx.packages/files/usr/lib/pkgconfig:{self.artifacts_dir}/data/data/tx.packages/files/usr/lib64/pkgconfig",
            "PKG_CONFIG_SYSROOT_DIR": str(self.artifacts_dir),

            "TARGET_ARCH": "",
            "TARGET_TRIPLE": self.target_triple,
            "HOST": self.target_triple,
            "BUILD": self.target_triple,

            "PREFIX": "/data/data/tx.packages/files/usr",
            "DESTDIR": str(self.artifacts_dir),

            "MAKEFLAGS": f"-j{self.parallel_jobs}",

            "ANDROID": "yes",
            "CROSS_COMPILE": "1",
        }

        # Add ccache if enabled
        if self.use_ccache:
            ccache = shutil.which("ccache")
            if ccache:
                env["CCACHE"] = ccache
                env["CC"] = f"{ccache} {env['CC']}"
                env["CXX"] = f"{ccache} {env['CXX']}"

        return env

    def get_tool_path(self, tool: str) -> Optional[Path]:
        """Get the path to a specific toolchain tool."""
        tool_map = {
            "clang": self.clang_path,
            "clang++": self.clang_pp_path,
            "ld.lld": self.lld_path,
            "ar": self.ar_path,
            "ranlib": self.ranlib_path,
            "strip": self.strip_path,
            "nm": self.nm_path,
            "objdump": self.objdump_path,
            "readelf": self.readelf_path,
        }
        return tool_map.get(tool)

    def to_dict(self) -> Dict:
        """Serialize configuration to dictionary."""
        d = asdict(self)
        # Convert Path objects to strings
        for key, value in d.items():
            if isinstance(value, Path):
                d[key] = str(value)
            elif isinstance(value, dict):
                d[key] = {k: str(v) if isinstance(v, Path) else v for k, v in value.items()}
            elif isinstance(value, list):
                d[key] = [str(v) if isinstance(v, Path) else v for v in value]
        return d

    def to_json(self, indent: int = 2) -> str:
        """Serialize configuration to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: Optional[Path] = None) -> None:
        """Save configuration to JSON file."""
        if path is None:
            path = self.configs_dir / "build_config.json"
        with open(path, "w") as f:
            f.write(self.to_json())
        logger.info(f"Configuration saved to: {path}")


import shutil
