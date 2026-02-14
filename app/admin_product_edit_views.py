"""Modular Product EDIT and CREATE API views. No formset, no multipart on basic save/create."""
import json
import logging

from django import forms
from django.db.models import Q, ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, View

from .models import ColorVariant, ColorVariantImage, JewelleryDetail, JewelleryImage, Product, SizeVariant
from .admin_forms import ProductBasicEditForm, JewelleryDetailForm, _validate_image_file, STANDARD_SIZES

logger = logging.getLogger(__name__)


class ProductCreateBasicView(View):
    """POST /admin/products/create-basic/ — JSON body, create product only. No variants, no images."""
    def post(self, request):
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON"]}}, status=400)
        # Normalise empty strings for optional fields so the form accepts them
        if data.get("slug") == "":
            data["slug"] = None
        if data.get("description") == "":
            data["description"] = ""
        if data.get("original_price") == "":
            data["original_price"] = None
        if data.get("material") == "":
            data["material"] = ""
        if data.get("category") == "":
            data["category"] = None
        form = ProductBasicEditForm(data, instance=None)
        if not form.is_valid():
            errors = {k: list(v) for k, v in form.errors.items()}
            return JsonResponse({"success": False, "errors": errors}, status=400)
        product = form.save()
        return JsonResponse({"success": True, "product_id": product.pk})


def _staff_required(view_func):
    """Require staff; use with View that uses StaffRequiredMixin from admin_views."""
    return view_func


class ProductEditView(DetailView):
    """GET only. Renders modular edit dashboard. Use StaffRequiredMixin in URL config or as mixin."""
    model = Product
    template_name = "admin/product_edit.html"
    context_object_name = "product"

    def get_queryset(self):
        return Product.objects.select_related("jewellery_detail").prefetch_related(
            "color_variants__size_variants",
            "color_variants__images",
            "jewellery_detail__images",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_menu"] = "products"
        context["form_title"] = "Edit Product"
        context["basic_form"] = ProductBasicEditForm(instance=self.object)
        context["standard_sizes"] = STANDARD_SIZES
        return context


class ProductUpdateBasicView(View):
    """POST /admin/products/<id>/update-basic/ — JSON body, no multipart."""
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON"]}}, status=400)
        # Never change product_type from edit page: use existing value if not in payload
        if "product_type" not in data and product.pk:
            data = {**data, "product_type": product.product_type}
        form = ProductBasicEditForm(data, instance=product)
        if not form.is_valid():
            return JsonResponse({"success": False, "errors": form.errors}, status=400)
        form.save(commit=False)
        update_fields = [f for f in form.changed_data if f in form.Meta.fields]
        if "name" in update_fields and "slug" not in update_fields:
            update_fields.append("slug")
        if update_fields:
            form.instance.save(update_fields=update_fields)
        return JsonResponse({"success": True})


class ProductToggleActiveView(View):
    """POST /admin/products/<id>/toggle-active/ — JSON body optional: { is_active: true|false }. Toggle or set product active status."""
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            data = {}
        if "is_active" in data:
            new_active = bool(data["is_active"])
        else:
            new_active = not product.is_active
        product.is_active = new_active
        product.save(update_fields=["is_active"])
        return JsonResponse({"success": True, "is_active": new_active})


class ProductVariantsListApiView(View):
    """GET /admin/products/<id>/variants/ — JSON list of color variants with sizes and images."""
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        variants = list(
            product.color_variants.prefetch_related("size_variants", "images").order_by("display_order", "name")
        )
        out = []
        for cv in variants:
            images = [{"id": img.id, "url": img.image.url if img.image else None, "is_primary": img.is_primary} for img in cv.images.all()]
            sizes = [{"id": sv.id, "size": sv.size, "stock_quantity": sv.stock_quantity, "sku": sv.sku or "", "is_active": sv.is_active} for sv in cv.size_variants.all()]
            out.append({
                "id": cv.id,
                "name": cv.name,
                "color_code": cv.color_code or "",
                "display_order": cv.display_order,
                "is_active": cv.is_active,
                "images": images,
                "sizes": sizes,
            })
        return JsonResponse({"variants": out})


class ProductVariantAddApiView(View):
    """POST /admin/products/<id>/variants/add/ — add color variant."""
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON"]}}, status=400)
        name = (data.get("name") or "").strip()
        if not name:
            return JsonResponse({"success": False, "errors": {"name": ["Name is required."]}}, status=400)
        if product.color_variants.filter(name__iexact=name).exists():
            return JsonResponse({"success": False, "errors": {"name": ["This color name already exists for this product."]}}, status=400)
        display_order = data.get("display_order")
        if display_order is None:
            display_order = product.color_variants.count()
        cv = ColorVariant.objects.create(
            product=product,
            name=name,
            color_code=(data.get("color_code") or "").strip() or "",
            display_order=display_order if isinstance(display_order, int) else 0,
            is_active=data.get("is_active", True),
        )
        return JsonResponse({
            "success": True,
            "variant": {
                "id": cv.id, "name": cv.name, "color_code": cv.color_code or "",
                "display_order": cv.display_order, "is_active": cv.is_active,
                "images": [], "sizes": [],
            },
        })


class VariantUpdateApiView(View):
    """POST /admin/variants/<variant_id>/update/ — update color variant."""
    def post(self, request, variant_id):
        cv = get_object_or_404(ColorVariant, pk=variant_id)
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON"]}}, status=400)
        name = (data.get("name") or "").strip()
        if not name:
            return JsonResponse({"success": False, "errors": {"name": ["Name is required."]}}, status=400)
        if cv.product.color_variants.filter(name__iexact=name).exclude(pk=cv.pk).exists():
            return JsonResponse({"success": False, "errors": {"name": ["This color name already exists for this product."]}}, status=400)
        update_kw = {}
        if "name" in data:
            update_kw["name"] = name
        if "color_code" in data:
            update_kw["color_code"] = (data.get("color_code") or "").strip() or ""
        if "display_order" in data:
            try:
                update_kw["display_order"] = int(data["display_order"])
            except (TypeError, ValueError):
                pass
        if "is_active" in data:
            update_kw["is_active"] = bool(data["is_active"])
        if update_kw:
            ColorVariant.objects.filter(pk=cv.pk).update(**update_kw)
        return JsonResponse({"success": True})


class VariantDeleteApiView(View):
    """POST /admin/variants/<variant_id>/delete/ — deactivate or delete color variant."""
    def post(self, request, variant_id):
        cv = get_object_or_404(ColorVariant, pk=variant_id)
        has_links = SizeVariant.objects.filter(color_variant=cv).filter(
            Q(order_items__isnull=False) | Q(cart_items__isnull=False)
        ).exists()
        if has_links:
            ColorVariant.objects.filter(pk=cv.pk).update(is_active=False)
            SizeVariant.objects.filter(color_variant=cv).update(is_active=False)
            return JsonResponse({"success": True, "deactivated": True})
        try:
            cv.delete()
            return JsonResponse({"success": True, "deleted": True})
        except ProtectedError:
            ColorVariant.objects.filter(pk=cv.pk).update(is_active=False)
            SizeVariant.objects.filter(color_variant=cv).update(is_active=False)
            return JsonResponse({"success": True, "deactivated": True})


class VariantAddSizeApiView(View):
    """POST /admin/variants/<variant_id>/sizes/add/ — add size variant. Size must not already exist for this color."""
    def post(self, request, variant_id):
        cv = get_object_or_404(ColorVariant, pk=variant_id)
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON"]}}, status=400)
        size = (data.get("size") or "").strip()
        if not size:
            return JsonResponse({"success": False, "errors": {"size": ["Size is required."]}}, status=400)
        if size not in STANDARD_SIZES:
            return JsonResponse({"success": False, "errors": {"size": ["Invalid size."]}}, status=400)
        if cv.size_variants.filter(size=size).exists():
            return JsonResponse({"success": False, "errors": {"size": ["This size already exists for this color."]}}, status=400)
        stock = 0
        if "stock_quantity" in data:
            try:
                stock = max(0, int(data["stock_quantity"]))
            except (TypeError, ValueError):
                pass
        sku = (data.get("sku") or "").strip() or None
        is_active = data.get("is_active", True)
        sv = SizeVariant.objects.create(
            color_variant=cv,
            size=size,
            stock_quantity=stock,
            sku=sku,
            is_active=bool(is_active),
        )
        return JsonResponse({
            "success": True,
            "size": {"id": sv.id, "size": sv.size, "stock_quantity": sv.stock_quantity, "sku": sv.sku or "", "is_active": sv.is_active},
        })


class SizeVariantUpdateStockView(View):
    """POST /admin/size/<id>/update-stock/ — { stock_quantity, sku?, is_active? }."""
    def post(self, request, pk):
        sv = get_object_or_404(SizeVariant, pk=pk)
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON"]}}, status=400)
        update_kw = {}
        if "stock_quantity" in data:
            try:
                qty = int(data["stock_quantity"])
                if qty < 0:
                    return JsonResponse({"success": False, "errors": {"stock_quantity": ["Cannot be negative."]}}, status=400)
                update_kw["stock_quantity"] = qty
            except (TypeError, ValueError):
                return JsonResponse({"success": False, "errors": {"stock_quantity": ["Invalid number."]}}, status=400)
        if "sku" in data:
            update_kw["sku"] = (data.get("sku") or "").strip() or None
        if "is_active" in data:
            update_kw["is_active"] = bool(data["is_active"])
        if update_kw:
            SizeVariant.objects.filter(pk=sv.pk).update(**update_kw)
        return JsonResponse({"success": True})


class VariantUploadImageView(View):
    """POST /admin/variants/<variant_id>/upload-image/ — multipart, single image."""
    def post(self, request, variant_id):
        cv = get_object_or_404(ColorVariant, pk=variant_id)
        if cv.images.count() >= 3:
            return JsonResponse({"success": False, "errors": {"image": ["Max 3 images per color."]}}, status=400)
        image_file = request.FILES.get("image")
        if not image_file:
            return JsonResponse({"success": False, "errors": {"image": ["No file provided."]}}, status=400)
        try:
            _validate_image_file(image_file, required=True)
        except forms.ValidationError as e:
            return JsonResponse({"success": False, "errors": {"image": [str(m) for m in e.messages]}}, status=400)
        img = ColorVariantImage.objects.create(
            color_variant=cv,
            image=image_file,
            is_primary=(cv.images.count() == 0),
        )
        return JsonResponse({
            "success": True,
            "image": {"id": img.id, "url": img.image.url if img.image else None, "is_primary": img.is_primary},
        })


class ProductImageDeleteView(View):
    """POST /admin/images/<image_id>/delete/ — delete ColorVariantImage."""
    def post(self, request, image_id):
        img = get_object_or_404(ColorVariantImage, pk=image_id)
        image_name = img.image.name if img.image else None
        storage = img.image.storage if img.image else None
        img.delete()
        if image_name and storage:
            try:
                storage.delete(image_name)
            except Exception:
                pass
        return JsonResponse({"success": True})


class ProductImageReplaceView(View):
    """POST /admin/images/<image_id>/replace/ — replace image file (multipart)."""
    def post(self, request, image_id):
        img = get_object_or_404(ColorVariantImage, pk=image_id)
        image_file = request.FILES.get("image")
        if not image_file:
            return JsonResponse({"success": False, "errors": {"image": ["No file provided."]}}, status=400)
        try:
            _validate_image_file(image_file, required=True)
        except forms.ValidationError as e:
            return JsonResponse({"success": False, "errors": {"image": [str(m) for m in e.messages]}}, status=400)
        old_name = img.image.name if img.image else None
        old_storage = img.image.storage if img.image else None
        img.image = image_file
        img.save(update_fields=["image"])
        if old_name and old_storage:
            try:
                old_storage.delete(old_name)
            except Exception:
                pass
        return JsonResponse({
            "success": True,
            "image": {"id": img.id, "url": img.image.url if img.image else None, "is_primary": img.is_primary},
        })


# --- Jewellery detail (product_type=jewellery) ---

class ProductJewelleryDetailApiView(View):
    """GET/POST /admin/products/<pk>/jewellery-detail/ — get or update JewelleryDetail. Product must be jewellery."""
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        if product.product_type != "jewellery":
            return JsonResponse({"success": False, "error": "Product is not jewellery."}, status=400)
        jd = getattr(product, "jewellery_detail", None)
        if not jd:
            return JsonResponse({
                "success": True,
                "detail": None,
                "images": [],
            })
        images = [
            {"id": img.id, "url": img.image.url if img.image else None, "is_primary": img.is_primary, "display_order": img.display_order}
            for img in jd.images.all().order_by("display_order", "id")
        ]
        return JsonResponse({
            "success": True,
            "detail": {
                "id": jd.id,
                "metal_type": jd.metal_type or "",
                "purity": jd.purity or "",
                "weight": str(jd.weight) if jd.weight is not None else "",
                "gemstone": jd.gemstone or "",
                "making_charge": str(jd.making_charge) if jd.making_charge is not None else "",
                "is_adjustable": jd.is_adjustable,
                "stock_quantity": jd.stock_quantity,
            },
            "images": images,
        })

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        if product.product_type != "jewellery":
            return JsonResponse({"success": False, "errors": {"__all__": ["Product is not jewellery."]}}, status=400)
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return JsonResponse({"success": False, "errors": {"__all__": ["Invalid JSON"]}}, status=400)
        jd = getattr(product, "jewellery_detail", None)
        if not jd:
            jd = JewelleryDetail(product=product, metal_type=data.get("metal_type") or "Gold", stock_quantity=1)
            jd.save()
        form = JewelleryDetailForm(data, instance=jd)
        if not form.is_valid():
            return JsonResponse({"success": False, "errors": form.errors}, status=400)
        form.save()
        return JsonResponse({"success": True})


class JewelleryUploadImageView(View):
    """POST /admin/products/<pk>/jewellery-upload-image/ — add image to product's jewellery detail. Creates detail if missing."""
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        if product.product_type != "jewellery":
            return JsonResponse({"success": False, "errors": {"image": ["Product is not jewellery."]}}, status=400)
        jd = getattr(product, "jewellery_detail", None)
        if not jd:
            jd = JewelleryDetail.objects.create(product=product, metal_type="Gold", stock_quantity=1)
        if jd.images.count() >= 3:
            return JsonResponse({"success": False, "errors": {"image": ["Max 3 images."]}}, status=400)
        image_file = request.FILES.get("image")
        if not image_file:
            return JsonResponse({"success": False, "errors": {"image": ["No file provided."]}}, status=400)
        try:
            _validate_image_file(image_file, required=True)
        except forms.ValidationError as e:
            return JsonResponse({"success": False, "errors": {"image": [str(m) for m in e.messages]}}, status=400)
        img = JewelleryImage.objects.create(
            jewellery_detail=jd,
            image=image_file,
            is_primary=(jd.images.count() == 0),
            display_order=jd.images.count(),
        )
        return JsonResponse({
            "success": True,
            "image": {"id": img.id, "url": img.image.url if img.image else None, "is_primary": img.is_primary},
        })


class JewelleryImageDeleteView(View):
    """POST /admin/jewellery-images/<image_id>/delete/."""
    def post(self, request, image_id):
        img = get_object_or_404(JewelleryImage, pk=image_id)
        image_name = img.image.name if img.image else None
        storage = img.image.storage if img.image else None
        img.delete()
        if image_name and storage:
            try:
                storage.delete(image_name)
            except Exception:
                pass
        return JsonResponse({"success": True})


class JewelleryImageReplaceView(View):
    """POST /admin/jewellery-images/<image_id>/replace/ — replace image file (multipart)."""
    def post(self, request, image_id):
        img = get_object_or_404(JewelleryImage, pk=image_id)
        image_file = request.FILES.get("image")
        if not image_file:
            return JsonResponse({"success": False, "errors": {"image": ["No file provided."]}}, status=400)
        try:
            _validate_image_file(image_file, required=True)
        except forms.ValidationError as e:
            return JsonResponse({"success": False, "errors": {"image": [str(m) for m in e.messages]}}, status=400)
        old_name = img.image.name if img.image else None
        old_storage = img.image.storage if img.image else None
        img.image = image_file
        img.save(update_fields=["image"])
        if old_name and old_storage:
            try:
                old_storage.delete(old_name)
            except Exception:
                pass
        return JsonResponse({
            "success": True,
            "image": {"id": img.id, "url": img.image.url if img.image else None, "is_primary": img.is_primary},
        })
