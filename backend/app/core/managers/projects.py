from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.managers.auth import AuthenticationError, AuthManager
from app.core.services.mcp_auth import MCPPrincipal
from app.core.services.mcp_mutations import (
    IdempotencyConflictError,
    IdempotencyInProgressError,
    MCPMutationResult,
    MutationVersionConflictError,
    completed_idempotency_replay,
    request_fingerprint,
)
from app.models import ActionOrigin, Business, Project, ProjectStatus, SearchJobOperation, User
from app.repositories.businesses import BusinessRepository
from app.repositories.mcp_operations import (
    MCPAuditRepository,
    MCPIdempotencyRepository,
)
from app.repositories.projects import ProjectRepository
from app.repositories.search import SearchRepository
from app.schemas.project import ProjectCreate, ProjectUpdate


class BusinessRequiredError(ValueError):
    pass


class ProjectNotFoundError(ValueError):
    pass


class ProjectManager:
    """Shared tenant-safe project rules for REST and future MCP tools."""

    def __init__(
        self,
        auth: AuthManager,
        businesses: BusinessRepository | None = None,
        projects: ProjectRepository | None = None,
        idempotency: MCPIdempotencyRepository | None = None,
        audit: MCPAuditRepository | None = None,
        search: SearchRepository | None = None,
        search_max_attempts: int = 5,
    ) -> None:
        self._auth = auth
        self._businesses = businesses or BusinessRepository()
        self._projects = projects or ProjectRepository()
        self._idempotency = idempotency or MCPIdempotencyRepository()
        self._audit = audit or MCPAuditRepository()
        self._search = search or SearchRepository()
        self._search_max_attempts = search_max_attempts

    async def _get_business(
        self, session: AsyncSession, access_token: str | None
    ) -> Business:
        user = await self._auth.get_user(session, access_token, "access")
        if user is None:
            raise AuthenticationError("Authentication required")
        business = await self._businesses.get_for_owner(session, user.id)
        if business is None:
            raise BusinessRequiredError("Business registration required")
        return business

    async def _get_actor_business(
        self, session: AsyncSession, access_token: str | None
    ) -> tuple[User, Business]:
        user = await self._auth.get_user(session, access_token, "access")
        if user is None:
            raise AuthenticationError("Authentication required")
        business = await self._businesses.get_for_owner(session, user.id)
        if business is None:
            raise BusinessRequiredError("Business registration required")
        return user, business

    async def list_projects(
        self, session: AsyncSession, access_token: str | None
    ) -> list[Project]:
        business = await self._get_business(session, access_token)
        return await self._projects.list_active(session, business.id)

    async def get_project(
        self, session: AsyncSession, access_token: str | None, project_id: int
    ) -> Project:
        business = await self._get_business(session, access_token)
        project = await self._projects.get_active(session, business.id, project_id)
        if project is None:
            raise ProjectNotFoundError("Project not found")
        return project

    async def list_projects_for_principal(
        self,
        session: AsyncSession,
        principal: MCPPrincipal,
        status: ProjectStatus | None = None,
    ) -> list[Project]:
        await self._require_principal_business(session, principal)
        return await self._projects.list_active(
            session, principal.business_id, status=status
        )

    async def list_projects_page_for_principal(
        self,
        session: AsyncSession,
        principal: MCPPrincipal,
        *,
        status: ProjectStatus | None,
        query: str | None,
        limit: int,
        offset: int,
        sort_by: str,
        descending: bool,
    ) -> tuple[list[Project], int]:
        await self._require_principal_business(session, principal)
        return await self._projects.list_active_page(
            session,
            principal.business_id,
            status=status,
            query=query,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            descending=descending,
        )

    async def get_project_for_principal(
        self,
        session: AsyncSession,
        principal: MCPPrincipal,
        project_id: int,
    ) -> Project:
        await self._require_principal_business(session, principal)
        project = await self._projects.get_active(
            session, principal.business_id, project_id
        )
        if project is None:
            raise ProjectNotFoundError("Project not found")
        return project

    async def _require_principal_business(
        self, session: AsyncSession, principal: MCPPrincipal
    ) -> Business:
        business = await self._businesses.get_for_owner(session, principal.user_id)
        if business is None or business.id != principal.business_id:
            raise BusinessRequiredError("Business registration required")
        return business

    async def create_project_for_principal(
        self,
        session: AsyncSession,
        principal: MCPPrincipal,
        data: ProjectCreate,
        idempotency_key: str,
    ) -> MCPMutationResult[Project]:
        await self._require_principal_business(session, principal)
        tool_name = "create_project"
        fingerprint = request_fingerprint(tool_name, data)
        claim = await self._idempotency.claim(
            session,
            principal=principal,
            tool_name=tool_name,
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
        )
        if not claim.is_new:
            if claim.record.request_fingerprint != fingerprint:
                self._audit.add(
                    session,
                    principal=principal,
                    tool_name=tool_name,
                    target_type="project",
                    target_id=claim.record.result_id,
                    outcome="idempotency_conflict",
                )
                await session.commit()
                raise IdempotencyConflictError(
                    "Idempotency key was already used with different input"
                )
            if (
                claim.record.state != "completed"
                or claim.record.result_type != "project"
                or claim.record.result_id is None
                or claim.record.response_body is None
            ):
                self._audit.add(
                    session,
                    principal=principal,
                    tool_name=tool_name,
                    target_type="project",
                    target_id=claim.record.result_id,
                    outcome="in_progress",
                )
                await session.commit()
                raise IdempotencyInProgressError("Create project is still in progress")
            project = self._project_from_snapshot(
                claim.record.response_body, principal.business_id
            )
            self._audit.add(
                session,
                principal=principal,
                tool_name=tool_name,
                target_type="project",
                target_id=project.id,
                outcome="idempotent_replay",
            )
            await session.commit()
            return MCPMutationResult(entity=project, replayed=True)

        project = Project(
            name=data.name,
            description=data.description,
            business_id=principal.business_id,
            status=data.status,
            version=1,
        )
        self._projects.add(session, project)
        await session.flush()
        snapshot: dict[str, object] = {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "status": project.status.value,
            "version": project.version,
        }
        self._idempotency.complete(
            claim.record,
            result_type="project",
            result_id=project.id,
            response_body=snapshot,
        )
        self._audit.add(
            session,
            principal=principal,
            tool_name=tool_name,
            target_type="project",
            target_id=project.id,
            outcome="success",
        )
        await session.commit()
        return MCPMutationResult(entity=project, replayed=False)

    async def update_project_for_principal(
        self,
        session: AsyncSession,
        principal: MCPPrincipal,
        project_id: int,
        data: ProjectUpdate,
        expected_version: int,
        idempotency_key: str,
    ) -> MCPMutationResult[Project]:
        await self._require_principal_business(session, principal)
        tool_name = "update_project"
        fingerprint = request_fingerprint(
            tool_name,
            {
                "project_id": project_id,
                "expected_version": expected_version,
                "project": data.model_dump(mode="json"),
            },
        )
        claim = await self._idempotency.claim(
            session,
            principal=principal,
            tool_name=tool_name,
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
        )
        replay = completed_idempotency_replay(
            claim, fingerprint=fingerprint, result_type="project"
        )
        project: Project | None
        if replay is not None:
            project = self._project_from_snapshot(replay, principal.business_id)
            self._audit.add(
                session,
                principal=principal,
                tool_name=tool_name,
                target_type="project",
                target_id=project.id,
                outcome="idempotent_replay",
            )
            await session.commit()
            return MCPMutationResult(entity=project, replayed=True)
        project = await self._projects.get_active_for_update(
            session, principal.business_id, project_id
        )
        if project is None:
            await session.rollback()
            self._audit.add(
                session,
                principal=principal,
                tool_name=tool_name,
                target_type="project",
                target_id=project_id,
                outcome="not_found",
            )
            await session.commit()
            raise ProjectNotFoundError("Project not found")
        if project.version != expected_version:
            current_version = project.version
            await session.rollback()
            self._audit.add(
                session,
                principal=principal,
                tool_name=tool_name,
                target_type="project",
                target_id=project_id,
                outcome="version_conflict",
            )
            await session.commit()
            raise MutationVersionConflictError(
                f"Project version conflict: expected {expected_version}, "
                f"current {current_version}"
            )
        if data.name is not None:
            project.name = data.name
        if data.status is not None:
            project.status = data.status
        if "description" in data.model_fields_set:
            project.description = data.description
        project.version += 1
        await session.flush()
        snapshot = self._project_snapshot(project)
        self._idempotency.complete(
            claim.record,
            result_type="project",
            result_id=project.id,
            response_body=snapshot,
        )
        self._audit.add(
            session,
            principal=principal,
            tool_name=tool_name,
            target_type="project",
            target_id=project.id,
            outcome="success",
        )
        await session.commit()
        return MCPMutationResult(entity=project, replayed=False)

    async def archive_project_for_principal(
        self,
        session: AsyncSession,
        principal: MCPPrincipal,
        project_id: int,
        expected_version: int,
        idempotency_key: str,
    ) -> bool:
        """Archive a project, returning True when the request is a safe replay."""
        await self._require_principal_business(session, principal)
        tool_name = "archive_project"
        fingerprint = request_fingerprint(
            tool_name,
            {"project_id": project_id, "expected_version": expected_version},
        )
        claim = await self._idempotency.claim(
            session,
            principal=principal,
            tool_name=tool_name,
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
        )
        replay = completed_idempotency_replay(
            claim, fingerprint=fingerprint, result_type="project_archive"
        )
        if replay is not None:
            self._audit.add(
                session,
                principal=principal,
                tool_name=tool_name,
                target_type="project",
                target_id=project_id,
                outcome="idempotent_replay",
            )
            await session.commit()
            return True
        project = await self._projects.get_for_business_for_update(
            session, principal.business_id, project_id
        )
        if project is None:
            await session.rollback()
            self._audit.add(
                session,
                principal=principal,
                tool_name=tool_name,
                target_type="project",
                target_id=project_id,
                outcome="not_found",
            )
            await session.commit()
            raise ProjectNotFoundError("Project not found")
        replayed = project.deleted_at is not None
        if not replayed:
            if project.version != expected_version:
                current_version = project.version
                await session.rollback()
                self._audit.add(
                    session,
                    principal=principal,
                    tool_name=tool_name,
                    target_type="project",
                    target_id=project_id,
                    outcome="version_conflict",
                )
                await session.commit()
                raise MutationVersionConflictError(
                    f"Project version conflict: expected {expected_version}, "
                    f"current {current_version}"
                )
            project.deleted_at = datetime.now(UTC)
            project.version += 1
            await self._search.enqueue(
                session,
                business_id=principal.business_id,
                project_id=project.id,
                operation=SearchJobOperation.DELETE_PROJECT,
                max_attempts=self._search_max_attempts,
            )
        self._idempotency.complete(
            claim.record,
            result_type="project_archive",
            result_id=project.id,
            response_body={"archived": True, "version": project.version},
        )
        self._audit.add(
            session,
            principal=principal,
            tool_name=tool_name,
            target_type="project",
            target_id=project.id,
            outcome="idempotent_replay" if replayed else "success",
        )
        await session.commit()
        return replayed

    @staticmethod
    def _project_from_snapshot(
        snapshot: dict[str, object], business_id: int
    ) -> Project:
        try:
            project_id_value = snapshot["id"]
            if not isinstance(project_id_value, int) or isinstance(
                project_id_value, bool
            ):
                raise TypeError
            project_id = project_id_value
            name = str(snapshot["name"])
            description_value = snapshot.get("description")
            description = (
                str(description_value) if description_value is not None else None
            )
            status = ProjectStatus(str(snapshot["status"]))
            version_value = snapshot["version"]
            if not isinstance(version_value, int) or isinstance(version_value, bool):
                raise TypeError
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("Stored project idempotency result is invalid") from exc
        return Project(
            id=project_id,
            name=name,
            description=description,
            business_id=business_id,
            status=status,
            version=version_value,
        )

    @staticmethod
    def _project_snapshot(project: Project) -> dict[str, object]:
        return {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "status": project.status.value,
            "version": project.version,
        }

    async def create_project(
        self,
        session: AsyncSession,
        access_token: str | None,
        data: ProjectCreate,
    ) -> Project:
        actor, business = await self._get_actor_business(session, access_token)
        project = Project(
            name=data.name,
            description=data.description,
            business_id=business.id,
            status=data.status,
        )
        self._projects.add(session, project)
        await session.flush()
        self._audit.record(
            session,
            business_id=business.id,
            actor_user_id=actor.id,
            interface=ActionOrigin.REST,
            action="project.create",
            target_type="project",
            target_id=project.id,
            outcome="success",
        )
        await session.commit()
        return project

    async def update_project(
        self,
        session: AsyncSession,
        access_token: str | None,
        project_id: int,
        data: ProjectUpdate,
    ) -> Project:
        actor, business = await self._get_actor_business(session, access_token)
        project = await self._projects.get_active(session, business.id, project_id)
        if project is None:
            self._audit.record(
                session,
                business_id=business.id,
                actor_user_id=actor.id,
                interface=ActionOrigin.REST,
                action="project.update",
                target_type="project",
                target_id=project_id,
                outcome="not_found",
            )
            await session.commit()
            raise ProjectNotFoundError("Project not found")
        if data.name is not None:
            project.name = data.name
        if data.status is not None:
            project.status = data.status
        if "description" in data.model_fields_set:
            project.description = data.description
        self._audit.record(
            session,
            business_id=business.id,
            actor_user_id=actor.id,
            interface=ActionOrigin.REST,
            action="project.update",
            target_type="project",
            target_id=project.id,
            outcome="success",
        )
        await session.commit()
        return project

    async def dismiss_project(
        self, session: AsyncSession, access_token: str | None, project_id: int
    ) -> None:
        actor, business = await self._get_actor_business(session, access_token)
        project = await self._projects.get_active(session, business.id, project_id)
        if project is None:
            self._audit.record(
                session,
                business_id=business.id,
                actor_user_id=actor.id,
                interface=ActionOrigin.REST,
                action="project.archive",
                target_type="project",
                target_id=project_id,
                outcome="not_found",
            )
            await session.commit()
            raise ProjectNotFoundError("Project not found")
        project.deleted_at = datetime.now(UTC)
        self._audit.record(
            session,
            business_id=business.id,
            actor_user_id=actor.id,
            interface=ActionOrigin.REST,
            action="project.archive",
            target_type="project",
            target_id=project.id,
            outcome="success",
        )
        await session.commit()
