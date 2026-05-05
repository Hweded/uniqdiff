"""Exception hierarchy for uniqdiff."""


class UniqDiffError(Exception):
    """Base class for all uniqdiff errors."""


class InvalidInputError(UniqDiffError):
    """Raised when input data or options are invalid."""


class KeyExtractionError(UniqDiffError):
    """Raised when a comparison key cannot be extracted from an item."""


class NormalizationError(UniqDiffError):
    """Raised when a normalizer fails."""


class ComparatorError(UniqDiffError):
    """Raised when a custom comparator fails."""


class UnsupportedFormatError(UniqDiffError):
    """Raised when a file format is unsupported."""


class MissingOptionalDependencyError(UniqDiffError):
    """Raised when an optional integration dependency is not installed."""


class CorruptedInputError(UniqDiffError):
    """Raised when an input file contains malformed records."""


class DiskLimitExceededError(UniqDiffError):
    """Raised when disk usage exceeds a configured limit."""


class TempStorageError(UniqDiffError):
    """Raised when temporary storage cannot be created or used safely."""
