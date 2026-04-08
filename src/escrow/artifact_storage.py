"""Artifact storage for Completion Packet - Task 6.1."""

from sqlalchemy.orm import Session

from .models import CompletionPacketModel


class ArtifactStorage:
    """Store and retrieve Completion Packets."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def store(self, job_id: str, deliverable: dict, evidence: list) -> CompletionPacketModel:
        """Store completion packet."""
        packet = CompletionPacketModel(
            job_id=job_id,
            deliverable_json=deliverable,
            evidence_json={"artifacts": evidence},
        )
        self._session.add(packet)
        self._session.commit()
        self._session.refresh(packet)
        return packet

    def get(self, job_id: str) -> CompletionPacketModel | None:
        """Get completion packet by job_id."""
        return self._session.get(CompletionPacketModel, job_id)
