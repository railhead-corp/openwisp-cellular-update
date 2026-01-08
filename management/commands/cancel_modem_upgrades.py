"""
Management command to cancel in-progress modem upgrade operations
"""
from django.core.management.base import BaseCommand
from django.db import models
from django.utils import timezone

from openwisp_modem_upgrader.swapper import load_model


class Command(BaseCommand):
    help = 'Cancel all in-progress modem upgrade operations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--status',
            type=str,
            default='in-progress',
            help='Status of operations to cancel (default: in-progress)',
        )
        parser.add_argument(
            '--set-to',
            type=str,
            default='aborted',
            choices=['aborted', 'failed'],
            help='Status to set cancelled operations to (default: aborted)',
        )
        parser.add_argument(
            '--device',
            type=str,
            help='MAC address of specific device to cancel upgrades for',
        )
        parser.add_argument(
            '--batch',
            type=int,
            help='Batch ID to cancel upgrades for',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be cancelled without actually cancelling',
        )

    def handle(self, *args, **options):
        ModemUpgradeOperation = load_model('ModemUpgradeOperation')
        ModemBatchUpgradeOperation = load_model('ModemBatchUpgradeOperation')
        
        # Build query
        qs = ModemUpgradeOperation.objects.filter(status=options['status'])
        
        if options['device']:
            qs = qs.filter(device__mac_address=options['device'])
        
        if options['batch']:
            qs = qs.filter(batch_id=options['batch'])
        
        count = qs.count()
        
        if count == 0:
            self.stdout.write(self.style.WARNING('No matching operations found'))
            return
        
        # Show what will be cancelled
        self.stdout.write(
            self.style.WARNING(f'\nFound {count} operation(s) with status "{options["status"]}":')
        )
        
        for op in qs.select_related('device', 'image', 'batch'):
            device_info = f"{op.device.name} ({op.device.mac_address})"
            image_info = f"{op.image.build}" if op.image else "N/A"
            batch_info = f" [Batch: {op.batch_id}]" if op.batch else ""
            self.stdout.write(f"  - {device_info} -> {image_info}{batch_info}")
        
        if options['dry_run']:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nDry run: Would set {count} operation(s) to status "{options["set_to"]}"'
                )
            )
            return
        
        # Cancel operations
        log_prefix = timezone.now().strftime('%Y-%m-%d %H:%M:%S') + ' - Operation cancelled via management command\n'
        
        for op in qs:
            op.status = options['set_to']
            op.log = log_prefix + (op.log or '')
            op.save()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSuccessfully cancelled {count} operation(s) - status set to "{options["set_to"]}"'
            )
        )
        
        # Update related batch operations
        batch_ids = qs.filter(batch__isnull=False).values_list('batch_id', flat=True).distinct()
        if batch_ids:
            for batch_id in batch_ids:
                batch = ModemBatchUpgradeOperation.objects.get(pk=batch_id)
                batch.update()
            self.stdout.write(
                self.style.SUCCESS(f'Updated {len(batch_ids)} related batch operation(s)')
            )
