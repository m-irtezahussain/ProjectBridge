from sqlalchemy.ext.asyncio import AsyncSession

from app.core.managers.auth import AuthenticationError, AuthManager
from app.core.managers.projects import BusinessRequiredError, ProjectNotFoundError
from app.core.services.mcp_auth import MCPPrincipal
from app.core.services.mcp_mutations import (
    IdempotencyConflictError,
    IdempotencyInProgressError,
    MCPMutationResult,
    MutationVersionConflictError,
    completed_idempotency_replay,
    request_fingerprint,
)
from app.models import (
    ActionOrigin,
    Business,
    SearchJobOperation,
    Task,
    TaskPriority,
    TaskSource,
    TaskStatus,
    User,
)
from app.repositories.businesses import BusinessRepository
from app.repositories.mcp_operations import (
    MCPAuditRepository,
    MCPIdempotencyRepository,
)
from app.repositories.projects import ProjectRepository
from app.repositories.search import SearchRepository
from app.repositories.tasks import TaskRepository, TaskSourceReferenceRecord
from app.repositories.users import UserRepository
from app.schemas.task import TaskCreate, TaskUpdate


class TaskNotFoundError(ValueError):
    pass


class AssigneeNotFoundError(ValueError):
    pass


class TaskManager:
    """Shared tenant-safe task rules for REST and MCP interfaces."""

    def __init__(
        self,
        auth: AuthManager,
        businesses: BusinessRepository | None = None,
        projects: ProjectRepository | None = None,
        tasks: TaskRepository | None = None,
        idempotency: MCPIdempotencyRepository | None = None,
        audit: MCPAuditRepository | None = None,
        users: UserRepository | None = None,
        search: SearchRepository | None = None,
        search_max_attempts: int = 5,
    ) -> None:
        self._auth = auth
        self._businesses = businesses or BusinessRepository()
        self._projects = projects or ProjectRepository()
        self._tasks = tasks or TaskRepository()
        self._idempotency = idempotency or MCPIdempotencyRepository()
        self._audit = audit or MCPAuditRepository()
        self._users = users or UserRepository()
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

    async def _require_project(
        self, session: AsyncSession, business_id: int, project_id: int
    ) -> None:
        project = await self._projects.get_active(session, business_id, project_id)
        if project is None:
            raise ProjectNotFoundError("Project not found")

    async def list_tasks(
        self,
        session: AsyncSession,
        access_token: str | None,
        project_id: int,
    ) -> list[Task]:
        business = await self._get_business(session, access_token)
        await self._require_project(session, business.id, project_id)
        return await self._tasks.list_active(session, business.id, project_id)

    async def get_task(
        self,
        session: AsyncSession,
        access_token: str | None,
        project_id: int,
        task_id: int,
    ) -> Task:
        business = await self._get_business(session, access_token)
        task = await self._tasks.get_active(
            session, business.id, project_id, task_id
        )
        if task is None:
            raise TaskNotFoundError("Task not found")
        return task

    async def create_task(
        self,
        session: AsyncSession,
        access_token: str | None,
        project_id: int,
        data: TaskCreate,
        source: TaskSource = TaskSource.REST,
    ) -> Task:
        actor, business = await self._get_actor_business(session, access_token)
        await self._require_project(session, business.id, project_id)
        await self._validate_assignee(session, business.id, data.assignee_id)
        task = Task(
            title=data.title,
            description=data.description,
            status=data.status,
            priority=data.priority,
            project_id=project_id,
            assignee_id=data.assignee_id,
            created_by=source,
        )
        self._tasks.add(session, task)
        await session.flush()
        await self._enqueue_task_sync(session, business.id, task)
        self._audit.record(
            session,
            business_id=business.id,
            actor_user_id=actor.id,
            interface=ActionOrigin.REST,
            action="task.create",
            target_type="task",
            target_id=task.id,
            outcome="success",
        )
        await session.commit()
        return task

    async def update_task(
        self,
        session: AsyncSession,
        access_token: str | None,
        project_id: int,
        task_id: int,
        data: TaskUpdate,
    ) -> Task:
        actor, business = await self._get_actor_business(session, access_token)
        task = await self._tasks.get_active(session, business.id, project_id, task_id)
        if task is None:
            self._audit.record(
                session,
                business_id=business.id,
                actor_user_id=actor.id,
                interface=ActionOrigin.REST,
                action="task.update",
                target_type="task",
                target_id=task_id,
                outcome="not_found",
            )
            await session.commit()
            raise TaskNotFoundError("Task not found")
        if data.title is not None:
            task.title = data.title
        if "description" in data.model_fields_set:
            task.description = data.description
        if data.status is not None:
            task.status = data.status
        if data.priority is not None:
            task.priority = data.priority
        if "assignee_id" in data.model_fields_set:
            await self._validate_assignee(session, business.id, data.assignee_id)
            task.assignee_id = data.assignee_id
        await self._enqueue_task_sync(session, business.id, task)
        self._audit.record(
            session,
            business_id=business.id,
            actor_user_id=actor.id,
            interface=ActionOrigin.REST,
            action="task.update",
            target_type="task",
            target_id=task.id,
            outcome="success",
        )
        await session.commit()
        return task

    async def dismiss_task(
        self,
        session: AsyncSession,
        access_token: str | None,
        project_id: int,
        task_id: int,
    ) -> None:
        actor, business = await self._get_actor_business(session, access_token)
        task = await self._tasks.get_active(session, business.id, project_id, task_id)
        if task is None:
            self._audit.record(
                session,
                business_id=business.id,
                actor_user_id=actor.id,
                interface=ActionOrigin.REST,
                action="task.archive",
                target_type="task",
                target_id=task_id,
                outcome="not_found",
            )
            await session.commit()
            raise TaskNotFoundError("Task not found")
        task.is_deleted = True
        await self._search.enqueue(
            session,
            business_id=business.id,
            project_id=task.project_id,
            task_id=task.id,
            operation=SearchJobOperation.DELETE_TASK,
            max_attempts=self._search_max_attempts,
        )
        self._audit.record(
            session,
            business_id=business.id,
            actor_user_id=actor.id,
            interface=ActionOrigin.REST,
            action="task.archive",
            target_type="task",
            target_id=task.id,
            outcome="success",
        )
        await session.commit()

    async def _require_principal_business(
        self, session: AsyncSession, principal: MCPPrincipal
    ) -> Business:
        business = await self._businesses.get_for_owner(session, principal.user_id)
        if business is None or business.id != principal.business_id:
            raise BusinessRequiredError("Business registration required")
        return business

    async def _validate_assignee(
        self,
        session: AsyncSession,
        business_id: int,
        assignee_id: int | None,
    ) -> None:
        if assignee_id is None:
            return
        assignee = await self._users.get_business_assignee(
            session, business_id, assignee_id
        )
        if assignee is None:
            raise AssigneeNotFoundError("Assignee not found in the connected business")

    async def list_assignees_for_principal(
        self, session: AsyncSession, principal: MCPPrincipal
    ) -> list[User]:
        await self._require_principal_business(session, principal)
        return await self._users.list_business_assignees(
            session, principal.business_id
        )

    async def list_tasks_page_for_principal(
        self,
        session: AsyncSession,
        principal: MCPPrincipal,
        project_id: int,
        *,
        status: TaskStatus | None,
        priority: TaskPriority | None,
        assignee_id: int | None,
        query: str | None,
        limit: int,
        offset: int,
        sort_by: str,
        descending: bool,
    ) -> tuple[list[Task], int]:
        await self._require_principal_business(session, principal)
        await self._require_project(session, principal.business_id, project_id)
        if assignee_id is not None:
            await self._validate_assignee(
                session, principal.business_id, assignee_id
            )
        return await self._tasks.list_active_page(
            session,
            principal.business_id,
            project_id,
            status=status,
            priority=priority,
            assignee_id=assignee_id,
            query=query,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            descending=descending,
        )

    async def get_task_for_principal(
        self,
        session: AsyncSession,
        principal: MCPPrincipal,
        project_id: int,
        task_id: int,
    ) -> Task:
        await self._require_principal_business(session, principal)
        task = await self._tasks.get_active(
            session, principal.business_id, project_id, task_id
        )
        if task is None:
            raise TaskNotFoundError("Task not found")
        return task

    async def get_source_reference_for_principal(
        self,
        session: AsyncSession,
        principal: MCPPrincipal,
        project_id: int,
        task_id: int,
    ) -> TaskSourceReferenceRecord:
        await self._require_principal_business(session, principal)
        reference = await self._tasks.get_source_reference(
            session, principal.business_id, project_id, task_id
        )
        if reference is None:
            raise TaskNotFoundError("Task not found")
        return reference

    async def create_task_for_principal(
        self,
        session: AsyncSession,
        principal: MCPPrincipal,
        project_id: int,
        data: TaskCreate,
        idempotency_key: str,
    ) -> MCPMutationResult[Task]:
        await self._require_principal_business(session, principal)
        tool_name = "create_task"
        try:
            await self._require_project(session, principal.business_id, project_id)
        except ProjectNotFoundError:
            self._audit.add(
                session,
                principal=principal,
                tool_name=tool_name,
                target_type="project",
                target_id=project_id,
                outcome="not_found",
            )
            await session.commit()
            raise
        await self._validate_assignee(
            session, principal.business_id, data.assignee_id
        )
        fingerprint = request_fingerprint(
            tool_name,
            {
                "project_id": project_id,
                "task": data.model_dump(mode="json"),
            },
        )
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
                    target_type="task",
                    target_id=claim.record.result_id,
                    outcome="idempotency_conflict",
                )
                await session.commit()
                raise IdempotencyConflictError(
                    "Idempotency key was already used with different input"
                )
            if (
                claim.record.state != "completed"
                or claim.record.result_type != "task"
                or claim.record.result_id is None
                or claim.record.response_body is None
            ):
                self._audit.add(
                    session,
                    principal=principal,
                    tool_name=tool_name,
                    target_type="task",
                    target_id=claim.record.result_id,
                    outcome="in_progress",
                )
                await session.commit()
                raise IdempotencyInProgressError("Create task is still in progress")
            task = self._task_from_snapshot(claim.record.response_body)
            self._audit.add(
                session,
                principal=principal,
                tool_name=tool_name,
                target_type="task",
                target_id=task.id,
                outcome="idempotent_replay",
            )
            await session.commit()
            return MCPMutationResult(entity=task, replayed=True)

        task = Task(
            title=data.title,
            description=data.description,
            status=data.status,
            priority=data.priority,
            project_id=project_id,
            assignee_id=data.assignee_id,
            created_by=TaskSource.MCP,
            version=1,
        )
        self._tasks.add(session, task)
        await session.flush()
        snapshot: dict[str, object] = {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "status": task.status.value,
            "priority": task.priority.value,
            "project_id": task.project_id,
            "assignee_id": task.assignee_id,
            "source_document_id": task.source_document_id,
            "source_candidate_id": task.source_candidate_id,
            "version": task.version,
        }
        self._idempotency.complete(
            claim.record,
            result_type="task",
            result_id=task.id,
            response_body=snapshot,
        )
        self._audit.add(
            session,
            principal=principal,
            tool_name=tool_name,
            target_type="task",
            target_id=task.id,
            outcome="success",
        )
        await self._enqueue_task_sync(session, principal.business_id, task)
        await session.commit()
        return MCPMutationResult(entity=task, replayed=False)

    async def update_task_for_principal(
        self,
        session: AsyncSession,
        principal: MCPPrincipal,
        project_id: int,
        task_id: int,
        data: TaskUpdate,
        expected_version: int,
        idempotency_key: str,
    ) -> MCPMutationResult[Task]:
        await self._require_principal_business(session, principal)
        tool_name = "update_task"
        fingerprint = request_fingerprint(
            tool_name,
            {
                "project_id": project_id,
                "task_id": task_id,
                "expected_version": expected_version,
                "task": data.model_dump(mode="json"),
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
            claim, fingerprint=fingerprint, result_type="task"
        )
        task: Task | None
        if replay is not None:
            task = self._task_from_snapshot(replay)
            self._audit.add(
                session,
                principal=principal,
                tool_name=tool_name,
                target_type="task",
                target_id=task.id,
                outcome="idempotent_replay",
            )
            await session.commit()
            return MCPMutationResult(entity=task, replayed=True)
        task = await self._tasks.get_active_for_update(
            session, principal.business_id, project_id, task_id
        )
        if task is None:
            await session.rollback()
            await self._audit_task_not_found(
                session, principal, tool_name, task_id
            )
            raise TaskNotFoundError("Task not found")
        if task.version != expected_version:
            current_version = task.version
            await session.rollback()
            self._audit.add(
                session,
                principal=principal,
                tool_name=tool_name,
                target_type="task",
                target_id=task_id,
                outcome="version_conflict",
            )
            await session.commit()
            raise MutationVersionConflictError(
                f"Task version conflict: expected {expected_version}, current {current_version}"
            )
        if data.title is not None:
            task.title = data.title
        if "description" in data.model_fields_set:
            task.description = data.description
        if data.status is not None:
            task.status = data.status
        if data.priority is not None:
            task.priority = data.priority
        if "assignee_id" in data.model_fields_set:
            try:
                await self._validate_assignee(
                    session, principal.business_id, data.assignee_id
                )
            except AssigneeNotFoundError:
                await session.rollback()
                self._audit.add(
                    session,
                    principal=principal,
                    tool_name=tool_name,
                    target_type="task",
                    target_id=task_id,
                    outcome="invalid_assignee",
                )
                await session.commit()
                raise
            task.assignee_id = data.assignee_id
        task.version += 1
        await session.flush()
        self._idempotency.complete(
            claim.record,
            result_type="task",
            result_id=task.id,
            response_body=self._task_snapshot(task),
        )
        self._audit.add(
            session,
            principal=principal,
            tool_name=tool_name,
            target_type="task",
            target_id=task.id,
            outcome="success",
        )
        await self._enqueue_task_sync(session, principal.business_id, task)
        await session.commit()
        return MCPMutationResult(entity=task, replayed=False)

    async def archive_task_for_principal(
        self,
        session: AsyncSession,
        principal: MCPPrincipal,
        project_id: int,
        task_id: int,
        expected_version: int,
        idempotency_key: str,
    ) -> bool:
        await self._require_principal_business(session, principal)
        tool_name = "archive_task"
        fingerprint = request_fingerprint(
            tool_name,
            {
                "project_id": project_id,
                "task_id": task_id,
                "expected_version": expected_version,
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
            claim, fingerprint=fingerprint, result_type="task_archive"
        )
        if replay is not None:
            self._audit.add(
                session,
                principal=principal,
                tool_name=tool_name,
                target_type="task",
                target_id=task_id,
                outcome="idempotent_replay",
            )
            await session.commit()
            return True
        task = await self._tasks.get_for_project_for_update(
            session, principal.business_id, project_id, task_id
        )
        if task is None:
            await session.rollback()
            await self._audit_task_not_found(
                session, principal, tool_name, task_id
            )
            raise TaskNotFoundError("Task not found")
        replayed = bool(task.is_deleted)
        if not replayed:
            if task.version != expected_version:
                current_version = task.version
                await session.rollback()
                self._audit.add(
                    session,
                    principal=principal,
                    tool_name=tool_name,
                    target_type="task",
                    target_id=task_id,
                    outcome="version_conflict",
                )
                await session.commit()
                raise MutationVersionConflictError(
                    f"Task version conflict: expected {expected_version}, "
                    f"current {current_version}"
                )
            task.is_deleted = True
            task.version += 1
            await self._search.enqueue(
                session,
                business_id=principal.business_id,
                project_id=task.project_id,
                task_id=task.id,
                operation=SearchJobOperation.DELETE_TASK,
                max_attempts=self._search_max_attempts,
            )
        self._idempotency.complete(
            claim.record,
            result_type="task_archive",
            result_id=task.id,
            response_body={"archived": True, "version": task.version},
        )
        self._audit.add(
            session,
            principal=principal,
            tool_name=tool_name,
            target_type="task",
            target_id=task.id,
            outcome="idempotent_replay" if replayed else "success",
        )
        await session.commit()
        return replayed

    async def _enqueue_task_sync(
        self, session: AsyncSession, business_id: int, task: Task
    ) -> None:
        await self._search.enqueue(
            session,
            business_id=business_id,
            project_id=task.project_id,
            task_id=task.id,
            operation=SearchJobOperation.UPSERT_TASK,
            max_attempts=self._search_max_attempts,
        )

    async def assign_task_for_principal(
        self,
        session: AsyncSession,
        principal: MCPPrincipal,
        project_id: int,
        task_id: int,
        assignee_id: int,
        expected_version: int,
        idempotency_key: str,
    ) -> MCPMutationResult[Task]:
        await self._require_principal_business(session, principal)
        tool_name = "assign_task"
        fingerprint = request_fingerprint(
            tool_name,
            {
                "project_id": project_id,
                "task_id": task_id,
                "assignee_id": assignee_id,
                "expected_version": expected_version,
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
            claim, fingerprint=fingerprint, result_type="task"
        )
        task: Task | None
        if replay is not None:
            task = self._task_from_snapshot(replay)
            self._audit.add(
                session,
                principal=principal,
                tool_name=tool_name,
                target_type="task",
                target_id=task.id,
                outcome="idempotent_replay",
            )
            await session.commit()
            return MCPMutationResult(entity=task, replayed=True)
        task = await self._tasks.get_active_for_update(
            session, principal.business_id, project_id, task_id
        )
        if task is None:
            await session.rollback()
            await self._audit_task_not_found(
                session, principal, tool_name, task_id
            )
            raise TaskNotFoundError("Task not found")
        if task.version != expected_version:
            current_version = task.version
            await session.rollback()
            self._audit.add(
                session,
                principal=principal,
                tool_name=tool_name,
                target_type="task",
                target_id=task_id,
                outcome="version_conflict",
            )
            await session.commit()
            raise MutationVersionConflictError(
                f"Task version conflict: expected {expected_version}, current {current_version}"
            )
        try:
            await self._validate_assignee(
                session, principal.business_id, assignee_id
            )
        except AssigneeNotFoundError:
            await session.rollback()
            self._audit.add(
                session,
                principal=principal,
                tool_name=tool_name,
                target_type="task",
                target_id=task_id,
                outcome="invalid_assignee",
            )
            await session.commit()
            raise
        task.assignee_id = assignee_id
        task.version += 1
        await session.flush()
        self._idempotency.complete(
            claim.record,
            result_type="task",
            result_id=task.id,
            response_body=self._task_snapshot(task),
        )
        self._audit.add(
            session,
            principal=principal,
            tool_name=tool_name,
            target_type="task",
            target_id=task.id,
            outcome="success",
        )
        await self._enqueue_task_sync(session, principal.business_id, task)
        await session.commit()
        return MCPMutationResult(entity=task, replayed=False)

    async def _audit_task_not_found(
        self,
        session: AsyncSession,
        principal: MCPPrincipal,
        tool_name: str,
        task_id: int,
    ) -> None:
        self._audit.add(
            session,
            principal=principal,
            tool_name=tool_name,
            target_type="task",
            target_id=task_id,
            outcome="not_found",
        )
        await session.commit()

    @staticmethod
    def _task_from_snapshot(snapshot: dict[str, object]) -> Task:
        try:
            task_id_value = snapshot["id"]
            project_id_value = snapshot["project_id"]
            if (
                not isinstance(task_id_value, int)
                or isinstance(task_id_value, bool)
                or not isinstance(project_id_value, int)
                or isinstance(project_id_value, bool)
            ):
                raise TypeError
            task_id = task_id_value
            title = str(snapshot["title"])
            description_value = snapshot.get("description")
            description = (
                str(description_value) if description_value is not None else None
            )
            status = TaskStatus(str(snapshot["status"]))
            priority = TaskPriority(str(snapshot["priority"]))
            project_id = project_id_value
            assignee_id_value = snapshot.get("assignee_id")
            if assignee_id_value is not None and (
                not isinstance(assignee_id_value, int)
                or isinstance(assignee_id_value, bool)
            ):
                raise TypeError
            assignee_id = assignee_id_value
            version_value = snapshot["version"]
            if not isinstance(version_value, int) or isinstance(version_value, bool):
                raise TypeError
            source_document_id = snapshot.get("source_document_id")
            source_candidate_id = snapshot.get("source_candidate_id")
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("Stored task idempotency result is invalid") from exc
        return Task(
            id=task_id,
            title=title,
            description=description,
            status=status,
            priority=priority,
            project_id=project_id,
            assignee_id=assignee_id,
            created_by=TaskSource.MCP,
            source_document_id=(
                source_document_id if isinstance(source_document_id, int) else None
            ),
            source_candidate_id=(
                source_candidate_id if isinstance(source_candidate_id, int) else None
            ),
            version=version_value,
        )

    @staticmethod
    def _task_snapshot(task: Task) -> dict[str, object]:
        return {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "status": task.status.value,
            "priority": task.priority.value,
            "project_id": task.project_id,
            "assignee_id": task.assignee_id,
            "source_document_id": task.source_document_id,
            "source_candidate_id": task.source_candidate_id,
            "version": task.version,
        }
