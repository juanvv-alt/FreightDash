import asyncio

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from supply.geo import load_port_geos
from supply.ingest import AISIngestor


class Command(BaseCommand):
    help = (
        "Ingest AIS vessel positions from aisstream.io into vessel state and "
        "port-call events. Use --replay to run offline from a JSONL file."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--replay",
            help="Path to a JSONL file of aisstream messages (no API key needed).",
        )
        parser.add_argument(
            "--duration-seconds",
            type=int,
            default=0,
            help="Exit after N seconds (cron mode). 0 = run forever.",
        )
        parser.add_argument(
            "--with-aggregation",
            action="store_true",
            help="Run daily aggregate_supply from this process shortly after midnight.",
        )

    def handle(self, *args, **options):
        ports = load_port_geos(basin="pacific")
        if not ports:
            self.stdout.write(
                self.style.WARNING(
                    'No active ports found. Run "seed_pacific_ports" first; '
                    "arrivals/departures cannot be detected without geofences."
                )
            )

        ingestor = AISIngestor(
            api_key=getattr(settings, "AISSTREAM_API_KEY", ""),
            ports=ports,
            stdout=self.stdout,
        )

        replay_path = options.get("replay")
        if replay_path:
            self._run_replay(ingestor, replay_path)
            return

        if not ingestor.api_key:
            raise CommandError(
                "AISSTREAM_API_KEY is not set. Set it in the environment (free key "
                "from aisstream.io) or use --replay <file.jsonl> for offline mode."
            )

        asyncio.run(
            self._run_live(
                ingestor,
                options["duration_seconds"],
                options["with_aggregation"],
            )
        )

    def _run_replay(self, ingestor, path):
        self.stdout.write(f"Replaying AIS messages from {path} ...")
        with open(path, "r") as fh:
            stats = ingestor.replay(fh)
        self.stdout.write(self.style.SUCCESS(f"Replay complete: {stats}"))

    async def _run_live(self, ingestor, duration_seconds, with_aggregation):
        tasks = [asyncio.create_task(ingestor.run(duration_seconds))]
        if with_aggregation:
            tasks.append(asyncio.create_task(self._daily_aggregation_loop()))
        try:
            await tasks[0]
        finally:
            ingestor.stop()
            for task in tasks[1:]:
                task.cancel()
            await asyncio.gather(*tasks[1:], return_exceptions=True)

    async def _daily_aggregation_loop(self):
        """Lightweight scheduler: run aggregate_supply once per local day.

        Replaces Celery for the worker deployment -- sleeps until just after the
        next local midnight, aggregates, repeats.
        """
        from asgiref.sync import sync_to_async

        while True:
            now = timezone.localtime()
            tomorrow = (now + timezone.timedelta(days=1)).date()
            next_run = timezone.make_aware(
                timezone.datetime.combine(tomorrow, timezone.datetime.min.time())
            ) + timezone.timedelta(minutes=10)
            await asyncio.sleep(max(60, (next_run - now).total_seconds()))
            try:
                await sync_to_async(call_command, thread_sensitive=True)(
                    "aggregate_supply"
                )
                self.stdout.write(
                    self.style.SUCCESS("Daily supply aggregation complete.")
                )
            except Exception as exc:  # keep the ingester alive on aggregation errors
                self.stdout.write(self.style.ERROR(f"Aggregation failed: {exc!r}"))
