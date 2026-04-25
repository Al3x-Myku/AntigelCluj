"""Models package — import all models so SQLAlchemy sees them."""

from backend.models.user import User                        # noqa: F401
from backend.models.device import Device                    # noqa: F401
from backend.models.service_ticket import ServiceTicket     # noqa: F401
from backend.models.api_key import APIKey                   # noqa: F401
