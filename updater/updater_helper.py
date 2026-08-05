import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path, PurePosixPath


def wait_for_process(
    process_id: int,
    timeout: float = 30.0,
) -> None:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        try:
            os.kill(
                process_id,
                0,
            )
        except OSError:
            return

        time.sleep(
            0.5
        )

    raise RuntimeError(
        "Spotify+ did not close in time."
    )


def copy_installation(
    source: Path,
    destination: Path,
) -> None:
    ignored_names = {
        "updates",
        "__pycache__",
    }

    def ignore(
        directory: str,
        names: list[str],
    ) -> set[str]:
        del directory

        return {
            name
            for name in names
            if name in ignored_names
        }

    shutil.copytree(
        source,
        destination,
        dirs_exist_ok=True,
        ignore=ignore,
    )


def validate_archive_member(
    member_name: str,
) -> None:
    normalized = member_name.replace(
        "\\",
        "/",
    )

    path = PurePosixPath(
        normalized
    )

    if path.is_absolute():
        raise RuntimeError(
            "Update archive contains an absolute path."
        )

    if ".." in path.parts:
        raise RuntimeError(
            "Update archive contains path traversal."
        )

    if (
        len(path.parts) > 0
        and ":" in path.parts[0]
    ):
        raise RuntimeError(
            "Update archive contains an invalid drive path."
        )


def safe_extract_archive(
    archive: zipfile.ZipFile,
    destination: Path,
) -> None:
    for member in archive.infolist():
        validate_archive_member(
            member.filename
        )

        if (
            member.external_attr >> 16
        ) & 0o170000 == 0o120000:
            raise RuntimeError(
                "Symbolic links are not allowed in update packages."
            )

    archive.extractall(
        destination
    )


def cleanup_old_backups(
    backup_root: Path,
    keep: int,
) -> None:
    if not backup_root.exists():
        return

    backups = sorted(
        (
            item
            for item in backup_root.iterdir()
            if item.is_dir()
        ),
        key=lambda item:
            item.stat().st_mtime,
        reverse=True,
    )

    for old_backup in backups[
        max(
            0,
            keep,
        ):
    ]:
        shutil.rmtree(
            old_backup,
            ignore_errors=True,
        )


def replace_installation(
    extracted_dir: Path,
    install_dir: Path,
) -> None:
    for item in extracted_dir.iterdir():
        target = (
            install_dir
            / item.name
        )

        if item.is_dir():
            shutil.copytree(
                item,
                target,
                dirs_exist_ok=True,
            )

        else:
            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            shutil.copy2(
                item,
                target,
            )


def restore_backup(
    backup_dir: Path,
    install_dir: Path,
) -> None:
    if not backup_dir.exists():
        return

    copy_installation(
        backup_dir,
        install_dir,
    )


def launch_application(
    target: Path,
    arguments: list[str],
) -> None:
    if target.suffix.lower() in {
        ".py",
        ".pyw",
    }:
        command = [
            sys.executable,
            str(target),
            *arguments,
        ]

    else:
        command = [
            str(target),
            *arguments,
        ]

    subprocess.Popen(
        command,
        cwd=str(
            target.parent
        ),
        close_fds=True,
    )


def run(
    instruction_file: Path,
) -> int:
    with instruction_file.open(
        "r",
        encoding="utf-8",
    ) as file:
        instruction = json.load(
            file
        )

    package_path = Path(
        instruction[
            "package_path"
        ]
    ).resolve()

    install_dir = Path(
        instruction[
            "install_dir"
        ]
    ).resolve()

    backup_dir = Path(
        instruction[
            "backup_dir"
        ]
    ).resolve()

    launch_target = Path(
        instruction[
            "launch_target"
        ]
    ).resolve()

    launch_args = [
        str(value)
        for value in instruction.get(
            "launch_args",
            [],
        )
    ]

    process_id = int(
        instruction[
            "process_id"
        ]
    )

    backup_retention = max(
        1,
        int(
            instruction.get(
                "backup_retention",
                3,
            )
        ),
    )

    if not package_path.exists():
        raise RuntimeError(
            "Downloaded update package no longer exists."
        )

    if package_path.suffix.lower() != ".zip":
        raise RuntimeError(
            "Update package must be a ZIP archive."
        )

    if not install_dir.exists():
        raise RuntimeError(
            "Application installation directory does not exist."
        )

    staging_dir = (
        instruction_file.parent
        / "apply-staging"
    )

    wait_for_process(
        process_id
    )

    if staging_dir.exists():
        shutil.rmtree(
            staging_dir,
            ignore_errors=True,
        )

    if backup_dir.exists():
        shutil.rmtree(
            backup_dir,
            ignore_errors=True,
        )

    backup_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        copy_installation(
            install_dir,
            backup_dir,
        )

        staging_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        with zipfile.ZipFile(
            package_path,
            "r",
        ) as archive:
            bad_member = archive.testzip()

            if bad_member is not None:
                raise RuntimeError(
                    "Update ZIP integrity check failed at "
                    f"{bad_member}."
                )

            safe_extract_archive(
                archive,
                staging_dir,
            )

        extracted_root = staging_dir

        children = list(
            staging_dir.iterdir()
        )

        if not children:
            raise RuntimeError(
                "Update ZIP is empty."
            )

        if (
            len(children) == 1
            and children[0].is_dir()
        ):
            extracted_root = (
                children[0]
            )

        if not any(
            extracted_root.iterdir()
        ):
            raise RuntimeError(
                "Update package contains no application files."
            )

        replace_installation(
            extracted_root,
            install_dir,
        )

        success_file = (
            instruction_file.parent
            / "last-update-success.json"
        )

        success_file.write_text(
            json.dumps(
                {
                    "version":
                        instruction.get(
                            "version",
                            "",
                        ),
                    "installed_at":
                        int(
                            time.time()
                        ),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        instruction_file.unlink(
            missing_ok=True
        )

        cleanup_old_backups(
            backup_dir.parent,
            backup_retention,
        )

        launch_application(
            launch_target,
            launch_args,
        )

        return 0

    except Exception as error:
        try:
            restore_backup(
                backup_dir,
                install_dir,
            )

            launch_application(
                launch_target,
                launch_args,
            )

        except Exception:
            pass

        error_file = (
            instruction_file.parent
            / "last-update-error.txt"
        )

        error_file.write_text(
            (
                f"{type(error).__name__}: "
                f"{error}"
            ),
            encoding="utf-8",
        )

        return 1

    finally:
        shutil.rmtree(
            staging_dir,
            ignore_errors=True,
        )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(2)

    raise SystemExit(
        run(
            Path(
                sys.argv[1]
            )
        )
    )