from abc import ABC, abstractmethod
from typing import Optional

from domain.models.advisor_auth import AdvisorLaunchToken, AdvisorSession


class AdvisorAuthRepository(ABC):
    @abstractmethod
    def create_launch_token(self, token: AdvisorLaunchToken) -> None:
        """Persist a single-use advisor launch token."""
        pass

    @abstractmethod
    def consume_launch_token(self, token_hash: str) -> Optional[AdvisorLaunchToken]:
        """Atomically consume and return a launch token by hash."""
        pass

    @abstractmethod
    def create_session(self, session: AdvisorSession) -> None:
        """Persist an advisor session."""
        pass

    @abstractmethod
    def find_session(self, token_hash: str) -> Optional[AdvisorSession]:
        """Return an active advisor session by hash."""
        pass

    @abstractmethod
    def delete_session(self, token_hash: str) -> bool:
        """Delete a persisted advisor session by hash."""
        pass
