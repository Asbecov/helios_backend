import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from remnawave.exceptions import ConflictError, NotFoundError, ServerError
from remnawave.exceptions.general import ApiErrorResponse

from helios_backend.services.panel import (
    BasePanelService,
    MarzbanService,
    PanelService,
    PanelServiceError,
    PanelUserAlreadyExistsError,
    RemnawaveService,
    create_panel_backend,
    get_panel_service,
)


@pytest.mark.anyio
async def test_create_panel_backend() -> None:
    """Verify create_panel_backend instantiates requested backend with kwargs."""
    marzban = create_panel_backend(
        panel_type="marzban",
        base_url="https://marzban.example.com",
        username="admin",
        password="secretpassword",
    )
    assert isinstance(marzban, MarzbanService)
    assert marzban.base_url == "https://marzban.example.com"
    assert marzban.username == "admin"
    assert marzban.password == "secretpassword"

    remnawave = create_panel_backend(
        panel_type="remnawave",
        base_url="https://remna.example.com",
        api_token="test_token",
    )
    assert isinstance(remnawave, RemnawaveService)
    assert remnawave.base_url == "https://remna.example.com"
    assert remnawave.api_token == "test_token"

    with pytest.raises(PanelServiceError, match="unsupported panel type"):
        create_panel_backend(panel_type="unknown_panel")


@pytest.mark.anyio
async def test_get_panel_service_factory() -> None:
    """Verify get_panel_service factory function creates a valid PanelService."""
    service = get_panel_service(panel_type="remnawave")
    assert isinstance(service, PanelService)
    assert isinstance(service.backend, RemnawaveService)


@pytest.mark.anyio
async def test_panel_service_delegates_to_backend() -> None:
    """Verify PanelService facade delegates all operations to underlying backend."""
    mock_backend = AsyncMock(spec=BasePanelService)
    mock_backend.get_user_info.return_value = {
        "expire": 1234567890,
        "subscription_url": "https://sub.link/xyz",
    }
    mock_backend.get_subscription_url.return_value = "https://sub.link/xyz"

    service = PanelService(backend=mock_backend)
    now = datetime.now(UTC)

    await service.create_user("alice", now)
    mock_backend.create_user.assert_awaited_once_with(username="alice", expires_at=now)

    await service.extend_user("alice", now)
    mock_backend.extend_user.assert_awaited_once_with(username="alice", expires_at=now)

    info = await service.get_user_info("alice")
    assert info["subscription_url"] == "https://sub.link/xyz"
    mock_backend.get_user_info.assert_awaited_once_with(username="alice")

    url = await service.get_subscription_url("alice")
    assert url == "https://sub.link/xyz"
    mock_backend.get_subscription_url.assert_awaited_once_with(username="alice")

    await service.delete_user("alice")
    mock_backend.delete_user.assert_awaited_once_with(username="alice")

    await service.close()
    mock_backend.close.assert_awaited_once()


@pytest.mark.anyio
async def test_remnawave_service_create_user_success() -> None:
    """Verify RemnawaveService creates user successfully."""
    service = RemnawaveService(
        base_url="https://remna.example.com",
        api_token="valid_token",
    )
    mock_sdk = MagicMock()
    mock_sdk.users.create_user = AsyncMock()

    with patch.object(service, "_ensure_client", AsyncMock(return_value=mock_sdk)):
        now = datetime.now(UTC)
        await service.create_user("bob", now)
        mock_sdk.users.create_user.assert_awaited_once()
        call_kwargs = mock_sdk.users.create_user.await_args.kwargs
        assert call_kwargs["body"].username == "bob"
        assert call_kwargs["body"].expire_at == now


@pytest.mark.anyio
async def test_remnawave_service_create_user_already_exists() -> None:
    """Verify RemnawaveService maps ConflictError to PanelUserAlreadyExistsError."""
    service = RemnawaveService(
        base_url="https://remna.example.com",
        api_token="valid_token",
    )
    mock_sdk = MagicMock()
    mock_sdk.users.create_user = AsyncMock(
        side_effect=ConflictError(
            status_code=409,
            error=ApiErrorResponse(
                message="User already exists",
                code="USER_ALREADY_EXISTS",
            ),
        )
    )

    with (
        patch.object(service, "_ensure_client", AsyncMock(return_value=mock_sdk)),
        pytest.raises(PanelUserAlreadyExistsError, match="already exists"),
    ):
        await service.create_user("bob", datetime.now(UTC))


@pytest.mark.anyio
async def test_remnawave_service_create_user_server_error() -> None:
    """Verify RemnawaveService maps general errors to PanelServiceError."""
    service = RemnawaveService(
        base_url="https://remna.example.com",
        api_token="valid_token",
    )
    mock_sdk = MagicMock()
    mock_sdk.users.create_user = AsyncMock(
        side_effect=ServerError(
            status_code=500,
            error=ApiErrorResponse(
                message="Internal error",
                code="INTERNAL_SERVER_ERROR",
            ),
        )
    )

    with (
        patch.object(service, "_ensure_client", AsyncMock(return_value=mock_sdk)),
        pytest.raises(PanelServiceError, match="failed to create Remnawave user"),
    ):
        await service.create_user("bob", datetime.now(UTC))


@pytest.mark.anyio
async def test_remnawave_service_extend_user() -> None:
    """Verify RemnawaveService extend_user updates user."""
    service = RemnawaveService(
        base_url="https://remna.example.com",
        api_token="valid_token",
    )
    mock_sdk = MagicMock()
    mock_sdk.users.update_user = AsyncMock()

    with patch.object(service, "_ensure_client", AsyncMock(return_value=mock_sdk)):
        now = datetime.now(UTC)
        await service.extend_user("bob", now)
        mock_sdk.users.update_user.assert_awaited_once()
        call_kwargs = mock_sdk.users.update_user.await_args.kwargs
        assert call_kwargs["body"].username == "bob"
        assert call_kwargs["body"].expire_at == now


@pytest.mark.anyio
async def test_remnawave_service_get_user_info_and_subscription_url() -> None:
    """Verify RemnawaveService retrieves user info and subscription URL."""
    service = RemnawaveService(
        base_url="https://remna.example.com",
        api_token="valid_token",
    )
    mock_sdk = MagicMock()
    expiry = datetime(2030, 1, 1, 12, 0, 0, tzinfo=UTC)
    mock_user = MagicMock()
    mock_user.expire_at = expiry
    mock_user.subscription_url = "https://remna.example.com/sub/token123"
    mock_sdk.users.get_user_by_username = AsyncMock(return_value=mock_user)

    with patch.object(service, "_ensure_client", AsyncMock(return_value=mock_sdk)):
        info = await service.get_user_info("bob")
        assert info["expire"] == int(expiry.timestamp())
        assert info["subscription_url"] == "https://remna.example.com/sub/token123"

        url = await service.get_subscription_url("bob")
        assert url == "https://remna.example.com/sub/token123"


@pytest.mark.anyio
async def test_remnawave_service_get_user_info_not_found() -> None:
    """Verify RemnawaveService returns None fields when user is not found."""
    service = RemnawaveService(
        base_url="https://remna.example.com",
        api_token="valid_token",
    )
    mock_sdk = MagicMock()
    mock_sdk.users.get_user_by_username = AsyncMock(
        side_effect=NotFoundError(
            status_code=404,
            error=ApiErrorResponse(message="Not found", code="NOT_FOUND"),
        )
    )

    with patch.object(service, "_ensure_client", AsyncMock(return_value=mock_sdk)):
        info = await service.get_user_info("unknown")
        assert info == {"expire": None, "subscription_url": None}

        url = await service.get_subscription_url("unknown")
        assert url is None


@pytest.mark.anyio
async def test_remnawave_service_delete_user() -> None:
    """Verify RemnawaveService looks up user UUID and deletes user."""
    service = RemnawaveService(
        base_url="https://remna.example.com",
        api_token="valid_token",
    )
    user_uuid = uuid.uuid4()
    mock_sdk = MagicMock()
    mock_user = MagicMock()
    mock_user.uuid = user_uuid
    mock_sdk.users.get_user_by_username = AsyncMock(return_value=mock_user)
    mock_sdk.users.delete_user = AsyncMock()

    with patch.object(service, "_ensure_client", AsyncMock(return_value=mock_sdk)):
        await service.delete_user("bob")
        mock_sdk.users.get_user_by_username.assert_awaited_once_with(username="bob")
        mock_sdk.users.delete_user.assert_awaited_once_with(uuid=str(user_uuid))


@pytest.mark.anyio
async def test_remnawave_service_delete_user_not_found_ignored() -> None:
    """Verify delete_user silently ignores NotFoundError."""
    service = RemnawaveService(
        base_url="https://remna.example.com",
        api_token="valid_token",
    )
    mock_sdk = MagicMock()
    mock_sdk.users.get_user_by_username = AsyncMock(
        side_effect=NotFoundError(
            status_code=404,
            error=ApiErrorResponse(message="Not found", code="NOT_FOUND"),
        )
    )

    with patch.object(service, "_ensure_client", AsyncMock(return_value=mock_sdk)):
        # Must not raise
        await service.delete_user("ghost")


@pytest.mark.anyio
async def test_remnawave_service_delete_none_username() -> None:
    """Verify delete_user does nothing when username is None or empty."""
    service = RemnawaveService(
        base_url="https://remna.example.com",
        api_token="valid_token",
    )
    mock_sdk = MagicMock()
    mock_sdk.users.get_user_by_username = AsyncMock()

    with patch.object(service, "_ensure_client", AsyncMock(return_value=mock_sdk)):
        await service.delete_user(None)
        await service.delete_user("")
        mock_sdk.users.get_user_by_username.assert_not_called()
