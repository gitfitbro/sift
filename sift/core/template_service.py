"""Template management service - business logic for template operations."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import yaml

from sift.core import TemplateDetail, TemplateInfo, TemplatePhaseDetail
from sift.models import TEMPLATES_DIR, SessionTemplate, ensure_dirs

logger = logging.getLogger("sift.core.template")


class TemplateService:
    """Manages session template operations."""

    def list_templates(self) -> list[TemplateInfo]:
        """List all available templates."""
        ensure_dirs()
        paths = sorted(list(TEMPLATES_DIR.glob("*.yaml")) + list(TEMPLATES_DIR.glob("*.yml")))

        results = []
        for tp in paths:
            try:
                t = SessionTemplate.from_file(tp)
                results.append(
                    TemplateInfo(
                        name=t.name,
                        stem=tp.stem,
                        description=t.description,
                        phase_count=len(t.phases),
                        output_count=len(t.outputs),
                    )
                )
            except Exception as e:
                logger.warning("Failed to load template %s: %s", tp.stem, e)
                results.append(
                    TemplateInfo(
                        name=tp.stem,
                        stem=tp.stem,
                        description=f"Error: {e}",
                        phase_count=0,
                        output_count=0,
                    )
                )
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
            phases.append(
                TemplatePhaseDetail(
                    id=p.id,
                    name=p.name,
                    prompt=p.prompt,
                    capture_types=[c.type for c in p.capture],
                    required=any(c.required for c in p.capture),
                    extract_field_ids=[e.id for e in p.extract],
                    depends_on=p.depends_on,
                )
            )

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
            CaptureError: If source file not found.
            SiftError: If template is invalid.
        """
        from sift.errors import CaptureError

        ensure_dirs()
        if not path.exists():
            raise CaptureError(f"File not found: {path}", file_path=str(path))

        from sift.errors import SiftError

        try:
            t = SessionTemplate.from_file(path)
        except SiftError:
            raise
        except Exception as e:
            raise SiftError(f"Invalid template: {e}") from e

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
            TemplateNotFoundError: If template not found.
        """
        return self._find_template_path(name)

    def install_from_url(self, url: str) -> TemplateInfo:
        """Download and install a template from a URL.

        Supports raw YAML URLs (e.g., GitHub raw files).

        Args:
            url: URL to a YAML template file.

        Raises:
            CaptureError: If download fails.
            SiftError: If template is invalid.
        """
        import tempfile
        import urllib.request

        from sift.errors import CaptureError, SiftError

        ensure_dirs()

        # Download to a temporary file
        try:
            with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as tmp:
                tmp_path = Path(tmp.name)
                urllib.request.urlretrieve(url, tmp_path)
        except Exception as e:
            raise CaptureError(
                f"Failed to download template from {url}: {e}",
                file_path=url,
            ) from e

        # Validate and import
        try:
            t = SessionTemplate.from_file(tmp_path)
        except SiftError:
            tmp_path.unlink(missing_ok=True)
            raise
        except Exception as e:
            tmp_path.unlink(missing_ok=True)
            raise SiftError(f"Downloaded file is not a valid template: {e}") from e

        slug = t.name.lower().replace(" ", "-").replace("_", "-")
        dest = TEMPLATES_DIR / f"{slug}.yaml"
        shutil.copy2(tmp_path, dest)
        tmp_path.unlink(missing_ok=True)

        logger.info("Installed template '%s' from %s to %s", t.name, url, dest)

        return TemplateInfo(
            name=t.name,
            stem=dest.stem,
            description=t.description,
            phase_count=len(t.phases),
            output_count=len(t.outputs),
        )

    def search_templates(self, query: str) -> list[TemplateInfo]:
        """Search templates by name, description, or tags.

        Args:
            query: Search string to match against template name, description, and tags.
        """
        query_lower = query.lower()
        all_templates = self.list_templates()
        results = []

        for t in all_templates:
            # Check name and description
            if query_lower in t.name.lower() or query_lower in t.description.lower():
                results.append(t)
                continue

            # Check tags (need to load full template for metadata)
            try:
                path = self._find_template_path(t.stem)
                full = SessionTemplate.from_file(path)
                if any(query_lower in tag.lower() for tag in full.tags):
                    results.append(t)
            except Exception:
                pass

        return results

    def _find_template_path(self, name: str) -> Path:
        """Find a template file by name."""
        from sift.errors import TemplateNotFoundError

        for ext in (".yaml", ".yml"):
            path = TEMPLATES_DIR / f"{name}{ext}"
            if path.exists():
                return path
        # Try as absolute/relative path
        p = Path(name)
        if p.exists():
            return p
        raise TemplateNotFoundError(name, search_dir=str(TEMPLATES_DIR))
