from enum import Enum


class AutomationState(str, Enum):
    IDLE = "idle"
    PURGE = "purge"
    OFFSET = "offset"
    CALIBRATION = "calibration"
    STABILIZING = "stabilizing"
    MEASURING = "measuring"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    ERROR = "error"
