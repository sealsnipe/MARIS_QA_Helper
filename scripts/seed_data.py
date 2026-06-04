"""Shared customer/user definitions for seed scripts."""

GLOBAL_CUSTOMER: tuple[str, str] = ("global", "Global")

PRODUCTION_CUSTOMERS: tuple[tuple[str, str], ...] = (
    ("bg-ludwigshafen", "BG Ludwigshafen"),
    ("bg-frankfurt", "BG Frankfurt"),
    ("detmold-lippe", "Detmold Lippe"),
    ("kkrr", "Katholische Kliniken Rhein Ruhr"),
)

ALL_CUSTOMERS = (GLOBAL_CUSTOMER,) + PRODUCTION_CUSTOMERS

ADMIN_EMAILS: frozenset[str] = frozenset(
    {
        "admin@example.com",
        "matthias.schindler@maris-healthcare.de",
    }
)

INTEGRATION_USER_EMAIL = "integration@internal"

DEFAULT_PASSWORD = "GeheimesPW!"

DEFAULT_USERS: tuple[dict, ...] = (
    {
        "email": "admin@example.com",
        "password": DEFAULT_PASSWORD,
        "customers": tuple(slug for slug, _ in PRODUCTION_CUSTOMERS),
        "is_admin": True,
    },
    {
        "email": INTEGRATION_USER_EMAIL,
        "password": DEFAULT_PASSWORD,
        "customers": tuple(slug for slug, _ in PRODUCTION_CUSTOMERS),
        "is_admin": False,
    },
)
