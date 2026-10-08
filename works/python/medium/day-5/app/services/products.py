from uuid import UUID
from sqlalchemy.orm import Session
from app.crud.products_repository import ProductRepository
from app.schemas.products import ProductCreate, ProductResponse, ProductUpdate
from app.schemas.enums import ProductStatus
from app.core.logger import get_logger

logger = get_logger(__name__)


class ProductService:
    def __init__(self, db: Session):
        self.repo = ProductRepository(db)

    def create_product(self, data: ProductCreate) -> ProductResponse:
        # check for duplicate SKU before hitting the DB constraint
        # gives a cleaner error message than catching IntegrityError
        existing = self.repo.get_by_sku(data.sku)
        if existing:
            raise ValueError(f"A product with SKU '{data.sku}' already exists")

        return self.repo.create_product(data)

    def get_product(self, product_id: UUID) -> ProductResponse:
        product = self.repo.get_by_id(product_id)
        if product is None:
            raise ValueError(f"Product {product_id} not found")
        return product

    def get_by_sku(self, sku: str) -> ProductResponse:
        product = self.repo.get_by_sku(sku)
        if product is None:
            raise ValueError(f"Product with SKU '{sku}' not found")
        return product

    def list_products(
        self,
        status: ProductStatus | None = None,
        category: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ProductResponse]:
        # pass status as string — the ORM column is String(20), not an enum column
        status_val = status.value if status is not None else None
        return self.repo.get_all(
            status=status_val, category=category, skip=skip, limit=limit
        )

    def update_product(self, product_id: UUID, data: ProductUpdate) -> ProductResponse:
        # verify it exists first — gives a 404-style error, not a silent no-op
        existing = self.repo.get_by_id(product_id)
        if existing is None:
            raise ValueError(f"Product {product_id} not found")

        # if SKU is being changed, check it doesn't collide with another product
        update_dict = data.model_dump(exclude_unset=True)
        if "sku" in update_dict:
            collision = self.repo.get_by_sku(update_dict["sku"])
            if collision and collision.id != product_id:
                raise ValueError(
                    f"SKU '{update_dict['sku']}' is already taken by another product"
                )

        updated = self.repo.update_product(product_id, update_dict)
        if updated is None:
            raise ValueError(f"Product {product_id} not found")
        return updated

    def discontinue_product(self, product_id: UUID) -> ProductResponse:
        # dedicated method for status transitions — don't let callers set arbitrary statuses
        existing = self.repo.get_by_id(product_id)
        if existing is None:
            raise ValueError(f"Product {product_id} not found")

        if existing.status == ProductStatus.discontinued:
            raise ValueError(f"Product {product_id} is already discontinued")

        updated = self.repo.update_product(
            product_id, {"status": ProductStatus.discontinued.value}
        )
        logger.info(f"Product {product_id} ({existing.sku}) marked as discontinued")
        return updated

    def restock(self, product_id: UUID, quantity: int) -> ProductResponse:
        if quantity <= 0:
            raise ValueError("Restock quantity must be greater than 0")

        existing = self.repo.get_by_id(product_id)
        if existing is None:
            raise ValueError(f"Product {product_id} not found")

        if existing.status == ProductStatus.discontinued:
            raise ValueError("Cannot restock a discontinued product")

        new_quantity = existing.stock_quantity + quantity
        # if the product was out_of_stock, restocking makes it available again
        new_status = (
            ProductStatus.available.value
            if existing.status == ProductStatus.out_of_stock
            else existing.status.value
        )

        updated = self.repo.update_product(
            product_id,
            {"stock_quantity": new_quantity, "status": new_status},
        )
        logger.info(
            f"Restocked product {product_id} ({existing.sku}) by {quantity} units → {new_quantity} total"
        )
        return updated

    def delete_product(self, product_id: UUID) -> None:
        existing = self.repo.get_by_id(product_id)
        if existing is None:
            raise ValueError(f"Product {product_id} not found")

        # CRUD raises ValueError if product exists in order_line_items (RESTRICT FK)
        deleted = self.repo.delete_product(product_id)
        if not deleted:
            raise ValueError(f"Product {product_id} not found")
        logger.info(f"Deleted product {product_id} ({existing.sku})")
