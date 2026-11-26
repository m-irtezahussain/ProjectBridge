from pydantic import BaseModel, ConfigDict

RESOURCE_SCHEMA_VERSION = "1.0"
RESOURCE_MIME_TYPE = "application/vnd.projectbridge.context+json;version=1"


class ResourceLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rel: str
    uri: str


class CompactProjectResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = RESOURCE_SCHEMA_VERSION
    uri: str
    id: int
    name: str
    status: str
    description_excerpt: str | None
    links: list[ResourceLink]


class CompactTaskResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = RESOURCE_SCHEMA_VERSION
    uri: str
    id: int
    project_id: int
    title: str
    description_excerpt: str | None
    status: str
    priority: str
    assignee_id: int | None
    source_document_id: int | None
    links: list[ResourceLink]


class CompactDocumentResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = RESOURCE_SCHEMA_VERSION
    uri: str
    id: int
    project_id: int | None
    filename: str
    status: str
    mime_type: str
    size_bytes: int | None
    content_sha256: str | None
    links: list[ResourceLink]


class ResourcePageRepresentation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = RESOURCE_SCHEMA_VERSION
    uri: str
    items: list[dict[str, object]]
    limit: int
    has_more: bool
    next_cursor: str | None
    next_uri: str | None


class ResourceCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")
    server: str
    server_version: str
    resource_schema_version: str
    mime_type: str
    pagination: dict[str, object]
    safety: dict[str, object]
    scopes: dict[str, str]
    templates: list[dict[str, str]]
