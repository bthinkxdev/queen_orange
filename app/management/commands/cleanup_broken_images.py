"""
Management command to clean up broken image references.

This command finds ProductImage and Category instances where the image file
doesn't exist on disk and optionally removes those database records.

Usage:
    python manage.py cleanup_broken_images
    python manage.py cleanup_broken_images --delete
    python manage.py cleanup_broken_images --delete --dry-run
"""
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from app.models import ProductImage, Category


class Command(BaseCommand):
    help = 'Find and optionally remove ProductImage and Category records with missing image files'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Delete broken image references from database',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--category',
            action='store_true',
            help='Also check Category images',
        )

    def handle(self, *args, **options):
        delete = options['delete']
        dry_run = options['dry_run']
        check_categories = options['category']
        
        self.stdout.write(self.style.SUCCESS('\n=== Broken Image Reference Cleanup ===\n'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made\n'))
        
        # Check ProductImage instances
        broken_product_images = []
        total_product_images = ProductImage.objects.count()
        
        self.stdout.write(f'Checking {total_product_images} product images...')
        
        for product_image in ProductImage.objects.all():
            if product_image.image:
                try:
                    file_path = product_image.image.path
                    if not os.path.exists(file_path) or not os.path.isfile(file_path):
                        broken_product_images.append(product_image)
                except (ValueError, AttributeError, OSError):
                    # File path is invalid or doesn't exist
                    broken_product_images.append(product_image)
        
        # Check Category instances if requested
        broken_categories = []
        if check_categories:
            total_categories = Category.objects.exclude(image__isnull=True).exclude(image='').count()
            self.stdout.write(f'Checking {total_categories} category images...')
            
            for category in Category.objects.exclude(image__isnull=True).exclude(image=''):
                if category.image:
                    try:
                        file_path = category.image.path
                        if not os.path.exists(file_path) or not os.path.isfile(file_path):
                            broken_categories.append(category)
                    except (ValueError, AttributeError, OSError):
                        # File path is invalid or doesn't exist
                        broken_categories.append(category)
        
        # Report findings
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write('='*60)
        
        self.stdout.write(f'\nProduct Images:')
        self.stdout.write(f'  Total: {total_product_images}')
        self.stdout.write(f'  Broken: {len(broken_product_images)}')
        self.stdout.write(f'  Valid: {total_product_images - len(broken_product_images)}')
        
        if broken_product_images:
            self.stdout.write(f'\n  Broken Product Images:')
            for img in broken_product_images:
                product_name = img.product.name if img.product else 'Unknown'
                image_name = img.image.name if img.image else 'No file'
                self.stdout.write(f'    - ID {img.id}: {product_name} -> {image_name}')
        
        if check_categories:
            total_categories_with_images = Category.objects.exclude(image__isnull=True).exclude(image='').count()
            self.stdout.write(f'\nCategory Images:')
            self.stdout.write(f'  Total with images: {total_categories_with_images}')
            self.stdout.write(f'  Broken: {len(broken_categories)}')
            self.stdout.write(f'  Valid: {total_categories_with_images - len(broken_categories)}')
            
            if broken_categories:
                self.stdout.write(f'\n  Broken Category Images:')
                for cat in broken_categories:
                    image_name = cat.image.name if cat.image else 'No file'
                    self.stdout.write(f'    - ID {cat.id}: {cat.name} -> {image_name}')
        
        # Delete if requested
        if broken_product_images or broken_categories:
            if delete and not dry_run:
                self.stdout.write('\n' + '='*60)
                self.stdout.write(self.style.WARNING('DELETING BROKEN REFERENCES'))
                self.stdout.write('='*60)
                
                with transaction.atomic():
                    deleted_count = 0
                    
                    # Delete broken ProductImage records
                    for img in broken_product_images:
                        product_name = img.product.name if img.product else 'Unknown'
                        self.stdout.write(f'  Deleting ProductImage ID {img.id} (Product: {product_name})')
                        img.delete()
                        deleted_count += 1
                    
                    # Delete broken Category image references (set to empty, don't delete category)
                    for cat in broken_categories:
                        self.stdout.write(f'  Clearing image for Category ID {cat.id} ({cat.name})')
                        cat.image = None
                        cat.save(update_fields=['image'])
                        deleted_count += 1
                    
                    self.stdout.write(f'\n{self.style.SUCCESS(f"✓ Deleted {deleted_count} broken image reference(s)")}')
                    
            elif delete and dry_run:
                self.stdout.write('\n' + '='*60)
                self.stdout.write(self.style.WARNING('DRY RUN - Would delete:'))
                self.stdout.write('='*60)
                self.stdout.write(f'  {len(broken_product_images)} ProductImage record(s)')
                if check_categories:
                    self.stdout.write(f'  {len(broken_categories)} Category image reference(s)')
                self.stdout.write('\nRun without --dry-run to actually delete.')
                
            else:
                self.stdout.write('\n' + '='*60)
                self.stdout.write(self.style.WARNING('ACTION REQUIRED'))
                self.stdout.write('='*60)
                self.stdout.write('To delete broken references, run:')
                self.stdout.write('  python manage.py cleanup_broken_images --delete')
                self.stdout.write('\nTo see what would be deleted:')
                self.stdout.write('  python manage.py cleanup_broken_images --delete --dry-run')
        else:
            self.stdout.write(f'\n{self.style.SUCCESS("✓ No broken image references found!")}')
        
        self.stdout.write('\n' + '='*60 + '\n')


