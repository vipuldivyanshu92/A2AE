"""Double-entry ledger - Task 4.2."""

import uuid

from sqlalchemy.orm import Session

from .models import LedgerEntryModel
from .schemas.ledger import LedgerEntryType


class LedgerService:
    """Double-entry ledger for holds, releases, refunds, fees."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def record_hold(
        self,
        job_id: str,
        amount: str,
        hold_id: str,
        idempotency_key: str | None = None,
    ) -> LedgerEntryModel:
        """Record hold: escrow debits requester, credits escrow hold."""
        entry = LedgerEntryModel(
            entry_id=str(uuid.uuid4()),
            job_id=job_id,
            entry_type=LedgerEntryType.HOLD.value,
            amount=amount,
            debit_account=f"requester:{job_id}",
            credit_account=f"escrow_hold:{hold_id}",
            reference=hold_id,
            idempotency_key=idempotency_key,
        )
        self._session.add(entry)
        self._session.commit()
        return entry

    def record_release(
        self,
        job_id: str,
        amount: str,
        hold_id: str,
        doer_id: str,
        idempotency_key: str | None = None,
    ) -> LedgerEntryModel:
        """Record release: escrow hold debits, doer credits."""
        entry = LedgerEntryModel(
            entry_id=str(uuid.uuid4()),
            job_id=job_id,
            entry_type=LedgerEntryType.RELEASE.value,
            amount=amount,
            debit_account=f"escrow_hold:{hold_id}",
            credit_account=f"doer:{doer_id}",
            reference=f"settle:{job_id}",
            idempotency_key=idempotency_key,
        )
        self._session.add(entry)
        self._session.commit()
        return entry

    def record_refund(
        self,
        job_id: str,
        amount: str,
        hold_id: str,
        requester_id: str,
        idempotency_key: str | None = None,
    ) -> LedgerEntryModel:
        """Record refund: escrow hold debits, requester credits."""
        entry = LedgerEntryModel(
            entry_id=str(uuid.uuid4()),
            job_id=job_id,
            entry_type=LedgerEntryType.REFUND.value,
            amount=amount,
            debit_account=f"escrow_hold:{hold_id}",
            credit_account=f"requester:{requester_id}",
            reference=f"refund:{job_id}",
            idempotency_key=idempotency_key,
        )
        self._session.add(entry)
        self._session.commit()
        return entry
