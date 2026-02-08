import os
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from .models import Category


@receiver(post_delete, sender=Category)
def delete_category_image_file(sender, instance, **kwargs):
    """
    Delete image file from disk when Category instance is deleted
    """
    if instance.image:
        if os.path.isfile(instance.image.path):
            try:
                if hasattr(instance.image, 'close'):
                    instance.image.close()
            except Exception:
                pass
            os.remove(instance.image.path)


@receiver(pre_save, sender=Category)
def delete_old_category_image_on_update(sender, instance, **kwargs):
    """
    Delete old image file when Category is updated with a new image
    """
    if not instance.pk:
        return False

    try:
        old_image = Category.objects.get(pk=instance.pk).image
    except Category.DoesNotExist:
        return False

    # If image has changed, delete the old one
    if old_image and old_image != instance.image:
        if os.path.isfile(old_image.path):
            try:
                if hasattr(old_image, 'close'):
                    old_image.close()
            except Exception:
                pass
            os.remove(old_image.path)


