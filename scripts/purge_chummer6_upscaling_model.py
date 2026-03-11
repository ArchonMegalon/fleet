#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


TARGETS = [
    Path("/docker/chummercomplete/chummer-core-engine"),
    Path("/docker/chummercomplete/chummer-presentation"),
    Path("/docker/chummercomplete/chummer.run-services"),
]

MODEL_REL = Path("Chummer/Resources/source/upscaling/4x_FireAlpha.pth")
README_REL = Path("Chummer/Resources/source/upscaling/README.md")
IGNORE_LINE = str(MODEL_REL)
OLD_TEXT = (
    '6. In the bottom-left corner of the workspace, you will see an orange rectangle titled "Load Model". '
    'Click on the "Click to select a file" field inside of that, then navigate to and select 4x_FireAlpha.pth, '
    "which should be located in the same directory as this readme file. "
    "This is FireAlpha, the machine learning upscaling model that we've used for upscaling so far in Chummer5a "
    "and can upscale color images with transparency to four times its original size. If you want to upscale an "
    "image to an even larger size, you will need to modify the workflow in chaiNNer to feed the output image of "
    "one upscale into another upscaling step. If you wish to use a different upscaling model, this is the box "
    "you need to use to select your different model (though if it is saved in a NCNN or ONNX format instead of "
    "PyTorch, you will need to drag-and-drop the corresponding \"Load Model\" module from the left sidebar first "
    "and replace the original, PyTorch box with it)."
)
NEW_TEXT = (
    '6. In the bottom-left corner of the workspace, you will see an orange rectangle titled "Load Model". '
    'Click on the "Click to select a file" field inside of that, then select a local upscaling model file that '
    "you have installed outside the repository. The repo no longer ships `4x_FireAlpha.pth` or any other model "
    "weights, so keep those files in local-only storage and point chaiNNer at them manually. If you want to "
    "upscale an image to an even larger size, you will need to modify the workflow in chaiNNer to feed the output "
    "image of one upscale into another upscaling step. If you wish to use a different upscaling model, this is "
    "the box you need to use to select it (though if it is saved in a NCNN or ONNX format instead of PyTorch, "
    "you will need to drag-and-drop the corresponding \"Load Model\" module from the left sidebar first and "
    "replace the original PyTorch box with it)."
)


def ensure_ignore(repo: Path) -> None:
    gitignore = repo / ".gitignore"
    text = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    if IGNORE_LINE in text.splitlines():
        return
    if text and not text.endswith("\n"):
        text += "\n"
    text += IGNORE_LINE + "\n"
    gitignore.write_text(text, encoding="utf-8")


def rewrite_readme(repo: Path) -> None:
    path = repo / README_REL
    text = path.read_text(encoding="utf-8")
    if OLD_TEXT in text:
        text = text.replace(OLD_TEXT, NEW_TEXT)
        path.write_text(text, encoding="utf-8")


def main() -> int:
    for repo in TARGETS:
        model = repo / MODEL_REL
        if model.exists():
            model.unlink()
        ensure_ignore(repo)
        rewrite_readme(repo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
