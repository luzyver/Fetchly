import json

from django.core.management.base import BaseCommand, CommandError

from downloads.capabilities import check_capabilities


class Command(BaseCommand):
    help = "Check local media processing capabilities without external requests"

    def handle(self, *args, **options):
        result = check_capabilities()
        self.stdout.write(json.dumps(result))
        if not all(result.values()):
            raise CommandError("One or more media capabilities are unavailable")
