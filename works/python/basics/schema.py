# events-metadata:
# {
#   "id": "evt_123",
#   "type": "purchase",
#   "user_id": "user_42", ̰
#   "timestamp": "...",
#   "metadata": {
#       "amount": 1299.50,
# }
# }

from datetime import datetime
from enum import Enum
from pydantic import BaseModel

class TypeEnum(Enum):
    add_to_cart = "add_to_cart"
    proceed_to_order = "proceed_to_order"
    checkout = "checkout"
    payment_initiated = "payment_initiated"
    payment_processing = "payment_processing"
    payment_completed = "payment_completed"
    order_successful = "order_successful"
    delivered = "delivered"
    return_item = "return_item"

class EventMetadata(BaseModel):
    id: int
    type: TypeEnum
    user_id: int
    timestamp: datetime | None
    metadata: dict


events_metadata = {
    "id": 123,
    "type": TypeEnum.checkout.value,
    "user_id": 42,
    "timestamp": datetime.now(tz=None),
    "metadata": {"amount": 1299.50},
}

try:
    events = EventMetadata(**events_metadata)
    print(events.id)
    print(events.model_dump())
except Exception as e:
    print(e)


# read more on
# https://pydantic.dev/docs/validation/latest/concepts/models/
# https://pydantic.dev/docs/validation/2.1/usage/computed_fields/
