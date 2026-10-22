"""Output identities are distinct even when the file extensions coincide."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Format:
    key: str
    label: str
    folder: str
    extension: str
    protocol: int | None = None


FORMATS = (
    Format('step203', 'STEP AP203', 'STEP_AP203', '.step', 203),
    Format('step214', 'STEP AP214', 'STEP_AP214', '.step', 214),
    Format('step242', 'STEP AP242 · MBD lisansı', 'STEP_AP242', '.step', 242),
    Format('xt', 'Parasolid Text · X_T', 'PARASOLID_XT', '.x_t'),
    Format('xb', 'Parasolid Binary · X_B', 'PARASOLID_XB', '.x_b'),
    Format('iges', 'IGES', 'IGES', '.igs'),
    Format('stl_binary', 'STL Binary', 'STL_BINARY', '.stl'),
    Format('stl_ascii', 'STL ASCII', 'STL_ASCII', '.stl'),
)
BY_KEY = {item.key: item for item in FORMATS}
