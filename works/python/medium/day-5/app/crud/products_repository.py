from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.products import Product
from app.schemas.products import ProductCreate, ProductResponse
from app.core.logger import get_logger

logger = get_logger(__name__)


class ProductRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_product(self, product: ProductCreate) -> ProductResponse:
        product_orm = Product(**product.model_dump())
        self.db.add(product_orm)

        try:
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            logger.exception("Failed to create product due to integrity error")
            raise ValueError("Product creation failed due to integrity error") from e

        self.db.refresh(product_orm)  # was missing the argument
        logger.info(f"Created product {product_orm.id}")
        return ProductResponse.model_validate(product_orm)

    def get_by_id(self, product_id) -> ProductResponse | None:
        product_orm = self.db.query(Product).filter(Product.id == product_id).first()

        if product_orm is None:
            return None

        return ProductResponse.model_validate(product_orm)

    def get_by_sku(self, sku: str) -> ProductResponse | None:
        product_orm = self.db.query(Product).filter(Product.sku == sku).first()

        if product_orm is None:
            return None

        return ProductResponse.model_validate(product_orm)

    def get_all(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ProductResponse]:
        query = self.db.query(Product)

        if status is not None:
            query = query.filter(Product.status == status)

        if category is not None:
            query = query.filter(Product.category == category)

        products = query.offset(skip).limit(limit).all()
        return [ProductResponse.model_validate(p) for p in products]

    def update_product(self, product_id, update_data: dict) -> ProductResponse | None:
        product_orm = self.db.query(Product).filter(Product.id == product_id).first()

        if product_orm is None:
            return None

        for field, value in update_data.items():
            setattr(product_orm, field, value)

        try:
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            logger.exception("Failed to update product due to integrity error")
            raise ValueError("Product update failed due to integrity error") from e

        self.db.refresh(product_orm)
        return ProductResponse.model_validate(product_orm)

    def delete_product(self, product_id) -> bool:
        product_orm = self.db.query(Product).filter(Product.id == product_id).first()

        if product_orm is None:
            return False

        try:
            self.db.delete(product_orm)
            self.db.commit()
            return True
        except IntegrityError as e:
            self.db.rollback()
            # product is referenced by order_line_items with ondelete=RESTRICT
            raise ValueError(
                "Cannot delete product that exists in order line items"
            ) from e
