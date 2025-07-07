"""
Insert markers for code generation in openSAMPL files.

This module defines markers used to identify where new code should be inserted
when generating new vendors, metrics, and reference types.
"""

from pathlib import Path

from pydantic import BaseModel

opensampl_root = Path(__file__).parent.parent
template_dir = opensampl_root / "create" / "templates"


class InsertMarker(BaseModel):
    """
    Definition for a code insertion marker.

    Attributes:
        filepath: Path to the file where insertion should occur.
        comment_marker: Comment string that marks the insertion point.

    """

    filepath: Path
    template_name: str
    comment_marker: str

    @property
    def template_path(self) -> Path:
        """Path to the template"""
        return template_dir / self.template_name


class INSERT_MARKERS:  # noqa N801
    """
    Predefined insertion markers for various openSAMPL components.

    Contains markers for inserting new vendors, metrics, references, and ORM classes
    at the appropriate locations in the codebase.
    """

    VENDOR = InsertMarker(
        filepath=opensampl_root / "vendors" / "constants.py",
        template_name="vendor_template.txt",
        comment_marker="# --- CUSTOM VENDORS ---",
    )
    METRICS = InsertMarker(
        filepath=opensampl_root / "metrics.py",
        template_name="metric_template.txt",
        comment_marker="# --- CUSTOM METRICS ---",
    )
    REFERENCES = InsertMarker(
        filepath=opensampl_root / "references.py",
        template_name="reference_template.txt",
        comment_marker="# --- CUSTOM REFERENCE TYPES ---",
    )
    ORM_CLASS = InsertMarker(
        filepath=opensampl_root / "db" / "orm.py",
        template_name="orm_metadata.txt",
        comment_marker="# --- CUSTOM TABLES ---",
    )
    ORM_RELATIONSHIP = InsertMarker(
        filepath=opensampl_root / "db" / "orm.py",
        template_name="orm_relationship.txt",
        comment_marker="# --- CUSTOM PROBE METADATA RELATIONSHIP ---",
    )
