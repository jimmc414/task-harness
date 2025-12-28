"""Built-in validators for Task Harness.

Validators are used as preconditions and postconditions for tasks.

Categories:
- Environment: VirtualEnvActive, EnvVarSet, EnvVarEquals, PythonPackageAvailable
- Filesystem: FileExists, DirectoryExists, FileModifiedWithin, FileSizeInRange
- Tabular: TabularFileValid, TabularFileRowCount
- Network: HostReachable, SFTPConnectable
- Process: CommandAvailable
- Composite: AnyOf, AllOf
"""

# Base class - must be imported first
from harness.validators.base import Validator, ValidatorGroup

# Environment validators
from harness.validators.environment import (
    VirtualEnvActive,
    EnvVarSet,
    EnvVarEquals,
    PythonPackageAvailable,
)

# Filesystem validators
from harness.validators.filesystem import (
    FileExists,
    DirectoryExists,
    FileModifiedWithin,
    FileSizeInRange,
)

# Tabular validators
from harness.validators.tabular import (
    TabularFileValid,
    TabularFileRowCount,
)

# Network validators
from harness.validators.network import (
    HostReachable,
    SFTPConnectable,
)

# Composite validators
from harness.validators.composite import (
    AnyOf,
    AllOf,
    NoneOf,
    ConditionalValidator,
)

# Process validators
from harness.validators.process import CommandAvailable

__all__ = [
    # Base
    "Validator",
    "ValidatorGroup",
    # Environment
    "VirtualEnvActive",
    "EnvVarSet",
    "EnvVarEquals",
    "PythonPackageAvailable",
    # Filesystem
    "FileExists",
    "DirectoryExists",
    "FileModifiedWithin",
    "FileSizeInRange",
    # Tabular
    "TabularFileValid",
    "TabularFileRowCount",
    # Network
    "HostReachable",
    "SFTPConnectable",
    # Composite
    "AnyOf",
    "AllOf",
    "NoneOf",
    "ConditionalValidator",
    # Process
    "CommandAvailable",
]
