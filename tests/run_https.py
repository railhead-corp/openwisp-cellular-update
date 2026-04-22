#!/usr/bin/env python
import os
import sys
import django

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "openwisp2.settings")
    django.setup()
    
    from daphne.cli import CommandLineInterface
    cli = CommandLineInterface()
    cli.run([
        "-e", "ssl:8000:privateKey=key.pem:certKey=cert.pem",
        "openwisp2.routing:application"
    ])
