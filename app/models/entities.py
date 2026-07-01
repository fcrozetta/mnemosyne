from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.models.access import Purpose, Sensitivity
from app.models.observations import EntityType, ResolutionStatus, normalize_label


@dataclass(frozen=True, slots=True)
class AnimalProfileInput:
    animal_kind: str | None = None
    species: str | None = None
    breed: str | None = None
    sex: str | None = None
    color: str | None = None
    date_of_birth: str | None = None
    microchip_id: str | None = None
    identifiers: tuple[str, ...] = ()
    reference_notes: str | None = None


@dataclass(frozen=True, slots=True)
class AnimalProfile:
    animal_kind: str | None = None
    species: str | None = None
    breed: str | None = None
    sex: str | None = None
    color: str | None = None
    date_of_birth: str | None = None
    microchip_id: str | None = None
    identifiers: tuple[str, ...] = ()
    reference_notes: str | None = None


class ContactMethodKind(StrEnum):
    PHONE = "phone"
    EMAIL = "email"
    URL = "url"
    HANDLE = "handle"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class ContactMethodInput:
    kind: ContactMethodKind
    value: str
    label: str | None = None
    sensitivity: Sensitivity = Sensitivity.PERSONAL


@dataclass(frozen=True, slots=True)
class ContactMethod:
    kind: ContactMethodKind
    value: str
    label: str | None = None
    sensitivity: Sensitivity = Sensitivity.PERSONAL


@dataclass(frozen=True, slots=True)
class PersonProfileInput:
    display_name: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    contact_methods: tuple[ContactMethodInput, ...] = ()


@dataclass(frozen=True, slots=True)
class PersonProfile:
    display_name: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    contact_methods: tuple[ContactMethod, ...] = ()


@dataclass(frozen=True, slots=True)
class LocationProfileInput:
    location_kind: str | None = None
    street_address: str | None = None
    postal_code: str | None = None
    locality: str | None = None
    region: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None


@dataclass(frozen=True, slots=True)
class LocationProfile:
    location_kind: str | None = None
    street_address: str | None = None
    postal_code: str | None = None
    locality: str | None = None
    region: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None


@dataclass(frozen=True, slots=True)
class StoreProfileInput:
    store_kind: str | None = None
    website: str | None = None
    categories: tuple[str, ...] = ()
    country_scope: str | None = None
    physical_store_status: str | None = None
    source_urls: tuple[str, ...] = ()
    reference_notes: str | None = None


@dataclass(frozen=True, slots=True)
class StoreProfile:
    store_kind: str | None = None
    website: str | None = None
    categories: tuple[str, ...] = ()
    country_scope: str | None = None
    physical_store_status: str | None = None
    source_urls: tuple[str, ...] = ()
    reference_notes: str | None = None


@dataclass(frozen=True, slots=True)
class ItemProfileInput:
    item_kind: str | None = None
    category: str | None = None
    subcategory: str | None = None
    brand: str | None = None
    model: str | None = None
    variant: str | None = None
    color: str | None = None
    size: str | None = None
    serial_number: str | None = None
    identifiers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ItemProfile:
    item_kind: str | None = None
    category: str | None = None
    subcategory: str | None = None
    brand: str | None = None
    model: str | None = None
    variant: str | None = None
    color: str | None = None
    size: str | None = None
    serial_number: str | None = None
    identifiers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CreateEntityInput:
    type: EntityType
    label: str
    scope: str = "personal"
    sensitivity: Sensitivity = Sensitivity.PERSONAL
    allowed_purposes: tuple[Purpose, ...] = ()
    person: PersonProfileInput | None = None
    location: LocationProfileInput | None = None
    store: StoreProfileInput | None = None
    item: ItemProfileInput | None = None
    animal: AnimalProfileInput | None = None

    @property
    def normalized_label(self) -> str:
        return normalize_label(self.label)


@dataclass(frozen=True, slots=True)
class EntityRecord:
    id: str
    type: EntityType
    label: str
    normalized_label: str
    resolution_status: ResolutionStatus
    scope: str
    sensitivity: Sensitivity
    allowed_purposes: tuple[Purpose, ...]
    created_at: datetime
    updated_at: datetime
    person: PersonProfile | None = None
    location: LocationProfile | None = None
    store: StoreProfile | None = None
    item: ItemProfile | None = None
    animal: AnimalProfile | None = None


class EntityNotFoundError(LookupError):
    def __init__(self, id: str) -> None:
        super().__init__(f"Entity {id!r} was not found.")
        self.id = id


class InvalidEntityRequestError(ValueError):
    def __init__(self, error: str, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.error = error
        self.message = message
        self.field = field


__all__ = [
    "AnimalProfile",
    "AnimalProfileInput",
    "ContactMethod",
    "ContactMethodInput",
    "ContactMethodKind",
    "CreateEntityInput",
    "EntityNotFoundError",
    "EntityRecord",
    "InvalidEntityRequestError",
    "ItemProfile",
    "ItemProfileInput",
    "LocationProfile",
    "LocationProfileInput",
    "PersonProfile",
    "PersonProfileInput",
    "StoreProfile",
    "StoreProfileInput",
]
