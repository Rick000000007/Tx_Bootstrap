"""
Package Builder Module

Builds packages from recipes using various build systems (GNU autotools,
CMake, Meson, Python, Make, custom scripts) with parallel and incremental
build support.
"""

import os
import re
import json
import shutil
import logging
import tarfile
import subprocess
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field

from .config import BuildConfig
from .recipe import Recipe
from .downloader import SourceDownloader

logger = logging.getLogger(__name__)


@dataclass
class BuildResult:
    """Result of a package build."""
    success: bool
    recipe: Recipe
    build_time: float = 0.0
    stages_completed: List[str] = field(default_factory=list)
    stages_failed: List[str] = field(default_factory=list)
    install_prefix: Optional[Path] = None
    error: Optional[str] = None
    artifacts: List[Path] = field(default_factory=list)


class PackageBuilder:
    """Builds packages from recipes."""

    def __init__(self, config: BuildConfig):
        self.config = config
        self.downloader = SourceDownloader(config.downloads_dir)
        self._build_callbacks: List[Callable[[str, str, bool], None]] = []

    def register_callback(self, callback: Callable[[str, str, bool], None]) -> None:
        """Register a build progress callback.

        Args:
            callback: Function(pkg_name, stage, success) -> None
        """
        self._build_callbacks.append(callback)

    def build(self, recipe: Recipe, force_rebuild: bool = False) -> BuildResult:
        """Build a single package from its recipe."""
        import time
        start_time = time.time()

        stages_completed = []
        stages_failed = []
        error = None

        # Compute build cache key
        cache_key = self._compute_cache_key(recipe)
        cache_marker = self.config.cache_dir / f"{recipe.name}-{cache_key}.built"

        # Check cache
        if not force_rebuild and cache_marker.exists() and self.config.incremental:
            logger.info(f"Package {recipe.name} is up to date (cached)")
            return BuildResult(
                success=True,
                recipe=recipe,
                build_time=0.0,
                stages_completed=["cache_hit"],
                install_prefix=self.config.artifacts_dir / recipe.name
            )

        logger.info(f"Building {recipe.name} {recipe.full_version}")

        try:
            # Stage 1: Download sources
            self._notify(recipe.name, "download", True)
            self._download_sources(recipe)
            stages_completed.append("download")

            # Stage 2: Extract sources
            self._notify(recipe.name, "extract", True)
            source_dir = self._extract_sources(recipe)
            stages_completed.append("extract")

            # Stage 3: Apply patches
            self._notify(recipe.name, "patch", True)
            self._apply_patches(recipe, source_dir)
            stages_completed.append("patch")

            # Stage 4: Pre-build commands
            if recipe.pre_build_cmds:
                self._notify(recipe.name, "pre_build", True)
                self._run_commands(recipe.pre_build_cmds, source_dir, recipe, "pre_build")
                stages_completed.append("pre_build")

            # Stage 5: Configure
            self._notify(recipe.name, "configure", True)
            build_dir = self._configure(recipe, source_dir)
            stages_completed.append("configure")

            # Stage 6: Build
            self._notify(recipe.name, "build", True)
            self._run_build(recipe, build_dir or source_dir)
            stages_completed.append("build")

            # Stage 7: Post-build commands
            if recipe.post_build_cmds:
                self._notify(recipe.name, "post_build", True)
                self._run_commands(recipe.post_build_cmds, source_dir, recipe, "post_build")
                stages_completed.append("post_build")

            # Stage 8: Install to staging
            self._notify(recipe.name, "install", True)
            install_prefix = self._install(recipe, build_dir or source_dir)
            stages_completed.append("install")

            # Stage 9: Post-install commands
            if recipe.post_install_cmds:
                self._notify(recipe.name, "post_install", True)
                self._run_commands(recipe.post_install_cmds, install_prefix, recipe, "post_install")
                stages_completed.append("post_install")

            # Stage 10: Strip binaries (if enabled)
            if recipe.strip_binaries:
                self._notify(recipe.name, "strip", True)
                self._strip_binaries(recipe, install_prefix)
                stages_completed.append("strip")

            # Mark as cached
            cache_marker.touch()

            build_time = time.time() - start_time
            logger.info(f"Build completed: {recipe.name} in {build_time:.1f}s")

            return BuildResult(
                success=True,
                recipe=recipe,
                build_time=build_time,
                stages_completed=stages_completed,
                install_prefix=install_prefix,
                artifacts=list(install_prefix.rglob("*")) if install_prefix.exists() else []
            )

        except Exception as e:
            build_time = time.time() - start_time
            error = str(e)
            logger.error(f"Build failed for {recipe.name}: {error}")

            return BuildResult(
                success=False,
                recipe=recipe,
                build_time=build_time,
                stages_completed=stages_completed,
                stages_failed=stages_failed,
                error=error
            )

    def _download_sources(self, recipe: Recipe) -> None:
        """Download all sources for a recipe."""
        for source in recipe.sources:
            result = self.downloader.download_source(source, recipe.name)
            if not result.success:
                raise BuildError(f"Failed to download {source.url}: {result.error}")

    def _extract_sources(self, recipe: Recipe) -> Path:
        """Extract sources to the sources directory."""
        source_dir = self.config.sources_dir / recipe.source_dir

        # Remove existing source directory for clean build
        if source_dir.exists():
            shutil.rmtree(source_dir)

        for source in recipe.sources:
            archive_path = self.config.downloads_dir / self.downloader._get_filename(source, recipe.name)

            if not archive_path.exists():
                raise BuildError(f"Source archive not found: {archive_path}")

            # Determine extraction method
            suffix = archive_path.suffix.lower()
            name = archive_path.name.lower()

            if name.endswith('.tar.gz') or name.endswith('.tgz') or suffix == '.gz':
                # tar.gz
                if name.endswith('.tar.gz') or name.endswith('.tgz'):
                    with tarfile.open(archive_path, 'r:gz') as tf:
                        tf.extractall(self.config.sources_dir)
                else:
                    # Single gzipped file
                    import gzip
                    dest = source_dir / archive_path.stem
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with gzip.open(archive_path, 'rb') as gz:
                        dest.write_bytes(gz.read())
            elif name.endswith('.tar.bz2') or name.endswith('.tbz2'):
                with tarfile.open(archive_path, 'r:bz2') as tf:
                    tf.extractall(self.config.sources_dir)
            elif name.endswith('.tar.xz') or name.endswith('.txz'):
                with tarfile.open(archive_path, 'r:xz') as tf:
                    tf.extractall(self.config.sources_dir)
            elif name.endswith('.tar.zst'):
                self._extract_zstd(archive_path, self.config.sources_dir)
            elif name.endswith('.zip'):
                shutil.unpack_archive(archive_path, self.config.sources_dir)
            elif archive_path.is_dir():
                shutil.copytree(archive_path, source_dir)
            else:
                # Copy as-is
                source_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(archive_path, source_dir / archive_path.name)

        if not source_dir.exists():
            raise BuildError(f"Source directory not created: {source_dir}")

        return source_dir

    def _extract_zstd(self, archive_path: Path, dest_dir: Path) -> None:
        """Extract zstd-compressed tar archive."""
        try:
            import zstandard
            with open(archive_path, 'rb') as fh:
                dctx = zstandard.ZstdDecompressor()
                with dctx.stream_reader(fh) as reader:
                    with tarfile.open(fileobj=reader, mode='r|') as tf:
                        tf.extractall(dest_dir)
        except ImportError:
            # Fallback to external zstd command
            subprocess.run(
                ['tar', '--zstd', '-xf', str(archive_path), '-C', str(dest_dir)],
                check=True
            )

    def _apply_patches(self, recipe: Recipe, source_dir: Path) -> None:
        """Apply patches to the source directory."""
        if not recipe.patches:
            return

        for patch_file in recipe.patches:
            patch_path = self.config.patches_dir / recipe.name / patch_file
            if not patch_path.exists():
                patch_path = self.config.patches_dir / patch_file
            if not patch_path.exists():
                logger.warning(f"Patch not found: {patch_path}")
                continue

            logger.info(f"Applying patch: {patch_file}")

            cmd = ['patch'] + recipe.patch_args + ['-i', str(patch_path)]
            result = subprocess.run(
                cmd,
                cwd=source_dir,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                # Check if already applied (fuzz)
                if "previously applied" in result.stderr or "Skipping patch" in result.stdout:
                    logger.info(f"Patch {patch_file} already applied")
                else:
                    raise BuildError(f"Failed to apply patch {patch_file}: {result.stderr}")

    def _configure(self, recipe: Recipe, source_dir: Path) -> Optional[Path]:
        """Run configuration step based on build style."""
        build_style = recipe.build_style.lower()

        if build_style == "meta":
            # Meta package - no build needed
            return source_dir

        env = self.config.env.copy()
        env.update(recipe.env_vars)

        if build_style == "gnu":
            return self._configure_gnu(recipe, source_dir, env)
        elif build_style == "cmake":
            return self._configure_cmake(recipe, source_dir, env)
        elif build_style == "meson":
            return self._configure_meson(recipe, source_dir, env)
        elif build_style == "python":
            return self._configure_python(recipe, source_dir, env)
        elif build_style == "make":
            return self._configure_make(recipe, source_dir, env)
        elif build_style == "custom":
            # Custom build - configuration handled by pre_build_cmds
            return source_dir
        else:
            raise BuildError(f"Unknown build style: {build_style}")

    def _configure_gnu(self, recipe: Recipe, source_dir: Path, env: Dict[str, str]) -> Path:
        """Configure using GNU autotools (configure script)."""
        configure_script = source_dir / "configure"

        # Run autoreconf if configure doesn't exist
        if not configure_script.exists():
            logger.info("Running autoreconf to generate configure script")
            self._run_command(['autoreconf', '-fi'], source_dir, env)

        # Create build directory if needed
        build_dir = source_dir / recipe.build_dir if recipe.build_dir != "." else source_dir
        if build_dir != source_dir:
            build_dir.mkdir(parents=True, exist_ok=True)
            configure_cmd = ['../configure']
        else:
            configure_cmd = ['./configure']

        # Common configure args for Android
        configure_args = [
            f'--prefix=/data/data/tx.packages/files/usr',
            f'--host={self.config.target_triple}',
            f'--target={self.config.target_triple}',
            '--disable-shared' if recipe.static and not recipe.shared else '',
            '--enable-static' if recipe.static else '',
            '--disable-nls',
            '--disable-rpath',
        ]

        # Remove empty strings
        configure_args = [a for a in configure_args if a]
        configure_args.extend(recipe.configure_args)

        cmd = configure_cmd + configure_args
        self._run_command(cmd, build_dir, env)

        return build_dir

    def _configure_cmake(self, recipe: Recipe, source_dir: Path, env: Dict[str, str]) -> Path:
        """Configure using CMake."""
        build_dir = source_dir / (recipe.build_dir if recipe.build_dir != "." else "build")
        build_dir.mkdir(parents=True, exist_ok=True)

        # Find CMake toolchain file
        toolchain_file = self.config.toolchains_dir / "android.cmake"

        cmake_args = [
            f'-DCMAKE_TOOLCHAIN_FILE={self.config.ndk_path}/build/cmake/android.toolchain.cmake',
            f'-DANDROID_ABI={self.config.target_abi}',
            f'-DANDROID_NATIVE_API_LEVEL={self.config.min_api_level}',
            f'-DANDROID_PLATFORM=android-{self.config.min_api_level}',
            f'-DCMAKE_ANDROID_ARCH_ABI={self.config.target_abi}',
            f'-DCMAKE_ANDROID_API={self.config.min_api_level}',
            f'-DCMAKE_SYSTEM_NAME=Android',
            f'-DCMAKE_SYSTEM_VERSION={self.config.min_api_level}',
            f'-DCMAKE_ANDROID_NDK={self.config.ndk_path}',
            f'-DCMAKE_ANDROID_STL_TYPE=c++_shared',
            f'-DCMAKE_INSTALL_PREFIX=/data/data/tx.packages/files/usr',
            f'-DCMAKE_BUILD_TYPE=Release',
            f'-DCMAKE_C_COMPILER={self.config.clang_path}',
            f'-DCMAKE_CXX_COMPILER={self.config.clang_pp_path}',
            '-DCMAKE_POSITION_INDEPENDENT_CODE=ON',
        ]

        cmake_args.extend(recipe.cmake_args)
        cmd = ['cmake', str(source_dir)] + cmake_args
        self._run_command(cmd, build_dir, env)

        return build_dir

    def _configure_meson(self, recipe: Recipe, source_dir: Path, env: Dict[str, str]) -> Path:
        """Configure using Meson."""
        build_dir = source_dir / (recipe.build_dir if recipe.build_dir != "." else "build")

        # Create cross file
        cross_file = self._generate_meson_cross_file()

        meson_args = [
            'setup',
            str(build_dir),
            f'--cross-file={cross_file}',
            f'--prefix=/data/data/tx.packages/files/usr',
            '--buildtype=release',
            '-Ddefault_library=both',
        ]

        meson_args.extend(recipe.meson_args)
        self._run_command(['meson'] + meson_args, source_dir, env)

        return build_dir

    def _configure_python(self, recipe: Recipe, source_dir: Path, env: Dict[str, str]) -> Path:
        """Configure Python package (no-op, handled in build)."""
        return source_dir

    def _configure_make(self, recipe: Recipe, source_dir: Path, env: Dict[str, str]) -> Path:
        """Configure for simple Makefiles."""
        return source_dir

    def _generate_meson_cross_file(self) -> Path:
        """Generate a Meson cross-compilation file for Android."""
        cross_file = self.config.configs_dir / "android-cross.ini"
        cross_file.parent.mkdir(parents=True, exist_ok=True)

        content = f"""[binaries]
c = '{self.config.clang_path}'
cpp = '{self.config.clang_pp_path}'
ar = '{self.config.ar_path}'
strip = '{self.config.strip_path}'
ranlib = '{self.config.ranlib_path}'
ld = '{self.config.lld_path}'
pkgconfig = 'pkg-config'

[host_machine]
system = 'android'
cpu_family = 'aarch64'
cpu = 'armv8-a'
endian = 'little'

[properties]
needs_exe_wrapper = true
sys_root = '{self.config.sysroot}'
"""
        cross_file.write_text(content)
        return cross_file

    def _run_build(self, recipe: Recipe, build_dir: Path) -> None:
        """Run the build step."""
        env = self.config.env.copy()
        env.update(recipe.env_vars)

        build_style = recipe.build_style.lower()
        parallel_flag = f"-j{self.config.parallel_jobs}"

        if build_style == "meta":
            return

        if build_style == "python":
            # Python setuptools build
            self._run_command(
                [self._get_python(), 'setup.py', 'build'],
                build_dir, env
            )
        elif build_style == "cmake":
            self._run_command(
                ['cmake', '--build', '.', '--', parallel_flag],
                build_dir, env
            )
        elif build_style == "meson":
            self._run_command(
                ['meson', 'compile', '-C', '.'],
                build_dir, env
            )
        else:
            # GNU autotools, make, custom
            make_args = [parallel_flag]
            make_args.extend(recipe.make_args)
            if build_style == "make":
                make_args.append(f"CC={env.get('CC', 'clang')}")
                make_args.append(f"CXX={env.get('CXX', 'clang++')}")
                make_args.append(f"AR={env.get('AR', 'llvm-ar')}")
                make_args.append(f"RANLIB={env.get('RANLIB', 'llvm-ranlib')}")
                make_args.append("CROSS_COMPILE=")
            self._run_command(
                ['make'] + make_args,
                build_dir, env
            )

    def _install(self, recipe: Recipe, build_dir: Path) -> Path:
        """Install package to staging directory."""
        env = self.config.env.copy()
        env.update(recipe.env_vars)

        # Create package-specific staging directory
        install_prefix = self.config.artifacts_dir / recipe.name
        if install_prefix.exists():
            shutil.rmtree(install_prefix)
        install_prefix.mkdir(parents=True, exist_ok=True)

        env['DESTDIR'] = str(install_prefix)

        build_style = recipe.build_style.lower()

        if build_style == "meta":
            # Meta package - no install needed
            pass
        elif build_style == "python":
            self._run_command(
                [self._get_python(), 'setup.py', 'install',
                 '--root', str(install_prefix),
                 '--prefix=/data/data/tx.packages/files/usr'],
                build_dir, env
            )
        elif build_style == "cmake":
            self._run_command(
                ['cmake', '--install', '.', '--prefix',
                 str(install_prefix / 'data' / 'data' / 'tx.packages' / 'files' / 'usr')],
                build_dir, env
            )
        elif build_style == "meson":
            self._run_command(
                ['meson', 'install', '-C', '.', '--destdir', str(install_prefix)],
                build_dir, env
            )
        else:
            # GNU autotools, make
            make_args = [f'DESTDIR={install_prefix}']
            make_args.extend(recipe.make_args)
            if build_style == "make":
                make_args.append(f"CC={env.get('CC', 'clang')}")
                make_args.append(f"CXX={env.get('CXX', 'clang++')}")
                make_args.append(f"AR={env.get('AR', 'llvm-ar')}")
                make_args.append(f"RANLIB={env.get('RANLIB', 'llvm-ranlib')}")
                make_args.append("CROSS_COMPILE=")
            self._run_command(
                ['make'] + make_args + ['install'],
                build_dir, env
            )

        return install_prefix

    def _strip_binaries(self, recipe: Recipe, install_prefix: Path) -> None:
        """Strip debug symbols from binaries."""
        if not self.config.strip_path or not self.config.strip_path.exists():
            return

        for root, dirs, files in os.walk(install_prefix):
            for filename in files:
                file_path = Path(root) / filename

                # Check if it's an ELF binary
                try:
                    with open(file_path, 'rb') as f:
                        magic = f.read(4)
                        if magic != b'\x7fELF':
                            continue
                except Exception:
                    continue

                # Determine strip mode
                if filename.endswith('.a') or filename.endswith('.o'):
                    if not recipe.strip_static:
                        continue
                    strip_args = ['--strip-debug']
                elif filename.endswith('.so') or '.so.' in filename:
                    if not recipe.strip_shared:
                        continue
                    strip_args = ['--strip-unneeded']
                else:
                    strip_args = ['--strip-all']

                try:
                    subprocess.run(
                        [str(self.config.strip_path)] + strip_args + [str(file_path)],
                        check=True,
                        capture_output=True
                    )
                except subprocess.CalledProcessError:
                    pass  # Non-fatal

    def _run_commands(self, commands: List[str], cwd: Path, recipe: Recipe, stage: str) -> None:
        """Run a list of shell commands."""
        env = self.config.env.copy()
        env.update(recipe.env_vars)

        for cmd in commands:
            logger.debug(f"Running [{stage}]: {cmd}")
            self._run_command(['sh', '-c', cmd], cwd, env)

    def _run_command(self, cmd: List[str], cwd: Path, env: Dict[str, str]) -> None:
        """Run a command with proper environment."""
        logger.debug(f"Executing: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            cwd=cwd,
            env={**os.environ, **env},
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            stderr = result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr
            stdout = result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout
            raise BuildError(
                f"Command failed (exit {result.returncode}): {' '.join(cmd)}\n"
                f"STDOUT: {stdout}\nSTDERR: {stderr}"
            )

    def _get_python(self) -> str:
        """Get the Python interpreter path."""
        return shutil.which("python3") or shutil.which("python") or "python3"

    def _compute_cache_key(self, recipe: Recipe) -> str:
        """Compute a content-addressable cache key for a recipe."""
        hasher = hashlib.sha256()
        hasher.update(f"{recipe.name}:{recipe.full_version}".encode())
        hasher.update(json.dumps(recipe.configure_args, sort_keys=True).encode())
        hasher.update(json.dumps(recipe.make_args, sort_keys=True).encode())
        hasher.update(json.dumps(recipe.env_vars, sort_keys=True).encode())
        for source in recipe.sources:
            hasher.update(source.checksum.encode())
        return hasher.hexdigest()[:16]

    def _notify(self, pkg_name: str, stage: str, success: bool) -> None:
        """Notify callbacks of build progress."""
        for callback in self._build_callbacks:
            try:
                callback(pkg_name, stage, success)
            except Exception:
                pass


class BuildError(Exception):
    """Exception raised for build errors."""
    pass
