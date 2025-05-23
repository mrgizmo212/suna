from .sandbox import daytona

"""Sandbox provider abstraction.

This module exposes the current sandbox provider instance.  For now it wraps the
Daytona client but provides a neutral import path so scripts don't depend on
Daytona-specific modules."""

provider = daytona

