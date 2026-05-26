"""Abstract ports for security_validator (Hexagonal Architecture).

ADR-003: Ports are defined as ABCs here; adapters implement them in adapters/.
domain/ never imports from adapters/.
"""

from abc import ABC, abstractmethod

from security_validator.domain.entities import TelemetryPacket


class SignatureVerifier(ABC):
    @abstractmethod
    def verify(self, packet: TelemetryPacket, secret: str) -> bool:
        """Return True if the packet's HMAC signature is valid."""


class AuditLogger(ABC):
    @abstractmethod
    def log_rejection(self, packet: TelemetryPacket, reason: str) -> None:
        """Log a rejected packet for security audit purposes."""


class ValidPacketPublisher(ABC):
    @abstractmethod
    def publish(self, packet: TelemetryPacket) -> None:
        """Forward a validated packet to the next processing stage."""
