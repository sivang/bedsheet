"""Abstract base class for deployment targets."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from bedsheet.deploy.config import BedsheetConfig
from bedsheet.deploy.introspect import AgentMetadata


@dataclass
class GeneratedFile:
    """Represents a generated deployment file."""

    path: Path
    content: str
    executable: bool = False


class DeploymentTarget(ABC):
    """Abstract base class for deployment targets."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Target name (local, aws, gcp)."""
        pass

    @abstractmethod
    def generate(
        self,
        config: BedsheetConfig,
        agent_metadata: AgentMetadata,
        output_dir: Path,
    ) -> list[GeneratedFile]:
        """Generate deployment files for this target.

        Args:
            config: Bedsheet configuration
            agent_metadata: Extracted agent metadata
            output_dir: Directory to write files to

        Returns:
            List of generated files
        """
        pass

    @abstractmethod
    def validate(self, config: BedsheetConfig) -> list[str]:
        """Validate target-specific configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        pass
