from dataclasses import dataclass


@dataclass(frozen=True)
class SubjectEntry:
    subject: str
    description: str
    subject_type: str
