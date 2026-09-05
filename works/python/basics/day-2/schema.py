import json
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class TypeEnum(Enum):
    click = "click"
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
    id: int = Field(description="unique id of the event")
    type: TypeEnum = Field(
        description="Type of event, defaulted to `click`", default=TypeEnum.click
    )
    user_id: int = Field(description="unique id of the user")
    timestamp: datetime = Field(
        description="current timestamp", default_factory=lambda t: datetime.now(tz=None)
    )
    metadata: dict = Field(description="other relevant metadata")


def handlePrint(incoming_event):
    try:
        events = EventMetadata(**incoming_event)
        print(events.id)
        print(events.model_dump())
        print(json.dumps(events.model_dump_json(), indent=4))
        print("---------------------------------------------------\n\n")
    except Exception as e:
        print(e)



# Sample events

events_metadata_1 = {
    "id": 123,
    "user_id": 42,
    "metadata": {"amount": 1299.50},
}

events_metadata_2 = {
    "id": 124,
    "type": TypeEnum.checkout.value,
    "user_id": 78,
    "timestamp": datetime.now(tz=None),
    "metadata": {"amount": 1299.50},
}

handlePrint(events_metadata_1)
handlePrint(events_metadata_2)


# read more on
# https://pydantic.dev/docs/validation/latest/concepts/models/
# https://pydantic.dev/docs/validation/2.1/usage/computed_fields/
