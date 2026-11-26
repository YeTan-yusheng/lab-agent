from enum import IntEnum, StrEnum


class NotificationType(StrEnum):
    RESERVATION_SUBMITTED = "reservation_submitted"
    RESERVATION_APPROVED = "reservation_approved"
    RESERVATION_REJECTED = "reservation_rejected"
    RESERVATION_CANCELLED = "reservation_cancelled"
    RESERVATION_FORCE_CANCELLED = "reservation_force_cancelled"
    RESERVATION_EXPIRED = "reservation_expired"


class EmailStatus(IntEnum):
    PENDING = 0
    SENDING = 1
    SENT = 2
    FAILED = 3


class NotificationErrorCode(StrEnum):
    NOT_FOUND = "NOTIFICATION_NOT_FOUND"
    FORBIDDEN = "NOTIFICATION_FORBIDDEN"
    INVALID_STATUS = "NOTIFICATION_INVALID_STATUS"
    SEND_FAILED = "EMAIL_SEND_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"