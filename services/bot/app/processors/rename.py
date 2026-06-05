#genai: File rename — copy with new stem, preserve original extension and content.
from __future__ import annotations

import shutil
from pathlib import Path


def rename_file(input_path: Path, new_stem: str, output_dir: Path) -> Path:
    """
    Return a copy of input_path whose filename stem is replaced by new_stem.
    The file extension and all file content remain unchanged.

    Example:
        rename_file(Path("/tmp/Items.pdf"), "Quotation", Path("/tmp"))
        → /tmp/Quotation.pdf
    """
    clean_stem = new_stem.strip().rstrip(".")
    if not clean_stem:
        raise ValueError("New filename cannot be empty.")
    output_path = output_dir / f"{clean_stem}{input_path.suffix}"
    shutil.copy2(str(input_path), str(output_path))
    return output_path
