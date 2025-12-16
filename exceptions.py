"""Modem upgrader specific exceptions"""


class ModemUpgradeException(Exception):
    """Base exception for modem upgrade operations"""

    pass


class RecoverableModemFailure(ModemUpgradeException):
    """
    Raised when a modem upgrade failure is recoverable
    and the operation should be retried.
    """

    pass


class ModemUpgradeAborted(ModemUpgradeException):
    """
    Raised when a modem upgrade is aborted
    (e.g., image checksum mismatch, incompatible hardware).
    """

    pass


class ModemUpgradeNotNeeded(ModemUpgradeException):
    """
    Raised when the modem already has the target firmware installed.
    """

    pass


class ModemReconnectionFailed(ModemUpgradeException):
    """
    Raised when reconnection to device fails after modem upgrade.
    """

    pass


class ModemUpgradeOptionsException(ModemUpgradeException):
    """
    Raised when upgrade options validation fails.
    """

    pass
