# Security Policy

Please report security issues privately to the project maintainers.

`uniqdiff` treats user-provided key, normalizer, and comparator functions as trusted code.
Applications should not execute untrusted functions through this library.

Temporary files must be created in controlled directories and cleaned up after use.
