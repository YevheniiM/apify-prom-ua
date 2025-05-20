"""
Pydantic models for product data.

This module defines the data models for products extracted from Prom.ua.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict


class Product(BaseModel):
    """
    Product model representing a product from Prom.ua.

    Attributes:
        url: The URL of the product page
        title: The title/name of the product
        regular_price_uah: The regular price in Ukrainian hryvnia (UAH)
        discounted_price_uah: The discounted price in Ukrainian hryvnia (UAH), if available
        price_uah: The current price in Ukrainian hryvnia (UAH) - kept for backward compatibility
        currency: The currency code (usually UAH)
        image_url: The URL of the main product image
    """

    url: str = Field(..., description="Product page URL")
    title: Optional[str] = Field(None, description="Product title/name")
    regular_price_uah: Optional[float] = Field(None, description="Regular price in UAH")
    discounted_price_uah: Optional[float] = Field(None, description="Discounted price in UAH, if available")
    price_uah: Optional[float] = Field(None, description="Current price in UAH (for backward compatibility)")
    currency: Optional[str] = Field(None, description="Currency code (usually UAH)")
    image_url: Optional[str] = Field(None, description="URL of the main product image")

    # Model configuration
    model_config = ConfigDict(
        extra="ignore",  # Ignore extra fields when parsing
        json_encoders={
            # Custom encoders if needed
        }
    )

    @field_validator("price_uah", "regular_price_uah", "discounted_price_uah")
    def validate_price(cls, v: Optional[float]) -> Optional[float]:
        """Validate that price is a positive number if present."""
        if v is not None and v < 0:
            raise ValueError("Price must be a positive number")
        return v

    @field_validator("currency")
    def validate_currency(cls, v: Optional[str]) -> Optional[str]:
        """Normalize currency code to uppercase if present."""
        if v is not None:
            return v.upper()
        return v

    def to_dict(self) -> Dict[str, Any]:
        """Convert the model to a dictionary for dataset storage."""
        return self.model_dump(exclude_none=True)
