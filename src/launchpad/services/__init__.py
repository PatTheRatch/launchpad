"""Data services for Launchpad.

A service is responsible only for *retrieving* a domain model. Services know
nothing about rendering or display hardware. They are independent and
replaceable: any implementation of a given interface can be swapped in at the
composition root.
"""
