"""Domain enums.

Status transitions for SERVICE_JOB (enforced in service layer later):
  IN_PROGRESS -> DONE | CANCELLED
  DONE -> IN_PROGRESS | PAID | CANCELLED
  PAID, CANCELLED are terminal (returns/voids are separate documents).

DIRECT_SALE is created as PAID in one atomic checkout.
"""

from enum import Enum


class Role(str, Enum):
    ADMIN = "ADMIN"
    CASHIER = "CASHIER"


class TransactionType(str, Enum):
    DIRECT_SALE = "DIRECT_SALE"
    SERVICE_JOB = "SERVICE_JOB"


class TransactionStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class PaymentMethod(str, Enum):
    CASH = "CASH"
    GCASH = "GCASH"
    BANK_TRANSFER = "BANK_TRANSFER"
    CARD = "CARD"
    OTHER = "OTHER"


class ShiftStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class ShiftCloseTiming(str, Enum):
    ON_TIME = "ON_TIME"
    EARLY = "EARLY"
    EXTENDED = "EXTENDED"


class StockAdjustmentType(str, Enum):
    IN = "IN"
    OUT = "OUT"
    SET = "SET"
    SALE = "SALE"
    RETURN = "RETURN"
    REVERSAL = "REVERSAL"
    TRANSFER_OUT = "TRANSFER_OUT"
    TRANSFER_IN = "TRANSFER_IN"


class NotificationType(str, Enum):
    LOW_STOCK = "LOW_STOCK"


class ReturnType(str, Enum):
    VOID = "VOID"
    PARTIAL_RETURN = "PARTIAL_RETURN"


class ReturnStatus(str, Enum):
    COMPLETED = "COMPLETED"


class DocumentPrefix(str, Enum):
    INV = "INV"
    JO = "JO"
    RV = "RV"
    TR = "TR"
