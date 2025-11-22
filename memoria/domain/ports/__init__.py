"""
Ports - Protocol interfaces defining contracts for adapters.

Ports are abstract interfaces (Python Protocols) that define what
capabilities the domain needs from the infrastructure layer.

Adapters (outer layer) implement these ports.
Tests are written against ports, not concrete adapters.
"""
