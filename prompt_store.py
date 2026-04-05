"""Load prompt templates from prompts/*.txt."""

from __future__ import annotations

from pathlib import Path

PROMPT_FILES = {
    "proposed": {
        ("designer", "S1"): "rubric_designer_s1.txt",
        ("supervisor", "S1-CHK"): "rubric_supervisor_s1.txt",
        ("designer", "S2"): "rubric_designer_s2.txt",
        ("supervisor", "S2-CHK"): "rubric_supervisor_s2.txt",
        ("designer", "S3"): "rubric_designer_s3.txt",
        ("supervisor", "S3-CHK"): "rubric_supervisor_s3.txt",
    },
    "baseline": {
        ("designer", "S1"): "baseline_designer_s1.txt",
        ("designer", "S2"): "baseline_designer_s2.txt",
        ("designer", "S3"): "baseline_designer_s3.txt",
    },
    "scaffold_only": {
        ("designer", "S1"): "baseline_designer_s1.txt",
        ("supervisor", "S1-CHK"): "scaffold_supervisor_s1.txt",
        ("designer", "S2"): "baseline_designer_s2.txt",
        ("supervisor", "S2-CHK"): "scaffold_supervisor_s2.txt",
        ("designer", "S3"): "baseline_designer_s3.txt",
        ("supervisor", "S3-CHK"): "scaffold_supervisor_s3.txt",
    },
    "rubric_only": {
        ("designer", "S1"): "rubric_designer_s1.txt",
        ("designer", "S2"): "rubric_designer_s2.txt",
        ("designer", "S3"): "rubric_designer_s3.txt",
    },
}


class PromptStore:
    def __init__(self, base_dir: str = "prompts"):
        self.base_dir = Path(base_dir)

    def get(self, role: str, stage: str, profile: str = "proposed") -> str:
        profile_map = PROMPT_FILES.get(profile) or PROMPT_FILES["proposed"]
        filename = profile_map.get((role, stage))
        if not filename:
            return ""

        path = self.base_dir / filename
        if not path.exists():
            return ""

        return path.read_text(encoding="utf-8")
