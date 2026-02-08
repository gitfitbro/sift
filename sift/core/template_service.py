"""Template management service - business logic for template operations."""
from __future__ import annotations

import logging
import shutil
import yaml
from pathlib import Path

from sift.core import TemplateInfo, TemplateDetail, TemplatePhaseDetail
from sift.models import TEMPLATES_DIR, ensure_dirs, SessionTemplate

logger = logging.getLogger("sift.core.template")


class TemplateService:
    """Manages session template operations."""

    def list_templates(self) -> list[TemplateInfo]:
        """List all available templates."""
        ensure_dirs()
        paths = sorted(
            list(TEMPLATES_DIR.glob("*.yaml")) + list(TEMPLATES_DIR.glob("*.yml"))
        )

        results = []
        for tp in paths:
            try:
                t = SessionTemplate.from_file(tp)
                results.append(TemplateInfo(
                    name=t.name,
                    stem=tp.stem,
                    description=t.description,
                    phase_count=len(t.phases),
                    output_count=len(t.outputs),
                ))
            except Exception as e:
                logger.warning("Failed to load template %s: %s", tp.stem, e)
                results.append(TemplateInfo(
                    name=tp.stem,
                    stem=tp.stem,
                    description=f"Error: {e}",
                    phase_count=0,
                    output_count=0,
                ))
        return results

    def show_template(self, name: str) -> TemplateDetail:
        """Get full detail of a template by name.

        Raises:
            FileNotFoundError: If template not found.
        """
        path = self._find_template_path(name)
        t = SessionTemplate.from_file(path)

        phases = []
        for p in t.phases:
            phases.append(TemplatePhaseDetail(
                id=p.id,
                name=p.name,
                prompt=p.prompt,
                capture_types=[c.type for c in p.capture],
                required=any(c.required for c in p.capture),
                extract_field_ids=[e.id for e in p.extract],
                depends_on=p.depends_on,
            ))

        outputs = [{"type": o.type, "template": o.template} for o in t.outputs]

        return TemplateDetail(
            name=t.name,
            description=t.description,
            phases=phases,
            outputs=outputs,
        )

    def create_template(self, data: dict) -> Path:
        """Create a new template from a data dict. Returns path to saved file.

        Raises:
            ValueError: If template data is invalid.
        """
        ensure_dirs()
        name = data.get("name")
        if not name:
            raise ValueError("Template must have a 'name' field")

        slug = name.lower().replace(" ", "-").replace("_", "-")
        path = TEMPLATES_DIR / f"{slug}.yaml"
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        logger.info("Template saved to %s", path)
        return path

    def import_template(self, path: Path) -> TemplateInfo:
        """Import a template from an external file.

        Raises:
            FileNotFoundError: If source file not found.
            ValueError: If template is invalid.
        """
        ensure_dirs()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        try:
            t = SessionTemplate.from_file(path)
        except Exception as e:
            raise ValueError(f"Invalid template: {e}") from e

        dest = TEMPLATES_DIR / path.name
        shutil.copy2(path, dest)
        logger.info("Imported template '%s' to %s", t.name, dest)

        return TemplateInfo(
            name=t.name,
            stem=dest.stem,
            description=t.description,
            phase_count=len(t.phases),
            output_count=len(t.outputs),
        )

    def get_template_names(self) -> list[str]:
        """Get all template stem names (for shell completion)."""
        ensure_dirs()
        paths = list(TEMPLATES_DIR.glob("*.yaml")) + list(TEMPLATES_DIR.glob("*.yml"))
        return sorted(p.stem for p in paths)

    def find_template(self, name: str) -> Path:
        """Find a template by name. Public wrapper for _find_template_path.

        Raises:
            FileNotFoundError: If template not found.
        """
        return self._find_template_path(name)

    def _find_template_path(self, name: str) -> Path:
        """Find a template file by name."""
        for ext in (".yaml", ".yml"):
            path = TEMPLATES_DIR / f"{name}{ext}"
            if path.exists():
                return path
        # Try as absolute/relative path
        p = Path(name)
        if p.exists():
            return p
        raise FileNotFoundError(f"Template '{name}' not found in {TEMPLATES_DIR}")
