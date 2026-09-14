from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from schemas.enums import ProductCategory, ProductStatus


class ProductCreate(BaseModel):
    name: str
    sku: str = Field(description="unique identifier e.g. 'SHOE-RED-42'")
    price: float = Field(gt=0, description="price per unit in INR")
    category: ProductCategory
    stock_quantity: int = Field(ge=0, default=0)


class ProductResponse(ProductCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: ProductStatus
