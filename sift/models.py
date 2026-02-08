"""Core data models for sift."""
from __future__ import annotations
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from copy import deepcopy
from .config import get_sift_home

# ── Schema Versions ──
SCHEMA_VERSION_SESSION = 1
SCHEMA_VERSION_TEMPLATE = 1

# ── Paths ──
BASE_DIR = get_sift_home()
TEMPLATES_DIR = BASE_DIR / "templates"
SESSIONS_DIR = BASE_DIR / "sessions"

def ensure_dirs():
    """Create base directories if they don't exist."""
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


# ── Template Models ──
@dataclass
class ExtractionField:
    id: str
    type: str  # list, map, text, boolean
    prompt: str
    
    @classmethod
    def from_dict(cls, d: dict) -> "ExtractionField":
        return cls(id=d["id"], type=d.get("type", "text"), prompt=d["prompt"])


@dataclass 
class CaptureSpec:
    type: str  # audio, transcript, text
    required: bool = True
    
    @classmethod
    def from_dict(cls, d: dict) -> "CaptureSpec":
        return cls(type=d.get("type", "text"), required=d.get("required", True))


@dataclass
class PhaseTemplate:
    id: str
    name: str
    prompt: str
    capture: list[CaptureSpec] = field(default_factory=list)
    extract: list[ExtractionField] = field(default_factory=list)
    depends_on: Optional[str] = None
    
    @classmethod
    def from_dict(cls, d: dict) -> "PhaseTemplate":
        return cls(
            id=d["id"],
            name=d["name"],
            prompt=d.get("prompt", ""),
            capture=[CaptureSpec.from_dict(c) for c in d.get("capture", [])],
            extract=[ExtractionField.from_dict(e) for e in d.get("extract", [])],
            depends_on=d.get("depends_on"),
        )


@dataclass
class OutputSpec:
    type: str  # yaml, markdown, docx
    template: str
    filename: Optional[str] = None
    
    @classmethod
    def from_dict(cls, d: dict) -> "OutputSpec":
        return cls(
            type=d["type"],
            template=d.get("template", ""),
            filename=d.get("filename"),
        )


@dataclass
class SessionTemplate:
    name: str
    description: str
    phases: list[PhaseTemplate]
    outputs: list[OutputSpec] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    
    @classmethod
    def from_file(cls, path: Path) -> "SessionTemplate":
        from sift.errors import SchemaVersionError

        with open(path) as f:
            d = yaml.safe_load(f)

        file_version = d.get("schema_version", 0)
        if file_version > SCHEMA_VERSION_TEMPLATE:
            raise SchemaVersionError(
                str(path),
                found_version=file_version,
                expected_version=SCHEMA_VERSION_TEMPLATE,
            )

        return cls(
            name=d["name"],
            description=d.get("description", ""),
            phases=[PhaseTemplate.from_dict(p) for p in d.get("phases", [])],
            outputs=[OutputSpec.from_dict(o) for o in d.get("outputs", [])],
            metadata=d.get("metadata", {}),
        )
    
    def to_dict(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION_TEMPLATE,
            "name": self.name,
            "description": self.description,
            "phases": [
                {
                    "id": p.id,
                    "name": p.name,
                    "prompt": p.prompt,
                    "capture": [{"type": c.type, "required": c.required} for c in p.capture],
                    "extract": [{"id": e.id, "type": e.type, "prompt": e.prompt} for e in p.extract],
                    **({"depends_on": p.depends_on} if p.depends_on else {}),
                }
                for p in self.phases
            ],
            "outputs": [{"type": o.type, "template": o.template} for o in self.outputs],
            "metadata": self.metadata,
        }


def merge_templates(templates: list[SessionTemplate], stems: list[str]) -> SessionTemplate:
    """Merge multiple templates into one, namespacing phase IDs to avoid conflicts.

    Single-template input is returned unmodified (no namespacing).
    """
    if len(templates) == 1:
        return templates[0]

    merged_phases: list[PhaseTemplate] = []
    seen_outputs: set[tuple[str, str]] = set()
    merged_outputs: list[OutputSpec] = []

    for tmpl, stem in zip(templates, stems):
        for phase in tmpl.phases:
            ns_id = f"{stem}.{phase.id}"
            ns_depends = f"{stem}.{phase.depends_on}" if phase.depends_on else None
            merged_phases.append(PhaseTemplate(
                id=ns_id,
                name=phase.name,
                prompt=phase.prompt,
                capture=deepcopy(phase.capture),
                extract=deepcopy(phase.extract),
                depends_on=ns_depends,
            ))

        for out in tmpl.outputs:
            key = (out.type, out.template)
            if key not in seen_outputs:
                seen_outputs.add(key)
                merged_outputs.append(out)

    return SessionTemplate(
        name=" + ".join(t.name for t in templates),
        description="\n\n".join(t.description for t in templates if t.description),
        phases=merged_phases,
        outputs=merged_outputs,
        metadata={"source_templates": stems, "template_count": len(templates)},
    )


# ── Session Runtime State ──
@dataclass
class PhaseState:
    id: str
    status: str = "pending"  # pending, captured, transcribed, extracted, complete
    audio_file: Optional[str] = None
    transcript_file: Optional[str] = None
    extracted_file: Optional[str] = None
    captured_at: Optional[str] = None
    transcribed_at: Optional[str] = None
    extracted_at: Optional[str] = None
    source_document: Optional[str] = None  # references document id
    source_pages: Optional[str] = None     # e.g., "1-3" or "all"


@dataclass
class Session:
    name: str
    template_name: str
    created_at: str
    updated_at: str
    phases: dict[str, PhaseState]
    status: str = "active"  # active, complete, archived
    documents: list[dict] = field(default_factory=list)
    source_templates: list[str] = field(default_factory=list)
    
    @property
    def dir(self) -> Path:
        return SESSIONS_DIR / self.name
    
    @classmethod
    def create(cls, name: str, template: SessionTemplate) -> "Session":
        now = datetime.now().isoformat()
        phases = {}
        for pt in template.phases:
            phases[pt.id] = PhaseState(id=pt.id)
        
        session = cls(
            name=name,
            template_name=template.name,
            created_at=now,
            updated_at=now,
            phases=phases,
            source_templates=template.metadata.get("source_templates", []),
        )
        
        # Create directory structure
        session.dir.mkdir(parents=True, exist_ok=True)
        for phase_id in phases:
            (session.dir / "phases" / phase_id).mkdir(parents=True, exist_ok=True)
        (session.dir / "outputs").mkdir(parents=True, exist_ok=True)
        (session.dir / "documents").mkdir(parents=True, exist_ok=True)
        
        # Save template copy
        with open(session.dir / "template.yaml", "w") as f:
            yaml.dump(template.to_dict(), f, default_flow_style=False, sort_keys=False)
        
        # Save state
        session.save()
        return session
    
    def save(self):
        self.updated_at = datetime.now().isoformat()
        state = {
            "schema_version": SCHEMA_VERSION_SESSION,
            "name": self.name,
            "template_name": self.template_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "documents": self.documents,
            "source_templates": self.source_templates,
            "phases": {
                pid: {
                    "id": ps.id,
                    "status": ps.status,
                    "audio_file": ps.audio_file,
                    "transcript_file": ps.transcript_file,
                    "extracted_file": ps.extracted_file,
                    "captured_at": ps.captured_at,
                    "transcribed_at": ps.transcribed_at,
                    "extracted_at": ps.extracted_at,
                    "source_document": ps.source_document,
                    "source_pages": ps.source_pages,
                }
                for pid, ps in self.phases.items()
            },
        }
        with open(self.dir / "session.yaml", "w") as f:
            yaml.dump(state, f, default_flow_style=False, sort_keys=False)
    
    @classmethod
    def load(cls, name: str) -> "Session":
        from sift.errors import SessionNotFoundError, SchemaVersionError

        session_dir = SESSIONS_DIR / name
        if not session_dir.exists():
            raise SessionNotFoundError(name)

        with open(session_dir / "session.yaml") as f:
            d = yaml.safe_load(f)

        file_version = d.get("schema_version", 0)
        if file_version > SCHEMA_VERSION_SESSION:
            raise SchemaVersionError(
                str(session_dir / "session.yaml"),
                found_version=file_version,
                expected_version=SCHEMA_VERSION_SESSION,
            )

        phases = {}
        for pid, ps in d.get("phases", {}).items():
            phases[pid] = PhaseState(
                id=ps["id"],
                status=ps.get("status", "pending"),
                audio_file=ps.get("audio_file"),
                transcript_file=ps.get("transcript_file"),
                extracted_file=ps.get("extracted_file"),
                captured_at=ps.get("captured_at"),
                transcribed_at=ps.get("transcribed_at"),
                extracted_at=ps.get("extracted_at"),
                source_document=ps.get("source_document"),
                source_pages=ps.get("source_pages"),
            )

        return cls(
            name=d["name"],
            template_name=d["template_name"],
            created_at=d["created_at"],
            updated_at=d["updated_at"],
            phases=phases,
            status=d.get("status", "active"),
            documents=d.get("documents", []),
            source_templates=d.get("source_templates", []),
        )
    
    def get_template(self) -> SessionTemplate:
        return SessionTemplate.from_file(self.dir / "template.yaml")
    
    def phase_dir(self, phase_id: str) -> Path:
        return self.dir / "phases" / phase_id
    
    def get_transcript(self, phase_id: str) -> Optional[str]:
        ps = self.phases.get(phase_id)
        if ps and ps.transcript_file:
            path = self.phase_dir(phase_id) / ps.transcript_file
            if path.exists():
                return path.read_text()
        return None
    
    def get_extracted(self, phase_id: str) -> Optional[dict]:
        ps = self.phases.get(phase_id)
        if ps and ps.extracted_file:
            path = self.phase_dir(phase_id) / ps.extracted_file
            if path.exists():
                with open(path) as f:
                    return yaml.safe_load(f)
        return None
