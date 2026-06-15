from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from supply.aggregation import build_snapshot
from supply.analytics import generate_signal, persist_signal
from supply.models import SNAPSHOT_CLASSES


class Command(BaseCommand):
    help = (
        "Aggregate current vessel state into DailySupplySnapshot rows and "
        "compute the per-class SupplySignal for a given date (default: today)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            help="Date to aggregate (YYYY-MM-DD). Defaults to today (local).",
        )
        parser.add_argument("--basin", default="pacific")

    def handle(self, *args, **options):
        if options.get("date"):
            target_date = datetime.strptime(options["date"], "%Y-%m-%d").date()
        else:
            target_date = timezone.localdate()
        basin = options["basin"]

        snapshots = build_snapshot(target_date, basin=basin)
        self.stdout.write(
            self.style.SUCCESS(
                f"Built {len(snapshots)} supply snapshots for {target_date}."
            )
        )

        for vessel_class in SNAPSHOT_CLASSES:
            result = generate_signal(vessel_class, as_of=target_date)
            persist_signal(result, target_date)
            self.stdout.write(
                f"  {vessel_class}: {result.direction} "
                f"(score={result.score:+.2f}, conf={result.confidence:.2f}, "
                f"{result.method})"
            )

        self.stdout.write(self.style.SUCCESS("Supply signals updated."))
