"""
Audit ColorVariant / ColorVariantImage / SizeVariant data integrity.

Run: python manage.py audit_variant_integrity

Checks:
- ColorVariantImage: all must have valid color_variant_id (FK).
- SizeVariant: no duplicate (color_variant_id, size); no negative stock.
- Orphan records (e.g. images whose color_variant was deleted without CASCADE).
"""
from django.core.management.base import BaseCommand
from django.db.models import Count

from app.models import ColorVariant, ColorVariantImage, SizeVariant


class Command(BaseCommand):
    help = "Audit variant and image integrity: orphans, duplicate sizes, negative stock."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Do not fix anything; reserved for future use.",
        )

    def handle(self, *args, **options):
        errors = []
        # 1) Images without valid color_variant (should not exist with FK not null)
        invalid_fk = ColorVariantImage.objects.filter(color_variant_id__isnull=True)
        if invalid_fk.exists():
            errors.append(f"ColorVariantImage with null color_variant_id: {invalid_fk.count()}")

        # 2) Images whose color_variant no longer exists (should not happen with CASCADE)
        cv_ids = set(ColorVariant.objects.values_list("pk", flat=True))
        orphan_images = ColorVariantImage.objects.exclude(color_variant_id__in=cv_ids)
        if orphan_images.exists():
            errors.append(f"ColorVariantImage with missing color_variant: {orphan_images.count()}")

        # 3) Duplicate (color_variant, size) in SizeVariant
        dup_sizes = (
            SizeVariant.objects.values("color_variant_id", "size")
            .annotate(cnt=Count("id"))
            .filter(cnt__gt=1)
        )
        if dup_sizes:
            errors.append(f"Duplicate (color_variant, size) in SizeVariant: {list(dup_sizes)}")

        # 4) Negative stock (DB constraint should prevent; audit anyway)
        neg_stock = SizeVariant.objects.filter(stock_quantity__lt=0)
        if neg_stock.exists():
            errors.append(f"SizeVariant with negative stock: {neg_stock.count()}")

        if errors:
            self.stderr.write(self.style.ERROR("Integrity issues found:"))
            for e in errors:
                self.stderr.write(self.style.ERROR(f"  - {e}"))
            return
        self.stdout.write(self.style.SUCCESS("Audit passed: no orphan images, no duplicate sizes, no negative stock."))
